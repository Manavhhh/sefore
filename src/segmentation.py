"""
Region and Contour Analysis Module.
Extracts connected components, polygon contours, morphological properties,
and geometric features for each candidate oil spill region.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import cv2

@dataclass
class SpillCandidate:
    id: int
    pixel_area: int
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    perimeter: float
    centroid: Tuple[float, float]  # (cx, cy)
    width: int
    height: int
    aspect_ratio: float
    compactness: float
    contour: np.ndarray  # (N, 1, 2)
    mean_intensity: Optional[float] = None
    contrast_ratio: Optional[float] = None

class ContourSegmenter:
    """
    Analyzes binary segmentation masks to extract distinct spill candidates and geometric features.
    """

    def __init__(self, min_contour_points: int = 4):
        self.min_contour_points = min_contour_points

    def extract_candidates(
        self,
        binary_mask: np.ndarray,
        normalized_image: Optional[np.ndarray] = None,
    ) -> List[SpillCandidate]:
        """
        Extracts all candidate spill regions from the binary mask.
        Supports multiple candidate regions and calculates comprehensive shape metrics.
        """
        mask_u8 = (binary_mask > 0).astype(np.uint8) * 255

        # Find external contours
        contours, hierarchy = cv2.findContours(
            mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        candidates: List[SpillCandidate] = []
        for idx, cnt in enumerate(contours):
            if len(cnt) < self.min_contour_points:
                continue

            area = cv2.contourArea(cnt)
            if area <= 0:
                continue

            perimeter = cv2.arcLength(cnt, closed=True)
            if perimeter <= 0:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w) / float(h) if h > 0 else 1.0

            # Compactness / Circularity: 4 * pi * Area / Perimeter^2 (1.0 for perfect circle)
            compactness = float(4.0 * np.pi * area / (perimeter**2))

            # Centroid calculation via moments
            moments = cv2.moments(cnt)
            if moments["m00"] != 0:
                cx = float(moments["m10"] / moments["m00"])
                cy = float(moments["m01"] / moments["m00"])
            else:
                cx = float(x + w / 2.0)
                cy = float(y + h / 2.0)

            # Intensity metrics if image is provided
            mean_intensity = None
            contrast_ratio = None
            if normalized_image is not None:
                # Create mask for this single contour
                c_mask = np.zeros_like(mask_u8)
                cv2.drawContours(c_mask, [cnt], -1, 255, -1)
                spill_pixels = normalized_image[c_mask == 255]
                if len(spill_pixels) > 0:
                    mean_intensity = float(np.mean(spill_pixels))

                    # Local surrounding sea window for contrast calculation
                    pad = 30
                    y1 = max(0, y - pad)
                    y2 = min(normalized_image.shape[0], y + h + pad)
                    x1 = max(0, x - pad)
                    x2 = min(normalized_image.shape[1], x + w + pad)
                    local_crop = normalized_image[y1:y2, x1:x2]
                    local_mask = c_mask[y1:y2, x1:x2]
                    surrounding = local_crop[local_mask == 0]
                    if len(surrounding) > 0:
                        surr_mean = float(np.mean(surrounding))
                        contrast_ratio = float((surr_mean - mean_intensity) / (surr_mean + 1e-5))

            candidate = SpillCandidate(
                id=idx + 1,
                pixel_area=int(area),
                bbox=(x, y, w, h),
                perimeter=float(perimeter),
                centroid=(cx, cy),
                width=w,
                height=h,
                aspect_ratio=aspect_ratio,
                compactness=compactness,
                contour=cnt,
                mean_intensity=mean_intensity,
                contrast_ratio=contrast_ratio,
            )
            candidates.append(candidate)

        # Rank candidates by area descending
        candidates.sort(key=lambda c: c.pixel_area, reverse=True)
        # Re-index ids
        for i, c in enumerate(candidates):
            c.id = i + 1

        return candidates
