"""
Evaluation Metrics Module.
Calculates IoU, Dice Coefficient, Precision, and Recall between predicted binary masks
and Zenodo ground-truth masks.
"""

from typing import Dict
import numpy as np

class SegmentationEvaluator:
    """
    Computes standard semantic segmentation benchmarks without fabricating data or metrics.
    """

    @staticmethod
    def evaluate(pred_mask: np.ndarray, gt_mask: np.ndarray) -> Dict[str, float]:
        """
        Calculates IoU, Dice, Precision, and Recall.

        Args:
            pred_mask: Binary numpy array (0 = bg, 1 = spill)
            gt_mask: Binary numpy array (0 = bg, 1 = spill)

        Returns:
            Dictionary containing iou, dice, precision, recall, and pixel counts.
        """
        p = (pred_mask > 0).astype(bool)
        g = (gt_mask > 0).astype(bool)

        intersection = np.logical_and(p, g).sum()
        union = np.logical_or(p, g).sum()
        pred_sum = p.sum()
        gt_sum = g.sum()

        # Intersection over Union (Jaccard Index)
        if union == 0:
            iou = 1.0 if pred_sum == 0 and gt_sum == 0 else 0.0
        else:
            iou = float(intersection / union)

        # Dice Coefficient (F1-score)
        if pred_sum + gt_sum == 0:
            dice = 1.0
        else:
            dice = float((2.0 * intersection) / (pred_sum + gt_sum))

        # Precision: TP / (TP + FP)
        if pred_sum == 0:
            precision = 1.0 if gt_sum == 0 else 0.0
        else:
            precision = float(intersection / pred_sum)

        # Recall: TP / (TP + FN)
        if gt_sum == 0:
            recall = 1.0 if pred_sum == 0 else 0.0
        else:
            recall = float(intersection / gt_sum)

        return {
            "iou": round(iou, 4),
            "dice": round(dice, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "tp_pixels": int(intersection),
            "pred_pixels": int(pred_sum),
            "gt_pixels": int(gt_sum),
        }
