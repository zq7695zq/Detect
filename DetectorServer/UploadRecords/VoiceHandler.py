import pickle
import threading
import time

import librosa
import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean, correlation


class VoiceHandler:
    def __init__(self, dtw_threshold=4000):
        # voice_features : [{id:, name:, features:, type:}]
        self.voice_features = []
        self.dtw_threshold = dtw_threshold
        self.features_lock = threading.Lock()
        self.recording_lock = threading.Lock()
        self.is_recording = False
        self.last_record_time = time.time() - 20

    def get_is_recording(self):
        self.recording_lock.acquire()
        ret = self.is_recording
        self.recording_lock.release()
        return ret

    def set_recording(self, is_reco):
        now = time.time()
        if self.is_recording or now - self.last_record_time < 10:
            return
        self.recording_lock.acquire()
        self.is_recording = is_reco
        self.last_record_time = now if is_reco else now - 20
        self.recording_lock.release()

    def detect_voice(self, voice):
        self.features_lock.acquire()
        voice_mfcc = self.get_voice_feature(voice)
        ret = None
        min_dtw = 9999
        for f in self.voice_features:
            dtw = fastdtw(f['features'].T, voice_mfcc.T, dist=correlation)[0]
            if dtw < min_dtw:
                min_dtw = dtw
                ret = f
        self.features_lock.release()
        if min_dtw < 1:
            return ret
        return None

    def add_feature(self, feature):
        self.features_lock.acquire()
        self.voice_features.append(feature)
        self.features_lock.release()

    def has_feateure(self):
        self.features_lock.acquire()
        ret = len(self.voice_features) > 0
        self.features_lock.release()
        return ret

    def dump_feature(self, feature):
        return pickle.dumps(feature)

    def load_feature(self, feature):
        return pickle.loads(feature)

    def get_voice_feature(self, audio_file):
        trimmed_audio, sr = self.dynamic_trim_audio(audio_file)
        mfcc = librosa.feature.mfcc(y=trimmed_audio, sr=sr)
        return mfcc

    def dynamic_trim_audio(self, audio_file, window_size=5, threshold_ratio=3):
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
