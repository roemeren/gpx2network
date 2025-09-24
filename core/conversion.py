import os
import xml.etree.ElementTree as ET
import zipfile
import pandas as pd

def tcx_to_gpx(tcx_path: str, gpx_path: str):
    """Convert a single TCX file to a GPX file.

    Parses the Garmin TCX (Training Center XML) file at ``tcx_path``
    and writes a corresponding GPX file to ``gpx_path``. The output
    GPX contains a single track with all available track points,
    including latitude, longitude, elevation (if present), and time,
    and adds a <type> tag inside <trk> with the activity type taken
    from the TCX Activity's Sport attribute (or "unknown" if absent).

    Args:
        tcx_path (str): Path to the input TCX file.
        gpx_path (str): Path where the output GPX file will be written.
    """
    ns = {"tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
    tree = ET.parse(tcx_path)
    root = tree.getroot()

    # ---- Extract Sport attribute ----
    # Grab the first Activity's Sport attribute if it exists
    sport = "unknown"
    activity_elem = root.find(".//tcx:Activities/tcx:Activity", ns)
    if activity_elem is not None:
        sport = activity_elem.attrib.get("Sport", "unknown")

    # map sport to align with GPX activity types
    sport = map_activity_type(sport)

    # ---- Create GPX root ----
    gpx = ET.Element(
        "gpx",
        version="1.1",
        creator="tcx-to-gpx-script",
        xmlns="http://www.topografix.com/GPX/1/1",
    )
    trk = ET.SubElement(gpx, "trk")
    name = ET.SubElement(trk, "name")
    name.text = os.path.basename(tcx_path)

    # Add the <type> tag with the Sport value
    type_tag = ET.SubElement(trk, "type")
    type_tag.text = sport

    trkseg = ET.SubElement(trk, "trkseg")

    # ---- Extract all Trackpoints ----
    for tp in root.findall(".//tcx:Trackpoint", ns):
        pos = tp.find("tcx:Position", ns)
        time = tp.find("tcx:Time", ns)
        if pos is None:
            continue

        lat = pos.find("tcx:LatitudeDegrees", ns)
        lon = pos.find("tcx:LongitudeDegrees", ns)
        if lat is None or lon is None:
            continue

        trkpt = ET.SubElement(trkseg, "trkpt", lat=lat.text, lon=lon.text)

        if time is not None:
            ET.SubElement(trkpt, "time").text = time.text

        ele = tp.find("tcx:AltitudeMeters", ns)
        if ele is not None:
            ET.SubElement(trkpt, "ele").text = ele.text

    # ---- Write to file ----
    ET.ElementTree(gpx).write(gpx_path, encoding="utf-8", xml_declaration=True)

def tcx_to_gpx_batch(input_folder: str, output_folder: str):
    """Convert all TCX files in a folder to GPX.

    Iterates through the given input folder, converts each ``.tcx`` file
    to a ``.gpx`` file with the same base name, and saves it to the
    output folder.

    This is useful because some activities in Garmin Connect cannot
    be exported directly as GPX when they are too large, but TCX
    exports are still allowed.

    Args:
        input_folder (str): Path to the folder containing TCX files.
        output_folder (str): Path to the folder where GPX files will be saved.

    Example:
        # Change these paths to your folders
        input_dir = "../data/raw/tcx"
        output_dir = "../data/raw/gpx"
        batch_convert(input_dir, output_dir)
        print("All files converted.")
    """
    os.makedirs(output_folder, exist_ok=True)
    for fname in os.listdir(input_folder):
        if fname.lower().endswith(".tcx"):
            in_path = os.path.join(input_folder, fname)
            out_path = os.path.join(
                output_folder, os.path.splitext(fname)[0] + ".gpx"
            )
            print(f"Converting {fname} -> {os.path.basename(out_path)}")
            tcx_to_gpx(in_path, out_path)

def map_activity_type(raw_type: str) -> str:
    """Map a raw activity type string to a broad category.

    Args:
        raw_type (str): Original activity type text.

    Returns:
        str: Normalized activity category or the original value.
    """
    if not raw_type:
        return "unknown"
    t = raw_type.lower()
    if "cycling" in t or "biking" in t:
        return "cycling"
    if "running" in t:
        return "running"
    if "walking" in t or "hiking" in t:
        return "walking"
    return raw_type

def extract_gpx_info(zip_file):
    """
    Extract GPX files from a zip and return a sorted DataFrame
    with columns: file, activity_type, activity_type_group, has_timestamps.

    Args:
        zip_file (str): Path to the zip archive containing GPX files.

    Returns:
        pandas.DataFrame: Sorted DataFrame with activity information.
    """
    base_dir = os.path.dirname(os.path.abspath(zip_file))
    temp_dir = os.path.join(base_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)

    # Extract .gpx files
    with zipfile.ZipFile(zip_file, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".gpx"):
                zf.extract(name, temp_dir)

    rows = []

    for root, _, files in os.walk(temp_dir):
        for fname in files:
            if fname.lower().endswith(".gpx"):
                fpath = os.path.join(root, fname)
                activity_type = "unknown"
                has_timestamps = False
                try:
                    tree = ET.parse(fpath)
                    r = tree.getroot()

                    # look for <type> tags (ignoring namespace)
                    for t in r.iter():
                        tag_name = t.tag.split("}")[-1]
                        if tag_name == "type" and t.text:
                            activity_type = t.text.strip()
                            break  # take the first one

                    # check if any <time> tag exists
                    has_timestamps = any(
                        elem.tag.split("}")[-1] == "time" for elem in r.iter()
                    )

                except ET.ParseError:
                    print(f"Warning: could not parse {fpath}")

                rows.append({
                    "file": os.path.relpath(fpath, temp_dir),
                    "activity_type": activity_type,
                    "activity_type_group": map_activity_type(activity_type),
                    "has_timestamps": has_timestamps
                })

    df = pd.DataFrame(rows)
    # Sort by file name for a consistent order
    df = df.sort_values(by="file").reset_index(drop=True)
    return df
