"""
Classical Computer Vision Oil Spill Detector.
Implements adaptive thresholding, morphological filtering, and look-alike suppression.
"""

from typing import Dict, Any, Optional
import numpy as np
import cv2
from .detector_base import BaseDetector

class ClassicalDetector(BaseDetector):
    """
    Classical multi-stage computer vision detector for suspected oil spills in SAR imagery.
    Combines adaptive local thresholding, intensity clamping, morphological reconstruction,
    and look-alike suppression.
    """

    def __init__(
        self,
        adaptive_block_size: int = 101,
        adaptive_c: float = 25.0,
        max_intensity_threshold: int = 35,
        min_area_pixels: int = 250,
        max_area_fraction: float = 0.35,
        morph_kernel_size: int = 5,
        border_margin: int = 15,
    ):
        """
        Args:
            adaptive_block_size: Size of pixel neighborhood for local background calculation (must be odd).
            adaptive_c: Constant subtracted from the mean; higher values demand stronger dark contrast.
            max_intensity_threshold: Maximum brightness allowed for a pixel to be an oil candidate.
            min_area_pixels: Minimum pixel area to filter out high-frequency radar speckle dips.
            max_area_fraction: Maximum image fraction allowed to prevent classifying entire low-wind sea basins.
            morph_kernel_size: Kernel size for morphological opening and closing.
            border_margin: Distance from image borders to exclude edge/sensor boundary artifacts.
        """
        if adaptive_block_size % 2 == 0:
            adaptive_block_size += 1

        self.adaptive_block_size = adaptive_block_size
        self.adaptive_c = adaptive_c
        self.max_intensity_threshold = max_intensity_threshold
        self.min_area_pixels = min_area_pixels
        self.max_area_fraction = max_area_fraction
        self.morph_kernel_size = morph_kernel_size
        self.border_margin = border_margin

    def get_hyperparameters(self) -> Dict[str, Any]:
        return {
            "adaptive_block_size": self.adaptive_block_size,
            "adaptive_c": self.adaptive_c,
            "max_intensity_threshold": self.max_intensity_threshold,
            "min_area_pixels": self.min_area_pixels,
            "max_area_fraction": self.max_area_fraction,
            "morph_kernel_size": self.morph_kernel_size,
            "border_margin": self.border_margin,
        }

    def detect(
        self,
        normalized_image: np.ndarray,
        raw_db: Optional[np.ndarray] = None,
        valid_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Detects suspected oil spills and returns a binary mask (0 = background, 1 = suspected spill).
        """
        h, w = normalized_image.shape[:2]
        total_pixels = h * w

        if valid_mask is None:
            valid_mask = np.ones((h, w), dtype=bool)

        # 1. Local Adaptive Thresholding (Detecting local backscatter depression)
        # Slicks are significantly darker than the surrounding sea surface
        blurred = cv2.GaussianBlur(normalized_image, (5, 5), 0)
        local_mean = cv2.boxFilter(
            blurred,
            ddepth=-1,
            ksize=(self.adaptive_block_size, self.adaptive_block_size),
            borderType=cv2.BORDER_REFLECT,
        )

        # Candidate pixels: significantly darker than local background AND below global upper threshold
        contrast_drop = local_mean.astype(np.float32) - blurred.astype(np.float32)
        candidate_mask = (
            (contrast_drop > self.adaptive_c)
            & (blurred < self.max_intensity_threshold)
            & valid_mask
        )

        candidate_u8 = (candidate_mask.astype(np.uint8)) * 255

        # 2. Morphological Operations
        # Opening: removes isolated single-pixel speckle noise
        # Closing: connects fragmented slick filaments and fills small holes
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.morph_kernel_size, self.morph_kernel_size),
        )
        opened = cv2.morphologyEx(candidate_u8, cv2.MORPH_OPEN, kernel)
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

        # 3. Look-Alike & Size-Based Suppression via Connected Components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            closed, connectivity=8
        )

        final_mask = np.zeros((h, w), dtype=np.uint8)
        max_allowed_pixels = int(total_pixels * self.max_area_fraction)

        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            left = stats[i, cv2.CC_STAT_LEFT]
            top = stats[i, cv2.CC_STAT_TOP]
            width = stats[i, cv2.CC_STAT_WIDTH]
            height = stats[i, cv2.CC_STAT_HEIGHT]

            # Filter tiny speckle noise
            if area < self.min_area_pixels:
                continue

            # Filter massive low-wind ocean zones (covering huge portions of scene)
            if area > max_allowed_pixels:
                continue

            # Suppress border-clipped sensor artifacts
            if (
                left < self.border_margin
                or top < self.border_margin
                or (left + width) > (w - self.border_margin)
                or (top + height) > (h - self.border_margin)
            ):
                # If a small region touches the edge, it's often a clipping artifact
                if area < self.min_area_pixels * 3:
                    continue

            # Add valid candidate to final mask
            final_mask[labels == i] = 1

        return final_mask
