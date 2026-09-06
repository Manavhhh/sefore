"""
Heuristic Confidence Score Module.
Calculates a transparent, multi-factor confidence rating (0.0 - 1.0)
for candidate oil spill detections.
NOTE: This is explicitly a heuristic confidence score, NOT a calibrated probability.
"""

from typing import Dict, Any
import numpy as np
from .segmentation import SpillCandidate

class ConfidenceScorer:
    """
    Transparent Heuristic Confidence Evaluator.
    
    Formula:
      Heuristic Confidence = w_contrast * S_contrast
                           + w_size * S_size
                           + w_shape * S_shape
                           + w_border * S_border

    Where:
      1. S_contrast: Evaluates how much darker the spill is relative to local sea (0.0 to 1.0).
         S_contrast = clip(contrast_ratio * 2.5, 0.0, 1.0)
      2. S_size: Gaussian-like response peaking around realistic spill sizes (500 to 50,000 pixels).
         Penalizes both tiny speckles (< 100 px) and massive calm-sea ocean basins (> 200,000 px).
      3. S_shape: Slicks under wind/currents are elongated rather than circular.
         Moderate compactness (0.05 to 0.6) scores highest; perfect circles or chaotic noise score lower.
      4. S_border: Penalizes candidates located immediately against image edges where radar distortions occur.
    """

    def __init__(
        self,
        w_contrast: float = 0.40,
        w_size: float = 0.25,
        w_shape: float = 0.20,
        w_border: float = 0.15,
    ):
        self.w_contrast = w_contrast
        self.w_size = w_size
        self.w_shape = w_shape
        self.w_border = w_border

    def calculate_score(
        self,
        candidate: SpillCandidate,
        image_shape: tuple,
    ) -> float:
        """
        Calculates heuristic confidence score for a given candidate.
        """
        h, w = image_shape[:2]

        # 1. Contrast factor
        if candidate.contrast_ratio is not None:
            # Positive contrast_ratio means spill is darker than surroundings
            s_contrast = float(np.clip(candidate.contrast_ratio * 3.0, 0.1, 1.0))
        else:
            s_contrast = 0.5  # Neutral default

        # 2. Size factor
        area = candidate.pixel_area
        if area < 100:
            s_size = float(area / 100.0) * 0.5
        elif 100 <= area <= 50_000:
            s_size = 1.0
        elif 50_000 < area <= 200_000:
            # Gradually decay for very large low-wind look-alikes
            s_size = float(1.0 - (area - 50_000) / 150_000 * 0.5)
        else:
            s_size = 0.4

        # 3. Shape factor (compactness = 4*pi*area / perimeter^2)
        comp = candidate.compactness
        if 0.05 <= comp <= 0.65:
            s_shape = 1.0
        elif comp > 0.65:
            # Very round/circular (rare for natural slicks at sea)
            s_shape = 0.7
        else:
            # Very thin/fractured filaments
            s_shape = 0.6

        # 4. Border proximity factor
        x, y, cw, ch = candidate.bbox
        dist_left = x
        dist_top = y
        dist_right = w - (x + cw)
        dist_bottom = h - (y + ch)
        min_border_dist = min(dist_left, dist_top, dist_right, dist_bottom)

        if min_border_dist < 20:
            s_border = 0.4
        elif min_border_dist < 50:
            s_border = 0.7
        else:
            s_border = 1.0

        # Weighted combination
        raw_score = (
            self.w_contrast * s_contrast
            + self.w_size * s_size
            + self.w_shape * s_shape
            + self.w_border * s_border
        )

        final_score = float(np.clip(raw_score, 0.05, 0.98))
        return final_score
