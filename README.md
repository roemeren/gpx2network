# Belgian Bike Node Network Matcher 🚲

A Dash app to explore how your GPX rides align with Belgium’s bike node network.  
Upload a ZIP of your rides—these can be exports from Garmin Connect, Strava, 
files from an old Garmin device collecting dust, etc.—see matched nodes and segments on a map, and download the results.

---

## Demo

The app is deployed on [Render](https://gpx-bike-node-matcher.onrender.com) (heads-up: it can be a bit slow on free tiers).  
For a smoother ride, it’s recommended to run it locally.

## Features

- Upload and process your GPX rides in a ZIP file.
- Visualize matched bike segments and nodes on an interactive map.
- Aggregated statistics on matched nodes, segments, and segment length.
- Download processed results as a ZIP file.
- Data version display (from `data/processed/DATA_VERSION.txt`) so you know exactly which dataset you’re using.
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

### Step 3: Ensure system tools are available

- osmium-tool (used for OSM processing)
    - Linux: `sudo apt install osmium-tool`
    - Windows: use Conda or install via OSGeo packages
- ogr2ogr (GDAL)
    - Linux: `sudo apt install gdal-bin`
    - Windows: install QGIS or OSGeo4W and modify the following environment variables:
        - **Path**: Add the path to the folder that contains `ogr2ogr.exe`, e.g. `C:\Program Files\QGIS 3.28.6\bin`
        - **GDAL_DATA**: Add a variable with the path to the folder that contains `osmconf.ini` file (needed to run `ogr2ogr.exe`), e.g.`C:\Program Files\QGIS 3.28.6\apps\gdal\share\gdal`

### Step 4: Run the app

```bash
python -m app.app
```

### Step 5: Open http://127.0.0.1:8050 in your browser

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

- The free Render deployment can be quite slow; for production use, a higher-tier server or more resources are recommended.
- The app automatically shows the dataset version in the left panel, so you always know which bike network release you are using.
