import threading
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import torch

import Database
from CameraTools.CameraLoader import CamLoader_Q
from DetectorModel.Track.Tracker import Detection
from DetectorModel.fn import draw_single
from Events.Event import Event, get_gesture_by_name, get_action_color, get_action_event
from CameraTools.FrameBuffer import FrameBuffer
from DetectorModel.GestureLoader import GestureLoader
from DetectorModel.ModelsLoader import ModelsLoader
from CameraTools.RectTracker import RectTracker
from UploadRecords.VoiceHandler import VoiceHandler


class Detector:
    def __init__(self, detector_id, cam_source, owner, event_saver, models, restart_callback, db: Database,
                 show_threshold=25,
                 is_local_file=False):
        self.models: ModelsLoader = models

        self.models.addPoseNums(cam_source)

        self.models.addTracker(cam_source)

        self.models.addPysotModel(cam_source)

        self.detector_id = detector_id

        self.started = False  # 是否已经完整走完init

        self.available = True  # 是否已经正常启动

        self.cam_source = cam_source

        self.db = db

        self.owner = owner

        self.restart_callback = restart_callback

        self.cam = CamLoader_Q(cam_source, self.error_callback, queue_size=256,
                               preprocess=self.preproc, is_local_file=is_local_file).start()

        self.available = not self.cam.stopped

        self.fps_time = 0

        self.event_saver = event_saver

        self.show_threshold = show_threshold

        self.action_buffer = FrameBuffer(60)

        self.is_local_file = is_local_file

        self.stream_opened = False

        self.post_frames = deque(maxlen=120)

        self.started = True

        # self.post_frames_con = PostFramesController()

        # 物品超时和区域警报
        self.reminders = []

        self.reminder_buffer = FrameBuffer(60)

        self.reminder_lock = threading.Lock()

        self.rect_tracker = RectTracker(self.models.getPysotModel(cam_source))

        self.last_time_color = (0, 255, 0)

        # 音频识别
        self.voice_handler = VoiceHandler(self.db, self.detector_id)

        self.voice_buffer = FrameBuffer(60)

        self.show_voice_time = time.time()

        # 手势识别
        self.gesture_handler = GestureLoader()

        self.gesture_buffer = FrameBuffer(60)

        self.frame_count = 0

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

    def open_stream(self):
        self.post_frames.clear()
        self.stream_opened = True

    def close_stream(self):
        self.post_frames.clear()
        self.stream_opened = False

    def detect_frame(self):
        frame = self.cam.getitem()[0]
        origin_frame = np.copy(frame)
        # Detect humans bbox in the frame with detector model.
        detected = self.models.detect_model.detect(frame, need_resize=False, expand_bb=10)

        detected_bbox = []
        if detected is not None:
            detected_bbox = self.convert_to_bbox_array(detected)

        # Predict each tracks bbox of current frame from previous frames information with Kalman filter.
        self.models.getTracker(self.cam_source).predict()
        # Merge two source of predicted bbox together.
        for track in self.models.getTracker(self.cam_source).tracks:
            det = torch.tensor([track.to_tlbr().tolist() + [0.5, 1.0, 0.0]], dtype=torch.float32)
            detected = torch.cat([detected, det], dim=0) if detected is not None else det

        detections = []  # List of Detections object for tracking.
        if detected is not None:
            # detected = non_max_suppression(detected[None, :], 0.45, 0.2)[0]
            # Predict skeleton pose of each bboxs.
            poses = self.models.pose_model.predict(frame, detected[:, 0:4], detected[:, 4],
                                                   self.models.getPoseNums(self.cam_source))

            # Create Detections object.
            detections = [Detection(self.kpt2bbox(ps['keypoints'].numpy()),
                                    np.concatenate((ps['keypoints'].numpy(),
                                                    ps['kp_score'].numpy()), axis=1),
                                    ps['kp_score'].mean().numpy()) for ps in poses]

            # VISUALIZE.
            if self.models.args.show_detected:
                for bb in detected[:, 0:5]:
                    frame = cv2.rectangle(frame, (bb[0], bb[1]), (bb[2], bb[3]), (0, 0, 255), 1)
            # 过滤掉过于接近的Detection
            detections = self.filter_close_bboxes(detections)

        item_event = Event(Event.pending)
        item_frame = np.zeros_like(origin_frame)
        frame_with_item = None
        # 物品追踪
        if self.rect_tracker.tracker_inited:
            ret_rect = self.rect_tracker.track_frame(origin_frame, item_frame, self.last_time_color)
            frame_with_item = cv2.add(item_frame, origin_frame)
            self.reminder_lock.acquire()
            for rt in self.reminders:
                item_frame, self.last_time_color, isWarning, isMoved = rt.track_frame(item_frame, ret_rect,
                                                                                      detected_bbox)
                frame_with_item = cv2.add(item_frame, frame_with_item)
                if isWarning and not self.rect_tracker.isWarned:
                    self.rect_tracker.isWarned = True
                    item_event = Event(Event.pills_warning)
                    self.event_saver.addEvent(item_event, self.reminder_buffer.get_frames())
                elif not isWarning and isMoved:
                    self.rect_tracker.isWarned = False

            self.reminder_lock.release()
            self.reminder_buffer.add_frame(frame_with_item)

            # 补充事件结束后的一些帧进事件回放
            self.event_saver.pushMoreFrame(item_event, frame_with_item, 'pill')

        # Update tracks by matching each track information of current and previous frame or
        # create a new track if no matched.
        self.models.getTracker(self.cam_source).update(detections, frame)

        event_action = Event(Event.pending)
        action_frame = np.zeros_like(origin_frame)
        frame_with_action = np.zeros_like(origin_frame)
        # Predict Actions of each track.
        for i, track in enumerate(self.models.getTracker(self.cam_source).tracks):
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
                    clr = get_action_color(action_name)
                    event_action = get_action_event(action_name)
                    event_action.set_confidence(out[0].max() * 100)
                    # 发生事件处理
                    if event_action == event_action.fall_down:
                        self.event_saver.addEvent(event_action, track.frame_list)

            # VISUALIZE.
            if track.time_since_update == 0:
                if self.models.args.show_skeleton:
                    action_frame = draw_single(action_frame, track.keypoints_list[-1])
                action_frame = cv2.rectangle(action_frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 1)
                action_frame = cv2.putText(action_frame, str(track_id), (center[0], center[1]),
                                           cv2.FONT_HERSHEY_COMPLEX,
                                           0.4, (255, 0, 0), 2)
                action_frame = cv2.putText(action_frame, action, (bbox[0] + 5, bbox[1] + 15), cv2.FONT_HERSHEY_COMPLEX,
                                           0.4, clr, 1)

        frame_with_action = cv2.add(action_frame, frame)
        # 补充事件结束后的一些帧进事件回放
        self.event_saver.pushMoreFrame(event_action, frame_with_action, 'action')

        # if self.post_frames_con.stream_opened and not self.post_frames_con.post_frames_lock.locked():
        #     buffer = cv2.imencode(".jpg", frame)[1]
        #     self.post_frames_con.post_frames_lock.acquire()
        #     self.post_frames_con.add_stream_frame(buffer)
        #     self.post_frames_con.post_frames_lock.release()
        #     if self.post_frames_con.check_out_of_time():
        #         self.post_frames_con.clear_steam()
        # Show Frame.
        # frame = cv2.resize(frame, (0, 0), fx=2., fy=2.)

        # 手势识别
        event_gesture = Event(Event.pending)
        gesture_frame, gesture_label = self.gesture_handler.detect_frame(frame, [])
        frame_with_gesture = cv2.add(frame, gesture_frame)
        if gesture_label != 'unk':
            self.gesture_handler.next_frame(gesture_label)
        handle_res = self.gesture_handler.gesture_handle()
        if handle_res['reliable']:
            self.event_saver.addEvent(get_gesture_by_name(handle_res['label']), self.gesture_buffer.get_frames())
            # self.voice_handler.set_recording(True)
        else:
            pass
            # self.voice_handler.set_recording(False)
        self.gesture_buffer.add_frame(frame_with_gesture)
        # 补充事件结束后的一些帧进事件回放
        self.event_saver.pushMoreFrame(event_gesture, frame_with_gesture, 'gesture')

        # 语音识别
        event_voice = Event(Event.pending)
        if self.frame_count % 100 == 0:
            voices = self.cam.getVoices()
            if self.voice_handler.test_voice(voices):
                # 显示3s
                self.show_voice_time = time.time() + len(voices) * 30
                self.voice_handler.detect_voice_new(voices, self.detect_voice_callback)

        if self.show_voice_time > time.time():
            frame = cv2.putText(frame, 'voice recording',
                                (120, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
        # 补充事件结束后的一些帧进事件回放
        self.event_saver.pushMoreFrame(event_voice, frame, 'voice')


        fps_t = (time.time() - self.fps_time)
        # frame = cv2.putText(frame, '%d, FPS: %f' % (f, 1.0 / fps_t if fps_t != 0 else 1),
        #                     (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
        # frame = frame[:, :, ::-1]
        frame = cv2.putText(frame, str(datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                            (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)

        frame = cv2.add(action_frame, frame)
        frame = cv2.add(item_frame, frame)
        # frame = cv2.add(gesture_frame, frame)
        # 是否直播推流
        if self.cam.stream_live.stream_opened and self.cam.stream_live.check_out_of_time():
            self.cam.stream_live.write_frame(frame)
        self.fps_time = time.time()
        self.frame_count += 1
        return {"event_action": event_action,
                "frame": frame,
                "origin_frame": origin_frame,
                "fps": 1.0 / fps_t if fps_t > 0 else 0}
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
        # image = self.models.resize_fn(image)
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

    def filter_close_bboxes(self, detections, threshold_distance=40):
        def bbox_center(bbox):
            x, y, w, h = bbox
            return x + w / 2, y + h / 2

        filtered_detections = []
        for detection in detections:
            bbox = detection.tlbr
            bbox_center_x, bbox_center_y = bbox_center(bbox)

            is_close = False
            for filtered_detection in filtered_detections:
                filtered_bbox = filtered_detection.tlbr
                filtered_bbox_center_x, filtered_bbox_center_y = bbox_center(filtered_bbox)

                center_distance = np.sqrt(
                    (bbox_center_x - filtered_bbox_center_x) ** 2 + (bbox_center_y - filtered_bbox_center_y) ** 2)

                if center_distance < threshold_distance:
                    is_close = True
                    break

            if not is_close:
                filtered_detections.append(detection)

        return filtered_detections

    def detect_voice_callback(self, voice_file_name, label, voices):
        if len(self.voice_buffer) > 0 :
            self.event_saver.addEvent(Event.voice, self.voice_buffer.get_frames(), label)
            print(f"{voice_file_name} 检测到语音{label}！！！")
