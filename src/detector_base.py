"""
Detector Base Abstraction.
Defines the unified interface for both Classical Computer Vision and future U-Net Deep Learning detectors.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import numpy as np

class BaseDetector(ABC):
    """
    Abstract interface for oil spill detection algorithms.
    """

    @abstractmethod
    def detect(
        self,
        normalized_image: np.ndarray,
        raw_db: Optional[np.ndarray] = None,
        valid_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Executes oil spill detection on preprocessed imagery.

        Args:
            normalized_image: (H, W) uint8 preprocessed SAR backscatter image.
            raw_db: (H, W) float32 calibrated dB backscatter image.
            valid_mask: (H, W) boolean mask of valid ocean pixels.

        Returns:
            binary_mask: (H, W) uint8 binary mask where 1 = suspected oil spill, 0 = background.
        """
        pass

    @abstractmethod
    def get_hyperparameters(self) -> Dict[str, Any]:
        """
        Returns a dictionary of the detector's active configuration parameters.
        """
        pass
