import subprocess as sp
import time


class StreamLive:
    def __init__(self):
        self.camera_stream = None
        self.pipe = None
        self.last_time = time.time()
        self.stream_opened = False
        self.live_time = 30  # 超过30秒没有刷新，即视为关闭

    def open_stream(self, camera_stream, is_local_file):
        width = 384
        height = 384
        fps = 16
        self.camera_stream = camera_stream
        print("open_stream : %s" % self.camera_stream)
        command = ['ffmpeg',
                   '-y',
                   '-f', 'rawvideo',
                   '-vcodec', 'rawvideo',
                   '-pix_fmt', 'rgb24',
                   '-s', "{}x{}".format(width, height),
                   '-r', str(fps),
                   '-i', '-',
                   '-c:v', 'libx264',
                   '-pix_fmt', 'yuv420p',
                   '-preset', 'ultrafast',
                   '-f', 'rtsp' if not is_local_file else 'flv',
                   camera_stream]
        try:
            # 建立子进程(配置管道)
            self.pipe = sp.Popen(command, stdin=sp.PIPE)
            self.last_time = time.time()
            self.stream_opened = True
            return self.camera_stream
        except Exception as e:
            print(e)
            return ""

    def write_frame(self, frame):
        if self.pipe.poll() is not None:
            print('pipe exit', self.pipe.poll())
            return
        if self.pipe is not None:
            try:
                # 推流代码
                self.pipe.stdin.write(frame.tobytes())
            except Exception as e:
                print("Error write frame", e)


    def stop_stream(self):
        if not self.stream_opened:
            return
        self.pipe.kill()
        self.stream_opened = False
        print("stream_stopped" + self.camera_stream)

    def keep_live(self):
        self.last_time = time.time()

    def check_out_of_time(self):
        if time.time() - self.last_time > self.live_time:
            self.stop_stream()
            return False
        return True
