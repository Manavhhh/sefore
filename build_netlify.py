import os
import shutil
import json
from src.pipeline import OilSpillPipeline
from src.detector import ClassicalDetector

def build_netlify_package():
    dist_dir = "dist"
    os.makedirs(dist_dir, exist_ok=True)
    os.makedirs(os.path.join(dist_dir, "samples"), exist_ok=True)

    # 1. Copy core frontend files
    for f in ["index.html", "style.css", "app.js"]:
        shutil.copy(os.path.join("frontend", f), os.path.join(dist_dir, f))

    # 2. Run pipeline on selected top samples for instant client-side static playback on Netlify
    pipeline = OilSpillPipeline(
        detector=ClassicalDetector(
            adaptive_block_size=101,
            adaptive_c=25.0,
            max_intensity_threshold=35,
            min_area_pixels=250,
        )
    )

    samples_dir = "data/images/Oil"
    selected_samples = ["00000.tif", "00002.tif", "00004.tif", "00006.tif", "00007.tif", "00008.tif"]
    manifest = []

    print("Pre-rendering real detection results for Netlify static deployment...")
    for s in selected_samples:
        img_path = os.path.join(samples_dir, s)
        if not os.path.exists(img_path):
            continue
        sample_id = os.path.splitext(s)[0]
        sample_out = os.path.join(dist_dir, "samples", sample_id)
        os.makedirs(sample_out, exist_ok=True)

        res = pipeline.process_image(input_path=img_path, output_dir=sample_out)
        manifest.append({
            "name": s,
            "id": sample_id,
            "detected_regions_count": res["detected_regions_count"],
            "highest_confidence": res["highest_confidence"],
            "total_estimated_area_km2": res["total_estimated_area_km2"],
            "total_estimated_area_m2": res["total_estimated_area_m2"],
            "centroid_lat": res["features"][0]["properties"]["centroid_lat"] if res.get("features") else None,
            "centroid_lon": res["features"][0]["properties"]["centroid_lon"] if res.get("features") else None,
            "primary_suspect_name": res.get("vessel_analytics", {}).get("primary_suspect", {}).get("name"),
            "primary_suspect_score": res.get("vessel_analytics", {}).get("primary_suspect", {}).get("suspect_score"),
            "mask_url": f"samples/{sample_id}/mask.png",
            "overlay_url": f"samples/{sample_id}/overlay.png",
            "sar_url": f"samples/{sample_id}/preprocessed.png",
            "geojson_url": f"samples/{sample_id}/spill.geojson",
            "final_spill_data_url": f"samples/{sample_id}/final_spill_data.json",
        })
        print(f"  Rendered {s}: {res['detected_regions_count']} regions, {res['total_estimated_area_km2']} km², Top Suspect: {res.get('vessel_analytics', {}).get('primary_suspect', {}).get('name')}")

    with open(os.path.join(dist_dir, "samples_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    # Also copy to root for local dev
    with open("samples_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # 3. Create _redirects file for Netlify
    with open(os.path.join(dist_dir, "_redirects"), "w", encoding="utf-8") as f:
        f.write("/*    /index.html   200\n")

    print("\n[SUCCESS] Netlify package generated in 'dist/' directory with vessel attribution!")

if __name__ == "__main__":
    build_netlify_package()
