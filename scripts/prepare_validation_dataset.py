"""
Dataset Preparation Script for Zenodo Sentinel-1 SAR Validation.
Organizes available real Sentinel-1 SAR images and extracts matching ground-truth masks
into data/zenodo_validation/images and data/zenodo_validation/masks.
"""

import os
import shutil
import json
import py7zr

def prepare_zenodo_validation_dataset(
    source_images_dir: str = "data/images/Oil",
    masks_archive_path: str = "data/masks.7z",
    target_base_dir: str = "data/zenodo_validation",
):
    target_images_dir = os.path.join(target_base_dir, "images")
    target_masks_dir = os.path.join(target_base_dir, "masks")

    os.makedirs(target_images_dir, exist_ok=True)
    os.makedirs(target_masks_dir, exist_ok=True)

    print("==================================================================")
    print("  Preparing Zenodo Sentinel-1 Validation Dataset                  ")
    print("==================================================================")
    print(f"Source images: {source_images_dir}")
    print(f"Masks archive: {masks_archive_path}")
    print(f"Target dir   : {target_base_dir}\n")

    if not os.path.exists(source_images_dir):
        raise FileNotFoundError(f"Source images directory not found: {source_images_dir}")

    if not os.path.exists(masks_archive_path):
        raise FileNotFoundError(f"Masks archive not found: {masks_archive_path}")

    # List all available images
    img_files = sorted([f for f in os.listdir(source_images_dir) if f.lower().endswith(".tif")])
    print(f"Found {len(img_files)} real Sentinel-1 SAR GeoTIFF images in {source_images_dir}:")
    for f in img_files:
        size_mb = os.path.getsize(os.path.join(source_images_dir, f)) / (1024 * 1024)
        print(f"  - {f} ({size_mb:.2f} MB)")

    # Copy images to target directory
    print(f"\nCopying images to {target_images_dir}...")
    for f in img_files:
        src = os.path.join(source_images_dir, f)
        dst = os.path.join(target_images_dir, f)
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
            shutil.copy2(src, dst)

    # Extract corresponding masks from data/masks.7z
    print(f"\nExtracting matching ground-truth masks from {masks_archive_path}...")
    with py7zr.SevenZipFile(masks_archive_path, mode="r") as zm:
        archive_names = set(zm.getnames())
        pairs = []
        for f in img_files:
            mask_entry = f"Mask_oil/{f}"
            if mask_entry in archive_names:
                pairs.append((f, mask_entry))
            else:
                print(f"Warning: No ground truth mask found in archive for {f}")

        # Extract only matching masks
        targets_to_extract = [m for _, m in pairs]
        temp_extract_dir = os.path.join(target_base_dir, "_temp_masks")
        os.makedirs(temp_extract_dir, exist_ok=True)
        zm.extract(targets=targets_to_extract, path=temp_extract_dir)

        # Move extracted masks directly into target_masks_dir
        for img_name, mask_entry in pairs:
            extracted_file = os.path.join(temp_extract_dir, mask_entry)
            dst_mask = os.path.join(target_masks_dir, img_name)
            if os.path.exists(extracted_file):
                shutil.move(extracted_file, dst_mask)

        # Clean up temp dir
        shutil.rmtree(temp_extract_dir, ignore_errors=True)

    # Validate pairs
    manifest = []
    print("\nVerifying 1:1 image and mask pairing:")
    for f in img_files:
        img_path = os.path.join(target_images_dir, f)
        mask_path = os.path.join(target_masks_dir, f)
        img_exists = os.path.exists(img_path)
        mask_exists = os.path.exists(mask_path)
        status = "OK" if img_exists and mask_exists else "MISMATCH"
        print(f"  [{status}] Image: {f} <---> Mask: {f} (Mask exists: {mask_exists})")
        if img_exists and mask_exists:
            manifest.append({
                "sample_id": os.path.splitext(f)[0],
                "image_filename": f,
                "mask_filename": f,
                "image_path": img_path.replace("\\", "/"),
                "mask_path": mask_path.replace("\\", "/"),
                "image_bytes": os.path.getsize(img_path),
                "mask_bytes": os.path.getsize(mask_path),
            })

    manifest_path = os.path.join(target_base_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"\n[SUCCESS] Validation dataset ready with {len(manifest)} paired samples!")
    print(f"Manifest written to: {manifest_path}")
    return manifest

if __name__ == "__main__":
    prepare_zenodo_validation_dataset()
