import subprocess as sp
import time


class StreamLive:
    def __init__(self):
        self.pipe = None
        self.last_time = time.time()
        self.stream_opened = False
        self.live_time = 60  # 超过30秒没有刷新，即视为关闭

    def open_stream(self, camera_stream):
        width = 384
        height = 384
        fps = 24
        camera_stream = camera_stream + '_stream_from_server'
        command = ['ffmpeg',
                   '-y',
                   '-f', 'rawvideo',
                   '-vcodec', 'rawvideo',
                   '-pix_fmt', 'bgr24',
                   '-s', "{}x{}".format(width, height),
                   '-r', str(fps),
                   '-i', '-',
                   '-c:v', 'libx264',
                   '-pix_fmt', 'yuv420p',
                   '-preset', 'ultrafast',
                   '-f', 'rtsp',
                   camera_stream]
        try:
            # 建立子进程(配置管道)
            self.pipe = sp.Popen(command, stdin=sp.PIPE)
            self.stream_opened = True
        except Exception as e:
            print(e)

    def write_frame(self, frame):
        if self.pipe is not None:
            # 推流代码
            self.pipe.stdin.write(frame.tobytes())

    def stop_stream(self):
        self.pipe.kill()
        self.stream_opened = False

    def keep_live(self):
        self.last_time = time.time()

    def check_out_of_time(self):
        if time.time() - self.last_time > self.live_time:
            self.stop_stream()
            return False
        return True
