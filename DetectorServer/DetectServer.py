import base64
import configparser
import os
import re
import socket
import time
import traceback
from enum import Enum
from threading import Thread

from fastapi import FastAPI, Request, UploadFile, File, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware

import RedisTool
from Database import db_state, mysql_db_detector
from Detector import Detector
from DetectorController import DetectorController
from DetectorModel.ModelsLoader import ModelsLoader
from DetectorState import DetectorState
from Events.EventSaver import EventSaver
from Models import ModelAddReminder, ModelIsRecording
from MoveReminder import MoveReminder
from PacketModels.Models import ModelDetector, ModelAddDetector, ModelCam2Events, \
    ModelGetEventFrames, ModelDelEvent, ModelGetNotification
from StreamLive import StreamLive
from Token import Token


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


class DetectServer(FastAPI):

    def __init__(self, title: str = "Server"):
        super().__init__(title=title)
        self.add_middleware(GZipMiddleware)
        config = configparser.ConfigParser()
        config.read('config.ini')

        self.server_id = int(config.get("server", "server_id"))

        self.db = mysql_db_detector(config)

        self.Token = Token(config.get("token", "secret_key"))

        self.local_file_address = config.get("rtsp", "local_file_address")
        self.stream_out_address = config.get("rtsp", "stream_out_address")

        self.redis: RedisTool = RedisTool.redis_tool(
            config.get("redis", "host"),
            config.get("redis", "port"),
            config.get("redis", "pool_size"))

        self.detectors = []
        self.db.detector_get_by_server(self.server_id, self.detectors)

        self.detector_controller = DetectorController(self.detectors, self.redis, self.db)

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
                    if not d['cam_source'] in self.detector_controller.running_cam:
                        d['state'] = "death"
                    d['nickname'] = base64.b64encode(bytes(d['nickname'], encoding="utf-8"))
                ret['detectors'] = detectors
            return ret

        @self.post('/add_detector')
        async def add_detector(request: Request, m: ModelAddDetector):
            print('/add_detector')
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            new_detector = {}
            state = self.db.detector_add(m.cam_source, m.nickname, payload['id'], False, self.server_id, new_detector)
            ret = {'state': state.get_value()}
            if state == db_state.detector_add_error_unk:
                pass
            elif state == db_state.detector_cam_source_exist:
                pass
            elif state == db_state.detector_add_success:
                self.detectors.append(new_detector)
                self.detector_controller.append_detector({'cam_source': m.cam_source, 'owner': payload['id']}, 1)
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
            ret = {'state': 'get_event_frames_success', 'events': self.redis.get_event_frames(m.event_name)[1::6]}
            print('get_event_frames：' + str(len(str(ret))))
            return ret

        @self.post('/del_event')
        async def del_event(request: Request, m: ModelDelEvent):
            # todo 检查用户符合
            ret = {'state': 'del_event_success', 'events': self.redis.del_event(m.event_name, m.cam_source)}
            return ret

        @self.post('/get_notification')
        async def get_notification(request: Request, m: ModelGetNotification):
            # todo 检查用户符合
            noti = self.redis.get_notification(m.cam_source)
            state = 1 if noti is not None else 0
            notification = ""
            if state == 1:
                # 阅后即焚
                self.redis.del_notification(m.cam_source)
                notification = noti["event"].name
            ret = {
                'notification': notification,
                'state': state,
            }
            #
            return ret

        @self.get("/open_video")
        async def open_video(request: Request, cam_source):
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            is_owner = self.db.user_is_owner_cam_source(cam_source, payload['id'])
            ret = {"success": False,
                   "address": ""}
            if is_owner:
                # TODO 临时
                if cam_source in self.detector_controller.detectors_obj and \
                        self.detector_controller.detectors_thread[cam_source]['state'] == DetectorState.running:
                    _detector: Detector = self.detector_controller.detectors_obj.get(cam_source)
                    _stream: StreamLive = _detector.cam.stream_live
                    if not _stream.stream_opened:
                        if _detector.is_local_file:
                            cam_source = self.local_file_address
                        _stream.open_stream(cam_source, _detector.is_local_file)
                        print("open_video: %s, is_local_file: %s" % (cam_source, str(_detector.is_local_file)))
                    else:
                        print("cam_source: %s had opened!!" % cam_source)
                    ret['success'] = True
                    ret['address'] = self.stream_out_address
                else:
                    print("open_video error! cam_source: %s, detectors_obj: %s " % (
                        cam_source, self.detector_controller.detectors_obj))
                    print("in:" + str(cam_source in self.detector_controller.detectors_obj))
                    print("state:" + str(self.detector_controller.detectors_thread[cam_source]['state']))
            else:
                print("is not owner!!!!")
            print("open_video res: %s" % str(ret))
            return ret

        @self.get("/keep_video")
        async def keep_video(request: Request, cam_source):
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            is_owner = self.db.user_is_owner_cam_source(cam_source, payload['id'])
            if is_owner:
                if cam_source in self.detector_controller.detectors_obj and \
                        self.detector_controller.detectors_thread[cam_source]['state'] == DetectorState.running:
                    _detector: Detector = self.detector_controller.detectors_obj.get(cam_source)
                    _stream: StreamLive = _detector.cam.stream_live
                    if _stream.stream_opened:
                        _stream.keep_live()
                        print("keep_video:" + cam_source)

        @self.post("/add_video_reminder")
        async def add_video_reminder(request: Request, m: ModelAddReminder):
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            is_owner = self.db.user_is_owner_cam_source(m.cam_source, payload['id'])
            if is_owner:
                if m.cam_source in self.detector_controller.detectors_obj and \
                        self.detector_controller.detectors_thread[m.cam_source]['state'] == DetectorState.running:
                    _detector: Detector = self.detector_controller.detectors_obj.get(m.cam_source)
                    _detector.rect_tracker.add_rect_from_base64_jpg(tuple(m.rect), m.frame)
                    result = self.db.reminder_add(m.reminder_name, m.cam_source, m.select_time
                                                  , ','.join(str(i) for i in m.rect), payload['id'], m.reminder_type,
                                                  m.frame)
                    if 'reminder_id' in result:
                        newList = list(create_reminder_from_db_obj(obj, self.db)
                                       for obj in
                                       self.db.get_reminders_by_user_and_cam(payload['id'],
                                                                             m.cam_source,
                                                                             result['reminder_id']))
                        _detector.reminder_lock.acquire()
                        # 只能添加一个
                        _detector.reminders = newList
                        _detector.reminder_lock.release()
                        print("add_video_reminder:" + m.cam_source)
                    else:
                        print("add_video_reminder_error")

        # @self.get("/video_feed")
        # async def video_feed(request: Request, cam_source):
        #     payload = self.Token.verify_token(request.headers.get("Authorization"))
        #     is_owner = self.db.user_is_owner_cam_source(cam_source, payload['id'])
        #     if is_owner:
        #         frame = generate_frames(cam_source)
        #         if frame is not None:
        #             return StreamingResponse(content=frame, media_type="image/jpeg")
        #         else:
        #             return "error"
        #     else:
        #         return "error"

        @self.post("/upload_record")
        async def upload_record(request: Request, file: UploadFile = File(...)):
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            cam_source = request.headers.get("Cam-Source")
            is_owner = self.db.user_is_owner_cam_source(cam_source, payload['id'])
            if is_owner:
                if cam_source in self.detector_controller.detectors_obj and \
                        self.detector_controller.detectors_thread[cam_source]['state'] == DetectorState.running:
                    _detector: Detector = self.detector_controller.detectors_obj.get(cam_source)
                    if not os.path.exists("UploadRecords"):
                        os.makedirs("UploadRecords")
                    if not os.path.exists("UploadRecords\\Files"):
                        os.makedirs("UploadRecords\\Files")
                    # 临时保存
                    with open(f"UploadRecords\\Files\\temp_{file.filename}", "wb") as f:
                        f.write(await file.read())
                    # TODO 添加到数据库再读取回来
                    _detector.voice_handler.add_feature(
                        {
                            'id': -1,
                            'name': "test",
                            'features': _detector.voice_handler.get_voice_feature(
                                f"UploadRecords\\Files\\temp_{file.filename}"
                            ),
                            'type': -1
                        })

                    return {"message": "File received and saved temporarily."}

        @self.post("/detect_record")
        async def detect_record(request: Request, file: UploadFile = File(...)):
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            cam_source = request.headers.get("Cam-Source")
            is_owner = self.db.user_is_owner_cam_source(cam_source, payload['id'])
            if is_owner:
                if cam_source in self.detector_controller.detectors_obj and \
                        self.detector_controller.detectors_thread[cam_source]['state'] == DetectorState.running:
                    _detector: Detector = self.detector_controller.detectors_obj.get(cam_source)
                    _detector.gesture_handler.clean_gesture_buff()
                    if not os.path.exists("UploadRecords"):
                        os.makedirs("UploadRecords")
                    if not os.path.exists("UploadRecords\\Files"):
                        os.makedirs("UploadRecords\\Files")
                    # 临时保存
                    with open(f"UploadRecords\\Files\\temp_{file.filename}", "wb") as f:
                        f.write(await file.read())
                    detected = _detector.voice_handler.detect_voice(f"UploadRecords\\Files\\temp_{file.filename}")
                    if detected is None:
                        return {"state": False,
                                "message": "No voice has been detected"}
                    else:
                        return {"state": True,
                                "name": detected['name']}

        @self.post("/is_recording")
        async def is_recording(request: Request, m: ModelIsRecording):
            payload = self.Token.verify_token(request.headers.get("Authorization"))
            is_owner = self.db.user_is_owner_cam_source(m.cam_source, payload['id'])
            if is_owner:
                if m.cam_source in self.detector_controller.detectors_obj and \
                        self.detector_controller.detectors_thread[m.cam_source]['state'] == DetectorState.running:
                    _detector: Detector = self.detector_controller.detectors_obj.get(m.cam_source)
                    return {'state': _detector.voice_handler.get_is_recording()}
                else:
                    return {'state': False}
