import threading
import time

import numpy as np
import torch

from DetectorModel.Gesture.models.experimental import attempt_load
from DetectorModel.Gesture.utils.datasets import letterbox
from DetectorModel.Gesture.utils.general import check_img_size, non_max_suppression, scale_coords
from DetectorModel.Gesture.utils.plots import plot_one_box, colors


class GestureLoader:
    def __init__(self):
        self.conf_thres = 0.35
        self.iou_thres = 0.45
        self.classes = None
        self.agnostic_nms = False
        self.max_det = 1000

        self.device = torch.cuda.current_device()

        self.model = attempt_load("./DetectorModel/Gesture/shoushi.pt",
                                  map_location=lambda storage, loc: storage.cuda(self.device))

        self.stride = int(self.model.stride.max())  # model stride

        self.imgsz = check_img_size(384, s=self.stride)  # check image size

        self.names = self.model.module.names if hasattr(self.model, 'module') else self.model.names  # get class names

        self.gesture_buffer = []

        self.gesture_buffer_lock = threading.Lock()

        self.gesture_buffer_last_clean_time = time.time()

    def next_frame(self, gesture_label):
        if self.gesture_buffer_lock.locked():
            return
        self.gesture_buffer_lock.acquire()
        # 加入
        self.gesture_buffer.append({
            '_time': time.time(),
            'label': gesture_label
        })
        self.gesture_buffer_lock.release()

    def get_gesture_buff(self):
        three_seconds_ago = time.time() - 3
        self.gesture_buffer_lock.acquire()
        self.gesture_buffer = [gesture for gesture in self.gesture_buffer if gesture['_time'] >= three_seconds_ago]
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
        # TODO 假的，还没实现，因为手势识别不准
        reliable_label = 'unk'
        for gesture in gesture_buff:
            _time = gesture['_time']
            label = gesture['label']
            if label == 'ok' or label == 'yearh':
                gesture_correct_count += 1
                reliable_label = label

        return {'reliable': gesture_correct_count > 10,
                'label': reliable_label,
                }

    def detect_frame(self, org_frame, filter_label):
        img = [org_frame.copy()]
        # Letterbox and stack
        # Letterbox
        img0 = img.copy()
        img = np.stack([letterbox(x, self.imgsz, auto=True, stride=self.stride)[0] for x in img0], 0)
        # Convert to torch tensor
        img = torch.from_numpy(img.transpose(0, 3, 1, 2)).float().div(255.0).to(
            self.device)  # BGR to RGB, to bsx3x416x416
        # Get predictions
        pred = self.model(img, augment=False)[0]
        det = non_max_suppression(pred, self.conf_thres, self.iou_thres, self.classes, self.agnostic_nms,
                                  max_det=self.max_det)[0]
        # Create a blank image
        blank_img = np.zeros_like(img[0].permute(1, 2, 0).cpu().numpy(), dtype=np.uint8)

        label = "unk"
        if len(det):
            # Rescale boxes
            det[:, :4] = scale_coords(img.shape[2:], det[:, :4], blank_img.shape).round()

            # Check filter label and draw boxes
            unique_classes = det[:, -1].unique()
            if any(self.names[int(c)] in filter_label for c in unique_classes):
                return blank_img, "unk"

            for *xyxy, _, cls in det:
                label = self.names[int(cls)]
                plot_one_box(xyxy, blank_img, label=label, color=colors(int(cls), True), line_thickness=3)
        return blank_img, label

