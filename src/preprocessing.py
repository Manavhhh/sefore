"""
SAR Preprocessing Module for Sentinel-1 Imagery.
Performs calibration/dB scaling, speckle noise reduction, nodata masking, and contrast normalization.
"""

from typing import Tuple
import numpy as np
import cv2
from scipy.ndimage import uniform_filter

class SARPreprocessor:
    """
    Applies radiometric scaling, speckle filtering, and normalization to Sentinel-1 SAR backscatter.
    """

    def __init__(self, filter_size: int = 5, use_db: bool = True):
        self.filter_size = filter_size
        self.use_db = use_db

    def to_decibels(self, linear_data: np.ndarray, eps: float = 1e-6) -> np.ndarray:
        """
        Converts linear radar intensity to decibels (dB):
        sigma0_dB = 10 * log10(intensity + eps)
        """
        clamped = np.maximum(linear_data, eps)
        return 10.0 * np.log10(clamped)

    def lee_filter(self, img: np.ndarray, size: int = 5) -> np.ndarray:
        """
        Lee speckle filter implementation based on local window statistics.
        Smoothes speckle noise while preserving sharp slick boundaries.
        """
        mean = uniform_filter(img, size=size)
        sqr_mean = uniform_filter(img**2, size=size)
        variance = np.maximum(sqr_mean - mean**2, 0.0)

        overall_variance = np.var(img)
        if overall_variance == 0:
            return img

        weights = variance / (variance + overall_variance + 1e-7)
        filtered = mean + weights * (img - mean)
        return filtered

    def preprocess(
        self,
        vv_band: np.ndarray,
        vh_band: np.ndarray = None,
        nodata: float = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Executes complete preprocessing pipeline:
        1. Identifies and masks invalid/nodata pixels.
        2. Converts to dB if linear intensity is present.
        3. Applies speckle filtering.
        4. Normalizes to [0, 255] uint8 for visualization and CV operations.

        Returns:
            normalized_u8: (H, W) uint8 normalized image
            denoised_float: (H, W) float32 denoised dB backscatter
            valid_mask: (H, W) bool array where True indicates valid ocean data
        """
        raw_vv = vv_band.copy()

        # 1. Invalid pixel detection (nodata, NaNs, infs, or extreme out-of-range backscatter)
        valid_mask = np.isfinite(raw_vv) & (raw_vv > -90.0) & (raw_vv < 50.0)
        if nodata is not None:
            valid_mask = valid_mask & (raw_vv != nodata)

        if not np.any(valid_mask):
            raise ValueError("SAR image contains no valid pixels!")

        # 2. Convert to decibel scale if values appear linear (all non-negative)
        # If minimum valid value is >= 0, it is linear amplitude/intensity.
        # If values are negative (e.g. -35 dB to -10 dB), it is already calibrated in dB.
        if np.nanmin(raw_vv[valid_mask]) >= 0:
            sar_db = self.to_decibels(raw_vv)
        else:
            sar_db = raw_vv.copy()

        # Fill invalid pixels with median ocean value for smooth filtering
        ocean_median = float(np.median(sar_db[valid_mask]))
        sar_db[~valid_mask] = ocean_median

        # 3. Speckle Noise Reduction (Fast Lee Filter or Bilateral/Gaussian)
        denoised = self.lee_filter(sar_db, size=self.filter_size)
        # Apply gentle bilateral filter to preserve edges
        denoised_f32 = denoised.astype(np.float32)

        # 4. Percentile contrast stretching (2nd to 98th percentile of valid pixels)
        valid_denoised = denoised_f32[valid_mask]
        p_low, p_high = np.percentile(valid_denoised, (2.0, 98.0))
        if p_high - p_low < 1e-5:
            p_high = p_low + 1.0

        stretched = np.clip((denoised_f32 - p_low) / (p_high - p_low), 0.0, 1.0)
        normalized_u8 = (stretched * 255.0).astype(np.uint8)

        # Re-apply invalid mask
        normalized_u8[~valid_mask] = 0

        return normalized_u8, denoised_f32, valid_mask
