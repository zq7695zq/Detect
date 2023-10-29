import time

import RedisTool
from Event import Event
from NotificationSender import NotiSender


class EventSaver:
    def __init__(self, cam_source, redis: RedisTool, owner, db):
        self.cam_source = cam_source
        self.redis = redis
        self.owner = owner
        self.noti_sender = NotiSender(db, owner)

    def addEvent(self, event, frames, label=''):
        last_event = self.redis.get_last_event(self.cam_source)
        if last_event is None or float(time.time()) - float(last_event['time']) > 3.0:  # 三秒内发生同事件只添加最新一帧
            print("addEvent: " + event.name, "confidence :" + event.confi)
            if last_event is None:
                print("first frames:")
            else:
                print(float(time.time()) - float(last_event['time']))
            if label != '':
                event.label = label
            self.redis.add_event(self.cam_source, event, frames)

            # 添加通知消息
            self.redis.add_notification(self.cam_source, event, event.get_action_name())

            # 发送提示消息
            # self.noti_sender.send(event.name)

        else:
            if last_event is not None and last_event['event_name'] == event.get_action_name():
                self.redis.add_event_frame(last_event['name'], frames[-1])

    def getLastEvent(self):
        return self.redis.get_last_event(self.cam_source)

    def pushSingleFrame(self, last_event, frame):
        if last_event is not None:
            self.redis.add_event_frame(last_event['name'], frame)

    def pushMoreFrame(self, event, frame, event_type):
        # 补充事件结束后的一些帧进事件回放
        last_event = self.getLastEvent()
        if event == event.pending and last_event is not None and last_event['event'].get_event_type() == event_type:
            if float(time.time()) - float(last_event['time']) < 5:
                self.pushSingleFrame(last_event, frame)
