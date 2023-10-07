from enum import Enum


class Event(Enum):
    pending = 0
    fall_down = 1
    lying_down = 2
    walking = 3
    sitting = 4
    standing = 5
    gesture_yearh = 6
    gesture_ok = 7
    gesture_unk = 8
    pills_warning = 9

    def __init__(self, type):
        self.confi = "0"

    def set_confidence(self, c):
        self.confi = str(c)

    def get_action_name(self):
        switcher = {
            Event.pending: '未知',
            Event.fall_down: '摔倒',
            Event.lying_down: '躺下',
            Event.walking: '走路',
            Event.sitting: '坐',
            Event.standing: '站立',
            Event.gesture_yearh: 'yearh',
            Event.gesture_ok: 'ok',
            Event.pills_warning: '吃药超时',
        }
        if self in switcher:
            return switcher[self]
        return '未知事件'

    def get_event_type(self):
        unk = {
            Event.pending: '未知',
        }
        action = {
            Event.fall_down: '摔倒',
            Event.lying_down: '躺下',
            Event.walking: '走路',
            Event.sitting: '坐',
            Event.standing: '站立',
        }
        gesture = {
            Event.gesture_yearh: 'yearh',
            Event.gesture_ok: 'ok',

        }
        pill = {
            Event.pills_warning: '吃药超时',
        }
        if self in unk:
            return 'unk'
        elif self in action:
            return 'action'
        elif self in gesture:
            return 'gesture'
        elif self in pill:
            return 'pill'
        return '未知'

    def get_gesture_by_name(self, name):
        switcher = {
            'yearh': Event.gesture_yearh,
            'ok': Event.gesture_ok,
        }
        ret = switcher[name] if name in switcher else Event.gesture_unk
        # TODO 可靠度
        ret.set_confidence(1)
        return ret

