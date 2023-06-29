import time

import RedisTool
from NotificationSender import NotiSender


class EventSaver:
    def __init__(self, cam_source, redis: RedisTool, owner, db):
        self.cam_source = cam_source
        self.redis = redis
        self.owner = owner
        self.noti_sender = NotiSender(db, owner)

    def addEvent(self, event, frames):
        last_event = self.redis.get_last_event(self.cam_source)
        if last_event is None or float(time.time()) - float(last_event['time']) > 3.0:  # 三秒内发生同事件只添加最新一帧
            print("addEvent: " + event.name, "confidence :" + event.confi)
            if last_event is None:
                print("first frames:")
            else:
                print(float(time.time()) - float(last_event['time']))
            self.redis.add_event(self.cam_source, event, frames)

            # 添加通知消息
            self.redis.add_notification(self.cam_source, event)

            # 发送提示消息
            self.noti_sender.send(event.name)

        else:
            self.redis.add_event_frame(last_event['name'], frames[-1])



