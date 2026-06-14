import os
import csv
import re

def clean_compile_kmls(folder_path):
    all_nodes = []
    all_edges = []
    
    files = [f for f in os.listdir(folder_path) if f.lower().endswith('.kml')]
    print(f"📦 Unpacking {len(files)} KML files via deep text-scan...")

    for file_name in files:
        file_path = os.path.join(folder_path, file_name)
        base_name = os.path.splitext(file_name)[0]
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # 1. Look for coordinate pairs explicitly
        # Matches formats like: -1.045621,37.012345 or multiple coordinate streams
        coord_blocks = re.findall(r'<coordinates>([\s\S]*?)</coordinates>', content)
        
        if not coord_blocks:
            continue

        for block in coord_blocks:
            clean_block = block.strip()
            points = clean_block.split()
            
            if len(points) == 1:
                # It's a single dropped point (Node!)
                coord_set = points[0].split(',')
                if len(coord_set) >= 2:
                    all_nodes.append({
                        "name": base_name, # Names the node after your KML filename
                        "lat": float(coord_set[1]),
                        "lng": float(coord_set[0]),
                        "floor": 1,
                        "description": f"Imported campus coordinate mark"
                    })
            elif len(points) > 1:
                # It's a tracked path string (Edge!)
                start_pt = points[0].split(',')
                end_pt = points[-1].split(',')
                
                if len(start_pt) >= 2 and len(end_pt) >= 2:
                    try:
                        lon1, lat1 = float(start_pt[0]), float(start_pt[1])
                        lon2, lat2 = float(end_pt[0]), float(end_pt[1])
                        
                        # Calculate rough physical meter distance lengths
                        dist = (((lon1 - lon2) ** 2 + (lat1 - lat2) ** 2) ** 0.5) * 111000
                        
                        # Check naming conventions
                        if " to " in base_name.lower():
                            parts = base_name.split(" to ")
                            n_from, n_to = parts[0].strip(), parts[1].strip()
                        else:
                            n_from = f"{base_name}_Start"
                            n_to = f"{base_name}_End"
                            
                        all_edges.append({
                            "node_from": n_from,
                            "node_to": n_to,
                            "distance_meters": round(dist, 1)
                        })
                    except ValueError:
                        continue

    # Fallback backup generation: If no explicit tags match, create nodes directly from your names
    if not all_nodes and files:
        print("⚠️ Direct geometry tags missed. Auto-generating node entities from your filenames...")
        for file_name in files:
            name_attr = os.path.splitext(file_name)[0]
            if " to " not in name_attr.lower():
                # Note: Fallback nodes lack coordinates and may fail DB constraints
                all_nodes.append({"name": name_attr.strip(), "lat": 0.0, "lng": 0.0, "floor": 1, "description": "Auto-mapped node point (missing coords)"})

    # Write results
    with open('nodes.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["name", "lat", "lng", "floor", "description"])
        writer.writeheader()
        writer.writerows(all_nodes)

    with open('edges.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["node_from", "node_to", "distance_meters"])
        writer.writeheader()
        writer.writerows(all_edges)

    print(f"✅ Success! Saved {len(all_nodes)} nodes and {len(all_edges)} paths.")

if __name__ == "__main__":
    clean_compile_kmls(os.getcwd())