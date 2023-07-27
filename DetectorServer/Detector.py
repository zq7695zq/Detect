import threading
import time
from collections import deque

import cv2
import numpy as np
import torch

import NotificationSender
from CameraTools.CameraLoader import CamLoader_Q
from DetectorModel.Track.Tracker import Detection
from DetectorModel.fn import draw_single
from Events.Event import Event
from RectTracker import RectTracker

from MoveReminder import MoveReminder
from PostFramesController import PostFramesController


class Detector:
    def __init__(self, cam_source, owner, event_saver, models, restart_callback, interval_time=5, show_threshold=25):
        self.models = models

        self.started = False  # 是否已经完整走完init

        self.available = True  # 是否已经正常启动

        self.cam_source = cam_source

        self.owner = owner

        self.restart_callback = restart_callback

        self.cam = CamLoader_Q(cam_source, self.error_callback, interval_time, queue_size=256,
                               preprocess=self.preproc).start()

        self.available = not self.cam.stopped

        self.fps_time = 0

        self.event_saver = event_saver

        self.show_threshold = show_threshold

        self.started = True

        # self.post_frames_con = PostFramesController()

        self.rect_tracker = RectTracker(self.models.pysot_model)

        # 物品超时和区域警报
        self.reminders = []
        self.reminder_lock = threading.Lock()

    def error_callback(self, error):
        self.available = False
        print("error_callback", error)
        try:
            # 如果还没走完init不回调（回调会执行重新启动），通过启动者通过available观察是否已经成功启动
            # 而如果已经走完init，证明摄像头前N帧已经获取到，但是后面断开了，则回调->重启启动
            if self.started:
                self.restart_callback(self, self.started)
        except Exception as e:
            print("error_callback", "unk error", e)

    def is_available(self):
        return self.available

    def detect_frame(self):
        f = 0
        frame = self.cam.getitem()
        origin_frame = np.copy(frame)
        # Detect humans bbox in the frame with detector model.
        detected = self.models.detect_model.detect(frame, need_resize=False, expand_bb=10)

        detected_bbox = []
        if detected is not None:
            detected_bbox = self.convert_to_bbox_array(detected)

        # Predict each tracks bbox of current frame from previous frames information with Kalman filter.
        self.models.tracker.predict()
        # Merge two source of predicted bbox together.
        for track in self.models.tracker.tracks:
            det = torch.tensor([track.to_tlbr().tolist() + [0.5, 1.0, 0.0]], dtype=torch.float32)
            detected = torch.cat([detected, det], dim=0) if detected is not None else det

        detections = []  # List of Detections object for tracking.

        if detected is not None:
            # detected = non_max_suppression(detected[None, :], 0.45, 0.2)[0]
            # Predict skeleton pose of each bboxs.
            poses = self.models.pose_model.predict(frame, detected[:, 0:4], detected[:, 4])

            # Create Detections object.
            detections = [Detection(self.kpt2bbox(ps['keypoints'].numpy()),
                                    np.concatenate((ps['keypoints'].numpy(),
                                                    ps['kp_score'].numpy()), axis=1),
                                    ps['kp_score'].mean().numpy()) for ps in poses]

            # VISUALIZE.
            if self.models.args.show_detected:
                for bb in detected[:, 0:5]:
                    frame = cv2.rectangle(frame, (bb[0], bb[1]), (bb[2], bb[3]), (0, 0, 255), 1)

        # 物品追踪
        if self.rect_tracker.tracker_inited:
            ret_rect = self.rect_tracker.track_frame(origin_frame, frame)
            self.reminder_lock.acquire()
            for rt in self.reminders:
                frame = rt.track_frame(frame, ret_rect, detected_bbox)
            self.reminder_lock.release()

        # Update tracks by matching each track information of current and previous frame or
        # create a new track if no matched.
        self.models.tracker.update(detections, frame)
        event = Event(Event.pending)

        # Predict Actions of each track.
        for i, track in enumerate(self.models.tracker.tracks):
            if not track.is_confirmed():
                continue

            track_id = track.track_id
            bbox = track.to_tlbr().astype(int)
            center = track.get_center().astype(int)

            action = 'pending..'
            clr = (0, 255, 0)
            # Use 30 frames time-steps to prediction.
            if len(track.keypoints_list) == 30:
                pts = np.array(track.keypoints_list, dtype=np.float32)
                out = self.models.action_model.predict(pts, frame.shape[:2])
                # 可信度大于阈值才处理
                if out[0].max() * 100 > self.show_threshold:
                    action_name = self.models.action_model.class_names[out[0].argmax()]
                    action = '{}: {:.2f}%'.format(action_name, out[0].max() * 100)
                    if action_name == 'Fall Down':
                        clr = (255, 0, 0)
                        event = Event(Event.fall_down)
                    elif action_name == 'Lying Down':
                        clr = (255, 200, 0)
                        event = Event(Event.lying_down)
                    elif action_name == 'Walking':
                        clr = (255, 100, 0)
                        event = Event(Event.walking)
                    elif action_name == 'Sitting':
                        clr = (255, 100, 100)
                        event = Event(Event.sitting)
                    elif action_name == 'Standing':
                        clr = (255, 100, 255)
                        event = Event(Event.standing)
                    event.set_confidence(out[0].max() * 100)
                    # 发生事件处理
                    if event == event.fall_down:
                        self.event_saver.addEvent(event, track.frame_list)

            # VISUALIZE.
            if track.time_since_update == 0:
                if self.models.args.show_skeleton:
                    frame = draw_single(frame, track.keypoints_list[-1])
                frame = cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 1)
                frame = cv2.putText(frame, str(track_id), (center[0], center[1]), cv2.FONT_HERSHEY_COMPLEX,
                                    0.4, (255, 0, 0), 2)
                frame = cv2.putText(frame, action, (bbox[0] + 5, bbox[1] + 15), cv2.FONT_HERSHEY_COMPLEX,
                                    0.4, clr, 1)

        # if self.post_frames_con.stream_opened and not self.post_frames_con.post_frames_lock.locked():
        #     buffer = cv2.imencode(".jpg", frame)[1]
        #     self.post_frames_con.post_frames_lock.acquire()
        #     self.post_frames_con.add_stream_frame(buffer)
        #     self.post_frames_con.post_frames_lock.release()
        #     if self.post_frames_con.check_out_of_time():
        #         self.post_frames_con.clear_steam()
        # Show Frame.
        # frame = cv2.resize(frame, (0, 0), fx=2., fy=2.)
        fps_t = (time.time() - self.fps_time)
        frame = cv2.putText(frame, '%d, FPS: %f' % (f, 1.0 / fps_t if fps_t != 0 else 1),
                            (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        # frame = frame[:, :, ::-1]
        # 是否直播推流
        if self.cam.stream_live.stream_opened and self.cam.stream_live.check_out_of_time():
            self.cam.stream_live.write_frame(frame)
        self.fps_time = time.time()
        # print(fps_t)
        return {"event": event, "frame": frame, "origin_frame": origin_frame}
        # cv2.imwrite("./Results/img-" + str(time.time()) + ".jpg", frame)

    def image_resize(self, image, width=None, height=None, inter=cv2.INTER_AREA):
        # initialize the dimensions of the image to be resized and
        # grab the image size
        dim = None
        (h, w) = image.shape[:2]

        # if both the width and height are None, then return the
        # original image
        if width is None and height is None:
            return image

        # check to see if the width is None
        if width is None:
            # calculate the ratio of the height and construct the
            # dimensions
            r = height / float(h)
            dim = (int(w * r), height)

        # otherwise, the height is None
        else:
            # calculate the ratio of the width and construct the
            # dimensions
            r = width / float(w)
            dim = (width, int(h * r))

        # resize the image
        resized = cv2.resize(image, dim, interpolation=inter)

        # return the resized image
        return resized

    def preproc(self, image):
        """preprocess function for CameraLoader.
        """
        image = self.models.resize_fn(image)
        # image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return image

    def kpt2bbox(self, kpt, ex=20):
        """Get bbox that hold on all the keypoints (x,y)
        kpt: array of shape `(N, 2)`,
        ex: (int) expand bounding box,
        """
        return np.array((kpt[:, 0].min() - ex, kpt[:, 1].min() - ex,
                         kpt[:, 0].max() + ex, kpt[:, 1].max() + ex))

    def convert_to_bbox_array(self, detected_objects):
        return [(obj[1].item(), obj[0].item(), (obj[3] - obj[1]).item()
                 , (obj[2] - obj[0]).item()) for obj in detected_objects]
