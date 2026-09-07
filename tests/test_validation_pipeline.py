"""
Automated Test Suite for Sentinel-1 SAR Oil Spill Detection & Validation Pipeline.
Smart India Hackathon 2026 - PS ID: SIH26143

Tests all 16 required capabilities:
1. Sentinel-1 image loading
2. Ground-truth mask loading
3. Image/mask pairing integrity
4. Image/mask dimension compatibility
5. Multi-channel handling (VV vs VH band separation)
6. Binary mask generation from ClassicalDetector
7. IoU calculation correctness
8. Dice calculation correctness
9. Precision calculation correctness
10. Recall calculation correctness
11. Contour extraction
12. Pixel-to-geographic conversion
13. CRS transformation
14. Area calculation via projected UTM coordinates
15. GeoJSON generation
16. GeoJSON validity
"""

import os
import sys
import json
import unittest

# Ensure workspace root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS
from shapely.geometry import shape, Polygon

from src.io import SARLoader, SARImage
from src.preprocessing import SARPreprocessor
from src.detector import ClassicalDetector
from src.detector_base import BaseDetector
from src.segmentation import ContourSegmenter
from src.confidence import ConfidenceScorer
from src.geospatial import GeospatialConverter
from src.evaluation import SegmentationEvaluator

class TestOilSpillValidationPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.image_path = "data/zenodo_validation/images/00000.tif"
        cls.mask_path = "data/zenodo_validation/masks/00000.tif"
        if not os.path.exists(cls.image_path) or not os.path.exists(cls.mask_path):
            # Fallback to data/images/Oil
            cls.image_path = "data/images/Oil/00000.tif"
            cls.mask_path = "data/masks/Mask_oil/00000.tif"

    # 1. Sentinel-1 image loading
    def test_01_sentinel1_image_loading(self):
        sar_img = SARLoader.load(self.image_path)
        self.assertIsInstance(sar_img, SARImage)
        self.assertIsNotNone(sar_img.metadata)
        self.assertGreater(sar_img.metadata.width, 0)
        self.assertGreater(sar_img.metadata.height, 0)
        self.assertEqual(sar_img.vv_band.shape, (sar_img.metadata.height, sar_img.metadata.width))

    # 2. Ground-truth mask loading
    def test_02_ground_truth_mask_loading(self):
        with rasterio.open(self.mask_path) as src:
            mask_data = src.read(1)
            self.assertEqual(mask_data.ndim, 2)
            self.assertIn(mask_data.dtype, [np.uint8, np.int16, np.int32])
            unique_vals = set(np.unique(mask_data))
            # Foreground pixels should exist
            self.assertTrue(any(v > 0 for v in unique_vals))

    # 3. Image/mask pairing
    def test_03_image_mask_pairing(self):
        img_name = os.path.basename(self.image_path)
        mask_name = os.path.basename(self.mask_path)
        self.assertEqual(img_name, mask_name, "Image and mask filenames must match for authentic pairing.")

    # 4. Image/mask dimension compatibility
    def test_04_dimension_compatibility(self):
        with rasterio.open(self.image_path) as src_img:
            img_h, img_w = src_img.height, src_img.width
        with rasterio.open(self.mask_path) as src_mask:
            mask_h, mask_w = src_mask.height, src_mask.width
        self.assertEqual(img_h, mask_h, "Image height must strictly equal mask height.")
        self.assertEqual(img_w, mask_w, "Image width must strictly equal mask width.")

    # 5. Multi-channel handling (VV vs VH)
    def test_05_multichannel_handling(self):
        sar_img = SARLoader.load(self.image_path)
        self.assertGreaterEqual(sar_img.metadata.count, 2, "Sentinel-1 GeoTIFF contains multi-channel SAR data.")
        self.assertIsNotNone(sar_img.vh_band, "VH polarization band must be identified and preserved.")
        # Over sea, co-polarization (VV) has higher backscatter than cross-polarization (VH)
        med_vv = float(np.nanmedian(sar_img.vv_band))
        med_vh = float(np.nanmedian(sar_img.vh_band))
        self.assertGreater(med_vv, med_vh, "VV band median backscatter must exceed VH band median backscatter.")

    # 6. Binary mask generation
    def test_06_binary_mask_generation(self):
        sar_img = SARLoader.load(self.image_path)
        preprocessor = SARPreprocessor()
        norm_img, denoised_db, valid_mask = preprocessor.preprocess(sar_img.vv_band)

        detector = ClassicalDetector()
        binary_mask = detector.detect(norm_img, raw_db=denoised_db, valid_mask=valid_mask)
        self.assertEqual(binary_mask.shape, norm_img.shape)
        unique_vals = set(np.unique(binary_mask))
        self.assertTrue(unique_vals.issubset({0, 1}), "Mask must be strictly binary (0 and 1).")

    # 7. IoU calculation
    def test_07_iou_calculation(self):
        # 100% overlap
        mask_a = np.array([[1, 1, 0], [0, 1, 0]], dtype=np.uint8)
        mask_b = np.array([[1, 1, 0], [0, 1, 0]], dtype=np.uint8)
        m = SegmentationEvaluator.evaluate(mask_a, mask_b)
        self.assertAlmostEqual(m["iou"], 1.0, places=3)

        # Partial overlap (Intersection = 2, Union = 4 -> IoU = 0.5)
        mask_c = np.array([[1, 1, 0], [0, 0, 0]], dtype=np.uint8)
        mask_d = np.array([[0, 1, 1], [0, 1, 0]], dtype=np.uint8)
        m2 = SegmentationEvaluator.evaluate(mask_c, mask_d)
        # c has (0,0),(0,1). d has (0,1),(0,2),(1,1). Intersection=(0,1) count=1. Union=4 -> 0.25
        self.assertAlmostEqual(m2["iou"], 0.25, places=3)

    # 8. Dice calculation
    def test_08_dice_calculation(self):
        mask_a = np.array([[1, 1, 0], [0, 0, 0]], dtype=np.uint8)
        mask_b = np.array([[0, 1, 1], [0, 0, 0]], dtype=np.uint8)
        # Intersection = 1, sum = 2 + 2 = 4 -> Dice = 2 * 1 / 4 = 0.5
        m = SegmentationEvaluator.evaluate(mask_a, mask_b)
        self.assertAlmostEqual(m["dice"], 0.5, places=3)

    # 9. Precision calculation
    def test_09_precision_calculation(self):
        pred = np.array([[1, 1, 1, 1]], dtype=np.uint8)
        gt = np.array([[1, 1, 0, 0]], dtype=np.uint8)
        # TP = 2, Pred = 4 -> Precision = 0.5
        m = SegmentationEvaluator.evaluate(pred, gt)
        self.assertAlmostEqual(m["precision"], 0.5, places=3)

    # 10. Recall calculation
    def test_10_recall_calculation(self):
        pred = np.array([[1, 0, 0, 0]], dtype=np.uint8)
        gt = np.array([[1, 1, 1, 1]], dtype=np.uint8)
        # TP = 1, GT = 4 -> Recall = 0.25
        m = SegmentationEvaluator.evaluate(pred, gt)
        self.assertAlmostEqual(m["recall"], 0.25, places=3)

    # 11. Contour extraction
    def test_11_contour_extraction(self):
        synthetic_mask = np.zeros((200, 200), dtype=np.uint8)
        # Draw a filled rectangle of 40x40 = 1600 pixels
        synthetic_mask[50:90, 50:90] = 1
        segmenter = ContourSegmenter(min_contour_points=4)
        candidates = segmenter.extract_candidates(synthetic_mask)
        self.assertEqual(len(candidates), 1)
        self.assertAlmostEqual(candidates[0].pixel_area, 1600, delta=100)
        self.assertAlmostEqual(candidates[0].centroid[0], 69.5, delta=2)
        self.assertAlmostEqual(candidates[0].centroid[1], 69.5, delta=2)

    # 12. Pixel-to-geographic conversion
    def test_12_pixel_to_geographic(self):
        sar_img = SARLoader.load(self.image_path)
        geo_conv = GeospatialConverter(
            affine_transform=sar_img.metadata.transform,
            source_crs=sar_img.metadata.crs,
        )
        # Convert origin (0, 0)
        lon_0, lat_0 = geo_conv.pixel_to_geographic(0, 0)
        bounds = sar_img.metadata.bounds
        self.assertAlmostEqual(lon_0, bounds.left, places=4)
        self.assertAlmostEqual(lat_0, bounds.top, places=4)

    # 13. CRS transformation
    def test_13_crs_transformation(self):
        sar_img = SARLoader.load(self.image_path)
        self.assertIsNotNone(sar_img.metadata.crs)
        crs_epsg = sar_img.metadata.crs.to_epsg()
        self.assertEqual(crs_epsg, 4326, "Source Sentinel-1 GeoTIFF is georeferenced in WGS 84 (EPSG:4326).")

    # 14. Area calculation via projected UTM
    def test_14_area_calculation(self):
        sar_img = SARLoader.load(self.image_path)
        geo_conv = GeospatialConverter(
            affine_transform=sar_img.metadata.transform,
            source_crs=sar_img.metadata.crs,
        )
        # Create a polygon of ~0.01 deg square
        poly_4326 = Polygon([(4.0, 55.0), (4.01, 55.0), (4.01, 55.01), (4.0, 55.01), (4.0, 55.0)])
        area_info = geo_conv.calculate_physical_area(poly_4326, centroid_lon=4.005, centroid_lat=55.005)
        self.assertIn("estimated_area_m2", area_info)
        self.assertIn("estimated_area_km2", area_info)
        self.assertGreater(area_info["estimated_area_m2"], 100_000.0)
        self.assertEqual(area_info["utm_epsg"], 32631, "UTM Zone for Lon 4.0 East in North Sea should be 31N (EPSG:32631)")

    # 15. GeoJSON generation
    def test_15_geojson_generation(self):
        sar_img = SARLoader.load(self.image_path)
        geo_conv = GeospatialConverter(
            affine_transform=sar_img.metadata.transform,
            source_crs=sar_img.metadata.crs,
        )
        synthetic_mask = np.zeros((sar_img.metadata.height, sar_img.metadata.width), dtype=np.uint8)
        synthetic_mask[100:200, 100:200] = 1
        segmenter = ContourSegmenter()
        candidates = segmenter.extract_candidates(synthetic_mask)
        scorer = ConfidenceScorer()
        confidences = [scorer.calculate_score(c, synthetic_mask.shape) for c in candidates]

        geojson_fc = geo_conv.create_feature_collection(candidates, confidences)
        self.assertEqual(geojson_fc["type"], "FeatureCollection")
        self.assertEqual(len(geojson_fc["features"]), 1)
        feat = geojson_fc["features"][0]
        self.assertEqual(feat["type"], "Feature")
        self.assertIn("estimated_area_km2", feat["properties"])
        self.assertIn("centroid_lat", feat["properties"])
        self.assertIn("centroid_lon", feat["properties"])

    # 16. GeoJSON validity check
    def test_16_geojson_validity(self):
        sar_img = SARLoader.load(self.image_path)
        geo_conv = GeospatialConverter(
            affine_transform=sar_img.metadata.transform,
            source_crs=sar_img.metadata.crs,
        )
        synthetic_mask = np.zeros((sar_img.metadata.height, sar_img.metadata.width), dtype=np.uint8)
        synthetic_mask[300:450, 300:450] = 1
        segmenter = ContourSegmenter()
        candidates = segmenter.extract_candidates(synthetic_mask)
        geojson_fc = geo_conv.create_feature_collection(candidates, [0.85])

        # Validate with shapely
        for feat in geojson_fc["features"]:
            geom = shape(feat["geometry"])
            self.assertTrue(geom.is_valid, "Feature geometry must be a topologically valid Polygon.")
            self.assertFalse(geom.is_empty, "Feature geometry must not be empty.")
            # Coordinates should fall within geographic limits
            min_x, min_y, max_x, max_y = geom.bounds
            self.assertTrue(-180.0 <= min_x <= 180.0)
            self.assertTrue(-90.0 <= min_y <= 90.0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
