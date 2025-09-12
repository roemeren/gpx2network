from shared.common import *
from shared.process_gpx import *
from shared.download_data import *
import time

start_time = time.time()

# Ensure data and caches
pickle_paths = ensure_data()

# Read cached bike network GeoDataFrames
with open(pickle_paths["gdf_multiline_projected.geojson"], "rb") as f:
    bike_network = pickle.load(f)

with open(pickle_paths["gdf_point_projected.geojson"], "rb") as f:
    point_geodf = pickle.load(f)

# Process the GPX files and merge the results
# Note: there's still an error if no match is found
all_segments, all_nodes = process_gpx_zip(zip_file_path, bike_network, 
                                          point_geodf, False, True)

# Save results as GeoJSON for further use
all_segments.to_file(segments_file_path, driver="GeoJSON")
all_nodes.to_file(nodes_file_path, driver="GeoJSON")

end_time = time.time()
print(f"Processing finished in {end_time - start_time:.2f} seconds.")