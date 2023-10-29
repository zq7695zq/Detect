import re
import subprocess
import threading
import time

import cv2
import numpy as np
import ffmpeg
from queue import Queue
from threading import Thread

from CameraTools.StreamLive import StreamLive


class AudioFrame(object):
    def __init__(self, _bytes, _timestamp):
        self.bytes = _bytes
        self.timestamp = _timestamp


class CamLoader_Q:
    def __init__(self, camera, error_callback, batch_size=1, queue_size=256, preprocess=None, is_local_file=False):
        self.error_callback = error_callback
        self.camera_source = camera
        self.is_local_file = is_local_file

        self.init_stream(self.is_local_file)

        self.stopped = False
        if self.video_stream is None or self.audio_stream is None:
            self.error_callback(f"Source: {camera} cannot be opened!")
            self.stopped = True
        # 推流初始化
        self.stream_live = StreamLive()

        self.paused = False
        self.batch_size = batch_size
        self.Q_Video = Queue(maxsize=queue_size)
        self.Q_Voice = Queue(maxsize=queue_size)
        self.preprocess_fn = preprocess

        self.time_lock = threading.Lock()
        self.replay_lock = threading.Lock()

    def init_stream(self, is_local_file):
        probe = ffmpeg.probe(self.camera_source, rtsp_transport='tcp') if not is_local_file else ffmpeg.probe(
            self.camera_source)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        self.frame_width = 384
        self.frame_height = 384
        self.frame_rate = 24
        self.video_duration = float(video_stream['duration'])
        self.frame_duration = 30
        self.sample_rate = 48000
        self.video_time = float(0)
        self.voice_time = float(0)
        cmd = ['ffmpeg',
               '-i', self.camera_source,
               '-f', 'rawvideo',
               '-pix_fmt', 'rgb24',
               '-r', str(self.frame_rate),
               '-s', f'{self.frame_width}*{self.frame_height}',
               '-v', 'info',
               '-map', '0:v',
               'pipe:',
               ]
        if not is_local_file:
            cmd.append('-rtsp_transport')
            cmd.append('tcp')
        else:
            cmd.insert(1, '-stream_loop')
            cmd.insert(2, '-1')
        self.video_stream = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cmd = ['ffmpeg',
               '-i', self.camera_source,
               '-ar', '48000',
               '-ac', '1',
               '-f', 's16le',
               '-acodec', 'pcm_s16le',
               '-r', str(self.frame_rate),
               '-v', 'info',
               '-map', '0:a',
               'pipe:'
               ]
        if not is_local_file:
            cmd.append('-rtsp_transport')
            cmd.append('tcp')
        else:
            cmd.insert(1, '-stream_loop')
            cmd.insert(2, '-1')
        self.audio_stream = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def start(self):
        if self.stopped:
            return self
        Thread(target=self.update_video, args=(), daemon=True).start()
        Thread(target=self.update_playtime, args=(self.video_stream, True,), daemon=True).start()
        Thread(target=self.update_voice, args=(), daemon=True).start()
        Thread(target=self.update_playtime, args=(self.audio_stream, False,), daemon=True).start()
        c = 0
        while not self.grabbed():
            time.sleep(0.5)
            c += 1
            if c > 20:
                self.stop()
                return self
        return self

    def update_playtime(self, stream, is_video):
        lineAfterCarriage = ''
        while True:
            char = stream.stderr.read(1).decode('utf-8')
            if char == '' and stream.poll() != None:
                break
            if char != '':
                lineAfterCarriage += char
                if char == '\r':
                    if lineAfterCarriage.find('speed') != -1:
                        match = re.search(r"time=(\d+:\d+:\d+\.\d+)", lineAfterCarriage)
                        if match:
                            played_time_str = match.group(1)
                            if played_time_str == 'N/A':
                                continue
                            try:
                                played_time = sum(
                                    float(x) * 60 ** i for i, x in enumerate(reversed(played_time_str.split(":"))))
                                # print(f"{'音频' if not is_video else '视频'}已播放到 {played_time} 秒, 已播放{played_time // self.video_duration}次")
                                with self.time_lock:
                                    if is_video:
                                        self.video_time = played_time
                                    else:
                                        self.voice_time = played_time
                            except Exception as e:
                                print(f"无法解析播放时间: {played_time_str}. 错误信息: {e}")
                    lineAfterCarriage = ''
        time.sleep(1)

    def update_video(self):
        while not self.stopped:
            if self.Q_Video.full():
                with self.Q_Video.mutex:
                    self.Q_Video.queue.clear()
            frames = []
            get_time_start = time.time()
            for k in range(self.batch_size):
                # 读取视频帧
                in_bytes = self.video_stream.stdout.read(self.frame_width * self.frame_height * 3)
                if not in_bytes:
                    self.stop()
                    self.error_callback('Camera stream stopped! Source: ' + self.camera_source)
                    return
                frame = np.frombuffer(in_bytes, np.uint8).reshape(self.frame_height, self.frame_width, 3)

                if self.preprocess_fn is not None:
                    frame = self.preprocess_fn(frame)
                frames.append(frame)
                frames = np.stack(frames)
            time.sleep(1 / self.frame_rate)

            self.Q_Video.put(frames)

    def update_voice(self):
        voice_frame_width = int(self.sample_rate * (self.frame_duration / 1000.0) * 2)
        while not self.stopped:
            if self.Q_Voice.full():
                with self.Q_Voice.mutex:
                    self.Q_Voice.queue.clear()
            audio_frame_bytes = b''
            for k in range(self.batch_size):
                # Read audio frame
                get_time_start = time.time()
                audio_frame_bytes += self.audio_stream.stdout.read(voice_frame_width)
                if not audio_frame_bytes:
                    self.stop()
                    self.error_callback('Audio stream stopped! Source: ' + self.camera_source)
                    return
                with self.time_lock:
                    self.Q_Voice.put(AudioFrame(audio_frame_bytes, self.voice_time))
                get_time = time.time() - get_time_start
                sleep_time = self.frame_duration / 1000 - get_time
                time.sleep(sleep_time if sleep_time > 0 else 0)

    def pause(self):
        if self.paused:
            return
        self.paused = True
        self.audio_stream.terminate()
        self.video_stream.terminate()

    def continue_stream(self):
        """Return `True` if continued."""
        if self.paused:
            if self.is_local_file:
                self.init_local_file_stream()
            else:
                self.init_rtsp_stream()
            self.paused = False
        return not self.stopped

    def grabbed(self):
        """Return `True` if you can read a frame."""
        return self.Q_Video.qsize() > 0

    def getitem(self):
        return self.Q_Video.get()

    def getVoices(self):
        ret = []
        with self.Q_Voice.mutex:
            ret = list(self.Q_Voice.queue)
            self.Q_Voice.queue.clear()
        return ret

    def stop(self):
        if self.stopped:
            return
        self.stopped = True
        # self.audio_stream.terminate()
        self.video_stream.terminate()

    def __len__(self):
        return self.Q_Video.qsize()

    def __del__(self):
        self.audio_stream.terminate()
        self.video_stream.terminate()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.audio_stream.terminate()
        self.video_stream.terminate()

    def __align_sample_rate(self, source_sample_rate):
        if source_sample_rate > 48000:
            sample_rate = 48000
        elif source_sample_rate > 32000 and source_sample_rate < 48000:
            sample_rate = 32000
        elif source_sample_rate > 16000 and source_sample_rate < 32000:
            sample_rate = 16000
        else:
            sample_rate = 8000
        return sample_rate


def error(err):
    # print(err)
    return err


if __name__ == '__main__':
    # 用于捕获和打印stderr的线程

    cam = CamLoader_Q("D:\PyCharmProjects\Detect\DetectorServer\Videos\\test-video.mp4", error, queue_size=256,
                      is_local_file=True, preprocess=error).start()

    while True:
        frames = cam.getitem()
        cv2.imshow('frame', frames[0])
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam.stop()
    cv2.destroyAllWindows()
