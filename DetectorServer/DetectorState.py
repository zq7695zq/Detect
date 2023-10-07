from enum import Enum


class DetectorState(Enum):
    running = 1
    wait_to_stop = 2
    stoped = 3

    def __init__(self, type):
        pass