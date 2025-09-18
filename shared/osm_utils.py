from shared.common import *

def get_latest_geofabrik_date(country: str="belgium") -> str:
    """
    Returns the latest yymmdd string for a given country on Geofabrik Europe page.

    Args:
        country (str): country name, e.g., "belgium", "france", etc.

    Returns:
        str: latest date in YYMMDD format, e.g., "250917"
    """
    url = "https://download.geofabrik.de/europe/"
    resp = requests.get(url)
    resp.raise_for_status()
    
    # Regex pattern: country-YYMMDD.osm.pbf
    pattern = rf'{re.escape(country)}-(\d{{6}})\.osm\.pbf'
    matches = re.findall(pattern, resp.text)
    
    if not matches:
        raise ValueError(f"No files found for {country} on Geofabrik page")
    
    # Return the latest date
    latest_date = sorted(matches)[-1]
    return latest_date

def process_osm_data():
    current_os = platform.system()
    osm_version = get_latest_geofabrik_date()

    # Get absolute path to batch script to avoid relative path issues on Windows
    script_path = Path(os.path.join(SCRIPTS_FOLDER, "process_osm.bat")).resolve()

    if current_os == "Windows":
        subprocess.run(
            [script_path, osm_version],
            check=True,
            shell=True  # needed on Windows to run a .bat file
        )
    else:
        # not tested yet
        subprocess.run(["bash", script_path, osm_version], check=True)
