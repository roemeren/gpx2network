# ---------- Imports ----------
import geopandas as gpd
import pandas as pd
import os

# ---------- Constants ----------
# files and folders
UPLOAD_FOLDER = "app/uploads"
STATIC_FOLDER = "app/static"

# geoprocessing
multiline_geojson = 'data/processed/gdf_multiline.geojson'
multiline_parquet_proj = 'data/processed/gdf_multiline_projected.parquet'
point_parquet_proj = 'data/processed/gdf_point_projected.parquet'
