"""
FastAPI Backend for Sentinel-1 SAR Oil Spill Detection.
Smart India Hackathon 2026 - PS ID: SIH26143
"""

import os
import json
import shutil
import tempfile
from typing import Dict, Any
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.pipeline import OilSpillPipeline
from src.detector import ClassicalDetector

app = FastAPI(
    title="Sefore: Satellite-based Oil Spill Detection API",
    description="Automated Sentinel-1 SAR Oil Spill Detection and Geospatial Geolocation Module (SIH26143)",
    version="1.0.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default pipeline instance
pipeline = OilSpillPipeline(detector=ClassicalDetector(adaptive_block_size=101, adaptive_c=25.0, max_intensity_threshold=35, min_area_pixels=250))

# Ensure output directory exists
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("frontend", exist_ok=True)

@app.get("/health")
def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok", "service": "SIH26143-OilSpillDetector"}

@app.post("/detect")
async def detect_spill(
    file: UploadFile = File(...),
    adaptive_block_size: int = Query(101, description="Adaptive threshold block size"),
    adaptive_c: float = Query(25.0, description="Adaptive threshold sensitivity offset"),
) -> Dict[str, Any]:
    """
    Accepts a Sentinel-1 SAR GeoTIFF (.tif), executes end-to-end detection,
    and returns geolocated polygons, areas, confidence scores, and GeoJSON.
    """
    if not file.filename.lower().endswith((".tif", ".tiff")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload a valid Sentinel-1 GeoTIFF (.tif/.tiff).",
        )

    # Save uploaded file to temp file
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)

    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update detector hyperparameters if requested
        custom_detector = ClassicalDetector(
            adaptive_block_size=adaptive_block_size,
            adaptive_c=adaptive_c,
        )
        custom_pipeline = OilSpillPipeline(detector=custom_detector)

        # Run pipeline
        results = custom_pipeline.process_image(
            input_path=temp_file_path,
            output_dir=OUTPUT_DIR,
        )

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection pipeline failed: {str(e)}")
    finally:
        # Clean up temporary uploaded file
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.get("/sample-list")
def list_available_samples():
    """
    Returns list of local Sentinel-1 GeoTIFF test samples available for instant testing.
    """
    samples_dir = "data/images/Oil"
    if not os.path.exists(samples_dir):
        return {"samples": []}
    files = [f for f in os.listdir(samples_dir) if f.endswith(".tif")]
    return {"samples": files}

@app.get("/detect-sample/{sample_name}")
def detect_sample(sample_name: str):
    """
    Runs detection on a pre-downloaded Zenodo sample image.
    """
    sample_path = os.path.join("data/images/Oil", sample_name)
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail=f"Sample '{sample_name}' not found.")

    try:
        results = pipeline.process_image(
            input_path=sample_path,
            output_dir=OUTPUT_DIR,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

@app.get("/validation/samples")
def list_validation_samples():
    """
    Returns list of real Zenodo Sentinel-1 validation samples paired with ground truth.
    """
    manifest_path = "data/zenodo_validation/manifest.json"
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return {"samples": json.load(f)}
    
    val_images_dir = "data/zenodo_validation/images"
    if not os.path.exists(val_images_dir):
        return {"samples": []}
    files = sorted([f for f in os.listdir(val_images_dir) if f.endswith(".tif")])
    return {"samples": [{"sample_id": os.path.splitext(f)[0], "image_filename": f} for f in files]}

@app.get("/validation/summary")
def get_validation_summary():
    """
    Returns aggregate benchmark metrics for the ClassicalDetector across real Zenodo samples.
    """
    eval_json = "output/evaluation_results.json"
    if not os.path.exists(eval_json):
        raise HTTPException(status_code=404, detail="Evaluation results not found. Run evaluate.py first.")
    with open(eval_json, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/validation/evaluate/{sample_name}")
def evaluate_validation_sample(sample_name: str):
    """
    Runs detection on a Zenodo validation sample, compares with real Ground Truth,
    and returns detection metrics alongside actual IoU, Dice, Precision, Recall.
    """
    from src.evaluation import SegmentationEvaluator
    import rasterio

    if not sample_name.endswith(".tif"):
        sample_name += ".tif"

    img_path = os.path.join("data/zenodo_validation/images", sample_name)
    mask_path = os.path.join("data/zenodo_validation/masks", sample_name)

    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail=f"Validation image '{sample_name}' not found.")

    sample_id = os.path.splitext(sample_name)[0]
    sample_out = os.path.join("output/eval_results", sample_id)
    os.makedirs(sample_out, exist_ok=True)

    try:
        # Run detection pipeline
        res = pipeline.process_image(input_path=img_path, output_dir=sample_out)

        # Compute ground truth evaluation if mask exists
        metrics = None
        has_gt = os.path.exists(mask_path)
        if has_gt:
            with rasterio.open(res["mask_path"]) as p_src:
                pred_mask = p_src.read(1) > 0
            with rasterio.open(mask_path) as gt_src:
                gt_mask = gt_src.read(1) > 0

            metrics = SegmentationEvaluator.evaluate(pred_mask=pred_mask, gt_mask=gt_mask)

            # Generate comparison visual if not exists
            comp_path = os.path.join(sample_out, "gt_vs_pred_comparison.png")
            gt_img_path = os.path.join(sample_out, "ground_truth.png")

            comp_rgb = np.zeros((pred_mask.shape[0], pred_mask.shape[1], 3), dtype=np.uint8)
            tp_idx = np.logical_and(pred_mask, gt_mask)
            fp_idx = np.logical_and(pred_mask, ~gt_mask)
            fn_idx = np.logical_and(~pred_mask, gt_mask)
            comp_rgb[tp_idx] = [0, 230, 80]    # Green = TP
            comp_rgb[fp_idx] = [230, 40, 40]    # Red = FP
            comp_rgb[fn_idx] = [40, 120, 240]   # Blue = FN

            import cv2
            cv2.imwrite(comp_path, cv2.cvtColor(comp_rgb, cv2.COLOR_RGB2BGR))
            cv2.imwrite(gt_img_path, (gt_mask.astype(np.uint8)) * 255)

            res["ground_truth_metrics"] = metrics
            res["ground_truth_path"] = gt_img_path.replace("\\", "/")
            res["comparison_path"] = comp_path.replace("\\", "/")

        return res

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation evaluation failed: {str(e)}")

@app.get("/download/{file_type}")
def download_output_file(file_type: str):
    """
    Download generated output files: mask, overlay, preprocessed, geojson, or final_spill_data.
    """
    mapping = {
        "mask": os.path.join(OUTPUT_DIR, "mask.png"),
        "overlay": os.path.join(OUTPUT_DIR, "overlay.png"),
        "preprocessed": os.path.join(OUTPUT_DIR, "preprocessed.png"),
        "geojson": os.path.join(OUTPUT_DIR, "spill.geojson"),
        "final_spill_data": os.path.join(OUTPUT_DIR, "final_spill_data.json"),
    }
    file_path = mapping.get(file_type)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File for '{file_type}' not found.")

    media_types = {
        "mask": "image/png",
        "overlay": "image/png",
        "preprocessed": "image/png",
        "geojson": "application/geo+json",
        "final_spill_data": "application/json",
    }
    ext_map = {
        "mask": "png",
        "overlay": "png",
        "preprocessed": "png",
        "geojson": "geojson",
        "final_spill_data": "json",
    }
    filename = "final_spill_data.json" if file_type == "final_spill_data" else f"oil_spill_{file_type}.{ext_map[file_type]}"
    return FileResponse(file_path, media_type=media_types[file_type], filename=filename)

# Mount static files and frontend
app.mount("/output", StaticFiles(directory="output"), name="output")
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
