# Belgian Bike Node Network Matcher 🚲

![GitHub tag (latest)](https://img.shields.io/github/v/tag/roemeren/gpx-bike-node-matcher)
![Last Commit](https://img.shields.io/github/last-commit/roemeren/gpx-bike-node-matcher)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A Dash app to explore how your GPX rides align with Belgium’s bike node network.  
Upload a ZIP of your rides—these can be exports from Garmin Connect, Strava, 
files from an old Garmin device collecting dust, etc.—see matched nodes and segments on a map, and download the results.

---

## Demo

The app is deployed on [Render](https://gpx-bike-node-matcher.onrender.com) (heads-up: free-tier hosting makes ZIP processing a bit slow 🐢).  
For a smoother ride, it’s recommended to run it locally if the ZIP file contains more than 10-20 tracks.

## Features

- Upload and process your GPX rides in a ZIP file.
- Visualize matched bike segments and nodes on an interactive map.
- Aggregated statistics on matched nodes, segments, and segment length.
- Download processed results as a ZIP file.
- Optional display of the preloaded bike network.
- Clustered nodes for cleaner visualization.

## Data

The underlying bike network data comes from [Geofabrik OSM extracts](https://download.geofabrik.de/europe/).  
Dataset version is displayed in the app and stored in `data/processed/DATA_VERSION.txt`.  


## Running Locally

### Step 1: Clone the repo

```bash
git clone <repo_url>
cd <repo_name>
```
### Step 2: Create a Python 3.12 environment and install dependencies

```bash
python3.12 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```
### Step 3: Run the app

```bash
python -m app.app
```

### Step 4: Open the app in your browser

Open http://127.0.0.1:8050 in your browser

**Warning:** large GPX ZIPs can take a while. Patience is a virtue. ⏳

## Usage

- Upload a ZIP with GPX rides in the left panel.
- Click **Process ZIP** to compute matched segments and nodes.
- The map, KPIs and aggregated tables will update dynamically.
- Download processed results via the **PDownload Results** button.
- Filter by date and adjust cluster radius for node display.
- Click **Recenter Map** if needed.

## Project Structure (Highlights)

- `app/` – Dash app code
- `app/static/` – Generated results and static files
- `data/processed/` – Preprocessed bike network data + DATA_VERSION.txt
- `core/` – Helper functions and geoprocessing logic

## Notes

### Manual Update of Underlying Data

The app normally relies on preprocessed data in `data/processed/`, which is updated through an automated GitHub workflow that creates a pull request. 
However, if you want to update the data manually, **osmium** and **GDAL** need to be installed locally.

**Dependencies:**

- **osmium-tool** (for OSM processing)  
  - Linux: `sudo apt install osmium-tool`  
  - Windows: install via Conda or OSGeo packages
- **ogr2ogr** (GDAL)  
  - Linux: `sudo apt install gdal-bin`  
  - Windows: install QGIS or OSGeo4W and set the following environment variables:  
    - **Path**: folder containing `ogr2ogr.exe`, e.g., `C:\Program Files\QGIS 3.28.6\bin`  
    - **GDAL_DATA**: folder containing `osmconf.ini` (needed for `ogr2ogr.exe`), e.g., `C:\Program Files\QGIS 3.28.6\apps\gdal\share\gdal`

**How to Update Data Locally:**

- **Windows:**  
    From the repository root, run:  
    ```bash
    python -m scripts.geofabrik_processing
    ```
- **Linux**:
    A similar bash script scripts/geofabrik_processing.sh exists, but it is currently configured to work in combination with the GitHub workflow update_geofabrik.yml. Some modifications may be needed to run it fully standalone on a local Linux system.
