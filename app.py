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
network_geojson = 'data/intermediate/gdf_multiline.geojson'
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
            dl.LayerGroup(id="layer_group_network", children=[]),
            dl.LayerGroup(id="layer_group_click", children=[])
        ],
        center=initial_center,
        zoom=initial_zoom,
        style={'width': '100%', 'height': '50vh'}
    ),
    html.Div(id="map-center-output")
])

# Zoom-dependent points layer
@app.callback(
    Output('layer_group_points', 'children'),
    Input("map", "zoom")
)
def update_point_layer(zoom):
    children = []
    if zoom >= min_zoom_points:
        children.append(
            dl.GeoJSON(
                data=geojson_points,
                children=[dl.Tooltip(content="This is a <b>bike node<b/>")]
            )
        )
    return children

# Checklist-based network layer
@app.callback(
    Output('layer_group_network', 'children'),
    Input('toggle_network', 'value')
)
def toggle_network_layer(selected):
    if "network" in selected:
        return [
            dl.GeoJSON(
                data=geojson_network,
                options=dict(style=dict(color=color_network, weight=1, opacity=0.7))
            )
        ]
    return []

# Add test marker
@app.callback(
    Output("layer_group_click", "children"),
    Input("btn_process", "n_clicks")
)
def add_initial_center(n_clicks):
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
