#!/bin/bash
set -e  # Exit on error

# --- Instruction to run in (Git) Bash---
# Make sure the right Conda environment is activated first:
# 1. Initialize Conda for Git Bash (if not done already): conda init bash
# 2. Activate the environment that has osmium and ogr2ogr installed: conda activate my-env
# 3. Check that osmium is available: osmium --version
# 4. Run the script: bash process_osm.sh belgium 250917

echo "=== START OSM PROCESSING ==="

# --- Activate Conda environment ---
CONDA_PATH="/c/Users/remerencia/Anaconda3"   # use forward slashes for Git Bash
source "$CONDA_PATH/etc/profile.d/conda.sh"
conda activate gsm-env

TEMP_DIR="../data/temp"
echo "[INFO] Creating temp folder: $TEMP_DIR"
mkdir -p "$TEMP_DIR"

echo "[INFO] Changing directory to temp folder"
cd "$TEMP_DIR" || { echo "[ERROR] Failed to cd into $TEMP_DIR"; exit 1; }

# --- Get country and optional date from parameters ---
DATE=$1

if [ -z "$DATE" ]; then
    echo "[ERROR] Usage: $0 <yymmdd>"
    exit 1
fi

FILENAME="belgium-${DATE}.osm.pbf"

# --- Download OSM PBF if it does not exist ---
if [ -f "$FILENAME" ]; then
    echo "[INFO] $FILENAME already exists, skipping download"
else
    echo "[INFO] Downloading $FILENAME"
    curl -s -o "$FILENAME" "https://download.geofabrik.de/europe/$FILENAME"
    echo "[INFO] Download complete: $FILENAME"
fi

echo "[INFO] Filtering OSM data for rcn network relations"
osmium tags-filter "$FILENAME" r/network=rcn -o rcn_relations.osm.pbf
echo "[INFO] Extracted rcn relations"

echo "[INFO] Filtering OSM data for rcn_ref points"
osmium tags-filter rcn_relations.osm.pbf n/rcn_ref -o rcn_ref_points.osm.pbf
echo "[INFO] Extracted rcn_ref points"

echo "[INFO] Creating output GeoPackage: rcn_output.gpkg"
ogr2ogr -f "GPKG" rcn_output.gpkg rcn_relations.osm.pbf multilinestrings
ogr2ogr -f "GPKG" -update rcn_output.gpkg rcn_ref_points.osm.pbf points
echo "[INFO] GeoPackage created: rcn_output.gpkg"

echo "[INFO] Cleaning up temporary files (keeping $LATEST_FILE and rcn_output.gpkg)"
for f in *; do
    if [ "$f" != "$FILENAME" ] && [ "$f" != "rcn_output.gpkg" ]; then
        rm -f "$f"
    fi
done

echo "[INFO] Processing complete."
echo "=== END OSM PROCESSING ==="
