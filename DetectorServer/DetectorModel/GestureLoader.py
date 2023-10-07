import threading
import time

import cv2
import numpy as np
import torch

from CameraLoader import CamLoader
from models.experimental import attempt_load
from utils.datasets import letterbox
from utils.general import check_img_size, non_max_suppression, scale_coords
from utils.plots import plot_one_box, colors


class GestureLoader:
    def __init__(self):
        self.conf_thres = 0.25
        self.iou_thres = 0.45
        self.classes = None
        self.agnostic_nms = False
        self.max_det = 1000

        self.device = torch.cuda.current_device()

        self.model = attempt_load("./DetectorModel/Models/yolo-gesture/shoushi.pt",
                                  map_location=lambda storage, loc: storage.cuda(self.device))

        self.stride = int(self.model.stride.max())  # model stride

        self.imgsz = check_img_size(384, s=self.stride)  # check image size

        self.names = self.model.module.names if hasattr(self.model, 'module') else self.model.names  # get class names

        self.gesture_buffer = []

        self.gesture_buffer_lock = threading.Lock()

        self.gesture_buffer_last_clean_time = time.time()

    def next_frame(self, gesture_label, frame):
        if self.gesture_buffer_lock.locked():
            return
        self.gesture_buffer_lock.acquire()
        # 加入
        if time.time() - self.gesture_buffer_last_clean_time > 10:
            self.gesture_buffer.append({
                '_time': time.time(),
                'label': gesture_label,
                'frame': frame})
        self.gesture_buffer_lock.release()

    def get_gesture_buff(self):
        ten_seconds_ago = time.time() - 10.0
        self.gesture_buffer_lock.acquire()
        # 先过滤掉超过十秒的
        self.gesture_buffer = [gesture for gesture in self.gesture_buffer if gesture['_time'] >= ten_seconds_ago]
        ret = self.gesture_buffer.copy()
        self.gesture_buffer_lock.release()
        return ret

    def clean_gesture_buff(self):
        self.gesture_buffer_lock.acquire()
        self.gesture_buffer = []
        self.gesture_buffer_last_clean_time = time.time()
        self.gesture_buffer_lock.release()

    def gesture_handle(self):
        gesture_buff = self.get_gesture_buff()
        # 手势控制开启录音
        gesture_correct_count = -1
        frames = []
        # TODO 假的，还没实现，因为手势识别不准
        reliable_label = 'unk'
        for gesture in gesture_buff:
            _time = gesture['_time']
            label = gesture['label']
            if label == 'ok' or label == 'yearh':
                gesture_correct_count += 1
                reliable_label = label
                frames.append(gesture['frame'])

        return {'reliable': gesture_correct_count > 10,
                'label': reliable_label,
                'frames': [] if gesture_correct_count > 10 else frames}

    def detect_frame(self, img, filter_label):
        img = [img]
        # Letterbox
        img0 = img.copy()
        img = [letterbox(x, self.imgsz, auto=True, stride=self.stride)[0] for x in img0]

        # Stack
        img = np.stack(img, 0)

        # Convert
        img = img[:, :, :, ::-1].transpose(0, 3, 1, 2)  # BGR to RGB, to bsx3x416x416
        img = np.ascontiguousarray(img)
        img = torch.from_numpy(img).to(self.device)
        img = img.float()
        img /= 255.0  # 0 - 255 to 0.0 - 1.0

        pred = self.model(img, augment=False)[0]
        pred = non_max_suppression(pred, self.conf_thres, self.iou_thres, self.classes, self.agnostic_nms,
                                   max_det=self.max_det)
        det = pred[0]
        s, im0 = f'{0}: ', img0[0].copy()
        label = "unk"
        if len(det):
            # Rescale boxes from img_size to im0 size
            det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

            # Print results
            for c in det[:, -1].unique():
                n = (det[:, -1] == c).sum()  # detections per class
                s += f"{n} {self.names[int(c)]}{'s' * (n > 1)}, "  # add to string
                if self.names[int(c)] in filter_label:
                    return im0, "unk"
            for *xyxy, conf, cls in reversed(det):
                c = int(cls)  # integer class
                label = self.names[c]
                plot_one_box(xyxy, im0, label=label, color=colors(c, True), line_thickness=3)
        return im0, label


if __name__ == '__main__':
    fps_time = 0

    # Using threading.
    cam = CamLoader(0).start()
    gestureLoader = GestureLoader()

    while cam.grabbed():
        frames = cam.getitem()
        frames = gestureLoader.detect_frame(frames)
        frames = cv2.putText(frames, 'FPS: %f' % (1.0 / (time.time() - fps_time)),
                             (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        fps_time = time.time()
        cv2.imshow('frame', frames)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cam.stop()
    cv2.destroyAllWindows()
