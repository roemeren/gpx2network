import os
import xml.etree.ElementTree as ET
import geopandas as gpd

def tcx_to_gpx(tcx_path: str, gpx_path: str):
    """Convert a single TCX file to a GPX file.

    Parses the Garmin TCX (Training Center XML) file at ``tcx_path``
    and writes a corresponding GPX file to ``gpx_path``. The output
    GPX contains a single track with all available track points,
    including latitude, longitude, elevation (if present), and time.

    This conversion is handy when Garmin Connect will not export
    certain large activities directly as GPX but will allow TCX
    export.

    Args:
        tcx_path (str): Path to the input TCX file.
        gpx_path (str): Path where the output GPX file will be written.
    """
    ns = {
        "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
    }
    tree = ET.parse(tcx_path)
    root = tree.getroot()

    # Create GPX root
    gpx = ET.Element(
        "gpx",
        version="1.1",
        creator="tcx-to-gpx-script",
        xmlns="http://www.topografix.com/GPX/1/1",
    )
    trk = ET.SubElement(gpx, "trk")
    name = ET.SubElement(trk, "name")
    name.text = os.path.basename(tcx_path)
    trkseg = ET.SubElement(trk, "trkseg")

    # Extract all Trackpoints
    for tp in root.findall(".//tcx:Trackpoint", ns):
        pos = tp.find("tcx:Position", ns)
        time = tp.find("tcx:Time", ns)
        if pos is None:
            continue
        lat = pos.find("tcx:LatitudeDegrees", ns)
        lon = pos.find("tcx:LongitudeDegrees", ns)
        if lat is None or lon is None:
            continue

        trkpt = ET.SubElement(
            trkseg,
            "trkpt",
            lat=lat.text,
            lon=lon.text,
        )
        if time is not None:
            t = ET.SubElement(trkpt, "time")
            t.text = time.text

        # Optional: elevation
        ele = tp.find("tcx:AltitudeMeters", ns)
        if ele is not None:
            e = ET.SubElement(trkpt, "ele")
            e.text = ele.text

    # Write to file
    ET.ElementTree(gpx).write(gpx_path, encoding="utf-8", xml_declaration=True)


def batch_convert(input_folder: str, output_folder: str):
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
