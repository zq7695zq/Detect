import time

import cv2

from Reminder import Reminder


def convert_seconds(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return "{:02d}:{:02d}:{:02d}".format(int(hours), int(minutes), int(seconds))


class MoveReminder(Reminder):
    def draw(self, frame, last_rect):
        self.remaining_time = self.interval + self.start_time - time.time()
        bbox = last_rect
        font = cv2.FONT_HERSHEY_SIMPLEX
        if self.remaining_time <= 0:
            return cv2.putText(frame, "waring!!", (bbox[0] - 10, bbox[1] - 10), font, 0.5, (0, 0, 255), 1), (0, 0, 255), True
        else:
            return cv2.putText(frame, 'pills:' + convert_seconds(self.remaining_time),
                               (bbox[0] - 10, bbox[1] - 10), font, 0.5, (0, 255, 0), 1), (0, 255, 0), False

    def rect_moved(self, frame, last_rect):
        print('rect_moved!!!!')
        self.update_start_time()

    def rect_in(self, frame, last_rect):
        pass

    def get_state(self):
        pass

    def __init__(self, start_time, interval, init_rect):
        # interval 是秒数
        self.interval = interval
        self.isRemind = False
        self.remaining_time = 999999
        super().__init__(init_rect, start_time, move_distance=20, in_distance=120)
