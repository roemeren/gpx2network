# ---------- Imports ----------
import geopandas as gpd
import pandas as pd
import pickle
import os
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
from shapely.geometry import LineString, MultiLineString
from dash import html, dcc, Output, Input, State, dash_table
from dash.exceptions import PreventUpdate

# ---------- Constants ----------
# files and folders
UPLOAD_FOLDER = "data/uploads"
RES_FOLDER = "static" # folder for output files, automatically served by Dash for downloads

# processing
buffer_distance = 20  # buffer distance in meters
intersect_threshold = 0.75

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
initial_center =  [50.84606, 4.35213]
initial_zoom = 10
date_picker_min_date = datetime.date(2010, 1, 1)
date_picker_max_date = datetime.date.today()