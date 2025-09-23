# ---------- Imports ----------
import geopandas as gpd
import pandas as pd
import os

# ---------- Constants ----------
# files and folders
UPLOAD_FOLDER = "data/uploads"
RES_FOLDER = "static" # folder for output files, automatically served by Dash for downloads

# geoprocessing
multiline_geojson = 'data/geojson/gdf_multiline.geojson'
multiline_proj_parquet = 'data/geojson/gdf_multiline_projected.parquet'
point_proj_parquet = 'data/geojson/gdf_point_projected.parquet'

# application
progress_state = {
    "pct": 0,
    "processed-file": "",
    "btn-process-disabled": False,
    "btn-download-disabled": False
}

