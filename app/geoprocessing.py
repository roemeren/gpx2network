from core.common import *
from shapely.geometry import LineString, MultiLineString
import shutil
import zipfile
import gpxpy
from concurrent.futures import ProcessPoolExecutor, as_completed
# import time # for testing optimization: start/stop = time.time() (in s)

# --- geoprocessing parameters --- 
buffer_distance = 20  # in meters
intersect_threshold = 0.75

# --- concurrency parameters ---
# Minimum number of files before we even consider parallel parsing
PARALLEL_MIN_FILES = 20
# Minimum number of logical CPU cores required to enable parallel parsing (local only)
PARALLEL_MIN_CORES = 2

# --- helper function at module level (picklable) ---
def parse_single_gpx(gpx_file, zip_folder):
    gpx_path = os.path.join(zip_folder, gpx_file)
    with open(gpx_path, 'r', encoding='utf-8-sig') as fh:
        gpx = gpxpy.parse(fh)

    start_time = None
    if gpx.tracks and gpx.tracks[0].segments and gpx.tracks[0].segments[0].points:
        start_time = gpx.tracks[0].segments[0].points[0].time
    gpx_date = start_time.date() if start_time else None
    if gpx_date is None:
        return None

    line_segments = []
    for track in gpx.tracks:
        for seg in track.segments:
            pts = [(p.longitude, p.latitude) for p in seg.points]
            if len(pts) > 1:
                line_segments.append(LineString(pts))

    if not line_segments:
        return None

    geom = MultiLineString(line_segments) if len(line_segments) > 1 else line_segments[0]
    return {"gpx_name": os.path.basename(gpx_file), "gpx_date": gpx_date, "geometry": geom}

# --- main function ---
def process_gpx_zip(zip_file_path, bike_network, point_geodf):
    """
    Process a ZIP archive of GPX files and match tracks with a bike network.

    This function unzips the GPX files, parses each track into geometries,
    buffers them, calculates overlap with the bike network segments, filters
    segments exceeding the overlap threshold, and extracts corresponding bike nodes.

    Progress updates are written to `progress_state` throughout the steps.

    Uses sequential parsing for a small number of files and parallel parsing
    for larger ZIPs to improve performance.

    Args:
        zip_file_path (str): Path to the ZIP file containing GPX files.
        bike_network (GeoDataFrame): GeoDataFrame of bike network segments.
        point_geodf (GeoDataFrame): GeoDataFrame of bike nodes.

    Returns:
        tuple:
            GeoDataFrame: Matched bike network segments with GPX metadata.
            GeoDataFrame: Matched bike nodes corresponding to the segments.
    """

    # --- unzip ---
    zip_folder = os.path.join(UPLOAD_FOLDER, "temp")
    if os.path.exists(zip_folder):
        shutil.rmtree(zip_folder)
    os.makedirs(zip_folder, exist_ok=True)
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(zip_folder)

    # list GPX files
    gpx_files = [f for f in os.listdir(zip_folder) if f.lower().endswith(".gpx")]
    total_files = len(gpx_files)
    if total_files == 0:
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()

    # --- parse GPX files ---
    gpx_rows = []
    # added as environment variable in Render; used to disable parallel processing
    # on the free tier to prevent crashes or memory issues
    IS_RENDER = os.getenv("RENDER") == "true"
    use_parallel = (
        not IS_RENDER
        and os.cpu_count() >= PARALLEL_MIN_CORES
        and total_files >= PARALLEL_MIN_FILES
    )

    if not use_parallel:
        # Sequential parsing
        for i, gpx_file in enumerate(gpx_files, start=1):
            progress_state["current-task"] = f"Parsing GPX files (sequential): {i}/{total_files}"
            progress_state["pct"] = round(i / total_files * 50)
            result = parse_single_gpx(gpx_file, zip_folder)
            if result:
                gpx_rows.append(result)
    else:
        # Parallel parsing
        futures = []
        with ProcessPoolExecutor() as executor:
            for gpx_file in gpx_files:
                futures.append(executor.submit(parse_single_gpx, gpx_file, zip_folder))
            for i, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                if result:
                    gpx_rows.append(result)
                progress_state["current-task"] = f"Parsing GPX files (parallel): {i}/{total_files}"
                progress_state["pct"] = round(i / total_files * 50)

    if not gpx_rows:
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()

    all_gpx_gdf = gpd.GeoDataFrame(gpx_rows, crs="EPSG:4326")

    # --- reproject ---
    progress_state["current-task"] = "Reprojecting GPX geometries to Lambert 2008..."
    progress_state["pct"] = 55
    all_gpx_gdf = all_gpx_gdf.to_crs("EPSG:3812")

    # --- buffer GPX geometries ---
    progress_state["current-task"] = "Buffering GPX geometries..."
    progress_state["pct"] = 60
    all_gpx_gdf["buffer_geom"] = all_gpx_gdf.geometry.buffer(buffer_distance)
    gpx_buffers = all_gpx_gdf.set_geometry("buffer_geom")

    # --- spatial join ---
    progress_state["current-task"] = "Matching all GPX tracks with bike network..."
    progress_state["pct"] = 65
    # keep the buffered geometry as the active geometry
    joined = gpd.sjoin(
        bike_network,
        gpx_buffers[["gpx_name", "gpx_date", "buffer_geom"]].set_geometry("buffer_geom"),
        how="inner",
        predicate="intersects"
    )

    if joined.empty:
        progress_state["current-task"] = "No intersections found."
        progress_state["pct"] = 100
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()

    joined = joined.reset_index()
    joined = joined.merge(
        all_gpx_gdf[["buffer_geom", "gpx_name", "gpx_date"]],
        left_on="index_right", right_index=True, suffixes=("", "_gpx")
    )

    # --- intersection lengths ---
    progress_state["current-task"] = "Calculating intersection lengths..."
    progress_state["pct"] = 75
    joined["segment_length"] = joined.geometry.length
    joined["intersection_geom"] = joined.geometry.intersection(joined["buffer_geom"])
    joined["intersection_length"] = joined["intersection_geom"].length.fillna(0)
    mask = joined["segment_length"] > 0
    joined["overlap_percentage"] = 0.0
    joined.loc[mask, "overlap_percentage"] = (
        (joined.loc[mask, "intersection_length"] / joined.loc[mask, "segment_length"]).clip(0, 1)
    )

    # --- filter and drop extra columns ---
    mask = joined["overlap_percentage"] >= intersect_threshold
    drop_cols = [
        "index", "index_right", "buffer_geom",
        "gpx_name_gpx", "gpx_date_gpx",
        "segment_length", "intersection_geom", "intersection_length"
    ]

    all_segments = joined.loc[mask].drop(columns=drop_cols, errors="ignore").copy()

    if all_segments.empty:
        print("No segments exceeded threshold.")
        print(100)
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()

    # --- matched nodes ---
    progress_state["current-task"] = "Extracting matched bike nodes..."
    progress_state["pct"] = 90
    nodes_list = []
    for (gpx_name, gpx_date), grp in all_segments.groupby(["gpx_name", "gpx_date"]):
        node_ids = pd.Index(grp["osm_id_from"].tolist() + grp["osm_id_to"].tolist()).dropna().unique().tolist()
        if not node_ids:
            continue
        matched_nodes = point_geodf[point_geodf["osm_id"].isin(node_ids)].copy()
        if matched_nodes.empty:
            continue
        matched_nodes["gpx_name"] = gpx_name
        matched_nodes["gpx_date"] = gpx_date
        nodes_list.append(matched_nodes)

    all_nodes = (
        gpd.GeoDataFrame(pd.concat(nodes_list, ignore_index=True), crs=point_geodf.crs)
        if nodes_list
        else gpd.GeoDataFrame(columns=list(point_geodf.columns) + ["gpx_name", "gpx_date"])
    )

    progress_state["current-task"] = "Processing done!"
    progress_state["pct"] = 100

    return all_segments, all_nodes

def create_result_zip(segments_path, nodes_path):
    """
    Zip the two GeoJSON result files and return the zip file path.
    """
    zip_name = "matched_results.zip"
    zip_path = os.path.join(STATIC_FOLDER, zip_name)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(segments_path, arcname="all_matched_segments_wgs84.geojson")
        zf.write(nodes_path, arcname="all_matched_nodes_wgs84.geojson")
    
    return zip_name
