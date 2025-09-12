# imports
import geopandas as gpd
import pandas as pd
import gpxpy
import os
import zipfile
import pickle
import os
import gdown
import shutil
from shapely.geometry import LineString, MultiLineString
from datetime import datetime

# constants
zip_file_path = "data/raw/gpx-test.zip"
zip_folder = "data/raw/unzipped_gpx"
res_folder = "data/intermediate"
segments_file_path = "data/processed/all_matched_segments.geojson"
nodes_file_path = "data/processed/all_matched_nodes.geojson"
buffer_distance = 20  # buffer distance in meters
intersect_threshold = 0.75