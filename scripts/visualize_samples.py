"""
Visual Data Verification Utility for Sentinel-1 SAR & Ground-Truth Masks.
Generates multi-panel visual alignment figures (SAR VV, SAR VH, Ground Truth, and Overlay)
to verify spatial alignment between satellite imagery and annotated masks.
"""

import os
import glob
import rasterio
import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def normalize_sar_band(band: np.ndarray) -> np.ndarray:
    valid = np.isfinite(band)
    if not np.any(valid):
        return np.zeros_like(band, dtype=np.uint8)
    p_low, p_high = np.percentile(band[valid], (2.0, 98.0))
    if p_high - p_low < 1e-5:
        p_high = p_low + 1.0
    stretched = np.clip((band - p_low) / (p_high - p_low), 0.0, 1.0)
    stretched[~valid] = 0.0
    return (stretched * 255.0).astype(np.uint8)

def generate_visual_verifications(
    images_dir: str = "data/zenodo_validation/images",
    masks_dir: str = "data/zenodo_validation/masks",
    output_dir: str = "output/visual_verification",
    num_samples: int = 6,
):
    os.makedirs(output_dir, exist_ok=True)

    print("==================================================================")
    print("  PART 4: Visual Data Verification & Alignment Audit               ")
    print("==================================================================")

    img_paths = sorted(glob.glob(os.path.join(images_dir, "*.tif")))
    if not img_paths:
        print("No images found for visual verification.")
        return

    # Select samples (at least 6)
    selected_paths = img_paths[:max(6, min(len(img_paths), num_samples))]
    print(f"Generating visual alignment verification for {len(selected_paths)} samples...\n")

    for img_path in selected_paths:
        base_name = os.path.basename(img_path)
        sample_id = os.path.splitext(base_name)[0]
        mask_path = os.path.join(masks_dir, base_name)

        if not os.path.exists(mask_path):
            continue

        # Load SAR GeoTIFF
        with rasterio.open(img_path) as src_img:
            data = src_img.read()
            count = src_img.count

            if count >= 2:
                b0 = data[0].astype(np.float32)
                b1 = data[1].astype(np.float32)
                if float(np.nanmedian(b1)) > float(np.nanmedian(b0)):
                    vv_data, vh_data = b1, b0
                else:
                    vv_data, vh_data = b0, b1
            else:
                vv_data = data[0].astype(np.float32)
                vh_data = None

        # Load Ground Truth Mask
        with rasterio.open(mask_path) as src_mask:
            gt_mask = src_mask.read(1) > 0

        # Normalize bands for display
        vv_u8 = normalize_sar_band(vv_data)
        vh_u8 = normalize_sar_band(vh_data) if vh_data is not None else None

        # Create Overlay: Grayscale SAR VV with vibrant translucent green mask overlay
        overlay = cv2.cvtColor(vv_u8, cv2.COLOR_GRAY2RGB)
        green_layer = np.zeros_like(overlay)
        green_layer[:, :] = [0, 220, 50]  # Green in RGB

        mask_idx = gt_mask > 0
        overlay[mask_idx] = cv2.addWeighted(overlay[mask_idx], 0.55, green_layer[mask_idx], 0.45, 0)

        # Find contours of ground truth and outline in bright yellow
        mask_u8 = (gt_mask.astype(np.uint8)) * 255
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (255, 235, 0), 2)

        # Plot 4-panel figure
        fig, axes = plt.subplots(1, 4, figsize=(20, 5), dpi=150)

        axes[0].imshow(vv_u8, cmap="gray")
        axes[0].set_title(f"{sample_id}: Sentinel-1 SAR (VV)", fontsize=11, fontweight="bold")
        axes[0].axis("off")

        if vh_u8 is not None:
            axes[1].imshow(vh_u8, cmap="gray")
            axes[1].set_title(f"{sample_id}: Sentinel-1 SAR (VH)", fontsize=11, fontweight="bold")
        else:
            axes[1].imshow(vv_u8, cmap="gray")
            axes[1].set_title(f"{sample_id}: SAR (Single Band)", fontsize=11, fontweight="bold")
        axes[1].axis("off")

        axes[2].imshow(gt_mask, cmap="inferno")
        axes[2].set_title(f"{sample_id}: Ground-Truth Mask ({int(np.sum(gt_mask))} px)", fontsize=11, fontweight="bold")
        axes[2].axis("off")

        axes[3].imshow(overlay)
        axes[3].set_title(f"{sample_id}: SAR + GT Mask Overlay", fontsize=11, fontweight="bold")
        axes[3].axis("off")

        plt.suptitle(f"Sample {sample_id} - Real Zenodo Sentinel-1 SAR Spatial Alignment Audit", fontsize=13, fontweight="bold")
        plt.tight_layout()

        out_fig_path = os.path.join(output_dir, f"{sample_id}_alignment.png")
        plt.savefig(out_fig_path, bbox_inches="tight", dpi=150)
        plt.close(fig)

        print(f"  [OK] Saved alignment figure for {sample_id} -> {out_fig_path}")

    print(f"\n[SUCCESS] Visual alignment verification complete! Verified {len(selected_paths)} samples in {output_dir}")

if __name__ == "__main__":
    generate_visual_verifications()
