import base64

import cv2
import numpy as np

from Pysot.core.config import cfg
from Pysot.tracker.tracker_builder import build_tracker
from PysotModel import PysotModel


class RectTracker:
    def __init__(self, pysot_model: PysotModel):
        self.model = pysot_model.model
        # build tracker
        self.tracker = build_tracker(self.model)
        self.tracker_inited = False
        pass

    def add_rect(self, init_rect, frame):
        self.tracker.init(frame, init_rect)
        self.tracker_inited = True

    def add_rect_from_base64_jpg(self, init_rect, frame):
        # Decode base64-encoded screenshot to get the raw bytes
        frame_bytes = base64.b64decode(frame)
        # Convert bytes to NumPy array
        nparr = np.frombuffer(frame_bytes, np.uint8)
        # Decode the image as BGR format
        bgr_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        self.add_rect(init_rect, bgr_image)

    def track_frame(self, origin_frame, out_frame):
        if not self.tracker_inited:
            return
        outputs = self.tracker.track(origin_frame)
        bbox = None
        if 'polygon' in outputs:
            polygon = np.array(outputs['polygon']).astype(np.int32)
            cv2.polylines(out_frame, [polygon.reshape((-1, 1, 2))],
                          True, (0, 255, 0), 3)
            mask = ((outputs['mask'] > cfg.TRACK.MASK_THERSHOLD) * 255)
            mask = mask.astype(np.uint8)
            mask = np.stack([mask, mask * 255, mask]).transpose(1, 2, 0)
            out_frame = cv2.addWeighted(out_frame, 0.77, mask, 0.23, -1)
        else:
            bbox = list(map(int, outputs['bbox']))
            cv2.rectangle(out_frame, (bbox[0], bbox[1]),
                          (bbox[0] + bbox[2], bbox[1] + bbox[3]),
                          (0, 255, 0), 3)
        return bbox

    def del_rect(self, rect_id):
        pass
