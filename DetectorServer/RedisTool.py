import base64
import time
import uuid

import cv2
import numpy as np
import redis  # 导入redis 模块
from numpy import ndarray

from Events.Event import Event


def get_base64(string):
    return base64.b64encode(string.encode("utf-8")).decode('utf-8')


def frameToBase64(frame):
    base64_str = cv2.imencode(".jpg", frame[..., ::-1])[1]
    base64_str = base64.b64encode(base64_str)
    return base64_str


def strToEvent(event):
    if event is None:
        return None
    ret = eval(event)
    ret["event"] = Event(ret["event"])
    if "event_name" in ret:
        ret["event_name"] = get_base64(ret["event_name"])
    if "label" in ret:
        ret["label"] = get_base64(ret["label"])
    return ret


class redis_tool:

    def __init__(self, host, port, size):
        self.pool = redis.ConnectionPool(host=host, port=port, decode_responses=True)
        self.size = size

    def add_event(self, cam_source, event, frames):
        r = redis.Redis(connection_pool=self.pool)
        e_dict = {
            'event': event.value,
            'time': str(time.time()),
            'name': str(uuid.uuid4()),
            'event_name': str(event.get_action_name()),
            'cover_frame': frameToBase64(frames[0]),
        }
        r.rpush("cam_source_events_" + get_base64(cam_source), str(e_dict))
        for f in frames:
            r.rpush("event_" + get_base64(e_dict['name']), frameToBase64(f))
        r.expire("cam_source_events_" + get_base64(cam_source), 3600)
        r.expire("event_" + get_base64(e_dict['name']), 3600)

    def get_event_frame_count(self, event_name):
        r = redis.Redis(connection_pool=self.pool)
        return r.llen("event_" + get_base64(event_name))

    def del_event(self, event_name, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        events = r.lrange("cam_source_events_" + get_base64(cam_source), 0, -1)
        for e in events:
            if event_name in e:
                r.lrem("cam_source_events_" + get_base64(cam_source), 1, e)
                break
        r.delete("event_" + get_base64(event_name))

    def get_events_by_source(self, cam_source, page, page_size):
        r = redis.Redis(connection_pool=self.pool)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size - 1
        return [strToEvent(e) for e in r.lrange("cam_source_events_" + get_base64(cam_source), start_index, end_index)]

    def get_event_frames(self, event_name):
        r = redis.Redis(connection_pool=self.pool)
        return r.lrange("event_" + get_base64(event_name), 0, -1)

    def add_event_frame(self, event_name, frame):
        r = redis.Redis(connection_pool=self.pool)
        return r.rpush("event_" + get_base64(event_name), frameToBase64(frame))

    def get_last_event(self, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        return strToEvent(r.lindex("cam_source_events_" + get_base64(cam_source), -1))

    def set_norm_frame(self, cam_source, frame):
        r = redis.Redis(connection_pool=self.pool)
        r.set("cam_source_norm_frame_" + get_base64(cam_source), frameToBase64(frame))

    def get_last_norm_base64(self, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        return r.get("cam_source_norm_frame_" + get_base64(cam_source))

    def add_notification(self, cam_source, event, event_name):
        r = redis.Redis(connection_pool=self.pool)
        e_dict = {
            'event': event.value,
            'time': str(time.time()),
            'name': str(uuid.uuid4()),
            'event_name': event_name,
        }
        r.set("cam_source_notification_" + get_base64(cam_source), str(e_dict))
        r.expire("cam_source_notification_" + get_base64(cam_source), 3600)

    def get_notification(self, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        return strToEvent(r.get("cam_source_notification_" + get_base64(cam_source)))

    def del_notification(self, cam_source):
        r = redis.Redis(connection_pool=self.pool)
        r.delete("cam_source_notification_" + get_base64(cam_source))
