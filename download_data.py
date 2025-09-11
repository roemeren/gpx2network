import os
import gdown

# dictionary of files to be downloaded
files = {
    "1VhQtHiasyWSOzhNSainc-hc1kRV6eev-": "gdf_multiline.geojson",
    "1YERXQyFj5tPjf-cxqTsduAjqXebBDRms": "gdf_point.geojson",
}

def ensure_data():
    """
    Download required data files if they are not present locally.

    Checks for files in `data/bike_node_network`. 
    Downloads missing ones from Google Drive using their IDs.

    Returns:
        str: Path to the local data directory.

    Example:
        >>> from download_data import ensure_data
        >>> data_dir = ensure_data()
    """
    # create directly if it doesn't exist yet
    download_dir = os.path.join("data", "bike_node_network")
    os.makedirs(download_dir, exist_ok=True)

    # download files from Google Drive
    for fid, fname in files.items():
        output = os.path.join(download_dir, fname)
        if not os.path.exists(output):
            url = f"https://drive.google.com/uc?id={fid}"
            gdown.download(url, output, quiet=False)
        else:
            print(f"Skipping {fname} (already exists).")

    return download_dir  # optional: return the folder path