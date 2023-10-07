import numpy as np
import torch

from Actionsrecognition.Models import TwoStreamSpatialTemporalGraph
from pose_utils import normalize_points_with_size, scale_pose


class TSSTG(object):
    """Two-Stream Spatial Temporal Graph Model Loader.
    Args:
        weight_file: (str) Path to trained weights file.
        device: (str) Device to load the model on 'cpu' or 'cuda'.
    """

    def __init__(self,
                 weight_file='./DetectorModel/Models/TSSTG/tsstg-model.pth',
                 device='cuda'):
        self.graph_args = {'strategy': 'spatial'}
        self.class_names = ['Standing', 'Walking', 'Sitting', 'Lying Down',
                            'Stand up', 'Sit down', 'Fall Down']
        self.num_class = len(self.class_names)
        self.device = device

        self.model = TwoStreamSpatialTemporalGraph(self.graph_args, self.num_class).to(self.device)
        self.model.load_state_dict(torch.load(weight_file))
        self.model.eval()

    def predict(self, pts, image_size):
        """Predict actions from single person skeleton points and score in time sequence.
        Args:
            pts: (numpy array) points and score in shape `(t, v, c)` where
                t : inputs sequence (time steps),
                v : number of graph node (body parts),
                c : channel (x, y, score).
            image_size: (tuple of int) width, height of image frame.
        Returns:
            (numpy array) Probability of each class actions.
        """

        # Normalize and scale points
        pts[:, :, :2] = normalize_points_with_size(pts[:, :, :2], image_size[0], image_size[1])
        pts[:, :, :2] = scale_pose(pts[:, :, :2])

        # Additional points calculation and concatenation
        additional_pts = (pts[:, 1, :] + pts[:, 2, :]) / 2
        pts = np.concatenate((pts, np.expand_dims(additional_pts, 1)), axis=1)

        # Convert numpy to torch tensor, permute dimensions, and move to the specified device
        pts = torch.tensor(pts, dtype=torch.float32, device=self.device).permute(2, 0, 1).unsqueeze(0)

        # Calculate motion tensor
        mot = pts[:, :2, 1:, :] - pts[:, :2, :-1, :]

        # Get model output
        out = self.model((pts, mot))

        return out.detach().cpu().numpy()

