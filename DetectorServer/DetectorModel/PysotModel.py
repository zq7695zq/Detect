import cv2
import numpy as np
import torch

from Pysot.models.model_builder import ModelBuilder
from Pysot.core.config import cfg


class PysotModel:
    def __init__(self,
                 weight_file='./DetectorModel/Models/pysot/siamrpn_r50_l234_dwxcorr/model.pth',
                 config_file='./DetectorModel/Models/pysot/siamrpn_r50_l234_dwxcorr/config.yaml',
                 device='cuda'):
        cfg.merge_from_file(config_file)
        # create model
        self.model = ModelBuilder()
        # load model
        self.model.load_state_dict(torch.load(weight_file,
                                              map_location=lambda storage, loc: storage.cpu()))
        self.model.eval().to(device)


