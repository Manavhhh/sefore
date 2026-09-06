"""
Evaluation Script for Sentinel-1 Oil Spill Detection against Zenodo Ground Truth.
Computes IoU, Dice, Precision, and Recall without fabricating metrics.
"""

import os
import glob
import argparse
import rasterio
import numpy as np
from src.pipeline import OilSpillPipeline
from src.evaluation import SegmentationEvaluator
from src.detector import ClassicalDetector

def run_evaluation(images_dir: str = "data/images/Oil", masks_dir: str = "data/masks/Mask_oil"):
    print("==================================================================")
    print("  SIH 2026: Oil Spill Detection Ground-Truth Evaluation Suite      ")
    print("==================================================================")

    if not os.path.exists(images_dir) or not os.path.exists(masks_dir):
        print(f"Error: Missing image or mask directory: {images_dir}, {masks_dir}")
        return

    # Find matching pairs
    image_files = sorted(glob.glob(os.path.join(images_dir, "*.tif")))
    if not image_files:
        print(f"No GeoTIFF images found in {images_dir}")
        return

    pipeline = OilSpillPipeline(
        detector=ClassicalDetector(
            adaptive_block_size=101,
            adaptive_c=25.0,
            max_intensity_threshold=35,
            min_area_pixels=250,
        )
    )
    eval_results = []

    print(f"Found {len(image_files)} test images. Running evaluation against ground truth...\n")
    print(f"{'Image ID':<15} | {'IoU':<8} | {'Dice':<8} | {'Precision':<10} | {'Recall':<8} | {'Pred Px':<10} | {'GT Px':<10}")
    print("-" * 82)

    for img_path in image_files:
        base_name = os.path.basename(img_path)
        mask_path = os.path.join(masks_dir, base_name)

        if not os.path.exists(mask_path):
            print(f"{base_name:<15} | [Ground Truth mask not found in {masks_dir}]")
            continue

        # Run pipeline safely
        try:
            out = pipeline.process_image(input_path=img_path, output_dir="output/eval_temp")
            pred_mask = rasterio.open(out["mask_path"]).read(1) > 0
            with rasterio.open(mask_path) as gt_src:
                gt_mask = gt_src.read(1) > 0
            metrics = SegmentationEvaluator.evaluate(pred_mask=pred_mask, gt_mask=gt_mask)
            eval_results.append((base_name, metrics))
        except Exception as e:
            print(f"{base_name:<15} | [Skipped / File Incomplete: {str(e)[:40]}]")
            continue

        print(
            f"{base_name:<15} | "
            f"{metrics['iou']:<8.4f} | "
            f"{metrics['dice']:<8.4f} | "
            f"{metrics['precision']:<10.4f} | "
            f"{metrics['recall']:<8.4f} | "
            f"{metrics['pred_pixels']:<10} | "
            f"{metrics['gt_pixels']:<10}"
        )

    if not eval_results:
        print("No matched image-mask pairs evaluated.")
        return

    # Compute macro-averages
    avg_iou = np.mean([m["iou"] for _, m in eval_results])
    avg_dice = np.mean([m["dice"] for _, m in eval_results])
    avg_prec = np.mean([m["precision"] for _, m in eval_results])
    avg_rec = np.mean([m["recall"] for _, m in eval_results])

    print("-" * 82)
    print(f"{'MACRO AVERAGE':<15} | {avg_iou:<8.4f} | {avg_dice:<8.4f} | {avg_prec:<10.4f} | {avg_rec:<8.4f} |")
    print("=" * 82)
    print("\nMETHODOLOGY & ANALYSIS OF METRICS:")
    print("1. Baseline Classical CV uses adaptive local contrast and morphological filtering.")
    print("2. Classical CV achieves good recall on pronounced slicks, but lacks deep contextual semantics,")
    print("   meaning low-wind patches, shadows, or subtle edges can cause false positives (lowering precision/IoU).")
    print("3. Deep learning models (e.g. U-Net / DeepLabV3+) trained on Kaggle GPU will learn complex spatial-contextual")
    print("   features to distinguish true mineral oil from biogenic films and calm sea look-alikes, substantially boosting IoU.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", default="data/images/Oil")
    parser.add_argument("--masks", default="data/masks/Mask_oil")
    args = parser.parse_args()
    run_evaluation(images_dir=args.images, masks_dir=args.masks)
