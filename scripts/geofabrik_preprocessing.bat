@echo off
REM ============================================================
REM  Before running this script, make sure to set these environment variables:
REM      set  CONDA_PATH=C:\Users\<username>\Anaconda3\condabin   (temporary for this window)
REM      setx CONDA_PATH "C:\Users\remerencia\Anaconda3\condabin" (permanent)
REM      set  CONDA_ENV=<your-env>
REM      setx CONDA_ENV <your-env>
REM ============================================================
REM === START OSM PROCESSING ===

REM --- Activate Conda environment ---
set "CONDA_PATH=%CONDA_PATH%"
set "CONDA_ENV=%CONDA_ENV%"

if "%CONDA_PATH%"=="" (
    echo ERROR: CONDA_PATH is not set.
    exit /b 1
)
if "%CONDA_ENV%"=="" (
    echo ERROR: CONDA_ENV is not set.
    exit /b 1
)

CALL "%CONDA_PATH%\activate.bat" %CONDA_ENV%

REM --- Check parameters ---
IF "%1"=="" (
    echo [ERROR] Usage: %0 ^<yymmdd^>
    exit /b 1
)
SET DATE=%1
SET FILENAME=belgium-%DATE%.osm.pbf

REM --- Set temp directory ---
SET TEMP_DIR=data\intermediate
IF NOT EXIST "%TEMP_DIR%" (
    echo [INFO] Creating temp folder: %TEMP_DIR%
    mkdir "%TEMP_DIR%"
)

REM --- Download OSM PBF if it does not exist ---
IF EXIST "data\raw\%FILENAME%" (
    echo [INFO] data\raw\%FILENAME% already exists, skipping download
) ELSE (
    echo [INFO] Downloading %FILENAME%
    curl -o "data\raw\%FILENAME%" "https://download.geofabrik.de/europe/%FILENAME%"
    echo [INFO] Download complete: %FILENAME%
)

REM --- Filter OSM data for rcn network relations ---
echo [INFO] Filtering OSM data for rcn network relations
osmium tags-filter "data\raw\\%FILENAME%" r/network=rcn -o data\intermediate\rcn_relations.osm.pbf --overwrite
echo [INFO] Extracted rcn relations

echo [INFO] Filtering OSM data for rcn_ref points
osmium tags-filter data\intermediate\rcn_relations.osm.pbf n/rcn_ref -o data\intermediate\rcn_ref_points.osm.pbf --overwrite
echo [INFO] Extracted rcn_ref points

REM --- Create output GeoPackage ---
echo [INFO] Creating output GeoPackage: rcn_output.gpkg
ogr2ogr -f "GPKG" data\intermediate\rcn_output.gpkg data\intermediate\rcn_relations.osm.pbf multilinestrings
ogr2ogr -f "GPKG" -update data\intermediate\rcn_output.gpkg data\intermediate\rcn_ref_points.osm.pbf points
echo [INFO] GeoPackage created: data\intermediate\rcn_output.gpkg

echo [INFO] Processing complete.
echo === END OSM PROCESSING ===
