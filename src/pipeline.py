"""
Complete Oil Spill Detection Pipeline Orchestrator.
Connects data loader, preprocessor, pluggable detector, segmenter,
geospatial converter, confidence scorer, and file export.
"""

import os
import json
from typing import Dict, Any, Optional
import numpy as np
import cv2

from .io import SARLoader, SARImage
from .preprocessing import SARPreprocessor
from .detector_base import BaseDetector
from .detector import ClassicalDetector
from .segmentation import ContourSegmenter, SpillCandidate
from .confidence import ConfidenceScorer
from .geospatial import GeospatialConverter

class OilSpillPipeline:
    """
    End-to-end processing pipeline from raw Sentinel-1 GeoTIFF to geolocated GeoJSON.
    """

    def __init__(
        self,
        detector: Optional[BaseDetector] = None,
        preprocessor: Optional[SARPreprocessor] = None,
        segmenter: Optional[ContourSegmenter] = None,
        confidence_scorer: Optional[ConfidenceScorer] = None,
    ):
        self.detector = detector if detector is not None else ClassicalDetector()
        self.preprocessor = preprocessor if preprocessor is not None else SARPreprocessor()
        self.segmenter = segmenter if segmenter is not None else ContourSegmenter()
        self.confidence_scorer = confidence_scorer if confidence_scorer is not None else ConfidenceScorer()

    def process_image(
        self,
        input_path: str,
        output_dir: str = "output",
    ) -> Dict[str, Any]:
        """
        Executes the full pipeline on a Sentinel-1 GeoTIFF and writes outputs.
        """
        os.makedirs(output_dir, exist_ok=True)

        # 1. Load GeoTIFF and preserve geospatial metadata
        sar_img: SARImage = SARLoader.load(input_path)

        # 2. Preprocess SAR imagery (calibration, Lee speckle filtering, contrast normalization)
        norm_img, denoised_db, valid_mask = self.preprocessor.preprocess(
            vv_band=sar_img.vv_band,
            vh_band=sar_img.vh_band,
            nodata=sar_img.metadata.nodata,
        )

        # 3. Detect suspected oil spills using configured detector
        binary_mask = self.detector.detect(
            normalized_image=norm_img,
            raw_db=denoised_db,
            valid_mask=valid_mask,
        )

        # 4. Extract connected components, contours, and shape metrics
        candidates = self.segmenter.extract_candidates(
            binary_mask=binary_mask,
            normalized_image=norm_img,
        )

        # 5. Compute transparent heuristic confidence scores
        confidences = [
            self.confidence_scorer.calculate_score(c, norm_img.shape)
            for c in candidates
        ]

        # 6. Geospatial Conversion & Projected Area Calculation
        geo_converter = GeospatialConverter(
            affine_transform=sar_img.metadata.transform,
            source_crs=sar_img.metadata.crs,
        )
        geojson_data = geo_converter.create_feature_collection(candidates, confidences)

        # 7. Generate and save output files
        # A. Binary Mask: 0 = background, 255 = suspected spill
        mask_u8 = (binary_mask * 255).astype(np.uint8)
        mask_path = os.path.join(output_dir, "mask.png")
        cv2.imwrite(mask_path, mask_u8)

        # B. Color Overlay: Normalized SAR in grayscale with translucent red highlight on spill regions
        # and yellow contour borders
        overlay_rgb = cv2.cvtColor(norm_img, cv2.COLOR_GRAY2RGB)
        red_layer = np.zeros_like(overlay_rgb)
        red_layer[:, :] = [0, 0, 230]  # Vibrant Red in BGR

        spill_indices = binary_mask > 0
        alpha = 0.45
        overlay_rgb[spill_indices] = cv2.addWeighted(
            overlay_rgb[spill_indices], 1.0 - alpha, red_layer[spill_indices], alpha, 0
        )

        # Draw yellow contour outlines
        for c in candidates:
            cv2.drawContours(overlay_rgb, [c.contour], -1, (0, 235, 255), 2)  # Yellow outline
            cx, cy = int(c.centroid[0]), int(c.centroid[1])
            # Draw candidate ID label
            cv2.putText(
                overlay_rgb,
                f"#{c.id}",
                (cx - 10, cy - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

        overlay_path = os.path.join(output_dir, "overlay.png")
        cv2.imwrite(overlay_path, overlay_rgb)

        # Save preprocessed normalized SAR image for inspection
        norm_path = os.path.join(output_dir, "preprocessed.png")
        cv2.imwrite(norm_path, norm_img)

        # C. Save GeoJSON
        geojson_path = os.path.join(output_dir, "spill.geojson")
        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, indent=2)

        # 8. Summary statistics
        total_area_km2 = sum(
            f["properties"]["estimated_area_km2"] for f in geojson_data["features"]
        )
        total_area_m2 = sum(
            f["properties"]["estimated_area_m2"] for f in geojson_data["features"]
        )
        highest_conf = max(confidences) if confidences else 0.0

        summary = {
            "status": "success",
            "source_image": os.path.basename(input_path),
            "image_dimensions": {"width": sar_img.metadata.width, "height": sar_img.metadata.height},
            "source_crs": str(sar_img.metadata.crs),
            "detected_regions_count": len(candidates),
            "highest_confidence": round(highest_conf, 4),
            "total_estimated_area_km2": round(total_area_km2, 4),
            "total_estimated_area_m2": round(total_area_m2, 2),
            "mask_path": mask_path,
            "overlay_path": overlay_path,
            "geojson_path": geojson_path,
            "features": geojson_data["features"],
            "note": "Suspected oil-spill regions. Vessel responsibility is NOT determined by this module.",
        }

        return summary
