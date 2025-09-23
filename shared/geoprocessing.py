from shared.common import *
from shapely.geometry import Point, LineString, MultiLineString
import shutil
import zipfile
import gpxpy
import psutil

buffer_distance = 20  # in meters
intersect_threshold = 0.75

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
    # Step 1: Read and parse GPX file (specify encoding to avoid errors)
    with open(gpx_file_path, 'r', encoding='utf-8-sig') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
    
    # Extract GPX metadata (file name and modification time)
    gpx_name = os.path.basename(gpx_file_path)

    # Extract track segments as LineStrings
    line_segments = []
    for track in gpx.tracks:
        for segment in track.segments:
            track_points = [(point.longitude, point.latitude) for point in segment.points]
            # Ensure the segment has more than one point
            if len(track_points) > 1:  
                line_segments.append(LineString(track_points))

    # Convert to a MultiLineString if there are multiple segments
    if len(line_segments) > 1:
        print("Converting to MultiLineString")
        multi_line = MultiLineString(line_segments)
    else:
        # Just a LineString if there's only one segment
        multi_line = line_segments[0]
    
    # Create a GeoDataFrame in EPSG:4326 (WGS 84)
    gdf = gpd.GeoDataFrame(geometry=[multi_line], crs="EPSG:4326")

    # Reproject to Belgian Lambert 2008
    gdf_gpx = gdf.to_crs("EPSG:3812")
    
    # Extract activity date (only if timestamps are present → recorded activity)
    start_time = None
    if gpx.tracks and gpx.tracks[0].segments and gpx.tracks[0].segments[0].points:
        start_time = gpx.tracks[0].segments[0].points[0].time

    # Use date if timestamp exists, otherwise None
    gpx_time = start_time.date() if start_time else None

    # Skip further processing if no activity date (not a recorded activity)
    if gpx_time is None:
        print(f"Warning ({gpx_name}): no timestamps found → GPX is not a recorded activity, skipping.")
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()

    # Step 2: Buffer GPX track and find intersections with bike network
    buffered_gpx = gdf_gpx.copy()
    buffered_gpx['geometry'] = buffered_gpx['geometry'].buffer(buffer_distance)
    bike_segments_matched = bike_network[bike_network.intersects(buffered_gpx.geometry.iloc[0])]
    
    if bike_segments_matched.empty:
        print(f"Warning ({gpx_name}): no bike network segments intersect the GPX track, skipping.")
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()  # Return empty GeoDataFrames
    
    # Inner function to calculate overlap
    def calculate_overlap(segment):
        intersection = segment.geometry.intersection(buffered_gpx.geometry.iloc[0])
        return intersection.length / segment.geometry.length

    # Step 3: Filter based on the overlap threshold
    bike_segments_matched = bike_segments_matched.assign(
        overlap_percentage=bike_segments_matched.apply(calculate_overlap, axis=1))

    filtered_segments = bike_segments_matched[bike_segments_matched['overlap_percentage'] 
                                              >= intersect_threshold].copy()

    if filtered_segments.empty:
        print(f"Warning ({gpx_name}): matched segments found, but none exceeded the overlap threshold ({intersect_threshold:.0%}), skipping.")
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()  # Return empty GeoDataFrames

    # Step 4: Extract unique nodes from the matched segments
    unique_nodes = set(filtered_segments["osm_id_from"].tolist() + 
                       filtered_segments["osm_id_to"].tolist())
    
    # Step 5: Filter point GeoDataFrame (bike nodes) based on unique nodes from GPX match
    matched_nodes = point_geodf[point_geodf['osm_id'].isin(unique_nodes)].copy()

    # Step 6: Add GPX metadata
    filtered_segments["gpx_name"] = gpx_name
    filtered_segments["gpx_date"] = gpx_time
    matched_nodes["gpx_name"] = gpx_name
    matched_nodes["gpx_date"] = gpx_time
    
    # Step 7: Filter matched_nodes to only those actually used in this GPX file
    used_nodes = pd.concat([
        filtered_segments[['gpx_name', 'osm_id_from']].rename(columns={'osm_id_from': 'osm_id'}),
        filtered_segments[['gpx_name', 'osm_id_to']].rename(columns={'osm_id_to': 'osm_id'})
    ]).dropna()

    matched_nodes = matched_nodes.merge(used_nodes, 
                                        left_on=['gpx_name', 'osm_id'], 
                                        right_on=['gpx_name', 'osm_id'])

    return filtered_segments, matched_nodes

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
    zip_folder = os.path.join(UPLOAD_FOLDER, "unzipped_gpx")
    if os.path.exists(zip_folder):
        shutil.rmtree(zip_folder)
    os.makedirs(zip_folder, exist_ok=True)

    # Unzip the GPX files
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(zip_folder)

    # Initialize empty GeoDataFrames for segments and nodes
    all_segments = gpd.GeoDataFrame()
    all_nodes = gpd.GeoDataFrame()

    # Loop through each GPX file in the unzipped folder
    gpx_files = [f for f in os.listdir(zip_folder) if f.endswith(".gpx")]
    total = len(gpx_files)

    for i, gpx_file in enumerate(gpx_files, start=1):
        # process = psutil.Process(os.getpid())
        # print(f"Memory usage: {process.memory_info().rss / 1024**2:.2f} MB")
        if gpx_file.endswith(".gpx"):
            progress_state["processed-file"] = f"Processing: {gpx_file}"

            gpx_file_path = os.path.join(zip_folder, gpx_file)

            # Process each GPX file
            bike_segments, matched_nodes = process_gpx_file(gpx_file_path, bike_network, point_geodf)

            # Append results to the combined GeoDataFrames
            all_segments = gpd.GeoDataFrame(pd.concat([all_segments, bike_segments], ignore_index=True))
            all_nodes = gpd.GeoDataFrame(pd.concat([all_nodes, matched_nodes], ignore_index=True))

            # Update progress for polling
            pct = round(i / total * 100)
            progress_state["pct"] = pct
    
    print("Processing done!")

    # Temporary print: show all segments where osm_id_from or osm_id_to is None
    null_osm_rows = all_segments[
        all_segments['osm_id_from'].isnull() | all_segments['osm_id_to'].isnull()
    ]
    if not null_osm_rows.empty:
        print(f"\nOVERVIEW: Segments with missing OSM IDs:")
        print(null_osm_rows[['gpx_name', 'gpx_date', 'ref', 'node_from', 'node_to', 'osm_id_from', 'osm_id_to']])

    return all_segments, all_nodes

def create_result_zip(segments_path, nodes_path):
    """
    Zip the two GeoJSON result files and return the zip file path.
    """
    zip_path = os.path.join(RES_FOLDER, "matched_results.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(segments_path, arcname="all_matched_segments_wgs84.geojson")
        zf.write(nodes_path, arcname="all_matched_nodes_wgs84.geojson")
    return zip_path
