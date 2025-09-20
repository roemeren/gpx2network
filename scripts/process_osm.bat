@echo off
REM === START OSM PROCESSING ===

REM --- Activate Conda environment ---
SET CONDA_PATH=C:\Users\remerencia\Anaconda3\condabin
CALL "%CONDA_PATH%\activate.bat" gsm-env

REM --- Check parameters ---
IF "%1"=="" (
    echo [ERROR] Usage: %0 ^<yymmdd^>
    exit /b 1
)
SET DATE=%1
SET FILENAME=belgium-%DATE%.osm.pbf

REM --- Set temp directory ---
SET TEMP_DIR=data\temp
IF NOT EXIST "%TEMP_DIR%" (
    echo [INFO] Creating temp folder: %TEMP_DIR%
    mkdir "%TEMP_DIR%"
)

REM --- Download OSM PBF if it does not exist ---
IF EXIST "%FILENAME%" (
    echo [INFO] %FILENAME% already exists, skipping download
) ELSE (
    echo [INFO] Downloading %FILENAME%
    curl -s -o ".cache\%FILENAME%" "https://download.geofabrik.de/europe/%FILENAME%"
    echo [INFO] Download complete: %FILENAME%
)

REM --- Filter OSM data for rcn network relations ---
echo [INFO] Filtering OSM data for rcn network relations
osmium tags-filter ".cache\%FILENAME%" r/network=rcn -o data\temp\rcn_relations.osm.pbf --overwrite
echo [INFO] Extracted rcn relations

echo [INFO] Filtering OSM data for rcn_ref points
osmium tags-filter data\temp\rcn_relations.osm.pbf n/rcn_ref -o data\temp\rcn_ref_points.osm.pbf --overwrite
echo [INFO] Extracted rcn_ref points

REM --- Create output GeoPackage ---
echo [INFO] Creating output GeoPackage: rcn_output.gpkg
ogr2ogr -f "GPKG" data\temp\rcn_output.gpkg data\temp\rcn_relations.osm.pbf multilinestrings
ogr2ogr -f "GPKG" -update data\temp\rcn_output.gpkg data\temp\rcn_ref_points.osm.pbf points
echo [INFO] GeoPackage created: data\temp\rcn_output.gpkg

echo [INFO] Processing complete.
echo === END OSM PROCESSING ===
