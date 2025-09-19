import os
import sys
import pandas as pd
import geopandas as gpd
import platform
import subprocess
from pathlib import Path
from scripts.geofabrik_date import *
from tqdm import tqdm

# geoprocessing
SCRIPTS_FOLDER = "scripts"
buffer_distance = 20  # in meters
intersect_threshold = 0.75
node_width = 3
input_gpkg = "data/temp/rcn_output.gpkg"
multiline_geojson = 'data/geojson/gdf_multiline.geojson'
point_geojson = 'data/geojson/gdf_point.geojson'
multiline_geojson_proj = 'data/geojson/gdf_multiline_projected.geojson'
point_geojson_proj = 'data/geojson/gdf_point_projected.geojson'

def parse_and_filter_tags(tag_string, tags_to_keep=None):
    """
    Parse a string-encoded dictionary of tags and optionally filter keys.

    Args:
        tag_string (str): String in the format '"key"=>"value", ...'.
        tags_to_keep (list, optional): List of keys to retain. If None or empty, all keys are returned.

    Returns:
        dict: Parsed and optionally filtered dictionary of tags.
    """
    # Regular expression to match key-value pairs in the format 'key'=>"value"
    tag_pairs = re.findall(r'"(.*?)"=>"(.*?)"', tag_string)
    tag_dict = dict(tag_pairs)

    # Replace colons in the keys with underscores
    tag_dict = {k.replace(':', '_'): v for k, v in tag_dict.items()}

    # If tags_to_keep is None or empty, return all tags
    if tags_to_keep is None or len(tags_to_keep) == 0:
        return tag_dict
    
    # Filter the dictionary to keep only the desired tags
    filtered_tags = {k: v for k, v in tag_dict.items() if k in tags_to_keep}
    return filtered_tags

def explode_tags(df, tags_column, tags_to_keep=None):
    """
    Expand a column of string-encoded dictionaries in a GeoDataFrame into separate columns.

    Args:
        df (GeoDataFrame): Input GeoDataFrame containing a column with dictionary strings.
        tags_column (str): Name of the column to parse and expand.
        tags_to_keep (list, optional): List of keys to retain. If None, all keys are kept.

    Returns:
        GeoDataFrame: Original GeoDataFrame with the dictionary keys expanded as columns.
    """
    # Convert the string representation of the dictionary to a Python dictionary
    exploded_tags = df[tags_column].apply(lambda x: parse_and_filter_tags(x, tags_to_keep) if isinstance(x, str) else {})
    
    # Create a DataFrame from the exploded tags
    tags_df = pd.json_normalize(exploded_tags)
    
    # Combine the original DataFrame with the new tags DataFrame
    exploded_df = pd.concat([df.drop(columns=[tags_column]), tags_df], axis=1)
    
    return exploded_df

def enrich_with_osm_ids(
    gdf_multiline: gpd.GeoDataFrame,
    gdf_point: gpd.GeoDataFrame,
    max_dist: float = 20.0,
    node_width: int = 3,
    use_tqdm: bool = True
):
    """
    Enrich segment MultiLineStrings with osm_id_from and osm_id_to using buffer intersection.
    
    Args:
        gdf_multiline (GeoDataFrame): Line segments with 'ref' column formatted as "node_from-node_to".
        gdf_point (GeoDataFrame): Points with 'rcn_ref' (node number) and 'osm_id'.
        max_dist (float, optional): Buffer distance around segments to find candidate nodes (meters). Defaults to 20.0.
        node_width (int, optional): Width for zero-padding node IDs. Defaults to 3.
        use_tqdm (bool, optional): Whether to display a progress bar. Defaults to True.

    Returns:
        tuple:
            gdf_multiline_enriched (GeoDataFrame): Segments with 'osm_id_from' and 'osm_id_to'.
            gdf_point_with_join (GeoDataFrame): Original points with added 'rcn_ref_join' for matching.

    Notes:
        An alternative strategy to use a fast nearest join based on endpoints produced poor results 
        due to complex or curved MultiLineString geometries. This buffer-based intersection method 
        ensures more reliable matches.
    """
    # Make explicit copies to avoid modifying originals
    gdf_multiline = gdf_multiline.copy()
    gdf_point = gdf_point.copy()

    # --- Step 0: normalize node IDs as strings with leading zeros ---
    gdf_multiline['node_from'] = (
        gdf_multiline['ref'].str.split('-', expand=True)[0].astype(str).str.zfill(node_width)
    )
    gdf_multiline['node_to'] = (
        gdf_multiline['ref'].str.split('-', expand=True)[1].astype(str).str.zfill(node_width)
    )

    # Keep original rcn_ref, add a join column
    gdf_point['rcn_ref_join'] = gdf_point['rcn_ref'].astype(str).str.zfill(node_width)

    # --- Step 1: loop over segments with buffer ---
    osm_from_list = []
    osm_to_list = []

    if use_tqdm:
        iterator = tqdm(gdf_multiline.iterrows(), total=len(gdf_multiline), desc="Matching segments")
    else:
        iterator = gdf_multiline.iterrows()
        print_every = max(1, len(gdf_multiline) // 10)  # print 10 times during loop

    for idx, seg in iterator:
        buffer_geom = seg.geometry.buffer(max_dist)

        # Node FROM
        candidates_from = gdf_point[gdf_point['rcn_ref_join'] == seg['node_from']]
        candidates_from = candidates_from[candidates_from.intersects(buffer_geom)]
        if not candidates_from.empty:
            osm_from_list.append(candidates_from['osm_id'].min())
        else:
            osm_from_list.append(None)

        # Node TO
        candidates_to = gdf_point[gdf_point['rcn_ref_join'] == seg['node_to']]
        candidates_to = candidates_to[candidates_to.intersects(buffer_geom)]
        if not candidates_to.empty:
            osm_to_list.append(candidates_to['osm_id'].min())
        else:
            osm_to_list.append(None)

        # Print progress if not using tqdm
        if not use_tqdm and (idx + 1) % print_every == 0:
            percent = 100 * (idx + 1) / len(gdf_multiline)
            print(f"[INFO] Processed {idx + 1}/{len(gdf_multiline)} segments ({percent:.1f}%)")

    gdf_multiline['osm_id_from'] = osm_from_list
    gdf_multiline['osm_id_to'] = osm_to_list

    # --- Step 2: add match flag ---
    def match_flag(row):
        if pd.notna(row['osm_id_from']) and pd.notna(row['osm_id_to']):
            return 'full'
        elif pd.isna(row['osm_id_from']) and pd.isna(row['osm_id_to']):
            return 'none'
        else:
            return 'partial'

    gdf_multiline['osm_match_flag'] = gdf_multiline.apply(match_flag, axis=1)

    # --- Step 3: summary and printout ---
    missing = gdf_multiline[gdf_multiline['osm_match_flag'] != 'full']
    num_segments = len(gdf_multiline)
    num_full_matches = (gdf_multiline['osm_match_flag'] == 'full').sum()
    percent_full = 100 * num_full_matches / num_segments

    print(f"✅ Full matches: {num_full_matches}/{num_segments} ({percent_full:.3f}%)")

    if not missing.empty:
        display_cols = ['osm_id', 'node_from', 'node_to', 'osm_id_from', 'osm_id_to', 'osm_match_flag']
        print(f"⚠️ {len(missing)} segments missing matches (partial or none):")
        print(missing[display_cols].reset_index(drop=True))

    return gdf_multiline, gdf_point

def process_osm_data(use_tqdm=True):
    """
    Download Belgium OSM data, process segments and points, 
    enrich segments with OSM node IDs, and save GeoJSON outputs.
    """
    current_os = platform.system()
    print(f"[INFO] Running on {current_os}")

    osm_version = get_latest_geofabrik_date()
    print(f"[INFO] Latest Geofabrik OSM version: {osm_version}")

    # Download Belgium OSM, extract rcn data, create GeoPackage and keep key files
    if current_os == "Windows":
        # Get absolute path to batch script to avoid relative path issues on Windows
        script_path = Path(os.path.join(SCRIPTS_FOLDER, "process_osm.bat")).resolve()
        print(f"[INFO] Using script: {script_path}")
        # assumption: running locally
        subprocess.run(
            [script_path, osm_version],
            check=True,
            shell=True  # needed on Windows to run a .bat file
        )

    # Read from geopackage
    print(f"[INFO] Reading GeoPackage: {input_gpkg}")
    gdf_multiline = gpd.read_file(input_gpkg, layer=0)
    gdf_point = gpd.read_file(input_gpkg, layer=1)
    print(f"[INFO] Loaded {len(gdf_multiline)} multilines and {len(gdf_point)} points.")

    # List of tags you want to keep
    print("[INFO] Exploding multiline tags...")
    tags_to_keep = ["network_type", "ref", "route"]
    tags_column = 'other_tags'
    gdf_multiline = explode_tags(gdf_multiline, tags_column, tags_to_keep)
    before_filter = len(gdf_multiline)
    gdf_multiline = gdf_multiline[gdf_multiline['ref'].fillna('').str.contains('-', na=False)]
    print(f"[INFO] Filtered multilines from {before_filter} → {len(gdf_multiline)} valid segments.")

    # Process the points tags
    print("[INFO] Exploding point tags...")
    gdf_point = explode_tags(gdf_point, tags_column)
    print(f"[INFO] Points dataframe after tag processing: {len(gdf_point)} features.")

    # Convert to Belgian Lambert 2008
    print("[INFO] Projecting to Belgian Lambert 2008 (EPSG:3812)...")
    gdf_multiline_projected = gdf_multiline.to_crs(epsg=3812)
    gdf_point_projected = gdf_point.to_crs(epsg=3812)

    # Look up matching node osm_id for segment nodes
    print("[INFO] Enriching multilines with OSM node IDs...")
    gdf_multiline_projected, gdf_point_projected = \
        enrich_with_osm_ids(gdf_multiline_projected, gdf_point_projected, 
                            buffer_distance, node_width, use_tqdm)
    print("[INFO] Enrichment completed.")

    # Convert the enriched result back to WGS84
    print("[INFO] Converting back to WGS84 (EPSG:4326)...")
    gdf_multiline = gdf_multiline_projected.to_crs(epsg=4326)
    gdf_point = gdf_point_projected.to_crs(epsg=4326)

    # Save the outputs as GeoJSON and/or pickle for use in the app
    # compared to shapefiles there is no truncation of column names but takes longer
    print("[INFO] Saving GeoJSON outputs...")
    gdf_multiline.to_file(multiline_geojson, driver='GeoJSON')
    gdf_point.to_file(point_geojson, driver='GeoJSON')
    gdf_multiline_projected.to_file(multiline_geojson_proj, driver='GeoJSON')
    gdf_point_projected.to_file(point_geojson_proj, driver='GeoJSON')
    print("[INFO] All outputs saved successfully.")

if __name__ == "__main__":
    current_os = platform.system()
    use_tqdm = (current_os == "Windows")
    process_osm_data(use_tqdm)
    