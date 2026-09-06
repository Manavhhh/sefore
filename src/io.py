"""
Sentinel-1 SAR Data Ingestion Module.
Preserves geospatial metadata, affine transforms, CRS, bounds, and handles multi-band data.
"""

import os
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

@dataclass
class SARMetadata:
    crs: CRS
    transform: Affine
    width: int
    height: int
    count: int
    dtypes: Tuple[str, ...]
    bounds: rasterio.coords.BoundingBox
    nodata: Optional[float]
    profile: Dict[str, Any]

@dataclass
class SARImage:
    data: np.ndarray  # Shape: (bands, height, width) or (height, width)
    metadata: SARMetadata
    vv_band: np.ndarray
    vh_band: Optional[np.ndarray] = None

class SARLoader:
    """
    Robust GeoTIFF loader for Sentinel-1 Synthetic Aperture Radar (SAR) imagery.
    """

    @staticmethod
    def load(filepath: str) -> SARImage:
        """
        Loads a Sentinel-1 SAR GeoTIFF, validates dimensions and CRS, and extracts VV/VH bands.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"SAR GeoTIFF not found: {filepath}")

        with rasterio.open(filepath) as src:
            data = src.read()  # Shape: (count, height, width)
            meta = SARMetadata(
                crs=src.crs,
                transform=src.transform,
                width=src.width,
                height=src.height,
                count=src.count,
                dtypes=src.dtypes,
                bounds=src.bounds,
                nodata=src.nodata,
                profile=src.profile.copy(),
            )

            if src.count >= 2:
                # Over ocean, co-polarization (VV) has significantly higher backscatter than cross-pol (VH).
                # Automatically assign the higher-backscatter band to VV and the lower to VH.
                b0 = data[0].astype(np.float32)
                b1 = data[1].astype(np.float32)
                med0 = float(np.nanmedian(b0))
                med1 = float(np.nanmedian(b1))
                if med1 > med0:
                    vv, vh = b1, b0
                else:
                    vv, vh = b0, b1
            elif src.count == 1:
                vv = data[0].astype(np.float32)
                vh = None
            else:
                raise ValueError(f"Invalid band count in GeoTIFF: {src.count}")

        return SARImage(data=data, metadata=meta, vv_band=vv, vh_band=vh)
