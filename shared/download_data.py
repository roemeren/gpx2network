from shared.common import *

# dictionary of files to be downloaded
files = {
    "1A2iCQITn7YOrpZTpVog-jL6O7A_q2nYS": "gdf_multiline_projected.geojson",
    "1TSyKNFHXqGq4iyDyPaeC07Nw40m-j6TH": "gdf_point_projected.geojson",
}

def ensure_data():
    """
    Ensure that required GeoJSON data and cached Pickle files exist locally.

    - Downloads missing GeoJSON files from Google Drive into `data/intermediate`.
    - Creates corresponding `.pkl` files (faster to load) if they do not yet exist.

    Returns:
        dict: A mapping from original GeoJSON filenames to their local Pickle paths.

    Example:
        >>> from download_data import ensure_data
        >>> pickle_paths = ensure_data()
        >>> import pickle
        >>> with open(pickle_paths["gdf_point_projected.geojson"], "rb") as f:
        ...     point_geodf = pickle.load(f)
    """
    # Create directly if it doesn't exist yet
    download_dir = os.path.join("data", "intermediate")
    os.makedirs(download_dir, exist_ok=True)

    print("Checking required data files...")

    pickle_paths = {}

    for fid, fname in files.items():
        geojson_path = os.path.join(download_dir, fname)
        pickle_path = geojson_path.replace(".geojson", ".pkl")

        # Download GeoJSON if missing
        if not os.path.exists(geojson_path):
            print(f"Downloading missing file: {fname}...")
            url = f"https://drive.google.com/uc?id={fid}"
            gdown.download(url, geojson_path, quiet=False)

        # Create pickle cache if missing
        if not os.path.exists(pickle_path):
            print(f"Creating pickle cache for {fname}...")
            gdf = gpd.read_file(geojson_path)
            with open(pickle_path, "wb") as f:
                pickle.dump(gdf, f)

        pickle_paths[fname] = pickle_path

    return pickle_paths