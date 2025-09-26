from core.common import *
from shapely.geometry import LineString, MultiLineString
import shutil
import zipfile
import psutil
from lxml import etree
from concurrent.futures import ProcessPoolExecutor, as_completed
# import time # for testing optimization: start/stop = time.time() (in s)

# --- geoprocessing parameters --- 
buffer_distance = 20  # in meters
intersect_threshold = 0.75

# --- concurrency parameters ---
# Minimum number of files before we even consider parallel processing (local only)
PARALLEL_MIN_FILES = 20
# Minimum number of logical CPU cores required to enable parallel processing (local only)
PARALLEL_MIN_CORES = 2

# -- application parameters --
progress_state = {}

def process_gpx_file(gpx_file_path, bike_network, point_geodf):
    """
    Extracts and matches GPX track segments and nodes with a bike network.

    This function reads a GPX file, converts its tracks into geometries, 
    buffers them, and intersects with a given bike network to identify 
    matching segments. It also filters bike nodes corresponding to 
    matched segments and stores the unique OSM node IDs for each segment.

    Args:
        gpx_file_path (str): Path to the GPX file.
        bike_network (GeoDataFrame): GeoDataFrame of bike network segments.
        point_geodf (GeoDataFrame): GeoDataFrame of bike nodes.

    Returns:
        tuple:
            GeoDataFrame: Filtered bike network segments matched with the GPX track, 
                          including 'gpx_name', 'gpx_date', and the unique node 
                          identifiers 'osm_id_from' and 'osm_id_to'.
            GeoDataFrame: Matched bike nodes corresponding to the segments, 
                          including 'gpx_name' and 'gpx_date'.
    """
    tree = etree.parse(gpx_file_path)
    root = tree.getroot()

    ns = {"gpx": "http://www.topografix.com/GPX/1/1"}  # GPX namespace

    # Extract activity type
    type_elem = root.find(".//gpx:type", namespaces=ns)
    activity_type = type_elem.text if type_elem is not None else None

    # Extract GPX name
    gpx_name = os.path.basename(gpx_file_path)

    # Extract start time (first track point)
    time_elem = root.find(".//gpx:trk/gpx:trkseg/gpx:trkpt/gpx:time", namespaces=ns)
    gpx_date = None
    gpx_time = None
    if time_elem is not None:
        start_time = pd.to_datetime(time_elem.text, utc=True)
        gpx_date = start_time.date()
        gpx_time = start_time  # full timestamp including time

    # Extract start time
    time_elem = root.find(".//gpx:trk/gpx:trkseg/gpx:trkpt/gpx:time", namespaces=ns)
    gpx_date = None
    if time_elem is not None:
        gpx_date = pd.to_datetime(time_elem.text, utc=True).date()

    # Extract line segments
    line_segments = []
    for seg in root.findall(".//gpx:trk/gpx:trkseg", namespaces=ns):
        pts = [(float(p.attrib["lon"]), float(p.attrib["lat"]))
               for p in seg.findall("gpx:trkpt", namespaces=ns)]
        if len(pts) > 1:
            line_segments.append(LineString(pts))

    if not line_segments or gpx_date is None:
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()

    multi_line = MultiLineString(line_segments) if len(line_segments) > 1 else line_segments[0]
    res =  {
        "gpx_name": os.path.basename(gpx_file_path),
        "gpx_date": gpx_date,
        "geometry": multi_line,
        "activity_type": activity_type
    }

    # Create a GeoDataFrame in EPSG:4326 (WGS 84)
    gdf = gpd.GeoDataFrame([res], crs="EPSG:4326")

    # Reproject to Belgian Lambert 2008
    gdf_gpx = gdf.to_crs("EPSG:3812")
    
    # Skip further processing if no activity date (not a recorded activity)
    if gpx_time is None:
        # print(f"Warning ({gpx_name}): no timestamps found → GPX is not a recorded activity, skipping.")
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()

    # Step 2: Buffer GPX track and find intersections with bike network
    buffered_gpx = gdf_gpx.copy()
    buffered_gpx['geometry'] = buffered_gpx['geometry'].buffer(buffer_distance)
    bike_segments_matched = bike_network[bike_network.intersects(buffered_gpx.geometry.iloc[0])]
    
    if bike_segments_matched.empty:
        #print(f"Warning ({gpx_name}): no bike network segments intersect the GPX track, skipping.")
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()  # Return empty GeoDataFrames
    
    # Inner function to calculate overlap
    def calculate_overlap(segment):
        intersection = segment.geometry.intersection(buffered_gpx.geometry.iloc[0])
        return intersection.length / segment.geometry.length

    # Step 3: Filter based on the overlap threshold
    bike_segments_matched = bike_segments_matched.assign(
        overlap_percentage=bike_segments_matched.apply(calculate_overlap, axis=1))

    matched_segments = bike_segments_matched[bike_segments_matched['overlap_percentage'] 
                                              >= intersect_threshold].copy()

    if matched_segments.empty:
        #print(f"Warning ({gpx_name}): matched segments found, but none exceeded the overlap threshold ({intersect_threshold:.0%}), skipping.")
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()  # Return empty GeoDataFrames

    # Step 4: Extract unique nodes from the matched segments
    unique_nodes = set(matched_segments["osm_id_from"].tolist() + 
                       matched_segments["osm_id_to"].tolist())
    
    # Step 5: Filter point GeoDataFrame (bike nodes) based on unique nodes from GPX match
    matched_nodes = point_geodf[point_geodf['osm_id'].isin(unique_nodes)].copy()

    # Step 6: Add GPX metadata
    matched_segments["gpx_name"] = gpx_name
    matched_segments["gpx_date"] = gpx_time
    matched_nodes["gpx_name"] = gpx_name
    matched_nodes["gpx_date"] = gpx_time
    
    # Step 7: Filter matched_nodes to only those actually used in this GPX file
    used_nodes = pd.concat([
        matched_segments[['gpx_name', 'osm_id_from']].rename(columns={'osm_id_from': 'osm_id'}),
        matched_segments[['gpx_name', 'osm_id_to']].rename(columns={'osm_id_to': 'osm_id'})
    ]).dropna()

    matched_nodes = matched_nodes.merge(used_nodes, 
                                        left_on=['gpx_name', 'osm_id'], 
                                        right_on=['gpx_name', 'osm_id'])

    return matched_segments, matched_nodes

def process_gpx_zip(zip_file_path, bike_network, point_geodf):
    """
    Processes a ZIP archive of GPX files, extracting and matching tracks and nodes with a bike network.

    This function unzips GPX files, processes each file to extract track segments 
    and corresponding nodes using `process_gpx_file`, and combines the results 
    into unified GeoDataFrames. Optionally, the output can be converted to WGS84.

    Args:
        zip_file_path (str): Path to the ZIP file containing GPX files.
        bike_network (GeoDataFrame): GeoDataFrame of bike network segments.
        point_geodf (GeoDataFrame): GeoDataFrame of bike nodes.

    Returns:
        tuple:
            GeoDataFrame: Combined bike network segments matched with all GPX tracks.
            GeoDataFrame: Combined matched bike nodes corresponding to the segments.
    """
    print("Processing zip file...")
    # Ensure target folder is empty
    zip_folder = os.path.join(UPLOAD_FOLDER, "temp")
    if os.path.exists(zip_folder):
        shutil.rmtree(zip_folder)
    os.makedirs(zip_folder, exist_ok=True)

    # Unzip the GPX files
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(zip_folder)

    # Initialize empty GeoDataFrames for segments and nodes
    all_segments = gpd.GeoDataFrame()
    all_nodes = gpd.GeoDataFrame()

    # List GPX files
    gpx_files = [f for f in os.listdir(zip_folder) if f.lower().endswith(".gpx")]
    total_files = len(gpx_files)
    if total_files == 0:
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()
    
    # Loop through each GPX file in the unzipped folder
    seg_rows = []
    node_rows = []
    # added as environment variable in Render; used to disable parallel processing
    # on the free tier to prevent crashes or memory issues
    IS_RENDER = os.getenv("RENDER") == "true"
    use_parallel = (
        not IS_RENDER
        and os.cpu_count() >= PARALLEL_MIN_CORES
        and total_files >= PARALLEL_MIN_FILES
    )

    if not use_parallel:
        # Sequential procssing
        for i, gpx_file in enumerate(gpx_files, start=1):
            gpx_file_path = os.path.join(zip_folder, gpx_file)
            progress_state["show-dots"] = False
            progress_state["current-task"] = f"Processing GPX files (sequential): {i}/{total_files}"
            progress_state["pct"] = round(i / total_files * 100)
            matched_segments, matched_nodes = process_gpx_file(gpx_file_path, bike_network, point_geodf)
            if not matched_segments.empty:
                seg_rows.append(matched_segments)
            if not matched_nodes.empty:
                node_rows.append(matched_nodes)
    else:
        # Parallel processing
        futures = []
        with ProcessPoolExecutor() as executor:
            for gpx_file in gpx_files:
                gpx_file_path = os.path.join(zip_folder, gpx_file)
                futures.append(executor.submit(process_gpx_file, gpx_file_path, bike_network, point_geodf))
            for i, future in enumerate(as_completed(futures), start=1):
                matched_segments, matched_nodes = future.result()
                if not matched_segments.empty:
                    seg_rows.append(matched_segments)
                if not matched_nodes.empty:
                    node_rows.append(matched_nodes)
                # Update progress only after each file finishes
                progress_state["current-task"] = f"Processing GPX files (parallel): {i}/{total_files}"
                progress_state["pct"] = round(i / total_files * 100)

    if not seg_rows:
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()

    # convert to single DataFrame
    all_segments = gpd.GeoDataFrame(pd.concat(seg_rows, ignore_index=True))
    all_nodes = gpd.GeoDataFrame(pd.concat(node_rows, ignore_index=True))
    
    print("Processing done!")

    # # Temporary print: show all segments where osm_id_from or osm_id_to is None
    # null_osm_rows = all_segments[
    #     all_segments['osm_id_from'].isnull() | all_segments['osm_id_to'].isnull()
    # ]
    # if not null_osm_rows.empty:
    #     print(f"\nOVERVIEW: Segments with missing OSM IDs:")
    #     print(null_osm_rows[['gpx_name', 'gpx_date', 'ref', 'node_from', 'node_to', 'osm_id_from', 'osm_id_to']])

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
