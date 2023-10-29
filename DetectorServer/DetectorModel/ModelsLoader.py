import argparse

from DetectorModel.ActionsEstLoader import TSSTG
from Detection.Utils import ResizePadding
from DetectorLoader import TinyYOLOv3_onecls
from PoseEstimateLoader import SPPE_FastPose
from PysotModel import PysotModel
from Track.Tracker import Tracker
from pPose_nms import PoseNMS


class ModelsLoader:

    def __init__(self):
        # todo 准备去除
        par = argparse.ArgumentParser(description='Human Fall Detection Demo.')
        par.add_argument('-C', '--camera', default="0",  # required=True,  # default=2,
                         help='Source of camera or video file path.')
        par.add_argument('--detection_input_size', type=int, default=384,
                         help='Size of input in detection model in square must be divisible by 32 (int).')
        par.add_argument('--pose_input_size', type=str, default='224x160',
                         help='Size of input in pose model must be divisible by 32 (h, w)')
        par.add_argument('--pose_backbone', type=str, default='resnet50',
                         help='Backbone model for SPPE FastPose model.')
        par.add_argument('--show_detected', default=False, action='store_true',
                         help='Show all bounding box from detection.')
        par.add_argument('--show_skeleton', default=True, action='store_true',
                         help='Show skeleton pose.')
        par.add_argument('--save_out', type=str, default='',
                         help='Save display to video file.')
        par.add_argument('--device', type=str, default='cuda',
                         help='Device to run model on cpu or cuda.')
        self.args = par.parse_args()

        device = self.args.device

        # DETECTION MODEL.
        self.input_size_dets = self.args.detection_input_size
        self.detect_model = TinyYOLOv3_onecls(self.input_size_dets, device=device, conf_thres=0.8)

        # POSE MODEL.
        inp_pose = self.args.pose_input_size.split('x')
        inp_pose = (int(inp_pose[0]), int(inp_pose[1]))
        self.pose_model = SPPE_FastPose(self.args.pose_backbone, inp_pose[0], inp_pose[1], device=device)
        self.savedPoseNums = {}

        # Tracker.
        self.max_age = 30
        self.trackers = {}

        # Actions Estimate.
        self.action_model = TSSTG()

        self.resize_fn = ResizePadding(self.input_size_dets, self.input_size_dets)

        # ItemTracker
        self.pysot_models = {}

    def addPoseNums(self, cam_source):
        self.savedPoseNums[cam_source] = PoseNMS()

    def getPoseNums(self, cam_source):
        return self.savedPoseNums[cam_source]

    def addTracker(self, cam_source):
        self.trackers[cam_source] = Tracker(max_age=self.max_age, n_init=3)

    def getTracker(self, cam_source):
        return self.trackers[cam_source]

    def addPysotModel(self, cam_source):
        self.pysot_models[cam_source] = PysotModel()

    def getPysotModel(self, cam_source):
        return self.pysot_models[cam_source]