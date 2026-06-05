import os
import csv
from fastkml import kml
from shapely.geometry import Point, LineString
from pygeoif import geometry

def extract_kml_data(kml_filename):
    if not os.path.exists(kml_filename):
        print(f"❌ Error: {kml_filename} not found in this directory.")
        return

    with open(kml_filename, 'rb') as f:
        doc = f.read()

    k = kml.KML()
    k.from_string(doc)

    nodes = []
    edges = []

    # Features are nested inside KML Documents/Folders
    features = list(k.features())
    if not features:
        print("❌ No features found in KML.")
        return
        
    # Dig into the KML hierarchy to find Placemarks
    def parse_features(feature_list):
        for feature in feature_list:
            if hasattr(feature, 'features'):
                parse_features(feature.features())
            if isinstance(feature, kml.Placemark):
                name = feature.name if feature.name else "Unnamed Location"
                geom = feature.geometry
                
                # If it's a dropped pin (Point), it's a Node
                if geom.geom_type == 'Point':
                    nodes.append({
                        "name": name,
                        "floor": 1,
                        "description": f"Campus facility: {name}"
                    })
                
                # If it's a tracked path (LineString), it's an Edge
                elif geom.geom_type == 'LineString':
                    coords = list(geom.coords)
                    if len(coords) >= 2:
                        # KML lines don't always name their start/end nodes explicitly,
                        # so we use the description field or name variations.
                        desc = feature.description if feature.description else ""
                        
                        # Fallback naming logic for edges
                        if "to" in name.lower():
                            parts = name.split(" to ")
                            node_from, node_to = parts[0].strip(), parts[1].strip()
                        else:
                            node_from = name
                            node_to = f"{name}_Destination"

                        # Calculate approximate distance in meters using coordinate degrees 
                        # (1 degree latitude is approx 111,000 meters)
                        start_pt = coords[0]
                        end_pt = coords[-1]
                        approx_dist = (((start_pt[0]-end_pt[0])**2 + (start_pt[1]-end_pt[1])**2)**0.5) * 111000

                        edges.append({
                            "node_from": node_from,
                            "node_to": node_to,
                            "distance_meters": round(approx_dist, 1)
                        })

    parse_features(features)

    # Write out to nodes.csv
    with open('nodes.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["name", "floor", "description"])
        writer.writeheader()
        writer.writerows(nodes)
    print(f"✅ Extracted {len(nodes)} locations into nodes.csv")

    # Write out to edges.csv
    with open('edges.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["node_from", "node_to", "distance_meters"])
        writer.writeheader()
        writer.writerows(edges)
    print(f"✅ Extracted {len(edges)} path links into edges.csv")

if __name__ == "__main__":
    # Ensure your file from the app matches this filename
    extract_kml_data("export.kml")