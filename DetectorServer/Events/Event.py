import json
from enum import Enum


def get_gesture_by_name(name):
    switcher = {
        'yearh': Event.gesture_yearh,
        'ok': Event.gesture_ok,
    }
    ret = switcher[name] if name in switcher else Event.gesture_unk
    # TODO 可靠度
    ret.set_confidence(1)
    return ret


def get_action_color(name):
    class_names_colors = {'Standing': (255, 0, 0),
                          'Walking': (255, 100, 0),
                          'Sitting': (255, 100, 100),
                          'Lying Down': (255, 200, 0),
                          'Stand up': (255, 255, 100),
                          'Sit down': (255, 0, 100),
                          'Fall Down': (255, 0, 0)}
    return class_names_colors[name] if name in class_names_colors else (0, 255, 0)


def get_action_event(name):
    action_event = {'Standing': Event(Event.standing),
                    'Walking': Event(Event.walking),
                    'Sitting': Event(Event.sitting),
                    'Lying Down': Event(Event.lying_down),
                    'Stand up': Event(Event.stand_up),
                    'Sit down': Event(Event.sit_down),
                    'Fall Down': Event(Event.fall_down)}
    return action_event[name] if name in action_event else Event(Event.pending)


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
    voice = 10

    stand_up = 11
    sit_down = 12

    def __init__(self, type):
        self.confi = "0"
        self.label = "unk"

    def __str__(self):
        return self.get_action_name()

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
            Event.stand_up: '站起',
            Event.sit_down: '坐下',
            Event.gesture_yearh: 'yearh',
            Event.gesture_ok: 'ok',
            Event.pills_warning: '吃药超时',
            Event.voice: self.label,
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
            Event.stand_up: '站起',
            Event.sit_down: '坐下',
        }
        gesture = {
            Event.gesture_yearh: 'yearh',
            Event.gesture_ok: 'ok',

        }
        pill = {
            Event.pills_warning: '吃药超时',
        }
        voice = {
            Event.voice: '语音指令',
        }
        if self in unk:
            return 'unk'
        elif self in action:
            return 'action'
        elif self in gesture:
            return 'gesture'
        elif self in pill:
            return 'pill'
        elif self in voice:
            return 'voice'
        return '未知'
