#!/bin/bash
set -e

echo "=== START OSM PROCESSING ==="

TEMP_DIR="data/temp"
mkdir -p "$TEMP_DIR"
echo "[INFO] Temp directory ensured: $TEMP_DIR"

# --- Get parameters ---
DATE=$1
INPUT_FILE=$2  # full path to cached .osm.pbf

if [ -z "$DATE" ] || [ -z "$INPUT_FILE" ]; then
    echo "[ERROR] Usage: $0 <yymmdd> <input_file>"
    exit 1
fi

echo "[INFO] Using cached input file: $INPUT_FILE"
echo "[INFO] Processing date: $DATE"

# --- Filter OSM data ---
RCN_RELATIONS="$TEMP_DIR/rcn_relations.osm.pbf"
RCN_POINTS="$TEMP_DIR/rcn_ref_points.osm.pbf"

echo "[INFO] Filtering OSM relations (network=rcn)..."
#osmium tags-filter "$INPUT_FILE" r/network=rcn -o "$RCN_RELATIONS"
osmium tags-filter .cache/geofabrik/belgium-latest.osm.pbf r/network=rcn -o data/temp/rcn_relations.osm.pbf
echo "[INFO] Relations saved to: $RCN_RELATIONS"

echo "[INFO] Filtering OSM points (rcn_ref)..."
# osmium tags-filter "$RCN_RELATIONS" n/rcn_ref -o "$RCN_POINTS"
osmium tags-filter data/temp/rcn_relations.osm.pbf n/rcn_ref -o data/temp/rcn_ref_points.osm.pbf
echo "[INFO] Points saved to: $RCN_POINTS"

# --- Create GeoPackage ---
OUTPUT_GPKG="$TEMP_DIR/rcn_output.gpkg"
echo "[INFO] Creating GeoPackage: $OUTPUT_GPKG"

#ogr2ogr -f "GPKG" "$OUTPUT_GPKG" "$RCN_RELATIONS" multilinestrings
ogr2ogr -f "GPKG" data\temp\rcn_output.gpkg data\temp\rcn_relations.osm.pbf multilinestrings
echo "[INFO] Added multilinestrings layer to GeoPackage"

#ogr2ogr -f "GPKG" -update "$OUTPUT_GPKG" "$RCN_POINTS" points
ogr2ogr -f "GPKG" -update data/temp/rcn_output.gpkg data/temp/rcn_ref_points.osm.pbf points
echo "[INFO] Added points layer to GeoPackage"

echo "[INFO] GeoPackage created successfully: $OUTPUT_GPKG"

# --- Summary ---
NUM_RELATIONS=$(osmium count -t r "$RCN_RELATIONS" | awk '{print $1}')
NUM_POINTS=$(osmium count -t n "$RCN_POINTS" | awk '{print $1}')
echo "[INFO] Summary: $NUM_RELATIONS relations, $NUM_POINTS points"

echo "[INFO] Processing complete."
echo "=== END OSM PROCESSING ==="
