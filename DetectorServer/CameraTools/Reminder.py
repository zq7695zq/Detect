import time
from abc import abstractmethod
from datetime import datetime

import numpy as np


def bbox_distance(bbox1, bbox2):
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2
    center1 = np.array([x1 + w1 / 2, y1 + h1 / 2])
    center2 = np.array([x2 + w2 / 2, y2 + h2 / 2])
    return np.linalg.norm(center1 - center2)


max_num = 9999999


class Reminder:
    def __init__(self, init_rect, start_time, move_distance=max_num, in_distance=max_num):
        self.start_time = start_time
        self.move_distance = move_distance
        self.in_distance = in_distance
        self.init_rect = init_rect
        self.db = None
        self.reminder_id = -1

    @abstractmethod
    def rect_moved(self, frame, last_rect):
        pass

    @abstractmethod
    def draw(self, frame, last_rect):
        pass

    @abstractmethod
    def rect_in(self, frame, last_rect):
        pass

    def track_frame(self, frame, last_rect, human_rects):
        ret_frame = self.draw(frame, last_rect)
        if not self.move_distance == max_num and bbox_distance(self.init_rect, last_rect) > self.move_distance:
            self.rect_moved(frame, last_rect)
        elif not self.in_distance == max_num:
            isRemind = False
            for human_rect in human_rects:
                if bbox_distance(last_rect, human_rect) < self.in_distance:
                    isRemind = True
                    break
            if isRemind:
                self.rect_in(frame, last_rect)
        return ret_frame

    def update_start_time(self):
        self.start_time = time.time()
        if self.db is None or self.reminder_id == -1:
            return
        return self.db.reminder_update_start_time(self.reminder_id)
