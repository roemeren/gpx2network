#!/bin/bash
set -e

echo "=== START OSM PROCESSING ==="

TEMP_DIR="../data/temp"
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR" || { echo "[ERROR] Failed to cd into $TEMP_DIR"; exit 1; }

# --- Get parameters ---
DATE=$1
INPUT_FILE=$2  # full path to cached .osm.pbf

if [ -z "$DATE" ] || [ -z "$INPUT_FILE" ]; then
    echo "[ERROR] Usage: $0 <yymmdd> <input_file>"
    exit 1
fi

FILENAME="$INPUT_FILE"
echo "[INFO] Using cached input file: $FILENAME"

# --- Filter OSM data ---
osmium tags-filter "$FILENAME" r/network=rcn -o rcn_relations.osm.pbf
osmium tags-filter rcn_relations.osm.pbf n/rcn_ref -o rcn_ref_points.osm.pbf

# --- Create GeoPackage ---
ogr2ogr -f "GPKG" rcn_output.gpkg rcn_relations.osm.pbf multilinestrings
ogr2ogr -f "GPKG" -update rcn_output.gpkg rcn_ref_points.osm.pbf points
echo "[INFO] GeoPackage created: rcn_output.gpkg"

echo "[INFO] Processing complete."
echo "=== END OSM PROCESSING ==="
