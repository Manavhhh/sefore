"""
Command Line Interface for Sentinel-1 Oil Spill Detection Module.
Smart India Hackathon 2026 - PS ID: SIH26143
"""

import argparse
import sys
import os
from src.pipeline import OilSpillPipeline

def main():
    parser = argparse.ArgumentParser(
        description="Sentinel-1 SAR Oil Spill Detection CLI (SIH26143)"
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to Sentinel-1 SAR GeoTIFF (.tif)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="output",
        help="Output directory to save mask, overlay, and GeoJSON (default: output/)",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=101,
        help="Adaptive threshold neighborhood block size (default: 101)",
    )
    parser.add_argument(
        "--threshold-c",
        type=float,
        default=25.0,
        help="Adaptive threshold constant offset (default: 25.0)",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print("==================================================================")
    print("  SIH 2026: Sentinel-1 Satellite Oil Spill Detection Pipeline     ")
    print("==================================================================")
    print(f"Input Image : {args.input}")
    print(f"Output Path : {args.output}")
    print("Executing pipeline...")

    from src.detector import ClassicalDetector
    detector = ClassicalDetector(
        adaptive_block_size=args.block_size,
        adaptive_c=args.threshold_c,
    )
    pipeline = OilSpillPipeline(detector=detector)

    try:
        results = pipeline.process_image(input_path=args.input, output_dir=args.output)
    except Exception as e:
        print(f"\nPipeline execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n------------------- DETECTION SUMMARY -------------------")
    print(f"Detected regions: {results['detected_regions_count']}")
    print(f"Highest confidence: {results['highest_confidence']}")
    print(f"Estimated area: {results['total_estimated_area_km2']} km² ({results['total_estimated_area_m2']} m²)")
    print(f"GeoJSON: {results['geojson_path']}")
    print(f"Mask: {results['mask_path']}")
    print(f"Overlay: {results['overlay_path']}")
    print("---------------------------------------------------------")
    print("Note: This module detects and geolocates suspected oil-spill regions from Sentinel-1 SAR imagery.")
    print("      Vessel responsibility is NOT determined by this module.")
    print("      The resulting spill location will later be passed to the ocean-drift and AIS correlation modules.")

if __name__ == "__main__":
    main()
