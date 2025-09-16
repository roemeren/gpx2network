from shared.common import *
from shared.geoprocessing import *
from shared.download import *

# Ensure data and caches
pickle_paths = ensure_data()

# Ensure static folder exists
os.makedirs(RES_FOLDER, exist_ok=True)

# Load bike network GeoDataFrame (for processing)
with open(pickle_paths["gdf_multiline_projected.geojson"], "rb") as f:
    bike_network = pickle.load(f)

# Load bike network GeoJSON lines (for mapping)
with open(network_geojson , "r") as f:
   geojson_network = json.load(f)

# Load bike network GeoJSON points (for mapping)
with open(pickle_paths["gdf_point_projected.geojson"], "rb") as f:
    point_geodf = pickle.load(f)

# Other initialization
geojson_points = {}

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# ---------- Layout ----------
app.layout = dbc.Container(
    [
        html.Div([
            html.H1(
                "Belgian Bike Node Network Matcher",
                className="text-center my-2 display-4"
            ),
            html.P(
                "Upload a zip file with your GPX rides and see how they align with Belgium’s bike node network.",
                className="text-center text-muted mb-4"
            )
        ]),

        dbc.Row([
            # Left panel
            dbc.Col(
                [
                    dcc.Upload(
                        id="upload-zip",
                        children=html.Div(["Drag & Drop or ", html.A("Browse for ZIP")]),
                        accept=".zip",
                        multiple=False,
                        style={
                            "width": "100%", "height": "60px", "lineHeight": "60px",
                            "borderWidth": "1px", "borderStyle": "dashed",
                            "borderRadius": "5px", "textAlign": "center",
                            "margin-bottom": "10px"
                        },
                    ),
                    html.Div(id="browse-info"),
                    dbc.Button("Process ZIP", id="btn-process", color="primary", className="mb-2", disabled=True),
                    dbc.Progress(id="progress", value=0, striped=True, animated=True, className="mb-2"),
                    html.Div(id="process-status"),
                    html.Div(
                        dbc.Button(
                            "Download Results",
                            id="btn-download",
                            color="success",
                            className="mt-2",
                            external_link=True,
                            disabled=True,           # initially disabled
                            style={"display": "none"} # initially hidden
                        ),
                        id="download-container"
                    ),
                    # hidden polling interval
                    dcc.Interval(id="progress-poller", interval=500, disabled=True),
                    dcc.Store(id="dummy-store"),
                    # store matched segments and nodes
                    dcc.Store(id="geojson-store", data={})
                ],
                width=3
            ),

            # Right panel
            dbc.Col(
                [
                    # KPI row
                    dbc.Row([
                        dbc.Col(dbc.Card(dbc.CardBody([
                            html.H5("No. Segments"),
                            html.H2(id="kpi-totsegments", children="–")
                        ])), width=4),
                        dbc.Col(dbc.Card(dbc.CardBody([
                            html.H5("No. Nodes"),
                            html.H2(id="kpi-totnodes", children="–")
                        ])), width=4),
                        dbc.Col(dbc.Card(dbc.CardBody([
                            html.H5("Total Length (km)"),
                            html.H2(id="kpi-totlength", children="–")
                        ])), width=4),
                    ], className="mb-3"),
                    # Controls row
                    dbc.Row([
                        dbc.Col(
                            dcc.Checklist(
                                id="toggle-network",
                                options=[{"label": "Show Network", "value": "network"}],
                                value=[],
                                inline=True,
                                style={"marginLeft": "0px", "height": "100%"}
                            ),
                            width="auto",
                            style={"display": "flex", "alignItems": "center"}
                        ),
                        dbc.Col(
                            html.Div([
                                dbc.Label("Start Date", html_for="start-date-picker"),
                                dcc.DatePickerSingle(
                                    id="start-date-picker",
                                    date=date_picker_min_date,
                                    display_format="DD/MM/YYYY",
                                    month_format="MMMM YYYY",
                                    style={"height": "40px", "zIndex": 9999, "position": "relative"}
                                )
                            ]),
                            width="auto",
                            # zIndex and position ensure the calendar popup is on top of the map
                            style={"marginLeft": "20px", "height": "40px", "zIndex": 9999, "position": "relative"}
                        ),
                        dbc.Col(
                            html.Div([
                                dbc.Label("End Date ", html_for="end-date-picker"),
                                dcc.DatePickerSingle(
                                    id="end-date-picker",
                                    date=date_picker_max_date,
                                    display_format="DD/MM/YYYY",
                                    month_format="MMMM YYYY",
                                    style={"height": "40px", "zIndex": 9999, "position": "relative"}
                                )
                            ]),
                            width="auto",
                            # zIndex and position ensure the calendar popup is on top of the map
                            style={"marginLeft": "20px", "height": "40px", "zIndex": 9999, "position": "relative"}
                        ),
                    ], className="mb-2", align="center"),
                    # Map
                    dl.Map(
                        center=initial_center, 
                        zoom=initial_zoom, 
                        style={"width": "100%", "height": "500px"},
                        children=[
                            dl.TileLayer(
                                url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                                attribution='&copy; OSM &copy; <a href="https://carto.com/">CARTO</a>'
                            ),
                            # Preloaded network layer (initially hidden)
                            dl.GeoJSON(
                                data=geojson_network,
                                id='geojson-network',
                                options=dict(style=dict(color=color_network, weight=1, opacity=0))
                            ),
                            # Matched segments & nodes layers (drawn on top of network)
                            dl.LayerGroup(id="layer-group-match"),                     
                        ],
                        id="map"
                    ),
                ],
                width=9
            )
        ])
    ],
    fluid=True
)

# ---------- Callbacks ----------
@app.callback(
    Output("dummy-store", "data"),
    Input("upload-zip", "contents"),
    State("upload-zip", "filename"),
)
def save_uploaded_file(contents, filename):
    if contents is None:
        return True   # keep button disabled

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # decode base64 and save to disk
    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    saved_path = os.path.join(UPLOAD_FOLDER, filename)
    with open(saved_path, "wb") as f:
        f.write(decoded)

    # just needs to return something
    return {"status": "done"}

@app.callback(
    Output("process-status", "children"),
    Output("geojson-store", "data"),
    Output("download-container", "children"),
    Input("btn-process", "n_clicks"),
    State("upload-zip", "filename"),
    prevent_initial_call=True
)
def process_zip(n_clicks, filename):
    # Do nothing if no file is selected
    if not filename:
        print("No file selected!")
        raise PreventUpdate
    
    # Initialize progress
    progress_state["pct"] = 0
    progress_state["btn-process-disabled"] = True
    progress_state["btn-download-disabled"] = True

    zip_file_path = os.path.join(UPLOAD_FOLDER, filename)

    # Call geoprocessing function
    all_segments, all_nodes = process_gpx_zip(zip_file_path, bike_network,
                                              point_geodf)
    
    # Add segment lengths in km
    all_segments["length_km"] = all_segments.geometry.length / 1000.0

    # Convert back to WGS84 for mapping
    all_segments = all_segments.to_crs(epsg=4326) if not all_segments.empty else gpd.GeoDataFrame()
    all_nodes = all_nodes.to_crs(epsg=4326) if not all_nodes.empty else gpd.GeoDataFrame()

    # Save WGS84 results as GeoJSON for further use
    segments_file_path = os.path.join(RES_FOLDER, "all_matched_segments_wgs84.geojson")
    nodes_file_path = os.path.join(RES_FOLDER, "all_matched_nodes_wgs84.geojson")
    all_segments.to_file(segments_file_path, driver="GeoJSON")
    all_nodes.to_file(nodes_file_path, driver="GeoJSON")

    # Create zip of results
    results_zip = create_result_zip(segments_file_path, nodes_file_path)

    # Build a download link
    rel_path = os.path.relpath(results_zip, start="static")
    download_link = dbc.Button(
        "Download Results",
        href=f"/static/{rel_path.replace(os.sep, '/')}",
        color="success",
        className="mt-2",
        external_link=True,
        id="btn-download",
        disabled=False
    )

    # Read files for mapping
    geojson_lines = all_segments.__geo_interface__
    geojson_points = all_nodes.__geo_interface__

    # Re-enable button
    progress_state["btn-process-disabled"] = False
    progress_state["btn-download-disabled"] = False

    return (
        f"Finished processing {filename}",
        {
            "segments": geojson_lines, 
            "nodes": geojson_points,
        },
        download_link
    )

@app.callback(
    Output("kpi-totsegments", "children"),
    Output("kpi-totnodes", "children"),
    Output("kpi-totlength", "children"),
    Output("layer-group-match", "children"),
    Input("geojson-store", "data"),
    Input("start-date-picker", "date"),
    Input("end-date-picker", "date"),
    Input("map", "zoom")
)
def update_kpis(store, start_date, end_date, zoom):
    if not store: return None, None, None, None
    
    # Load segments GeoDataFrame from stored GeoJSON
    gdf_segments = gpd.GeoDataFrame.from_features(store["segments"]["features"])
    gdf_nodes = gpd.GeoDataFrame.from_features(store["nodes"]["features"])

    # Convert gpx_date from str to date
    gdf_segments["gpx_date"] = pd.to_datetime(gdf_segments["gpx_date"], format="%Y-%m-%d").dt.date
    gdf_nodes["gpx_date"] = pd.to_datetime(gdf_nodes["gpx_date"], format="%Y-%m-%d").dt.date

    # Safely parse start/end dates from pickers to datetime
    try:
        start = (
            pd.to_datetime(start_date).date()
            if start_date
            else gdf_segments["gpx_date"].min().date()
        )
        end = (
            pd.to_datetime(end_date).date()
            if end_date
            else gdf_segments["gpx_date"].max().date()
        )
    except Exception:
        # Exit callback early if user is still typing / invalid input
        return None, None, None, None

    # Filter by date range
    mask = (gdf_segments["gpx_date"] >= start) & (gdf_segments["gpx_date"] <= end)
    gdf_segments_filtered = gdf_segments.loc[mask]
    mask = (gdf_nodes["gpx_date"] >= start) & (gdf_nodes["gpx_date"] <= end)
    gdf_nodes_filtered = gdf_nodes.loc[mask]

    # Recompute KPIs
    total_segments = gdf_segments_filtered["osm_id"].nunique()
    total_nodes = gdf_nodes_filtered["osm_id"].nunique()
    total_length = round(
        gdf_segments_filtered.drop_duplicates("osm_id")["length_km"].sum(), 2
    )

    if zoom >= min_zoom_points:
        res_points = dl.GeoJSON(
            data=gdf_nodes_filtered.__geo_interface__,
            children=[dl.Tooltip(content="This is a <b>bike node</b>")]
        )
    else:
        res_points = None

    return (
        total_segments, 
        total_nodes, 
        total_length,
        [dl.GeoJSON(
            data=gdf_segments_filtered.__geo_interface__, 
            id='geojson-seg',
            options=dict(style=dict(color=color_match, weight=5)),
            children=[dl.Tooltip(content="This is a <b>matched segment<b/>")]
        ),
        res_points]
    )

@app.callback(
    Output("progress", "value"),
    Output("progress", "label"),
    Output("progress-poller", "disabled"), # required otherwise no update
    Output("btn-process", "disabled"),
    Output("btn-download", "disabled"),
    Input("progress-poller", "n_intervals")
)
def update_progress(_):
    pct = progress_state.get("pct", 0)
    done = progress_state.get("done", False)
    label = f"{pct}%" if pct >= 5 else ""
    btn_disabled = progress_state.get("btn-process-disabled", False)
    btn_download_disabled = progress_state.get("btn-download-disabled", False)
    return pct, label, done, btn_disabled, btn_download_disabled

@app.callback(
    Output("browse-info", "children"),
    Input("upload-zip", "contents"), # input required (also in def)
    State('upload-zip', 'filename')
)
def show_info(c, f):
    return f"File name: {f}"

@app.callback(
    Output('geojson-network', 'options'),
    Input('toggle-network', 'value')
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
        return dict(style=dict(color=color_network, weight=1, opacity=0.6))
    return dict(style=dict(color=color_network, weight=1, opacity=0))

if __name__ == '__main__':
    app.run(debug=True)
