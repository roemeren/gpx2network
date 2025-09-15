from shared.common import *
from shared.geoprocessing import *
from shared.download import *

# Initialization
initial_center =  [50.84606, 4.35213]
initial_zoom = 10

# Ensure data and caches
pickle_paths = ensure_data()

# Read cached bike network GeoDataFrames
with open(pickle_paths["gdf_multiline_projected.geojson"], "rb") as f:
    bike_network = pickle.load(f)

with open(pickle_paths["gdf_point_projected.geojson"], "rb") as f:
    point_geodf = pickle.load(f)

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
                    # hidden polling interval
                    dcc.Interval(id="progress-poller", interval=500, disabled=True),
                    dcc.Store(id="dummy-store")
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
                            dl.LayerGroup(id="geojson-layer")
                        ],
                        id="map"
                    )
                ],
                width=9
            )
        ])
    ],
    fluid=True
)

# ---------- Callbacks ----------
@app.callback(
    # Output("btn-process", "disabled"),
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
    Output("geojson-layer", "children"),
    Output("kpi-totsegments", "children"),
    Output("kpi-totnodes", "children"),
    Output("kpi-totlength", "children"),
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
    progress_state["btn-disabled"] = True

    zip_file_path = os.path.join(UPLOAD_FOLDER, filename)

    # Call geoprocessing function
    all_segments, all_nodes = process_gpx_zip(zip_file_path, bike_network,
                                              point_geodf)

    # Save results as GeoJSON for further use
    all_segments.to_file(segments_file_path, driver="GeoJSON")
    all_nodes.to_file(nodes_file_path, driver="GeoJSON")

    # Convert back to WGS84 for mapping
    if not all_segments.empty and not all_nodes.empty:
        all_segments_wgs84 = all_segments.to_crs(epsg=4326)
        all_nodes_wgs84 = all_nodes.to_crs(epsg=4326)

    # Read file for mapping
    geojson = all_segments_wgs84.__geo_interface__

    # Compute KPIs using projected coordinates
    total_segments = len(all_segments)
    total_nodes = len(all_nodes)
    total_length = round(all_segments.length.sum()/1000, 2)

    # Re-enable button
    progress_state["btn-disabled"] = False

    return (
        f"Finished processing {filename}",
        [dl.GeoJSON(data=geojson, id="geojson")],
        total_segments,
        total_nodes,
        total_length
    )

@app.callback(
    Output("progress", "value"),
    Output("progress", "label"),
    Output("progress-poller", "disabled"), # required otherwise no update
    Output("btn-process", "disabled"),
    Input("progress-poller", "n_intervals")
)
def update_progress(_):
    pct = progress_state.get("pct", 0)
    done = progress_state.get("done", False)
    label = f"{pct}%" if pct >= 5 else ""
    btn_disabled = progress_state.get("btn-disabled", False)
    return pct, label, done, btn_disabled

@app.callback(
    Output("browse-info", "children"),
    Input("upload-zip", "contents"), # input required (also in def)
    State('upload-zip', 'filename')
)
def show_info(c, f):
    return f"File name: {f}"

if __name__ == '__main__':
    app.run(debug=True)
