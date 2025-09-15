# ---------- Imports ----------
import geopandas as gpd
import pandas as pd
import gpxpy
import os
import zipfile
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
import statistics
import threading
from shapely.geometry import LineString, MultiLineString
from datetime import datetime
from dash import html, dcc, Output, Input, State
from dash.exceptions import PreventUpdate

# ---------- Constants ----------
# files and folders
UPLOAD_FOLDER = "data/uploads"
RES_FOLDER = "data/processed"

# processing
buffer_distance = 20  # buffer distance in meters
intersect_threshold = 0.75

# application
progress_state = {"pct": 0, "done": False, "btn-disabled": False}
network_geojson = 'data/intermediate/gdf_multiline_simplified.geojson'
color_match = '#f39c12'
color_network = '#7f8c8d'
min_zoom_points = 11
initial_center =  [50.84606, 4.35213]
initial_zoom = 10