from core.common import *
from app.geoprocessing import *
from app.utils import *
import json
import base64
import threading
import datetime
from dash import no_update, Dash, html, dcc, Output, Input, State, dash_table
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash.exceptions import PreventUpdate

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

# Ensure static folder exists
os.makedirs(STATIC_FOLDER, exist_ok=True)

# Load bike network GeoDataFrames (for processing)
bike_network_seg = gpd.read_parquet(multiline_parquet_proj)
bike_network_node = gpd.read_parquet(point_parquet_proj)

# Load simplified bike network GeoJSON lines (for mapping)
with open(multiline_geojson , "r") as f:
   geojson_network = json.load(f)

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

# Check memory usage before processing
process = psutil.Process(os.getpid())
print(f"Memory usage after initializing application: {process.memory_info().rss / 1024**2:.2f} MB")

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
                    dbc.Button("Process ZIP", id="btn-process", color="primary", className="mb-2", disabled=False),
                    dbc.Progress(id="progress", value=0, striped=True, animated=True, className="mb-2"),
                    html.Div(
                        id="processing-status",
                        style={
                            "padding": "5px 10px",
                            "borderRadius": "5px",
                            "fontFamily": "monospace",
                            "color": color_processing,
                            "fontSize": "0.95rem"
                        }
                    ),
                    html.Div(id="load-status"),
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
                    # --- Show data and app version ---
                    html.Div(f"Data version: {get_data_version()} (source: Geofabrik)", style={"fontSize": "12px", "color": "#666", "marginTop": "10px"}),
                    html.Div(f"App version: {get_latest_git_tag()}", style={"fontSize": "12px", "color": "#666"}),
                    # hidden polling interval
                    dcc.Interval(id="progress-poller", interval=2000, disabled=True),
                    dcc.Store(id="dummy-store"),
                    # store matched segments and nodes
                    dcc.Store(id="geojson-store-full", data={}),
                    # store filtered & aggregated matched segments and nodes
                    dcc.Store(id="geojson-store-filtered", data={})
                ],
                width=3
            ),

            # Right panel
            dbc.Col(
                [
                    # KPI row
                    dbc.Row([
                        dbc.Col(dbc.Card(dbc.CardBody([
                            html.H5("No. Matched Nodes"),
                            html.H2(id="kpi-totnodes", children="–"),
                            html.Div(
                                f"out of {len(bike_network_node)}",
                                style={"fontSize": "12px", "color": "#666", "marginTop": "2px"}
                            )
                        ])), width=4),
                        dbc.Col(dbc.Card(dbc.CardBody([
                            html.H5("No. Matched Segments"),
                            html.H2(id="kpi-totsegments", children="–"),
                            html.Div(
                                f"out of {len(bike_network_seg)}",
                                style={"fontSize": "12px", "color": "#666", "marginTop": "2px"}
                            )
                        ])), width=4),
                        dbc.Col(dbc.Card(dbc.CardBody([
                            html.H5("Total Matched Segment Length (km)"),
                            html.H2(id="kpi-totlength", children="–"),
                            html.Div(
                                f"out of {bike_network_seg['length_km'].sum():.0f} km",
                                style={"fontSize": "12px", "color": "#666", "marginTop": "2px"}
                            )
                        ])), width=4),
                    ], className="mb-3"),
                    # Controls row
                    dbc.Row([
                        dbc.Col(
                            dbc.Button("Recenter Map", id="reset-map-btn", color="secondary", style={"marginLeft": "20px"}),
                            width="auto",
                            style={"display": "flex", "alignItems": "center"}
                        ),
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
                                dbc.Label("End Date", html_for="end-date-picker"),
                                dcc.DatePickerSingle(
                                    id="end-date-picker",
                                    date=date_picker_max_date,
                                    display_format="DD/MM/YYYY",
                                    month_format="MMMM YYYY",
                                    style={"height": "40px", "zIndex": 9999, "position": "relative"}
                                )
                            ]),
                            width="3",
                            # zIndex and position ensure the calendar popup is on top of the map
                            style={"marginLeft": "20px", "height": "40px", "zIndex": 9999, "position": "relative"}
                        ),
                        dbc.Col(
                            html.Div([
                                dbc.Label("Cluster Radius", html_for="cluster-radius-slider"),
                                dcc.Slider(
                                    id="cluster-radius-slider",
                                    min=20,
                                    max=300,
                                    step=10,
                                    value=100,
                                    marks={i: str(i) for i in range(20, 301, 50)},
                                    tooltip={"always_visible": True}
                                )
                            ]),
                            width="3"
                        )
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
                            dl.LayerGroup(id="layer-segments"),
                            dl.LayerGroup(id="layer-nodes"),
                            # Highlighted segments
                            dl.LayerGroup(id="layer-selected-segments"),
                            # Highlighted segments from nodes
                            dl.LayerGroup(id="layer-selected-nodes")           
                        ],
                        id="map"
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H4("Aggregated Segment Statistics"),
                                    html.P(
                                        "Select one or more segments in the table to highlight them on the map (in red).",
                                        style={"fontStyle": "italic", "color": "#555", "marginTop": "5px"}
                                    ),
                                    dash_table.DataTable(
                                        id="table-segments-agg",
                                        columns=[],
                                        data=[],
                                        page_size=25,
                                        row_selectable="multi", # <-- enable row selection
                                        style_table={
                                            'maxHeight': '400px', # adjust height as needed
                                            'overflowY': 'auto',
                                            'overflowX': 'auto'
                                        },
                                        style_cell={
                                            'textAlign': 'left',
                                            'padding': '5px',
                                            'minWidth': '80px',
                                            'width': '150px',
                                            'maxWidth': '200px'
                                        },
                                        fixed_rows={'headers': True},
                                        sort_action='native'
                                    )
                                ],
                                width=6,
                                style={"paddingRight": "10px"}  # add space to the right
                            ),
                            dbc.Col(
                                [
                                    html.H4("Aggregated Node Statistics"),
                                    html.P(
                                        "Select one or more nodes in the table to highlight their segments on the map (in blue).",
                                        style={"fontStyle": "italic", "color": "#555", "marginTop": "5px"}
                                    ),
                                    dash_table.DataTable(
                                        id="table-nodes-agg",
                                        columns=[],
                                        data=[],
                                        page_size=25,
                                        row_selectable="multi", # <-- enable row selection
                                        style_table={
                                            'maxHeight': '400px',  # same height as segments table
                                            'overflowY': 'auto',
                                            'overflowX': 'auto'
                                        },
                                        style_cell={
                                            'textAlign': 'left',
                                            'padding': '5px',
                                            'minWidth': '80px',
                                            'width': '150px',
                                            'maxWidth': '200px'
                                        },
                                        fixed_rows={'headers': True},
                                        sort_action='native'
                                    )
                                ],
                                width=6,
                                style={"paddingLeft": "10px"}   # add space to the left
                            )
                        ],
                        className="mt-4"
                    )
                ],
                width=9
            )
        ])
    ],
    fluid=True
)

# ---------- Callbacks ----------
processing_thread = None  # thread reference

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
    Output("load-status", "children"),
    Input("btn-process", "n_clicks"),
    State("upload-zip", "filename"),
    prevent_initial_call=True
)
def process_zip(_, filename):
    if not filename:
        raise PreventUpdate

    zip_file_path = os.path.join(UPLOAD_FOLDER, filename)
    progress_state["pct"] = 0
    progress_state["btn-process-disabled"] = True
    progress_state["btn-download-disabled"] = True
    progress_state["processed-file"] = f"Processing {filename}..."

    def worker():
        progress_state["running"] = True
        all_segments, all_nodes = process_gpx_zip(zip_file_path, bike_network_seg, bike_network_node)

        all_segments = all_segments.to_crs(epsg=4326) if not all_segments.empty else gpd.GeoDataFrame()
        all_nodes = all_nodes.to_crs(epsg=4326) if not all_nodes.empty else gpd.GeoDataFrame()

        segments_file_path = os.path.join(STATIC_FOLDER, "all_matched_segments_wgs84.geojson")
        nodes_file_path = os.path.join(STATIC_FOLDER, "all_matched_nodes_wgs84.geojson")
        all_segments.to_file(segments_file_path, driver="GeoJSON")
        all_nodes.to_file(nodes_file_path, driver="GeoJSON")

        zip_name = create_result_zip(segments_file_path, nodes_file_path)

        # Only update store when processing is done
        progress_state["store_data"] = {
            "segments": all_segments.__geo_interface__,
            "nodes": all_nodes.__geo_interface__,
            # must be relative to app root here for Dash download link
            "download_href": os.path.join("static", zip_name)
        }
        progress_state["pct"] = 100
        progress_state["btn-process-disabled"] = False
        progress_state["btn-download-disabled"] = False
        progress_state["processed-file"] = f"Finished processing {filename}"
        # disable polling
        progress_state["running"] = False

    global processing_thread
    processing_thread = threading.Thread(target=worker)
    processing_thread.start()

    # no need to return anything, only used for triggering polling
    return ""

@app.callback(
    Output("progress", "value"),
    Output("progress", "label"),
    Output("progress-poller", "disabled"),
    Output("processing-status", "children"),
    Output("btn-process", "disabled"),
    Output("btn-download", "disabled"),
    Output("btn-download", "href"),
    Output("btn-download", "style"),
    Output("geojson-store-full", "data"),
    Input("progress-poller", "n_intervals"),
    Input("load-status", "children"),
    prevent_initial_call=True
)
def update_progress(*_):
    pct = progress_state.get("pct", 0)
    processed_file = progress_state.get("processed-file", "")
    btn_disabled = progress_state.get("btn-process-disabled", False)
    btn_download_disabled = progress_state.get("btn-download-disabled", True)
    # only stop polling when the processing thread has effectively finished
    poller_disabled = not progress_state.get("running", True)
    label = f"{pct}%" if pct >= 5 else ""
    href = progress_state.get("store_data", {}).get("download_href")
    style = {"display": "block"} if pct >= 100 else {"display": "none"}

    # Only update store when ready
    store_data = progress_state.get("store_data") if pct >= 100 else no_update

    return pct, label, poller_disabled, processed_file, btn_disabled, btn_download_disabled, href, style, store_data

@app.callback(
    Output("kpi-totsegments", "children"),
    Output("kpi-totnodes", "children"),
    Output("kpi-totlength", "children"),
    Output("geojson-store-filtered", "data"),
    Input("geojson-store-full", "data"),
    Input("start-date-picker", "date"),
    Input("end-date-picker", "date"),
)
def filter_data(store, start_date, end_date):
    """Filter bike segments and nodes by date and compute KPIs.

    Args:
        store (dict): Original GeoJSON data with 'segments' and 'nodes'.
        start_date (str): Start date (YYYY-MM-DD), defaults to earliest date.
        end_date (str): End date (YYYY-MM-DD), defaults to latest date.

    Returns:
        tuple: (total_segments, total_nodes, total_length, filtered GeoJSON dict)
    """
    if not store or not store.get("segments", {}).get("features"):
        return None, None, None, {}

    gdf_segments = gpd.GeoDataFrame.from_features(store["segments"]["features"])
    gdf_nodes = gpd.GeoDataFrame.from_features(store["nodes"]["features"])

    gdf_segments["gpx_date"] = pd.to_datetime(gdf_segments["gpx_date"]).dt.date
    gdf_nodes["gpx_date"] = pd.to_datetime(gdf_nodes["gpx_date"]).dt.date

    try:
        start = pd.to_datetime(start_date).date() if start_date else gdf_segments["gpx_date"].min()
        end = pd.to_datetime(end_date).date() if end_date else gdf_segments["gpx_date"].max()
    except Exception:
        return None, None, None, {}

    seg_mask = (gdf_segments["gpx_date"] >= start) & (gdf_segments["gpx_date"] <= end)
    node_mask = (gdf_nodes["gpx_date"] >= start) & (gdf_nodes["gpx_date"] <= end)

    gdf_segments_filtered = gdf_segments.loc[seg_mask]
    gdf_nodes_filtered = gdf_nodes.loc[node_mask]

    # Helper function for building tooltip
    def build_tooltip(label_prefix, label_value, kpi_dict):
        # First line: prefix in light grey, value in black and larger font
        tooltip_lines = [
            f'<span style="color: #999; font-size: 14px;">{label_prefix}</span>'
            f'<span style="color: #000; font-size: 16px; font-weight: bold;">{label_value}</span>'
            '<br>'  # simple line break for spacing
        ]
        
        # KPI lines in smaller font
        for kpi_name, kpi_value in kpi_dict.items():
            tooltip_lines.append(
                f'<span style="color: #999; font-size: 11px;">{kpi_name}: </span>'
                f'<b style="color: #000; font-size: 11px;">{kpi_value}</b>'
            )
        return "<br>".join(tooltip_lines)

    # -- Aggregate segments --
    gdf_segments_filtered["gpx_date"] = pd.to_datetime(gdf_segments_filtered["gpx_date"])
    agg_seg = gdf_segments_filtered.groupby((["ref", "osm_id", "osm_id_from", "osm_id_to"])).agg(
        length_km=("length_km", "max"),
        count_gpx=("gpx_name", "nunique"),
        max_overlap_percentage=("overlap_percentage", "max"),
        first_date=("gpx_date", "min"),
        last_date=("gpx_date", "max"),
        # preserve geometry
        geometry=("geometry", "first")
    ).reset_index()
    agg_seg = gpd.GeoDataFrame(agg_seg, geometry="geometry", crs=gdf_segments_filtered.crs)

    # Apply formatting and sort result
    agg_seg["length_km"] = agg_seg["length_km"].round(2)
    agg_seg["max_overlap_percentage"] = agg_seg["max_overlap_percentage"].round(2)
    agg_seg["first_date"] = agg_seg["first_date"].dt.strftime("%Y-%m-%d")
    agg_seg["last_date"] = agg_seg["last_date"].dt.strftime("%Y-%m-%d")
    agg_seg = agg_seg.sort_values("count_gpx", ascending=False)

    # Add tooltip
    agg_seg["tooltip"] = agg_seg.apply(
        lambda row: build_tooltip(
            "segment ",
            row["ref"],
            {
                "Visits (GPX)": row["count_gpx"],
                "First visit": row["first_date"],
                "Last visit": row["last_date"],
                "Length (km)": f'{row["length_km"]:.1f}',
                "Best match (%)": f'{100*row["max_overlap_percentage"]:.0f}%'
            }
        ),
        axis=1
    )

    # -- Aggregate nodes --
    gdf_nodes_filtered["gpx_date"] = pd.to_datetime(gdf_nodes["gpx_date"])
    agg_nodes = gdf_nodes_filtered.groupby(["rcn_ref", "osm_id"]).agg(
        count_gpx=("gpx_date", "nunique"),
        first_date=("gpx_date", "min"),
        last_date=("gpx_date", "max"),
        # preserve geometry
        geometry=("geometry", "first")
    ).reset_index()
    agg_nodes = gpd.GeoDataFrame(agg_nodes, geometry="geometry", crs=gdf_nodes_filtered.crs)

    # Apply formatting and sort result
    agg_nodes["first_date"] = agg_nodes["first_date"].dt.strftime("%Y-%m-%d")
    agg_nodes["last_date"] = agg_nodes["last_date"].dt.strftime("%Y-%m-%d")
    agg_nodes = agg_nodes.sort_values("count_gpx", ascending=False)

    # Add tooltip
    agg_nodes["tooltip"] = agg_nodes.apply(
        lambda row: build_tooltip(
            "node ",
            row["rcn_ref"],
            {
                "Visits (GPX)": row["count_gpx"],
                "First visit": row["first_date"],
                "Last visit": row["last_date"],
            }
        ),
        axis=1
    )

    # Calculate KPIs
    total_segments = len(agg_seg)
    total_nodes = len(agg_nodes)
    total_length = round(agg_seg["length_km"].sum(), 2)

    return (
        total_segments,
        total_nodes,
        total_length,
        {
            "segments": agg_seg.__geo_interface__,
            "nodes": agg_nodes.__geo_interface__
        }
    )

@app.callback(
    Output("layer-segments", "children"),
    Input("geojson-store-filtered", "data"),
)
def update_segments(filtered_data):
    """Render filtered bike segments on the map.

    Args:
        filtered_data (dict): Filtered GeoJSON data.

    Returns:
        dl.GeoJSON or None: Segment layer component.
    """
    if not filtered_data:
        return None
    return dl.GeoJSON(
        data=filtered_data["segments"],
        id="geojson-seg",
        options=dict(style=dict(color=color_match, weight=5))
    )

@app.callback(
    Output("layer-nodes", "children"),
    Input("geojson-store-filtered", "data"),
    Input("cluster-radius-slider", "value"),
)
def update_nodes(filtered_data, cluster_radius):
    """Render bike nodes

    Args:
        filtered_data (dict): Filtered and aggregated GeoJSON data.

    Returns:
        dl.GeoJSON or None: Node layer component.
    """
    if not filtered_data:
        return None
    else:
        return dl.GeoJSON(
            data=filtered_data["nodes"],
            cluster=True,
            zoomToBoundsOnClick=True,
            superClusterOptions={"radius": cluster_radius}
        )

@app.callback(
    Output("table-segments-agg", "data"),
    Output("table-segments-agg", "columns"),
    Output("table-nodes-agg", "data"),
    Output("table-nodes-agg", "columns"),
    Input("geojson-store-filtered", "data"),
)
def update_aggregated_tables(filtered_data):
    """Aggregate segment and node data for display in Dash tables.

    Args:
        filtered_data (dict): GeoJSON-like dictionary with "segments" and "nodes" features.

    Returns:
        tuple: 
            seg_data (list[dict]): Aggregated segment records.
            seg_columns (list[dict]): Column definitions for segments table.
            node_data (list[dict]): Aggregated node records.
            node_columns (list[dict]): Column definitions for nodes table.
    """
    if not filtered_data:
        return [], [], [], []
    
    agg_seg = gpd.GeoDataFrame.from_features(filtered_data["segments"]["features"])
    agg_nodes = gpd.GeoDataFrame.from_features(filtered_data["nodes"]["features"])

    # remove the geometry
    agg_seg = agg_seg.drop(columns="geometry")
    agg_nodes = agg_nodes.drop(columns="geometry")

    seg_columns = [{"name": c, "id": c} for c in agg_seg.columns]
    seg_data = agg_seg.to_dict("records")
    node_columns = [{"name": c, "id": c} for c in agg_nodes.columns]
    node_data = agg_nodes.to_dict("records")

    return seg_data, seg_columns, node_data, node_columns

@app.callback(
    Output("browse-info", "children"),
    Input("upload-zip", "contents"), # input required (also in def)
    State('upload-zip', 'filename')
)
def show_info(_, f):
    if f is None:
        return "No file selected"
    return f"Selected file: {f}"

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

@app.callback(
    Output("map", "center"),
    Output("map", "zoom"),
    Output("map", "key"),  # Force the map to fully re-render
    Input("reset-map-btn", "n_clicks"),
    prevent_initial_call=True
)
def reset_map(n_clicks):
    """Recenter the map to its initial center and zoom level.

    Args:
        n_clicks (int): Number of times the recenter button was clicked.

    Returns:
        list, int, str: Default center [lat, lon], default zoom, and updated key.
    """
    return initial_center, initial_zoom, f"map-{n_clicks}"

@app.callback(
    Output("layer-selected-segments", "children"),
    Input("table-segments-agg", "selected_rows"),
    State("table-segments-agg", "data"),
    State("geojson-store-filtered", "data"),
)
def highlight_selected_segments(selected_rows, table_data, filtered_data):
    """Highlight selected segments on the map.

    Filters the segment GeoDataFrame by the selected rows from the
    aggregated table and returns a GeoJSON layer with highlighted
    geometry.

    Args:
        selected_rows (list[int]): Indices of selected rows in the segments table.
        table_data (list[dict]): Data from the aggregated segments table.
        filtered_data (dict): Filtered GeoJSON data containing segments.

    Returns:
        dl.GeoJSON or None: Highlighted GeoJSON layer if matches are found,
        otherwise None.
    """
    if not selected_rows or not filtered_data or "segments" not in filtered_data:
        return None

    # Get all selected 'ref' values
    ref_values = [table_data[i]["osm_id"] for i in selected_rows]

    # Convert filtered segments to GeoDataFrame
    gdf_seg = gpd.GeoDataFrame.from_features(filtered_data["segments"]["features"])

    # Filter for the selected segments
    selected_geom = gdf_seg[gdf_seg["osm_id"].isin(ref_values)]

    if selected_geom.empty:
        return None

    # Return GeoJSON layer for all selected segments
    return dl.GeoJSON(
        data=selected_geom.__geo_interface__,
        options=dict(style=dict(color=color_highlight_segment, weight=6))
    )

@app.callback(
    Output("layer-selected-nodes", "children"),
    Input("table-nodes-agg", "selected_rows"),
    State("table-nodes-agg", "data"),
    State("geojson-store-filtered", "data"),
)
def highlight_segments_from_nodes(selected_node_rows, node_data, filtered_data):
    """Highlight segments connected to selected nodes on the map.

    Uses selected node IDs from the aggregated nodes table to filter
    segments where either endpoint matches, then returns a GeoJSON
    layer with highlighted geometry.

    Args:
        selected_node_rows (list[int]): Indices of selected rows in the nodes table.
        node_data (list[dict]): Data from the aggregated nodes table.
        filtered_data (dict): Filtered and aggregated GeoJSON data containing segments.

    Returns:
        dl.GeoJSON or None: Highlighted GeoJSON layer if matching segments exist,
        otherwise None.
    """
    if not selected_node_rows or not filtered_data or "segments" not in filtered_data:
        return None  # nothing selected

    # Get selected node IDs or refs
    selected_nodes = [node_data[i]["osm_id"] for i in selected_node_rows]

    # Convert filtered segments to GeoDataFrame
    gdf_seg = gpd.GeoDataFrame.from_features(filtered_data["segments"]["features"])

    # Filter segments where node_from or node_to is in selected_nodes
    mask = gdf_seg["osm_id_from"].isin(selected_nodes) | gdf_seg["osm_id_to"].isin(selected_nodes)
    gdf_highlight = gdf_seg[mask]

    if gdf_highlight.empty:
        return None

    # Return GeoJSON layer with blue highlight
    return dl.GeoJSON(
        data=gdf_highlight.__geo_interface__,
        options=dict(style=dict(color=color_highlight_node, weight=5))
    )

if __name__ == '__main__':
    app.run(debug=True)
