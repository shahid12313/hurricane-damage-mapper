"""PyTorch dataset over the processed xBD files written by src/preprocess.py."""

from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

# OpenCV's own thread pool can deadlock inside DataLoader worker processes
cv2.setNumThreads(0)

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def read_rgb(path):
    return cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB)


def to_tensor(rgb):
    """uint8 (H, W, 3) -> normalized float tensor (3, H, W), as the pretrained encoder expects."""
    x = (rgb.astype(np.float32) / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
    return torch.from_numpy(x.transpose(2, 0, 1).copy())


class BuildingDataset(Dataset):
    """Pre-disaster image -> building / background mask, for the localization model.

    split_dirs: one or more folders like data/processed/tier1
    crop:       random square crop size for training; None returns the full 1024x1024 tile
    augment:    random flips and 90-degree rotations
    """

    def __init__(self, split_dirs, crop=512, augment=True, max_tiles=None):
        self.mask_paths = []
        for d in split_dirs:
            self.mask_paths += sorted(Path(d, "masks").glob("*.png"))
        if max_tiles:
            self.mask_paths = self.mask_paths[:max_tiles]
        self.crop = crop
        self.augment = augment

    def __len__(self):
        return len(self.mask_paths)

    def image_path(self, i):
        mask_path = self.mask_paths[i]
        return mask_path.parent.parent / "images" / f"{mask_path.stem}_pre.jpg"

    def __getitem__(self, i):
        image = read_rgb(self.image_path(i))
        mask = (cv2.imread(str(self.mask_paths[i]), cv2.IMREAD_GRAYSCALE) > 0).astype(np.float32)

        if self.crop:
            h, w = mask.shape
            y = np.random.randint(0, h - self.crop + 1)
            x = np.random.randint(0, w - self.crop + 1)
            image = image[y:y + self.crop, x:x + self.crop]
            mask = mask[y:y + self.crop, x:x + self.crop]

        if self.augment:
            if np.random.rand() < 0.5:
                image, mask = image[:, ::-1], mask[:, ::-1]
            if np.random.rand() < 0.5:
                image, mask = image[::-1], mask[::-1]
            k = np.random.randint(4)
            image, mask = np.rot90(image, k), np.rot90(mask, k)

        return to_tensor(image), torch.from_numpy(mask.copy())[None]
