import folium # type: ignore
import requests # type: ignore
import geopandas as gpd # type: ignore
from shapely.geometry import Point # type: ignore
from urllib.parse import quote_plus
import pandas as pd # type: ignore

# Function to get coordinates from the IGN geocodage service
def get_coordinates(address):
    url_address = quote_plus(address)
    url = f"https://data.geopf.fr/geocodage/search?limit=1&q={url_address}"
    response = requests.get(url).json()
    if response["features"]:
        coords = response["features"][0]["geometry"]["coordinates"]
        lon, lat = coords[0], coords[1]
        return lon, lat
    else:
        raise ValueError(f"Address '{address}' not found!")

# Function to create a buffer around the coordinates
def create_buffer(lon, lat, distance_m=1000):
    point = Point(lon, lat)
    buffer = point.buffer(distance_m / 111320)  # 1 degree ~ 111.32 km
    return buffer

# Function to query food stores from Overpass API
def get_food_stores(buffer):
    minx, miny, maxx, maxy = buffer.bounds
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      node["shop"="supermarket"]({miny},{minx},{maxy},{maxx});
      node["shop"="convenience"]({miny},{minx},{maxy},{maxx});
      way["shop"="supermarket"]({miny},{minx},{maxy},{maxx});
      way["shop"="convenience"]({miny},{minx},{maxy},{maxx});
    );
    out center;
    """
    response = requests.get(overpass_url, params={'data': overpass_query})
    data = response.json()
    return pd.DataFrame(data['elements'])

# Function to query fastfood from Overpass API
def get_fastfood(buffer):
    minx, miny, maxx, maxy = buffer.bounds
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      node["amenity"="fast_food"]({miny},{minx},{maxy},{maxx});
      way["amenity"="fast_food"]({miny},{minx},{maxy},{maxx});
    );
    out center;
    """
    response = requests.get(overpass_url, params={'data': overpass_query})
    data = response.json()
    return pd.DataFrame(data['elements'])

# Function to query restaurants from Overpass API
def get_restaurants(buffer):
    minx, miny, maxx, maxy = buffer.bounds
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      node["amenity"="restaurant"]({miny},{minx},{maxy},{maxx});
      way["amenity"="restaurant"]({miny},{minx},{maxy},{maxx});
    );
    out center;
    """
    response = requests.get(overpass_url, params={'data': overpass_query})
    data = response.json()
    return pd.DataFrame(data['elements'])

# Function to transform and clean Overpass data
def process_food_stores(df):
    if df.empty:
        return gpd.GeoDataFrame()

    # Normalize the tags field and add geometry
    tags = pd.json_normalize(df['tags'])
    df = pd.concat([df, tags], axis=1)
    
    # Merge nodes and ways by adding center coordinates for ways
    df['lon'] = df.apply(lambda x: x['center']['lon'] if 'center' in x and x['type'] == 'way' else x['lon'], axis=1)
    df['lat'] = df.apply(lambda x: x['center']['lat'] if 'center' in x and x['type'] == 'way' else x['lat'], axis=1)
    df = df.drop(columns=['center', 'nodes', 'tags'], errors='ignore')

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['lon'], df['lat']), crs="EPSG:4326")
    return gdf

# Function to transform and clean Overpass data
def process_fastfood(df):
    if df.empty:
        return gpd.GeoDataFrame()

    # Normalize the tags field and add geometry
    tags = pd.json_normalize(df['tags'])
    df = pd.concat([df, tags], axis=1)

    # Merge nodes and ways by adding center coordinates for ways
    df['lon'] = df.apply(lambda x: x['center']['lon'] if 'center' in x and x['type'] == 'way' else x['lon'], axis=1)
    df['lat'] = df.apply(lambda x: x['center']['lat'] if 'center' in x and x['type'] == 'way' else x['lat'], axis=1)
    df = df.drop(columns=['center', 'nodes', 'tags'], errors='ignore')

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['lon'], df['lat']), crs="EPSG:4326")
    return gdf

# Function to transform and clean Overpass data
def process_restaurants(df):
    if df.empty:
        return gpd.GeoDataFrame()

    # Normalize the tags field and add geometry
    tags = pd.json_normalize(df['tags'])
    df = pd.concat([df, tags], axis=1)

    # Merge nodes and ways by adding center coordinates for ways
    df['lon'] = df.apply(lambda x: x['center']['lon'] if 'center' in x and x['type'] == 'way' else x['lon'], axis=1)
    df['lat'] = df.apply(lambda x: x['center']['lat'] if 'center' in x and x['type'] == 'way' else x['lat'], axis=1)
    df = df.drop(columns=['center', 'nodes', 'tags'], errors='ignore')

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['lon'], df['lat']), crs="EPSG:4326")
    return gdf

# Function to create the map
def create_map(gdf_city, gdf_stores, gdf_fastfood, gdf_restaurants, output_file='map.html'):
    # Create base map (initial center can be arbitrary since we'll adjust with fit_bounds)
    map = folium.Map(location=[gdf_city.geometry.y[0], gdf_city.geometry.x[0]], zoom_start=14, control_scale=True)

    # Add OpenStreetMap tile layer
    folium.TileLayer('OpenStreetMap').add_to(map)

    # Create FeatureGroup for the city location (your position)
    city_fg = folium.FeatureGroup(name='Your Position', show=True)
    folium.Marker(
        [gdf_city.geometry.y[0], gdf_city.geometry.x[0]],
        popup="Your Position",
        icon=folium.Icon(color='red')
    ).add_to(city_fg)
    city_fg.add_to(map)

    # Create FeatureGroup for the food stores
    stores_fg = folium.FeatureGroup(name='Food Stores', show=True)
    for idx, row in gdf_stores.iterrows():
        popup_html = f"""
        <b>Name:</b> {row.get('name', 'Unknown store')}<br>
        <b>Address:</b> {row.get('addr:street', '')} {row.get('addr:housenumber', '')}<br>
        <b>City:</b> {row.get('addr:city', '')}
        """
        folium.Marker(
            [row.geometry.y, row.geometry.x],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color='blue', icon='shopping-cart', prefix='fa')
        ).add_to(stores_fg)
    stores_fg.add_to(map)

    # Create FeatureGroup for the fast food places
    fastfood_fg = folium.FeatureGroup(name='Fast Food', show=True)
    for idx, row in gdf_fastfood.iterrows():
        popup_html = f"""
        <b>Name:</b> {row.get('name', 'Unknown fast food')}<br>
        <b>Address:</b> {row.get('addr:street', '')} {row.get('addr:housenumber', '')}<br>
        <b>City:</b> {row.get('addr:city', '')}
        """
        folium.Marker(
            [row.geometry.y, row.geometry.x],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color='orange', icon='burger', prefix='fa')
        ).add_to(fastfood_fg)
    fastfood_fg.add_to(map)

    # Create FeatureGroup for the restaurants
    restaurants_fg = folium.FeatureGroup(name='Restaurants', show=True)
    for idx, row in gdf_restaurants.iterrows():
        popup_html = f"""
        <b>Name:</b> {row.get('name', 'Unknown restaurant')}<br>
        <b>Address:</b> {row.get('addr:street', '')} {row.get('addr:housenumber', '')}<br>
        <b>City:</b> {row.get('addr:city', '')}
        """
        folium.Marker(
            [row.geometry.y, row.geometry.x],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color='green', icon='utensils', prefix='fa')
        ).add_to(restaurants_fg)
    restaurants_fg.add_to(map)

    # Improved title display for map
    addFixedOverlay(map, "<h1>Food and Dining Around You</h1>", cornerRef="TC", position=(15, -150),
                    div_style="max-width: 400px; padding: 15px; background-color: rgba(255, 255, 255, 0.65); "
                              "border-radius: 10px; font-family: Arial, sans-serif; color: #333; font-size: 24px;")

    # Author information overlay
    addFixedOverlay(map, "<p>Author: B. Mancel. Date: 24/09/2024.</p>", cornerRef="BR", position=(15, 10),
                    div_style="max-width: 300px;")

    # Add a legend in the top-left corner
    legend_html = """
    <div style="width: 200px; background-color: white; border: 2px solid grey; border-radius: 10px; padding: 10px; font-size: 14px;">
        <h4 style="margin-top: 0;">Legend</h4>
        <i class="fa fa-map-marker fa-2x" style="color: red;"></i> Your Position<br>
        <i class="fa fa-shopping-cart fa-2x" style="color: blue;"></i> Food Stores<br>
        <i class="fa fa-burger fa-2x" style="color: orange;"></i> Fast Food<br>
        <i class="fa fa-utensils fa-2x" style="color: green;"></i> Restaurants
    </div>
    """
    addFixedOverlay(map, legend_html, cornerRef="TL", position=(15, 70), div_style="")

    # Calculate bounds to include all markers
    all_points = (
        list(gdf_stores.geometry.bounds.values) +
        list(gdf_fastfood.geometry.bounds.values) +
        list(gdf_restaurants.geometry.bounds.values)
    )
    if all_points:
        min_x = min(point[0] for point in all_points)
        min_y = min(point[1] for point in all_points)
        max_x = max(point[2] for point in all_points)
        max_y = max(point[3] for point in all_points)
        map.fit_bounds([[min_y, min_x], [max_y, max_x]])
    else:
        # If no points found, center on the city location
        map.fit_bounds([[gdf_city.geometry.y[0], gdf_city.geometry.x[0]]])

    # Add LayerControl to toggle visibility of layers
    folium.LayerControl(collapsed=False).add_to(map)

    # Save the map to an HTML file
    map.save(output_file)
    print(f"Map saved as {output_file}")

def addFixedOverlay(map, txtInHTML, cornerRef="BL", position=(50, 50), z_index=9999, div_style=""):
    switch = {"BL": 'bottom: {}px; left:{}px;',
              "TL": 'top: {}px; left:{}px;',
              "TR": 'top: {}px; right:{}px;',
              "BR": 'bottom: {}px; right:{}px;',
              "TC": 'top: {}px; left:50%; transform: translateX(-50%);',
              "BC": 'bottom: {}px; left:50%; transform: translateX(-50%);',
              }

    overlay_html = """
    <div style="position: fixed; {} z-index: {}; background-color: rgba(255, 255, 255, 0.8); padding: 20px; border-radius: 10px;
    border: 2px solid grey; font-size: 18px; font-weight: bold; color: black; text-align: center; box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.5);
    {}">
    {}
    </div>
    """.format(switch[cornerRef].format(position[0], position[1]), z_index, div_style, txtInHTML)

    map.get_root().html.add_child(folium.Element(overlay_html))

# Step 1: Get the address from the user
address = input("Please enter a French postal address: ")

# Step 2: Get coordinates of the address
lon, lat = get_coordinates(address)
print(f"Coordinates for '{address}': {lon}, {lat}")

# Step 3: Create a 1km buffer around the address
buffer = create_buffer(lon, lat, distance_m=1000)

# Step 4: Fetch food stores, fast food, and restaurants within the buffer
df_stores = get_food_stores(buffer)
df_fastfood = get_fastfood(buffer)
df_restaurants = get_restaurants(buffer)

# Step 5: Process the data into GeoDataFrames
gdf_stores = process_food_stores(df_stores)
gdf_fastfood = process_fastfood(df_fastfood)
gdf_restaurants = process_restaurants(df_restaurants)

# Step 6: Create the map
city_gdf = gpd.GeoDataFrame([{'geometry': Point(lon, lat)}], crs="EPSG:4326")
create_map(city_gdf, gdf_stores, gdf_fastfood, gdf_restaurants, output_file='map.html')