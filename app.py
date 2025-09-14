"""
TODO: investigate preloading the network layer and toggle visibility via style
to further reduce rendering time
"""

# Custom icon as per official docs https://leafletjs.com/examples/custom-icons/
import geopandas as gpd
import pandas as pd
import re
import plotly.express as px

import dash
import dash_leaflet as dl
import json
from dash import html, dcc
from dash.dependencies import Input, Output, State

multiline_dissolved_geojson = 'data/processed/all_matched_segments.geojson'
point_geojson = 'data/processed/all_matched_nodes.geojson'
network_geojson = 'data/intermediate/gdf_multiline_simplified.geojson'
min_zoom_points = 11
color_match = '#f39c12'
color_network = '#7f8c8d'

custom_icon = dict(
    iconUrl="https://leafletjs.com/examples/custom-icons/leaf-green.png",
    shadowUrl="https://leafletjs.com/examples/custom-icons/leaf-shadow.png",
    iconSize=[38, 95],
    shadowSize=[50, 64],
    iconAnchor=[22, 94],
    shadowAnchor=[4, 62],
    popupAnchor=[-3, -76],
)

tile_layers = {
    "default": dl.TileLayer(
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution='&copy; <a href="https://www.openstreetmap.org/">OSM</a>'
    ),
    "carto_light": dl.TileLayer(
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attribution='&copy; OSM &copy; <a href="https://carto.com/">CARTO</a>'
    ),
    "carto_dark": dl.TileLayer(
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attribution='&copy; OSM &copy; <a href="https://carto.com/">CARTO</a>'
    ),
    "osm_humanitarian": dl.TileLayer(
        url="https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        attribution='&copy; <a href="https://www.openstreetmap.org/">OSM</a> contributors'
    ),
    "esri_lightgray": dl.TileLayer(
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attribution='Tiles &copy; Esri &mdash; Source: Esri, OSM'
    )    
}

# Load the GeoJSON polyline data directly from a file
with open(multiline_dissolved_geojson, "r") as f:
    geojson_lines = json.load(f)

# Load the GeoJSON point data directly from a file
with open(point_geojson, "r") as f:
    geojson_points = json.load(f)

# Load the GeoJSON network polyline data directly from a file
with open(network_geojson , "r") as f:
   geojson_network = json.load(f)

# Initialization
initial_center =  [50.84606, 4.35213]
initial_zoom = 10

app = dash.Dash(__name__)

app.layout = html.Div([
    html.Div([
        dcc.Upload(
            id='upload_data',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select a File')
            ]),
            style={
                'width': '200px',
                'height': '40px',
                'lineHeight': '40px',
                'borderWidth': '1px',
                'borderStyle': 'dashed',
                'borderRadius': '5px',
                'textAlign': 'center',
                'marginRight': '10px'
            }
        ),
        html.Button("Show initial center", id="btn_process"),
        dcc.Checklist(
            id="toggle_network",
            options=[{"label": "Show Network", "value": "network"}],
            value=[],
            inline=True,
            style={"marginLeft": "20px"}
        )
    ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '10px'}),
    dl.Map(
        id="map",
        children=[
            tile_layers['carto_light'],
            dl.GeoJSON(
                data=geojson_lines, 
                id='geojson_lines',
                options=dict(style=dict(color=color_match, weight=5)),
                children=[dl.Tooltip(content="This is a <b>matched segment<b/>")]
            ),
            dl.LayerGroup(id="layer_group_points", children=[]),
            # Preloaded network layer
            dl.GeoJSON(
                data=geojson_network,
                id='geojson_network',
                # initially hidden
                options=dict(style=dict(color=color_network, weight=1, opacity=0))
            ),
            dl.LayerGroup(id="layer_group_click", children=[])
        ],
        center=initial_center,
        zoom=initial_zoom,
        style={'width': '100%', 'height': '50vh'}
    ),
    html.Div(id="map-center-output")
])

@app.callback(
    Output("map-center-output", "children"),
    Input("map", "zoom"),
    Input("btn_process", "n_clicks"),
    Input("upload_data", "contents"),
    State('upload_data', 'filename')
)
def show_info(zoom, n_clicks, contents, filename):
    """
    Display current map zoom, button click count, and uploaded file name.

    Args:
        zoom (int): Current zoom level of the map.
        n_clicks (int): Number of times the process button has been clicked.
        contents (str or None): Contents of the uploaded file.
        filename (str or None): Name of the uploaded file.

    Returns:
        str: Formatted string showing zoom, number of clicks, and file name.

    Note:
        Dash Leaflet (dl.Map) does not emit zoom or center properties unless they are explicitly initialized.
    """
    try:
        return f"Zoom: {zoom}, Number of clicks: {n_clicks}, File name: {filename}"
    except Exception as e:
        print(f"Error in show_zoom: {e}")
        print(f"zoom: {zoom}")
        return "Error in show_zoom"

@app.callback(
    Output('layer_group_points', 'children'),
    Input("map", "zoom")
)
def update_point_layer(zoom):
    """
    Show or hide the points layer based on the map zoom level.

    Args:
        zoom (int): Current zoom level of the map.

    Returns:
        list: List of Dash Leaflet children for the points LayerGroup.
    """
    children = []
    if zoom >= min_zoom_points:
        children.append(
            dl.GeoJSON(
                data=geojson_points,
                children=[dl.Tooltip(content="This is a <b>bike node<b/>")]
            )
        )
    return children

@app.callback(
    Output('geojson_network', 'options'),
    Input('toggle_network', 'value')
)
def toggle_network_visibility(selected):
    """
    Toggle the visibility of the preloaded network layer based on checklist selection.

    Args:
        selected (list): List of selected values from the network checklist.

    Returns:
        dict: Dash Leaflet style dict updating the layer's opacity.

    Note:
        The network GeoJSON is preloaded and its visibility is toggled by changing
        the opacity, which greatly improves rendering speed compared to dynamically
        adding or removing the layer.
    """
    if 'network' in selected:
        return dict(style=dict(color=color_network, weight=1, opacity=0.7))
    return dict(style=dict(color=color_network, weight=1, opacity=0))

@app.callback(
    Output("layer_group_click", "children"),
    Input("btn_process", "n_clicks")
)
def add_initial_center(n_clicks):
    """
    Add a marker at the map's initial center when the button is clicked.

    Args:
        n_clicks (int): Number of times the button has been clicked.

    Returns:
        list: List containing a single Dash Leaflet Marker placed at the initial center.
    """
    if n_clicks:
        marker = dl.Marker(
            position=initial_center,
            children=dl.Tooltip("This is the map's initial center"),
            id="click_marker",
            icon=custom_icon
        )
        return [marker]

if __name__ == '__main__':
    app.run()
