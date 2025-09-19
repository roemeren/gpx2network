#!/bin/bash
set -e

echo "=== START OSM PROCESSING ==="

TEMP_DIR="data/temp"
mkdir -p "$TEMP_DIR"

# --- Get parameters ---
DATE=$1
INPUT_FILE=$2  # full path to cached .osm.pbf

if [ -z "$DATE" ] || [ -z "$INPUT_FILE" ]; then
    echo "[ERROR] Usage: $0 <yymmdd> <input_file>"
    exit 1
fi

echo "[INFO] Using cached input file: $INPUT_FILE"

# --- Filter OSM data ---
RCN_RELATIONS="$TEMP_DIR/rcn_relations.osm.pbf"
RCN_POINTS="$TEMP_DIR/rcn_ref_points.osm.pbf"

osmium tags-filter "$INPUT_FILE" r/network=rcn -o "$RCN_RELATIONS"
osmium tags-filter "$RCN_RELATIONS" n/rcn_ref -o "$RCN_POINTS"

# --- Create GeoPackage ---
OUTPUT_GPKG="$TEMP_DIR/rcn_output.gpkg"

ogr2ogr -f "GPKG" "$OUTPUT_GPKG" "$RCN_RELATIONS" multilinestrings
ogr2ogr -f "GPKG" -update "$OUTPUT_GPKG" "$RCN_POINTS" points
echo "[INFO] GeoPackage created: $OUTPUT_GPKG"

echo "[INFO] Processing complete."
echo "=== END OSM PROCESSING ==="
