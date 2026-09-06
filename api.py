"""
FastAPI Backend for Sentinel-1 SAR Oil Spill Detection.
Smart India Hackathon 2026 - PS ID: SIH26143
"""

import os
import shutil
import tempfile
from typing import Dict, Any
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

@app.get("/download/{file_type}")
def download_output_file(file_type: str):
    """
    Download generated output files: mask, overlay, preprocessed, or geojson.
    """
    mapping = {
        "mask": os.path.join(OUTPUT_DIR, "mask.png"),
        "overlay": os.path.join(OUTPUT_DIR, "overlay.png"),
        "preprocessed": os.path.join(OUTPUT_DIR, "preprocessed.png"),
        "geojson": os.path.join(OUTPUT_DIR, "spill.geojson"),
    }
    file_path = mapping.get(file_type)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File for '{file_type}' not found.")

    media_types = {
        "mask": "image/png",
        "overlay": "image/png",
        "preprocessed": "image/png",
        "geojson": "application/geo+json",
    }
    filename = f"oil_spill_{file_type}.{'png' if file_type != 'geojson' else 'geojson'}"
    return FileResponse(file_path, media_type=media_types[file_type], filename=filename)

# Mount static files and frontend
app.mount("/output", StaticFiles(directory="output"), name="output")
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
