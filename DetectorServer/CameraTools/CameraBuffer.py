from collections import deque


class CameraBuffer:
    def __init__(self, cam_source, buffer_size=60):
        self.buffer_size = buffer_size
        self.frameBuff = deque(maxlen=buffer_size)

    def append(self, frame):
        self.frameBuff.append(frame)

    def clear(self):
        self.frameBuff.clear()

    def pop(self):
        return self.frameBuff.pop()
