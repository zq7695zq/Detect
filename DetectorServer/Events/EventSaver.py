import time

import RedisTool


class EventSaver:
    def __init__(self, cam_source, redis: RedisTool):
        self.cam_source = cam_source
        self.redis = redis

    def addEvent(self, event, frames):
        print("addEvent: " + event.name)
        last_event = self.redis.get_last_event(self.cam_source)
        if last_event is None or float(time.time()) - float(last_event['time']) > 3.0:  # 三秒内发生同事件只添加最新一帧
            if last_event is None:
                print("frist frames:")
            else:
                print(float(time.time()) - float(last_event['time']))
            self.redis.add_event(self.cam_source, event, frames)
        else:
            self.redis.add_event_frame(last_event['name'], frames[-1])
