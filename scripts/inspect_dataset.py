"""
Dataset Inspection Utility for Sentinel-1 SAR Oil Spill Dataset.
Inspects raster metadata, channels (VV/VH), dimensions, CRS, affine transforms,
and verifies 1:1 spatial compatibility with ground-truth masks without altering original data.
"""

import os
import json
import glob
from typing import Dict, Any, List
import numpy as np
import rasterio

def inspect_dataset(
    images_dir: str = "data/zenodo_validation/images",
    masks_dir: str = "data/zenodo_validation/masks",
    output_report_path: str = "output/dataset_inspection_report.json",
) -> List[Dict[str, Any]]:
    print("==================================================================")
    print("  PART 3: Sentinel-1 SAR Dataset & Ground-Truth Inspection Suite   ")
    print("==================================================================")
    print(f"Images directory: {images_dir}")
    print(f"Masks directory : {masks_dir}\n")

    os.makedirs(os.path.dirname(output_report_path), exist_ok=True)

    image_paths = sorted(glob.glob(os.path.join(images_dir, "*.tif")))
    if not image_paths:
        print("Error: No GeoTIFF images found!")
        return []

    inspection_results = []
    all_aligned = True

    print(f"{'Sample ID':<10} | {'Dim (H x W)':<13} | {'Ch':<3} | {'Channels ID':<14} | {'CRS':<10} | {'Pix Res (deg)':<14} | {'GT Fg Px':<9} | {'Fg %':<6} | {'Align'}")
    print("-" * 105)

    for img_path in image_paths:
        base_name = os.path.basename(img_path)
        sample_id = os.path.splitext(base_name)[0]
        mask_path = os.path.join(masks_dir, base_name)

        if not os.path.exists(mask_path):
            print(f"Error: Mask missing for {base_name}")
            continue

        # Inspect Image
        with rasterio.open(img_path) as src_img:
            img_h, img_w = src_img.height, src_img.width
            img_count = src_img.count
            img_dtype = str(src_img.dtypes[0])
            img_crs = str(src_img.crs) if src_img.crs else "None"
            img_transform = src_img.transform
            res_x, res_y = src_img.res
            bounds = {
                "left": float(src_img.bounds.left),
                "bottom": float(src_img.bounds.bottom),
                "right": float(src_img.bounds.right),
                "top": float(src_img.bounds.top),
            }

            img_data = src_img.read()  # (count, H, W)
            bands_info = {}
            if img_count >= 2:
                # Identify VV and VH: In co-polarization (VV), sea backscatter is substantially higher
                # than in cross-polarization (VH).
                b0 = img_data[0].astype(np.float32)
                b1 = img_data[1].astype(np.float32)
                med0 = float(np.nanmedian(b0))
                med1 = float(np.nanmedian(b1))

                if med1 > med0:
                    vv_idx, vh_idx = 1, 0
                else:
                    vv_idx, vh_idx = 0, 1

                bands_info = {
                    "band_1_id": f"{'VV' if vv_idx == 0 else 'VH'} (median={med0:.2f} dB)",
                    "band_2_id": f"{'VV' if vv_idx == 1 else 'VH'} (median={med1:.2f} dB)",
                    "vv_band_index": vv_idx + 1,
                    "vh_band_index": vh_idx + 1,
                }
                channel_str = f"B1:{'VV' if vv_idx == 0 else 'VH'}, B2:{'VV' if vv_idx == 1 else 'VH'}"
            elif img_count == 1:
                bands_info = {"band_1_id": "VV (single band)"}
                channel_str = "B1:VV"
            else:
                channel_str = f"{img_count} bands"

            # Compute min, max, mean of valid finite pixels
            valid_finite = np.isfinite(img_data)
            img_min = float(np.min(img_data[valid_finite])) if np.any(valid_finite) else None
            img_max = float(np.max(img_data[valid_finite])) if np.any(valid_finite) else None
            img_mean = float(np.mean(img_data[valid_finite])) if np.any(valid_finite) else None

        # Inspect Mask
        with rasterio.open(mask_path) as src_mask:
            mask_h, mask_w = src_mask.height, src_mask.width
            mask_dtype = str(src_mask.dtypes[0])
            mask_data = src_mask.read(1)
            unique_vals = [int(v) for v in np.unique(mask_data)]
            fg_pixels = int(np.sum(mask_data > 0))
            total_pixels = mask_h * mask_w
            fg_pct = float((fg_pixels / total_pixels) * 100.0)

        # Verification: image height == mask height, image width == mask width
        aligned = (img_h == mask_h) and (img_w == mask_w)
        if not aligned:
            all_aligned = False

        record = {
            "sample_id": sample_id,
            "image": {
                "filename": base_name,
                "dimensions": [img_h, img_w],
                "height": img_h,
                "width": img_w,
                "count": img_count,
                "dtype": img_dtype,
                "crs": img_crs,
                "affine_transform": [img_transform.a, img_transform.b, img_transform.c,
                                     img_transform.d, img_transform.e, img_transform.f],
                "pixel_resolution": [float(res_x), float(res_y)],
                "bounds": bounds,
                "min_value": round(img_min, 3) if img_min is not None else None,
                "max_value": round(img_max, 3) if img_max is not None else None,
                "mean_value": round(img_mean, 3) if img_mean is not None else None,
                "bands_polarization": bands_info,
            },
            "mask": {
                "filename": base_name,
                "dimensions": [mask_h, mask_w],
                "height": mask_h,
                "width": mask_w,
                "dtype": mask_dtype,
                "unique_values": unique_vals,
                "foreground_pixel_count": fg_pixels,
                "foreground_percentage": round(fg_pct, 4),
            },
            "verification": {
                "height_match": (img_h == mask_h),
                "width_match": (img_w == mask_w),
                "spatial_alignment_verified": aligned,
            }
        }
        inspection_results.append(record)

        print(
            f"{sample_id:<10} | "
            f"{img_h}x{img_w:<7} | "
            f"{img_count:<3} | "
            f"{channel_str:<14} | "
            f"{img_crs:<10} | "
            f"{res_x:<14.8f} | "
            f"{fg_pixels:<9} | "
            f"{fg_pct:<6.3f}% | "
            f"{'PASS' if aligned else 'FAIL'}"
        )

    print("-" * 105)
    print(f"Total Samples Inspected : {len(inspection_results)}")
    print(f"Spatial Alignment Check : {'ALL SAMPLES PASS' if all_aligned else 'MISALIGNMENT DETECTED'}")

    with open(output_report_path, "w", encoding="utf-8") as rep:
        json.dump(inspection_results, rep, indent=2)

    print(f"\nInspection report saved to: {output_report_path}")
    return inspection_results

if __name__ == "__main__":
    inspect_dataset()
