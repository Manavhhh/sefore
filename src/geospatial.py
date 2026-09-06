"""
Geospatial Conversion and Physical Area Calculation Module.
Transforms image pixel coordinates to EPSG:4326 coordinates,
calculates accurate metric surface areas via dynamic UTM reprojection,
and constructs validated GeoJSON FeatureCollections.
"""

import json
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from rasterio.transform import Affine
from rasterio.crs import CRS
from shapely.geometry import Polygon, MultiPolygon, mapping
from shapely.ops import transform as shapely_transform
import pyproj
from .segmentation import SpillCandidate

class GeospatialConverter:
    """
    Handles pixel-to-geographic projection and metric area calculations.
    """

    def __init__(self, affine_transform: Affine, source_crs: CRS):
        self.affine = affine_transform
        self.source_crs = source_crs

    def pixel_to_geographic(self, col: float, row: float) -> Tuple[float, float]:
        """
        Converts pixel column (x) and row (y) to geographic coordinates (X, Y)
        using the affine transform:
        X = a * col + b * row + c
        Y = d * col + e * row + f
        """
        x_geo, y_geo = self.affine * (col, row)
        return float(x_geo), float(y_geo)

    def contour_to_polygon(self, contour: np.ndarray) -> Optional[Polygon]:
        """
        Converts pixel contour points (N, 1, 2) to a Shapely Polygon in source CRS.
        """
        if len(contour) < 3:
            return None

        # Flatten contour points (col, row)
        coords = []
        for pt in contour:
            col, row = pt[0][0], pt[0][1]
            lon, lat = self.pixel_to_geographic(col, row)
            coords.append((lon, lat))

        # Close polygon if not closed
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        poly = Polygon(coords)
        if not poly.is_valid:
            # Fix self-intersections or topology errors
            poly = poly.buffer(0)

        if poly.is_empty:
            return None

        return poly

    @staticmethod
    def get_utm_epsg(lon: float, lat: float) -> int:
        """
        Determines the EPSG code of the optimal UTM zone for given longitude and latitude.
        """
        zone_number = int(np.floor((lon + 180) / 6)) + 1
        if lat >= 0:
            return 32600 + zone_number  # WGS 84 / UTM North
        else:
            return 32700 + zone_number  # WGS 84 / UTM South

    def calculate_physical_area(self, poly_4326: Polygon, centroid_lon: float, centroid_lat: float) -> Dict[str, float]:
        """
        Calculates physical area in m² and km² by projecting the EPSG:4326 polygon
        to the appropriate local UTM projection.
        """
        utm_epsg = self.get_utm_epsg(centroid_lon, centroid_lat)
        proj_from = pyproj.CRS("EPSG:4326")
        proj_to = pyproj.CRS(f"EPSG:{utm_epsg}")

        project = pyproj.Transformer.from_crs(proj_from, proj_to, always_xy=True).transform
        poly_utm = shapely_transform(project, poly_4326)

        area_m2 = float(poly_utm.area)
        area_km2 = float(area_m2 / 1_000_000.0)

        return {
            "estimated_area_m2": area_m2,
            "estimated_area_km2": area_km2,
            "utm_epsg": utm_epsg,
        }

    def candidate_to_geojson_feature(
        self,
        candidate: SpillCandidate,
        confidence_score: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Converts a SpillCandidate into a GeoJSON Feature with real EPSG:4326 coordinates
        and physical metrics.
        """
        poly = self.contour_to_polygon(candidate.contour)
        if poly is None:
            return None

        # Convert centroid pixel to geographic coordinates
        c_lon, c_lat = self.pixel_to_geographic(candidate.centroid[0], candidate.centroid[1])

        # Compute metric area in m² and km²
        area_metrics = self.calculate_physical_area(poly, c_lon, c_lat)

        # Convert bbox corners to geographic coordinates
        x, y, w, h = candidate.bbox
        min_lon, min_lat = self.pixel_to_geographic(x, y + h)
        max_lon, max_lat = self.pixel_to_geographic(x + w, y)

        properties = {
            "candidate_id": candidate.id,
            "heuristic_confidence_score": round(confidence_score, 4),
            "estimated_area_m2": round(area_metrics["estimated_area_m2"], 2),
            "estimated_area_km2": round(area_metrics["estimated_area_km2"], 4),
            "pixel_area": candidate.pixel_area,
            "perimeter_pixels": round(candidate.perimeter, 2),
            "centroid_lon": round(c_lon, 6),
            "centroid_lat": round(c_lat, 6),
            "bbox_geographic": {
                "min_lon": round(min(min_lon, max_lon), 6),
                "min_lat": round(min(min_lat, max_lat), 6),
                "max_lon": round(max(min_lon, max_lon), 6),
                "max_lat": round(max(min_lat, max_lat), 6),
            },
            "aspect_ratio": round(candidate.aspect_ratio, 3),
            "compactness": round(candidate.compactness, 4),
            "utm_projection": f"EPSG:{area_metrics['utm_epsg']}",
            "note": "Estimated detected area. Vessel responsibility is NOT determined by this module.",
        }

        feature = {
            "type": "Feature",
            "geometry": mapping(poly),
            "properties": properties,
        }
        return feature

    def create_feature_collection(
        self,
        candidates: List[SpillCandidate],
        confidences: List[float],
    ) -> Dict[str, Any]:
        """
        Builds a valid GeoJSON FeatureCollection containing all detected regions.
        """
        features = []
        for cand, conf in zip(candidates, confidences):
            feat = self.candidate_to_geojson_feature(cand, conf)
            if feat is not None:
                features.append(feat)

        geojson = {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {
                    "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
                }
            },
            "features": features,
        }
        return geojson
