"""
Evaluation Suite for Sentinel-1 ClassicalDetector against Real Zenodo Ground Truth.
Smart India Hackathon 2026 - PS ID: SIH26143

Computes actual semantic segmentation metrics:
- Intersection over Union (IoU / Jaccard Index)
- Dice Coefficient (F1-score)
- Precision (Positive Predictive Value)
- Recall (Sensitivity / True Positive Rate)

Zero fabricated numbers: all calculations are executed directly on the
predicted binary masks vs Zenodo ground-truth raster masks.
"""

import os
import glob
import json
import argparse
from typing import Dict, Any, List
import numpy as np
import rasterio
import cv2

from src.pipeline import OilSpillPipeline
from src.detector import ClassicalDetector
from src.evaluation import SegmentationEvaluator

def run_evaluation(
    images_dir: str = "data/zenodo_validation/images",
    masks_dir: str = "data/zenodo_validation/masks",
    output_dir: str = "output/eval_results",
    json_output_path: str = "output/evaluation_results.json",
) -> Dict[str, Any]:
    print("==================================================================")
    print("  SIH 2026: Sentinel-1 ClassicalDetector Benchmark Evaluation     ")
    print("==================================================================")
    print(f"Target Images: {images_dir}")
    print(f"Target Masks : {masks_dir}")
    print(f"Output Dir   : {output_dir}\n")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(json_output_path), exist_ok=True)

    if not os.path.exists(images_dir) or not os.path.exists(masks_dir):
        raise FileNotFoundError(f"Missing image or mask directory: {images_dir}, {masks_dir}")

    image_files = sorted(glob.glob(os.path.join(images_dir, "*.tif")))
    if not image_files:
        print(f"No GeoTIFF images found in {images_dir}")
        return {}

    detector = ClassicalDetector(
        adaptive_block_size=101,
        adaptive_c=25.0,
        max_intensity_threshold=35,
        min_area_pixels=250,
        max_area_fraction=0.35,
        morph_kernel_size=5,
        border_margin=15,
    )
    pipeline = OilSpillPipeline(detector=detector)

    total_candidates = len(image_files)
    successful_evaluations: List[Dict[str, Any]] = []
    failed_samples: List[Dict[str, str]] = []

    print(f"Evaluating {total_candidates} real Zenodo Sentinel-1 SAR samples against Ground Truth...\n")
    header_fmt = "{:<10} | {:<8} | {:<8} | {:<10} | {:<8} | {:<9} | {:<9} | {:<8} | {:<8}"
    print(header_fmt.format("Sample ID", "IoU", "Dice", "Precision", "Recall", "Pred Px", "GT Px", "TP Px", "H.Conf"))
    print("-" * 92)

    for img_path in image_files:
        base_name = os.path.basename(img_path)
        sample_id = os.path.splitext(base_name)[0]
        mask_path = os.path.join(masks_dir, base_name)

        if not os.path.exists(mask_path):
            failed_samples.append({"sample_id": sample_id, "reason": "Ground truth mask file missing on disk"})
            continue

        sample_out_dir = os.path.join(output_dir, sample_id)
        os.makedirs(sample_out_dir, exist_ok=True)

        try:
            # 1. Run pipeline to get prediction
            res = pipeline.process_image(input_path=img_path, output_dir=sample_out_dir)

            # 2. Read predicted binary mask
            with rasterio.open(res["mask_path"]) as pred_src:
                pred_mask = pred_src.read(1) > 0

            # 3. Read real Zenodo ground-truth mask
            with rasterio.open(mask_path) as gt_src:
                gt_mask = gt_src.read(1) > 0

            # 4. Verify shape compatibility
            if pred_mask.shape != gt_mask.shape:
                raise ValueError(f"Shape mismatch: Pred {pred_mask.shape} != GT {gt_mask.shape}")

            # 5. Compute rigorous segmentation metrics
            metrics = SegmentationEvaluator.evaluate(pred_mask=pred_mask, gt_mask=gt_mask)

            # 6. Generate Comparison Visual:
            # - Green = True Positive (detected correctly)
            # - Red = False Positive (detected by Classical CV, not in GT)
            # - Blue = False Negative (in GT, missed by Classical CV)
            comp_rgb = np.zeros((pred_mask.shape[0], pred_mask.shape[1], 3), dtype=np.uint8)
            tp_idx = np.logical_and(pred_mask, gt_mask)
            fp_idx = np.logical_and(pred_mask, ~gt_mask)
            fn_idx = np.logical_and(~pred_mask, gt_mask)

            comp_rgb[tp_idx] = [0, 230, 80]    # Green = TP
            comp_rgb[fp_idx] = [230, 40, 40]    # Red = FP
            comp_rgb[fn_idx] = [40, 120, 240]   # Blue = FN

            comparison_path = os.path.join(sample_out_dir, "gt_vs_pred_comparison.png")
            cv2.imwrite(comparison_path, cv2.cvtColor(comp_rgb, cv2.COLOR_RGB2BGR))

            # Also save ground-truth visualization
            gt_u8 = (gt_mask.astype(np.uint8)) * 255
            gt_path = os.path.join(sample_out_dir, "ground_truth.png")
            cv2.imwrite(gt_path, gt_u8)

            record = {
                "sample_id": sample_id,
                "image_file": base_name,
                "mask_file": base_name,
                "metrics": {
                    "iou": metrics["iou"],
                    "dice": metrics["dice"],
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                },
                "pixels": {
                    "true_positive": metrics["tp_pixels"],
                    "predicted": metrics["pred_pixels"],
                    "ground_truth": metrics["gt_pixels"],
                },
                "detection_summary": {
                    "detected_regions_count": res["detected_regions_count"],
                    "highest_heuristic_confidence": res["highest_confidence"],
                    "total_estimated_area_km2": res["total_estimated_area_km2"],
                    "total_estimated_area_m2": res["total_estimated_area_m2"],
                },
                "artifacts": {
                    "pred_mask": res["mask_path"].replace("\\", "/"),
                    "overlay": res["overlay_path"].replace("\\", "/"),
                    "ground_truth": gt_path.replace("\\", "/"),
                    "comparison": comparison_path.replace("\\", "/"),
                    "geojson": res["geojson_path"].replace("\\", "/"),
                }
            }
            successful_evaluations.append(record)

            print(
                f"{sample_id:<10} | "
                f"{metrics['iou']:<8.4f} | "
                f"{metrics['dice']:<8.4f} | "
                f"{metrics['precision']:<10.4f} | "
                f"{metrics['recall']:<8.4f} | "
                f"{metrics['pred_pixels']:<9} | "
                f"{metrics['gt_pixels']:<9} | "
                f"{metrics['tp_pixels']:<8} | "
                f"{res['highest_confidence']:<8.4f}"
            )

        except Exception as e:
            failed_samples.append({"sample_id": sample_id, "reason": str(e)})
            print(f"{sample_id:<10} | FAILED: {str(e)[:50]}")

    print("-" * 92)

    # Compute Macro Aggregate Metrics
    if not successful_evaluations:
        print("Evaluation aborted: No samples evaluated successfully.")
        return {}

    ious = [r["metrics"]["iou"] for r in successful_evaluations]
    dices = [r["metrics"]["dice"] for r in successful_evaluations]
    precisions = [r["metrics"]["precision"] for r in successful_evaluations]
    recalls = [r["metrics"]["recall"] for r in successful_evaluations]

    aggregate = {
        "mean_iou": round(float(np.mean(ious)), 4),
        "mean_dice": round(float(np.mean(dices)), 4),
        "mean_precision": round(float(np.mean(precisions)), 4),
        "mean_recall": round(float(np.mean(recalls)), 4),
        "median_iou": round(float(np.median(ious)), 4),
        "median_dice": round(float(np.median(dices)), 4),
        "median_precision": round(float(np.median(precisions)), 4),
        "median_recall": round(float(np.median(recalls)), 4),
        "min_iou": round(float(np.min(ious)), 4),
        "max_iou": round(float(np.max(ious)), 4),
    }

    print(
        f"{'MACRO MEAN':<10} | "
        f"{aggregate['mean_iou']:<8.4f} | "
        f"{aggregate['mean_dice']:<8.4f} | "
        f"{aggregate['mean_precision']:<10.4f} | "
        f"{aggregate['mean_recall']:<8.4f} |"
    )
    print(
        f"{'MEDIAN':<10} | "
        f"{aggregate['median_iou']:<8.4f} | "
        f"{aggregate['median_dice']:<8.4f} | "
        f"{aggregate['median_precision']:<10.4f} | "
        f"{aggregate['median_recall']:<8.4f} |"
    )
    print("=" * 92)

    print(f"\nEvaluated Samples  : {len(successful_evaluations)}/{total_candidates} successfully processed")
    if failed_samples:
        print(f"Failed Samples     : {len(failed_samples)}")
        for fs in failed_samples:
            print(f"  - {fs['sample_id']}: {fs['reason']}")

    report_payload = {
        "benchmark_metadata": {
            "dataset": "Zenodo Sentinel-1 SAR Oil Spill Dataset (Record 8346860)",
            "detector": "ClassicalDetector (Baseline Computer Vision)",
            "hyperparameters": detector.get_hyperparameters(),
            "total_available_samples": total_candidates,
            "successfully_evaluated_samples": len(successful_evaluations),
            "failed_samples_count": len(failed_samples),
            "failed_samples": failed_samples,
        },
        "aggregate_metrics": aggregate,
        "per_sample_evaluations": successful_evaluations,
    }

    with open(json_output_path, "w", encoding="utf-8") as jf:
        json.dump(report_payload, jf, indent=2)

    print(f"Complete benchmark results saved to: {json_output_path}\n")
    return report_payload

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate ClassicalDetector on Zenodo validation dataset")
    parser.add_argument("--images", default="data/zenodo_validation/images")
    parser.add_argument("--masks", default="data/zenodo_validation/masks")
    parser.add_argument("--output", default="output/eval_results")
    parser.add_argument("--json", default="output/evaluation_results.json")
    args = parser.parse_args()

    run_evaluation(
        images_dir=args.images,
        masks_dir=args.masks,
        output_dir=args.output,
        json_output_path=args.json,
    )
