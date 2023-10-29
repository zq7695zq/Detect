import collections
import os
import threading
import time
import wave
import librosa
import numpy as np
import webrtcvad
from fastdtw import fastdtw
from scipy.spatial.distance import correlation
from pathlib import Path


class VoiceHandler:
    def __init__(self, db, detector_id, dtw_threshold=4000):
        self.dtw_threshold = dtw_threshold
        self.features_lock = threading.Lock()
        self.recording_lock = threading.Lock()
        self.is_recording = False
        self.last_record_time = time.time() - 20
        self.db = db
        self.detector_id = detector_id
        self.voice_features = self.load_features()
        self.vad = webrtcvad.Vad(1)
        # 可选地，设置它的攻击性模式，它是一个介于 0 和 3 之间的整数。0 是过滤非语音的最不积极的，3 是最积极的。 （您也可以在创建 VAD 时设置模式，例如 vad = webrtcvad.Vad(3)）：
        self.mode = 6
        self.temp_voice_life = 60 * 5  # 保存30分钟

        self.voice_temp_frames = []

        threading.Timer(60, self.delete_voice_thread).start()

    def get_is_recording(self):
        with self.recording_lock:
            return self.is_recording

    def set_recording(self, is_reco):
        now = time.time()
        if self.is_recording or now - self.last_record_time < 10:
            return
        with self.recording_lock:
            self.is_recording = is_reco
            self.last_record_time = now if is_reco else now - 20

    def detect_voice(self, voice):
        voice_mfcc = self.get_voice_feature(voice)
        ret = None
        min_dtw = 9999
        with self.features_lock:
            for f in self.voice_features:
                dtw = fastdtw(f['feature'].T, voice_mfcc.T, dist=correlation)[0]
                if dtw < min_dtw:
                    min_dtw = dtw
                    ret = f
        if min_dtw < 1:
            return ret
        return None

    def test_voice(self, voices):
        if len(voices) < 300 / self.mode:
            return False
        return has_voiced_window(voices, self.vad, 48000, int(len(voices) / self.mode))

    def detect_voice_new(self, voices, callback):
        threading.Thread(target=self.detect_voice_thread, args=(voices, callback, ), daemon=True).start()

    def detect_voice_thread(self, voices, callback):
        voice_file_name = self.save_voices(voices)
        ret = self.detect_voice(voice_file_name)
        if ret:
            Path(voice_file_name).unlink()
            callback(voice_file_name, ret['label'], voices)

    def delete_voice_thread(self):
        files = self.get_voice_files(False)
        for file_path in files:
            current_time = time.time()
            try:
                # 提取文件名中的时间戳
                timestamp = float(file_path.stem.split('_')[2])
                # 检查时间差异
                if current_time - timestamp > self.temp_voice_life:
                    file_path.unlink()
                    print(f"Deleted: {file_path}")
            except (ValueError, IndexError):
                # 如果文件名格式不符合预期，跳过该文件
                continue

    def get_voice_files(self, is_saved):
        return [file_path for file_path in Path('UploadRecords/Files').iterdir()
                if file_path.suffix == ".wav" and f"_{self.detector_id}_" in file_path.name
                and (('_saved' in file_path.name) if is_saved else ('_saved' not in file_path.name))]

    def add_feature(self, feature):
        with self.features_lock:
            self.voice_features.append(feature)

    def has_feature(self):
        with self.features_lock:
            return len(self.voice_features) > 0

    def get_voice_feature(self, audio_file):
        trimmed_audio, sr = dynamic_trim_audio(audio_file)
        mfcc = librosa.feature.mfcc(y=trimmed_audio, sr=sr)
        return mfcc

    def save_feature(self, label, file_name, feature):
        new_file_name = str(Path(f'UploadRecords/Files/{Path(file_name).stem}_saved.wav'))
        os.rename(file_name, new_file_name)
        record = self.db.save_feature(self.detector_id, label, new_file_name, feature)
        with self.features_lock:
            if record is not None:
                self.voice_features.append(record)

    def save_feature_from_file(self, label, file_name):
        feature = self.get_voice_feature(file_name)
        new_file_name = str(Path(f'UploadRecords/Files/{Path(file_name).stem}_saved.wav'))
        os.rename(file_name, new_file_name)
        record = self.db.save_feature(self.detector_id, label, new_file_name, feature)
        with self.features_lock:
            if record is not None:
                self.voice_features.append(record)

    def save_voices(self, voices):
        file_name = str(Path(f"UploadRecords/Files/temp_{self.detector_id}_{time.time()}.wav"))
        # 创建式打开音频文件
        wf = wave.open(file_name, 'wb')
        # 设置音频文件的属性：声道数，采样位，采样频率
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        for v in voices:
            wf.writeframes(v.bytes)
        wf.close()
        return file_name

    def load_features(self):
        return self.db.load_records(self.detector_id)


def has_voiced_window(frames, vad, sample_rate, window_size):
    """
    Checks if there exists a window in the frame sequence where
    more than 90% of the frames are detected as speech by the VAD.

    Args:
    - frames: The sequence of audio frames.
    - vad: An instance of webrtcvad.Vad.
    - sample_rate: The audio sample rate, in Hz.
    - window_size: The size of the sliding window.

    Returns:
    - True if such a window exists, False otherwise.
    """

    ring_buffer = collections.deque(maxlen=window_size)
    for frame in frames:
        is_speech = vad.is_speech(frame.bytes, sample_rate)
        ring_buffer.append(is_speech)

        # Check if more than 90% of the frames in the window are voiced
        if len(ring_buffer) == window_size and sum(ring_buffer) > 0.9 * window_size:
            return True

    return False

def dynamic_trim_audio(audio_file, window_size=5, threshold_ratio=3):
    # 读取音频文件
    y, sr = librosa.load(audio_file)
    # 计算音频能量
    energy = librosa.feature.rms(y=y)
    # 将能量转换为分贝（dB）单位
    energy_db = librosa.amplitude_to_db(energy)
    # 使用滑动窗口计算整体能量
    window = np.ones(window_size) / float(window_size)
    smoothed_energy = np.convolve(energy_db[0], window, mode='same')
    # 根据整体能量动态调整阈值
    max_energy = np.max(smoothed_energy)
    threshold_db = max_energy * threshold_ratio
    # 找到超过阈值的第一个样本和最后一个样本的索引\

    non_silent_samples = np.where(energy_db > threshold_db)[1]

    if len(non_silent_samples) == 0:
        print("No non-silent samples found in the audio.")
        return None, sr

    start_sample = non_silent_samples[0] * len(y) // len(smoothed_energy)
    end_sample = non_silent_samples[-1] * len(y) // len(smoothed_energy)

    # 截断音频
    trimmed_audio = y[start_sample:end_sample]

    return trimmed_audio, sr


