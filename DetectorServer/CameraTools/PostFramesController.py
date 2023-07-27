import queue
import threading
import time


class PostFramesController:

    def __init__(self):
        self.post_frames_len = 60

        self.post_frames = queue.Queue(maxsize=self.post_frames_len)

        self.post_frames_lock = threading.Lock()

        self.post_frames_last_time_get_frame = time.time()

        self.stream_opened = False

    def open_stream(self):
        self.clear_steam()
        self.stream_opened = True

    def close_stream(self):
        self.clear_steam()
        self.stream_opened = False

    def pop_stream_frame(self):
        ret = self.post_frames.get()
        self.post_frames_last_time_get_frame = time.time()
        return ret

    def pop_frames(self):
        self.post_frames_lock.acquire()
        merged_bytes = b""
        while not self.post_frames.empty():
            merged_bytes += self.post_frames.get().tobytes()
        self.post_frames_lock.release()
        print("pop_frames:" + str(len(merged_bytes)))
        self.post_frames_last_time_get_frame = time.time()
        return merged_bytes

    def add_stream_frame(self, frame):
        if self.post_frames.qsize() >= self.post_frames_len:
            self.clear_steam()
        self.post_frames.put(frame)

    def clear_steam(self):
        while not self.post_frames.empty():
            self.post_frames.get()

    def get_stream_len(self):
        ret = self.post_frames.qsize()
        return ret

    def check_out_of_time(self):
        return time.time() - self.post_frames_last_time_get_frame > 60
