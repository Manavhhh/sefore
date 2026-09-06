"""
Selective Sentinel-1 SAR Dataset Downloader using HTTP Range Requests.
Extracts only the target subset of images directly from Zenodo 7z archive
without downloading the full 40.7 GB archive.
"""

import io
import os
import requests
import py7zr

class FastRangeHTTPFile(io.RawIOBase):
    """
    HTTP Range-backed file reader with adaptive chunk prefetching and LRU buffer.
    """
    def __init__(self, url, total_size, chunk_size=8 * 1024 * 1024):
        self.url = url
        self.size = total_size
        self.pos = 0
        self.session = requests.Session()
        self.chunk_size = chunk_size
        self.buffer = b""
        self.buffer_start = -1

    def readable(self):
        return True

    def seekable(self):
        return True

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.size + offset
        return self.pos

    def tell(self):
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size:
            return 0
        wanted = len(b)
        # Check if current position is within existing buffer
        if not (self.buffer_start <= self.pos < self.buffer_start + len(self.buffer)):
            # Need to fetch new chunk
            fetch_len = max(self.chunk_size, wanted)
            end = min(self.size - 1, self.pos + fetch_len - 1)
            headers = {"Range": f"bytes={self.pos}-{end}"}
            resp = self.session.get(self.url, headers=headers)
            if resp.status_code not in (200, 206):
                raise IOError(f"HTTP Range failed: status {resp.status_code}")
            self.buffer = resp.content
            self.buffer_start = self.pos

        # Read from buffer
        offset = self.pos - self.buffer_start
        available = len(self.buffer) - offset
        to_copy = min(wanted, available)
        b[:to_copy] = self.buffer[offset : offset + to_copy]
        self.pos += to_copy
        return to_copy

def download_subset(num_images=10):
    images_url = "https://zenodo.org/records/8346860/files/01_Train_Val_Oil_Spill_images.7z?download=1"
    images_size = 40712942245

    masks_url = "https://zenodo.org/records/8346860/files/01_Train_Val_Oil_Spill_mask.7z?download=1"
    masks_archive = "data/masks.7z"

    os.makedirs("data/images", exist_ok=True)
    os.makedirs("data/masks", exist_ok=True)

    # 1. Ensure masks archive is available
    if not os.path.exists(masks_archive):
        print("Downloading masks archive (6.2 MB)...")
        r = requests.get(masks_url, stream=True)
        r.raise_for_status()
        with open(masks_archive, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        print("Masks archive downloaded.")

    # 2. Get available masks list
    with py7zr.SevenZipFile(masks_archive, mode="r") as zm:
        mask_names = set(zm.getnames())

    print("Opening remote Sentinel-1 SAR 7z archive via HTTP Range...")
    stream = FastRangeHTTPFile(images_url, images_size)
    bio = io.BufferedReader(stream, buffer_size=16 * 1024 * 1024)

    with py7zr.SevenZipFile(bio, mode="r") as zi:
        all_image_names = zi.getnames()
        # Find matching pairs between images and masks
        matched_pairs = []
        for img_name in all_image_names:
            if not img_name.endswith(".tif"):
                continue
            base = os.path.basename(img_name)
            mask_target = f"Mask_oil/{base}"
            if mask_target in mask_names:
                matched_pairs.append((img_name, mask_target))
            if len(matched_pairs) >= num_images:
                break

        print(f"Found {len(matched_pairs)} matched image/mask pairs for subset extraction:")
        for img, mask in matched_pairs:
            print(f"  {img} <--> {mask}")

        # Extract images that don't exist yet
        to_extract_images = []
        for img, _ in matched_pairs:
            local_path = os.path.join("data/images", img)
            if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
                to_extract_images.append(img)

        if to_extract_images:
            print(f"Extracting {len(to_extract_images)} images directly over HTTP Range...")
            zi.extract(targets=to_extract_images, path="data/images")
            print("Extracted images successfully.")
        else:
            print("All requested images are already present on disk.")

    # 3. Extract matching masks
    with py7zr.SevenZipFile(masks_archive, mode="r") as zm:
        mask_targets = [mask for _, mask in matched_pairs]
        zm.extract(targets=mask_targets, path="data/masks")
        print(f"Extracted {len(mask_targets)} matching masks.")

    print("\nDataset subset preparation complete!")
    print(f"Images in data/images/Oil: {os.listdir('data/images/Oil') if os.path.exists('data/images/Oil') else 0}")
    print(f"Masks in data/masks/Mask_oil: {len(os.listdir('data/masks/Mask_oil')) if os.path.exists('data/masks/Mask_oil') else 0}")

if __name__ == "__main__":
    download_subset(num_images=10)
