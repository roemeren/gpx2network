from shared.common import *

def process_gpx_file(gpx_file_path, bike_network, point_geodf):
    """
    Extracts and matches GPX track segments and nodes with a bike network.

    This function reads a GPX file, converts its tracks into geometries, 
    buffers them, and intersects with a given bike network to identify 
    matching segments. It also filters bike nodes corresponding to 
    matched segments.

    Args:
        gpx_file_path (str): Path to the GPX file.
        bike_network (GeoDataFrame): GeoDataFrame of bike network segments.
        point_geodf (GeoDataFrame): GeoDataFrame of bike nodes.

    Returns:
        tuple:
            GeoDataFrame: Filtered bike network segments matched with the GPX track, 
                          including 'gpx_name' and 'gpx_date'.
            GeoDataFrame: Matched bike nodes corresponding to the segments, 
                          including 'gpx_name' and 'gpx_date'.
    """
    # Step 1: Read and parse GPX file (specify encoding to avoid errors)
    with open(gpx_file_path, 'r', encoding='utf-8-sig') as gpx_file:
        gpx = gpxpy.parse(gpx_file)
    
    # Extract GPX metadata (file name and modification time)
    gpx_name = os.path.basename(gpx_file_path)
    modification_time = datetime.fromtimestamp(os.path.getmtime(gpx_file_path)) # NOT A GOOD TIME INDICATOR

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
    
    #Create a GeoDataFrame in EPSG:4326 (WGS 84)
    gdf = gpd.GeoDataFrame(geometry=[multi_line], crs="EPSG:4326")

    # Reproject to Belgian Lambert 2008
    gdf_gpx = gdf.to_crs("EPSG:3812")
    
    # Extract start time (if available)
    start_time = gpx.tracks[0].segments[0].points[0].time if gpx.tracks else None
    gpx_time = modification_time if start_time is None else start_time
    gpx_time = gpx_time.date()  # Truncate to date (NOTE: NOT ACTUAL DATE OF THE GPX)

    # Step 2: Buffer GPX track and find intersections with bike network
    # note: copy and assign needed in order to avoid SettingWithCopyWarning
    buffered_gpx = gdf_gpx.copy()
    buffered_gpx['geometry'] = buffered_gpx['geometry'].buffer(buffer_distance)
    bike_segments_matched = bike_network[bike_network.intersects(buffered_gpx.geometry.iloc[0])]
    
    # Exit the function if no segments are matched
    if bike_segments_matched.empty:
        print(f"\tWarning: no matched segments found for this file.")
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()  # Return empty GeoDataFrames
    
    # Inner function to calculate overlap (apply faster than for loop)
    def calculate_overlap(segment):
        intersection = segment.geometry.intersection(buffered_gpx.geometry.iloc[0])
        return intersection.length / segment.geometry.length

    # Step 3: Filter based on the overlap threshold
    bike_segments_matched = bike_segments_matched.assign(
        overlap_percentage=bike_segments_matched.apply(calculate_overlap, axis=1))

    filtered_segments = bike_segments_matched[bike_segments_matched['overlap_percentage'] 
                                              >= intersect_threshold]

    # Exit the function if there are no segments with sufficient overlap
    if filtered_segments.empty:
        print(f"\tWarning: no segments found for this file with sufficient overlap.")
        return gpd.GeoDataFrame(), gpd.GeoDataFrame()  # Return empty GeoDataFrames

    # Step 4: Extract unique nodes from the matched segments
    filtered_segments = filtered_segments.assign(
        node_from=filtered_segments['ref'].str.split('-', expand=True)[0],
        node_to=filtered_segments['ref'].str.split('-', expand=True)[1]
    )
    unique_nodes = set(filtered_segments["node_from"].tolist() + 
                       filtered_segments["node_to"].tolist())
    
    # Step 5: Filter point GeoDataFrame (bike nodes) based on unique nodes from GPX match
    point_geodf_filtered = point_geodf[point_geodf['rcn_ref'].isin(unique_nodes)]
    point_geodf_filtered_buffered = point_geodf_filtered.copy()
    point_geodf_filtered_buffered['geometry'] = point_geodf_filtered_buffered['geometry'].buffer(buffer_distance)
    combined_polylines = filtered_segments.geometry.union_all()
    intersecting_indices = point_geodf_filtered_buffered[point_geodf_filtered_buffered.intersects(combined_polylines)].index
    matched_nodes_all = point_geodf_filtered.loc[intersecting_indices]
    matched_nodes = matched_nodes_all[matched_nodes_all['rcn_ref'].isin(unique_nodes)]

    # Return matched segments and matched nodes with GPX metadata
    filtered_segments["gpx_name"] = gpx_name
    filtered_segments["gpx_date"] = gpx_time
    matched_nodes = matched_nodes.assign(gpx_name=gpx_name)
    matched_nodes = matched_nodes.assign(gpx_date=gpx_time)

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
    # Ensure target folder is empty
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
        if gpx_file.endswith(".gpx"):

            gpx_file_path = os.path.join(zip_folder, gpx_file)

            # Process each GPX file
            print("Processing file: " + gpx_file_path)
            bike_segments, matched_nodes = process_gpx_file(gpx_file_path, bike_network, point_geodf)

            # Append results to the combined GeoDataFrames
            all_segments = gpd.GeoDataFrame(pd.concat([all_segments, bike_segments], ignore_index=True))
            all_nodes = gpd.GeoDataFrame(pd.concat([all_nodes, matched_nodes], ignore_index=True))

            # update progress for polling
            pct = round(i / total * 100)
            progress_state["pct"] = pct
    
    print("Processing done!")

    return all_segments, all_nodes
