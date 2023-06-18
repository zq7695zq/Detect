from enum import Enum


class Event(Enum):
    pending = 0
    fall_down = 1
    lying_down = 2
    walking = 3
    sitting = 4
    standing = 5

    def __init__(self, type):
        pass
