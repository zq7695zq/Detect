import base64
import time
import uuid

import cv2
import numpy as np
import redis  # 导入redis 模块
from numpy import ndarray

from Events.Event import Event


class redis_tool:

    def __init__(self, host, port, size):
        self.pool = redis.ConnectionPool(host=host, port=port, decode_responses=True)
        self.size = size

    def base64ToFrame(self, base64_str):
        imgString = base64.b64decode(base64_str)
        nparr = np.fromstring(imgString, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return image

    def frameToBase64(self, frame):
        base64_str = cv2.imencode(".jpg", frame)[1]
        base64_str = base64.b64encode(base64_str)
        return base64_str

    def strToEvent(self, event):
        if event is None:
            return None
        ret = eval(event)
        ret["event"] = Event(ret["event"])
        return ret

    def set_key_frame(self, cam_source, frame: ndarray):
        r = redis.Redis(connection_pool=self.pool)
        r.set("cam_source_key_frame_" + cam_source, self.frameToBase64(frame))

    def get_key_frame(self, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        return self.base64ToFrame(r.get("cam_source_key_frame_" + cam_source))

    def add_event(self, cam_source, event, frames):
        r = redis.Redis(connection_pool=self.pool)
        e_dict = {
            'event': event.value,
            'time': str(time.time()),
            'name': str(uuid.uuid4()),
        }
        r.rpush("cam_source_events_" + cam_source, str(e_dict))
        for f in frames:
            r.rpush("event_" + e_dict['name'], self.frameToBase64(f))

    def del_event(self, event_name, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        events = r.lrange("cam_source_events_" + cam_source, 0, -1)
        for e in events:
            if event_name in e:
                r.lrem("cam_source_events_" + cam_source, 1, e)
                break
        r.delete("event_" + event_name)

    def get_events_by_source(self, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        return [self.strToEvent(e) for e in r.lrange("cam_source_events_" + cam_source, 0, -1)]

    def get_event_frames(self, event_name):
        r = redis.Redis(connection_pool=self.pool)
        return r.lrange("event_" + event_name, 0, -1)

    def add_event_frames(self, event_name, frames):
        r = redis.Redis(connection_pool=self.pool)
        for f in frames:
            r.rpush("event_" + event_name, self.frameToBase64(f))

    def add_event_frame(self, event_name, frame):
        r = redis.Redis(connection_pool=self.pool)
        return r.rpush("event_" + event_name, self.frameToBase64(frame))

    def get_last_event(self, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        return self.strToEvent(r.lindex("cam_source_events_" + cam_source, -1))

    def set_norm_frame(self, cam_source, frame):
        r = redis.Redis(connection_pool=self.pool)
        r.set("cam_source_norm_frame_" + cam_source, self.frameToBase64(frame))

    def get_last_norm_base64(self, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        return r.get("cam_source_norm_frame_" + cam_source)
