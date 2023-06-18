import configparser
import time
from threading import Thread

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import RedisTool
from Database import db_state, mysql_db_detector
from Detector import Detector
from DetectorModel.ModelsLoader import ModelsLoader
from Events.EventSaver import EventSaver
from PacketModels.Models import ModelDetector, ModelAddDetector, ModelCam2Events, \
    ModelGetEventFrames, ModelDelEvent
from Token import Token


class Detector_Controller:

    def __init__(self, detectors, redis, models):

        self.redis = redis

        self.models = models

        self.detectors = detectors

        self.interval_time = 0  # 0.01秒检测一次

        self.detectors_thread = {}

        self.show_threshold = 25  # 展示动作的阈值 25%

        for d in self.detectors:
            self.append_detector(d)

    def append_detector(self, d):
        detector = Detector(d["cam_source"], EventSaver(d["cam_source"], self.redis), self.models,
                            self.interval_time, self.show_threshold)
        self.detectors_thread[d["cam_source"]] = Thread(target=self.update_thread, args=(detector, d["cam_source"]),
                                                        daemon=True).start()

    def update_thread(self, detector, cam_source):
        crycle_count = 0
        while True:
            time_start = time.time()
            ret = detector.detect_frame()
            # print("detecting on :" + cam_source + "  event:" + str(ret["event"]))
            # 每一百次侦察记录一次帧（充当封面）
            if crycle_count % 100 == 0:
                self.redis.set_norm_frame(cam_source, ret['origin_frame'])

            if not detector.is_available():
                # 重新启动
                self.detectors_thread[cam_source] = Thread(target=self.update_thread,
                                                           args=(detector, cam_source), daemon=True).start()
                break
            # print("run_time:" + str(time.time() - time_start))
            crycle_count += 1
            time.sleep(self.interval_time)


class DetectServer(FastAPI):

    def __init__(self, title: str = "Server"):
        super().__init__(title=title)

        config = configparser.ConfigParser()
        config.read('config.ini')

        self.server_id = int(config.get("server", "server_id"))

        self.db = mysql_db_detector(config)

        self.Token = Token(config.get("token", "secret_key"))

        self.redis: RedisTool = RedisTool.redis_tool(
            config.get("redis", "host"),
            config.get("redis", "port"),
            config.get("redis", "pool_size"))

        self.detectors = []
        self.db.detector_get_by_server(self.server_id, self.detectors)

        self.detector_controller = Detector_Controller(self.detectors, self.redis, ModelsLoader())

        print("DetectorServer加载完成")
        print("detectors : ", self.detectors)

        @self.middleware("http")
        async def process_token(request: Request, call_next):
            if request.url.path.startswith("/login") or request.url.path.startswith("/register"):
                return await call_next(request)
            _token = request.headers.get("Authorization")
            if not _token:
                return JSONResponse(content={"detail": "Missing token"}, status_code=401)
            payload = self.Token.verify_token(_token)
            if not payload:
                return JSONResponse(content={"detail": "Invalid token"}, status_code=401)
            response = await call_next(request)
            return response

        @self.on_event("startup")
        async def on_startup():
            # 在这里执行应用程序启动时需要执行的操作
            pass

        @self.on_event("shutdown")
        async def on_shutdown():
            # 在这里执行应用程序关闭时需要执行的操作
            pass

        @self.post('/detector')
        async def detector(request: Request, m: ModelDetector):
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            detectors = []
            state = self.db.detector_get_by_owner(payload['id'], detectors)
            ret = {'state': state.get_value()}
            if state == db_state.detector_get_error_unk:
                pass
            elif state == db_state.detector_get_error_user_is_not_exist:
                pass
            elif state == db_state.detector_get_success:
                for d in detectors:
                    d['image'] = self.redis.get_last_norm_base64(d['cam_source'])
                    events = self.redis.get_events_by_source(d['cam_source'])
                    d['state'] = "warning" if len(events) > 0 else "norm"
                ret['detectors'] = detectors
            return ret

        @self.post('/add_detector')
        async def add_detector(request: Request, m: ModelAddDetector):
            print('/add_detector')
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            new_detector = {}
            state = self.db.detector_add(m.cam_source, m.nickname, payload['id'], self.server_id, new_detector)
            ret = {'state': state.get_value()}
            if state == db_state.detector_add_error_unk:
                pass
            elif state == db_state.detector_cam_source_exist:
                pass
            elif state == db_state.detector_add_success:
                self.detectors.append(new_detector)
                self.detector_controller.append_detector(new_detector)
                pass
            return ret

        @self.post('/cam2events')
        async def cam2events(request: Request, m: ModelCam2Events):
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            is_owner = self.db.user_is_owner_cam_source(m.cam_source, payload['id'])
            if is_owner:
                ret = {'state': 'cam2events_success', 'events': self.redis.get_events_by_source(m.cam_source)}
            else:
                ret = {'state': 'cam2events_unk'}
            return ret

        @self.post('/get_event_frames')
        async def get_event_frames(request: Request, m: ModelGetEventFrames):
            # todo 检查用户符合
            ret = {'state': 'get_event_frames_success', 'events': self.redis.get_event_frames(m.event_name)}
            return ret

        @self.post('/del_event')
        async def del_event(request: Request, m: ModelDelEvent):
            # todo 检查用户符合
            ret = {'state': 'del_event_success', 'events': self.redis.del_event(m.event_name, m.cam_source)}
            return ret
