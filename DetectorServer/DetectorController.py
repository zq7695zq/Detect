import configparser
import os
import re
import socket
import time
import traceback
from enum import Enum
from threading import Thread

from cProfile import Profile


from Detector import Detector
from DetectorState import DetectorState
from Events.EventSaver import EventSaver
from ModelsLoader import ModelsLoader
from MoveReminder import MoveReminder



def validate_rtsp_address(address):
    # RTSP地址的正则表达式（不包含用户名和密码）
    pattern = r'rtsp:\/\/((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})(\.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){3}:[0-9]*\/[a-zA-Z0-9]*'
    reg_exp = re.compile(pattern)
    return reg_exp.match(address) is not None


def check_rtsp_connectivity(address):
    # 解析地址中的主机和端口
    rtsp_host = address.split("//")[1].split(":")[0]
    rtsp_port = int(address.split("//")[1].split(":")[1].split("/")[0])
    # 创建一个socket对象
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 尝试连接到rtsp服务器
    try:
        s.connect((rtsp_host, rtsp_port))
        # 定义一个rtsp请求的消息
        message = "OPTIONS " + address + " RTSP/1.0\r\nCSeq: 1\r\nUser-Agent: Python\r\n\r\n"
        # 发送请求
        s.send(message.encode())
        # 接收响应
        response = s.recv(1024)
        # 判断响应是否为200 OK
        if response.decode().startswith("RTSP/1.0 200 OK"):
            # 返回True表示连通
            return True
        else:
            # 返回False表示不连通
            return False
    except Exception as e:
        # 如果发生异常，返回False表示不连通
        return False
    finally:
        # 关闭socket
        s.close()


def check_local_file_exist(file_path):
    return os.path.exists(file_path)


def create_reminder_from_db_obj(db_obj, db):
    init_rect_tuple = tuple(map(int, db_obj['init_rect_str'].split(',')))
    select_time = db_obj['select_time_str'].total_seconds()
    ret = None
    if db_obj['reminder_type'] == 1:
        ret = MoveReminder(db_obj['start_time'], select_time, init_rect_tuple)
    elif db_obj['reminder_type'] == 2:
        pass
        # ret = MoveReminder(db_obj['start_time'], select_time)
    ret.db = db
    ret.reminder_id = db_obj['id']
    return ret


class DetectorController:
    def __init__(self, detectors, redis, db):

        self.redis = redis

        self.models = ModelsLoader()

        self.detectors = detectors

        self.db = db

        self.detectors_thread = {}

        self.detectors_obj = {}

        self.show_threshold = 20  # 展示动作的阈值 20%

        self.retest_interval_time = 3  # 连通性测试失败时重新测试间隔,

        self.restart_interval_time = 10  # 重启线程间隔

        self.max_fps = 30

        self.running_cam = {}

        for d in self.detectors:
            Thread(target=self.append_detector, args=(d, 1), daemon=True).start()

    def append_detector(self, d, count):
        while True:
            if count > 3:
                print("地址：%s 测试连接超过30次，停止测试..." % (d["cam_source"]))
                return
            elif count > 1:
                print("地址：%s 第%s次测试连通性中..." % (d["cam_source"], count))
            # 检查rtsp连通性
            if (not d['is_local_file'] and validate_rtsp_address(d["cam_source"]) and check_rtsp_connectivity(
                    d['cam_source'])) or \
                    (d['is_local_file'] and check_local_file_exist(d['cam_source'])):  # 检查本地视频是否存在
                detector = Detector(d['id'],
                                    d['cam_source'],
                                    d['owner'],
                                    EventSaver(d["cam_source"], self.redis, d['owner'], self.db),
                                    self.models,
                                    self.restart_detector,
                                    self.db,
                                    self.show_threshold,
                                    d['is_local_file'])
                # 加载提醒器
                # detector.reminders = list([create_reminder_from_db_obj(obj, self.db)
                #                            for obj in
                #                            self.db.get_reminders_by_user_and_cam(d['owner'], d["cam_source"])])
                self.detectors_obj[d["cam_source"]] = detector
                self.detectors_thread[d["cam_source"]] = {
                    'thread': Thread(target=self.update_thread, args=(detector, d["cam_source"]),
                                     daemon=True),
                    'state': DetectorState.running,
                    'detector': detector,
                    'test_time': 0
                }
                self.detectors_thread[d["cam_source"]]["thread"].start()
                if self.detectors_thread[d["cam_source"]]["detector"].available:
                    print("%s连接成功... " % d["cam_source"])
                    self.running_cam[d["cam_source"]] = True
                    return
            else:
                print('cam_source: %s, is_local_file: %s, check_local_file_exist: %s' % (
                    d['cam_source'], d['is_local_file'], check_local_file_exist(d['cam_source'])))
            print("地址：%s 第%s次测试连通性失败，三分钟后重新测试" % (d["cam_source"], count))
            count += 1
            time.sleep(self.retest_interval_time)

    def restart_detector(self, detector: Detector, isStarted: bool):
        if isStarted:
            self.running_cam.pop(detector.cam_source)
            # 关闭线程
            self.detectors_thread[detector.cam_source]['state'] = DetectorState.wait_to_stop
        print('restart_detector : ', detector.cam_source)
        self.append_detector({'cam_source': detector.cam_source, 'owner': detector.owner}, 1)

    def update_thread(self, detector, cam_source):
        cycle_count = 0

        # prof = Profile()
        while True:
            if self.detectors_thread[cam_source]['state'] == DetectorState.wait_to_stop:
                self.detectors_thread[cam_source]['state'] = DetectorState.stoped
                print("%s 断开连接，" % [cam_source])
                return

            time_start = time.time()
            try:
                ret = detector.detect_frame()
                # print("detecting on :" + cam_source + "  event:" + str(ret["event"]))
                # 每一百帧记录一次帧（充当封面）
                if cycle_count % 300 == 0:
                    self.redis.set_norm_frame(cam_source, ret['origin_frame'])
                    # prof.dump_stats("prof-" + str(time.time()) + ".prof")
                # interval_time = (ret['fps'] - self.max_fps) * (1/self.max_fps)
                print(f"fps: {ret['fps']}", end='\r')
                # if not detector.is_available():
                #     # 重新启动
                #     self.detectors_thread[cam_source] = Thread(target=self.update_thread,
                #                                                args=(detector, cam_source), daemon=True).start()
                #     break
                # print("run_time:" + str(time.time() - time_start))
                cycle_count += 1
                # print('sleep' + str(interval_time))
                # time.sleep(0 if interval_time < 0 else interval_time)
            except Exception as e:
                print(e)
                traceback.print_exc()
