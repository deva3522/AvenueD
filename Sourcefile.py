import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk
import os
import webbrowser
import platform
import subprocess
from folium.plugins import HeatMap, TimestampedGeoJson
import folium
from geopy.distance import geodesic as haversine
from datetime import datetime, timedelta
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

class Polygon:
    def __init__(self, vertices):
        self.vertices = vertices

    def contains(self, point):
        global xinters
        x, y = point.x, point.y
        n = len(self.vertices)
        inside = False
        p1 = self.vertices[0]
        for i in range(n + 1):
            p2 = self.vertices[i % n]
            if y > min(p1.y, p2.y):
                if y <= max(p1.y, p2.y):
                    if x <= max(p1.x, p2.x):
                        if p1.y != p2.y:
                            xinters = (y - p1.y) * (p2.x - p1.x) / (p2.y - p1.y) + p1.x
                        if p1.x == p2.x or x <= xinters:
                            inside = not inside
            p1 = p2
        return inside

def haversine(coord1, coord2):
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def move_vehicle(vehicle, vehicle_paths, steps=10):
    start = vehicle['start_location']
    end = vehicle['end_location']
    current_location = start

    for _ in range(steps):
        next_location = Point(
            current_location.x + (end.x - start.x) / steps,
            current_location.y + (end.y - start.y) / steps
        )
        vehicle_paths[vehicle['vehicle_id']].append(next_location)
        current_location = next_location

        if haversine((current_location.y, current_location.x), (end.y, end.x)) < 0.01:  # Close enough to the end
            break

def check_toll_zone_crossings(vehicle_path, toll_zones):
    crossings = []
    for point in vehicle_path:
        for zone in toll_zones:
            if zone['geometry'].contains(point):
                crossings.append({'vehicle_id': vehicle_path[0], 'zone_name': zone['zone_name'], 'location': point})
    return crossings

def get_congestion_level():
    return 'low'  # Placeholder value

def calculate_dynamic_toll(congestion_level, distance_travelled):
    if congestion_level == 'low':
        return 0.03 * distance_travelled
    elif congestion_level == 'medium':
        return 0.05 * distance_travelled
    elif congestion_level == 'high':
        return 0.08 * distance_travelled
    else:
        return 0.05 * distance_travelled

# Create a folium map centered around Chennai's approximate location
folium_map = folium.Map(location=[13.0827, 80.2707], zoom_start=6)

# Define service roads as additional paths within the toll zone
service_roads = [
    [Point(80.2167, 13.1027), Point(80.3270, 13.1027)],  # Example service road within Chennai
    [Point(80.2167, 13.1527), Point(80.3270, 13.1527)],  # Another service road
]

# Draw service roads
for road in service_roads:
    road_coords = [(p.y, p.x) for p in road]
    folium.PolyLine(road_coords, color='gray', dash_array='5, 10', weight=2).add_to(folium_map)


def visualize_paths_and_zones(vehicle_paths, toll_zones, crossings, service_roads=None, cross_cut_roads=None):
    # Create a Folium map centered around the first vehicle's start location
    first_vehicle_start = next(iter(vehicle_paths.values()))[0]
    folium_map = folium.Map(location=[first_vehicle_start.y, first_vehicle_start.x], zoom_start=6, tiles="CartoDB positron")

    # Define colors for routes
    colors = [
        "blue", "green", "red", "purple", "orange",
        "darkblue", "darkgreen", "darkred", "lightblue", "pink"
    ]

    # Toll Zones Layer
    toll_zone_layer = folium.FeatureGroup(name="Toll Zones")
    for zone in toll_zones:
        vertices = [(v.y, v.x) for v in zone['geometry'].vertices]
        folium.Polygon(
            vertices,
            color='yellow',
            fill=True,
            fill_color='yellow',
            fill_opacity=0.5,
            popup=(
                f"<b>Toll Zone: {zone['zone_name']}</b><br>"
                f"Charge: ₹{zone.get('charge', 'N/A')}<br>"
                f"Area: {zone.get('area', 'N/A')} sq.km"
            ),
            tooltip=f"Toll Zone: {zone['zone_name']}"
        ).add_to(toll_zone_layer)
    toll_zone_layer.add_to(folium_map)

    # Vehicle Routes and Animation Layers
    for idx, (vehicle_id, path) in enumerate(vehicle_paths.items()):
        line = [(p.y, p.x) for p in path]
        route_color = colors[idx % len(colors)]
        total_distance = sum(haversine((p1.y, p1.x), (p2.y, p2.x)) for p1, p2 in zip(path, path[1:]))

        # Add static route polyline
        folium.PolyLine(
            line,
            color=route_color,
            weight=3,
            popup=(
                f"<b>Vehicle ID: {vehicle_id}</b><br>"
                f"Route: Start ({line[0]}) to End ({line[-1]})<br>"
                f"Total Distance: {total_distance:.2f} km"
            ),
            tooltip=f"Vehicle {vehicle_id}: {total_distance:.2f} km"
        ).add_to(folium_map)

        # Prepare data for animation
        start_time = datetime.now()
        animated_features = []
        for i, point in enumerate(path):
            timestamp = (start_time + timedelta(seconds=i)).isoformat()
            animated_features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [point.x, point.y],
                },
                "properties": {
                    "time": timestamp,
                    "popup": f"Vehicle {vehicle_id}<br>Location: ({point.y}, {point.x})",
                    "style": {"color": route_color}
                },
            })

        # Add animation as a separate layer
        animation_layer = TimestampedGeoJson({
            "type": "FeatureCollection",
            "features": animated_features,
        }, period="PT1S", add_last_point=True, auto_play=False, loop=False, max_speed=5)
        animation_layer.layer_name = f"Vehicle {vehicle_id} Animation"
        animation_layer.add_to(folium_map)

    # Toll Crossings Heatmap Layer
    heatmap_layer = folium.FeatureGroup(name="Toll Crossing Heatmap")
    heatmap_data = [
        (crossing['location'].y, crossing['location'].x)
        for crossing in crossings
        if isinstance(crossing, dict) and 'location' in crossing and hasattr(crossing['location'], 'y') and hasattr(crossing['location'], 'x')
    ]
    if heatmap_data:
        HeatMap(heatmap_data, radius=10, blur=15, gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}).add_to(heatmap_layer)
    else:
        print("Warning: No valid crossings data found for the heatmap.")
    heatmap_layer.add_to(folium_map)

    # Service Roads Layer
    if service_roads:
        service_road_layer = folium.FeatureGroup(name="Service Roads")
        for road_coords in service_roads:
            folium.PolyLine(
                road_coords,
                color='gray',
                dash_array='5, 10',
                weight=2,
                tooltip="Service Road"
            ).add_to(service_road_layer)
        service_road_layer.add_to(folium_map)

    # Cross-Cut Roads Layer
    if cross_cut_roads:
        cross_cut_layer = folium.FeatureGroup(name="Cross-Cut Roads")
        for road_coords in cross_cut_roads:
            folium.PolyLine(
                road_coords,
                color='brown',
                dash_array='5, 5',
                weight=2,
                tooltip="Cross-Cut Road"
            ).add_to(cross_cut_layer)
        cross_cut_layer.add_to(folium_map)

    # Add Layer Control for interactivity
    folium.LayerControl(collapsed=False).add_to(folium_map)

    # Save and return the map file path
    file_path = "individual_animated_vehicle_paths_and_toll_zones.html"
    folium_map.save(file_path)
    return file_path


# Define toll zones
chennai_polygon = Polygon(
    [Point(80.2167, 13.0827), Point(80.2167, 13.1737), Point(80.3270, 13.1737), Point(80.3270, 13.0827)])

toll_zones = [
    {'zone_id': 1, 'zone_name': 'Chennai', 'geometry': chennai_polygon},
]

# Define vehicles and their routes
vehicles = [
    {'vehicle_id': 1, 'start_location': Point(80.27, 13.09), 'end_location': Point(76.27, 9.93)},   # Chennai to Kochi
    {'vehicle_id': 2, 'start_location': Point(80.27, 13.09), 'end_location': Point(80.68, 16.51)},  # Chennai to Amaravati
    {'vehicle_id': 3, 'start_location': Point(80.27, 13.09), 'end_location': Point(78.47, 17.38)},  # Chennai to Hyderabad
    {'vehicle_id': 4, 'start_location': Point(80.27, 13.09), 'end_location': Point(77.59, 12.97)},  # Chennai to Bangalore
    {'vehicle_id': 5, 'start_location': Point(80.27, 13.09), 'end_location': Point(72.88, 19.07)},  # Chennai to Mumbai
    {'vehicle_id': 6, 'start_location': Point(80.27, 13.09), 'end_location': Point(77.41, 23.25)},  # Chennai to Bhopal
    {'vehicle_id': 7, 'start_location': Point(80.27, 13.09), 'end_location': Point(85.88, 20.46)},  # Chennai to Cuttack
    {'vehicle_id': 8, 'start_location': Point(80.27, 13.09), 'end_location': Point(88.36, 22.57)},  # Chennai to Kolkata
    {'vehicle_id': 9, 'start_location': Point(80.27, 13.09), 'end_location': Point(77.10, 28.70)},  # Chennai to Delhi
    {'vehicle_id': 10, 'start_location': Point(80.27, 13.09), 'end_location': Point(85.33, 23.36)}, # Chennai to Ranchi
]

# Initialize vehicle paths
vehicle_paths = {vehicle['vehicle_id']: [vehicle['start_location']] for vehicle in vehicles}

# Define accounts and initial balances
accounts = [{'vehicle_id': vehicle['vehicle_id'], 'initial_balance': 100.0, 'balance': 100.0, 'toll_charges': 0.0} for vehicle in vehicles]

# Run simulation
for vehicle in vehicles:
    move_vehicle(vehicle, vehicle_paths, steps=100)

# Check toll zone crossings and deduct tolls
crossings = {}
for vehicle_id, path in vehicle_paths.items():
    crossings[vehicle_id] = check_toll_zone_crossings(path, toll_zones)
    congestion_level = get_congestion_level()
    distance_travelled = sum(haversine((point.y, point.x), (next_point.y, next_point.x))
                             for point, next_point in zip(path, path[1:]))
    toll = calculate_dynamic_toll(congestion_level, distance_travelled)
    for account in accounts:
        if account['vehicle_id'] == vehicle_id:
            account['balance'] -= toll
            account['toll_charges'] += toll  # Accumulate toll charges for each vehicle
            print(f"Vehicle ID: {vehicle_id}, Opening Balance: 100.0, Deduction for Toll: {toll:.2f}, Current Balance: {account['balance']:.2f}")
            break

# Visualize results
file_path = visualize_paths_and_zones(vehicle_paths, toll_zones, crossings)
print(f"Map saved to {file_path}")
print(f"Open this link in your browser to view the map:")
print(f"file://{os.path.abspath(file_path)}")

# Create Tkinter window
root = tk.Tk()
root.title("GPS TOLL BASED SIMULATION")

# Plotting toll charges
vehicle_ids = [account['vehicle_id'] for account in accounts]
initial_balances = [account['initial_balance'] for account in accounts]
final_balances = [account['balance'] for account in accounts]
toll_charges = [account['toll_charges'] for account in accounts]

# Plotting the graph in Tkinter
fig, ax = plt.subplots(figsize=(10, 6))
bar_width = 0.2
bar1 = ax.bar([v_id - 0.2 for v_id in vehicle_ids], initial_balances, width=bar_width, align='center', label='Initial Balance')
bar2 = ax.bar(vehicle_ids, final_balances, width=bar_width, align='center', label='Final Balance')
bar3 = ax.bar([v_id + 0.2 for v_id in vehicle_ids], toll_charges, width=bar_width, align='center', label='Toll Charges')
ax.set_xlabel('Vehicle ID')
ax.set_ylabel('Amount')
ax.set_title('Toll Charges and Balances')
ax.set_xticks(vehicle_ids)
ax.legend()

# Display the graph in Tkinter
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.draw()
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

# Adding the table (tree view) for displaying data
tree = ttk.Treeview(root)
tree["columns"] = ("Vehicle ID", "Initial Balance", "Final Balance", "Toll Charges")
tree.column('#0', width=0, stretch=tk.NO)
tree.column('Vehicle ID', anchor=tk.CENTER, width=100)
tree.column('Initial Balance', anchor=tk.CENTER, width=100)
tree.column('Final Balance', anchor=tk.CENTER, width=100)
tree.column('Toll Charges', anchor=tk.CENTER, width=100)

# Define headings
tree.heading('#0', text='', anchor=tk.CENTER)
tree.heading('Vehicle ID', text='Vehicle ID')
tree.heading('Initial Balance', text='Initial Balance')
tree.heading('Final Balance', text='Final Balance')
tree.heading('Toll Charges', text='Toll Charges')

# Insert data into the treeview
for vehicle_id, initial_balance, final_balance, toll_charge in zip(vehicle_ids, initial_balances, final_balances, toll_charges):
    tree.insert('', 'end', values=(vehicle_id, initial_balance, final_balance, toll_charge))

tree.pack()

# Adding the map link button
def open_map():
    abs_path = os.path.abspath(file_path)
    if platform.system() == "Darwin":  # macOS
        subprocess.run(["open", "-a", "Safari", abs_path])  # Open in Safari, change as needed
    else:
        webbrowser.open(f"file://{abs_path}")  # Default behavior for Windows and Linux

map_button = ttk.Button(root, text="Open Map", command=open_map)
map_button.pack(side=tk.BOTTOM, pady=10)

# Run the Tkinter main loop
root.mainloop()
