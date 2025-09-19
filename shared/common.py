# ---------- Imports ----------
import geopandas as gpd
import pandas as pd
import pickle
import os
import sys
import gdown
import shutil
import dash
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import zipfile, io, time, json
import gpxpy
import base64
import datetime
import xml.etree.ElementTree as ET
import requests
import re
import subprocess
import platform
from shapely.geometry import Point, LineString, MultiLineString
from dash import html, dcc, Output, Input, State, dash_table
from dash.exceptions import PreventUpdate
from pathlib import Path
from tqdm import tqdm

# ---------- Constants ----------
# files and folders
UPLOAD_FOLDER = "data/uploads"
RES_FOLDER = "static" # folder for output files, automatically served by Dash for downloads
SCRIPTS_FOLDER = "../scripts"

# geoprocessing
buffer_distance = 20  # in meters
intersect_threshold = 0.75
node_width = 3
input_gpkg = "data/temp/rcn_output.gpkg"
multiline_geojson = 'data/geojson/gdf_multiline.geojson'
point_geojson = 'data/geojson/gdf_point.geojson'
multiline_geojson_proj = 'data/geojson/gdf_multiline_projected.geojson'
point_geojson_proj = 'data/geojson/gdf_point_projected.geojson'

# application
progress_state = {
    "pct": 0,
    "processed-file": "",
    "btn-process-disabled": False,
    "btn-download-disabled": False
}
network_geojson = 'data/intermediate/gdf_multiline_simplified.geojson'
color_match = '#f39c12'
color_network = '#7f8c8d'
color_processing = '#343a40'
color_highlight_segment = "red"
color_highlight_node = "purple"
min_zoom_points = 11
initial_center =  [50.65, 4.45]
initial_zoom = 8
date_picker_min_date = datetime.date(2010, 1, 1)
date_picker_max_date = datetime.date.today()
