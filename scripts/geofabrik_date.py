import requests
import re

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

if __name__ == "__main__":
    print(get_latest_geofabrik_date())
