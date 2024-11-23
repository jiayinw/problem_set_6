from shiny import App, Inputs, Outputs, Session, ui, render
import pandas as pd
import altair as alt
import json
import numpy as np

# Load data
df_full = pd.read_csv('./alert_counts.csv')
geojson_file = "chicago-boundaries.geojson"

# Load GeoJSON data
with open(geojson_file) as f:
    chicago_geojson = json.load(f)

geo_data = alt.Data(values=chicago_geojson["features"])

# Extract coordinates from GeoJSON
coordinates = [
    coord
    for feature in chicago_geojson["features"]
    for polygon in feature["geometry"]["coordinates"]
    for coord in polygon[0]  # Assuming MultiPolygon geometries
]

# Convert to a NumPy array for easier processing
coordinates = np.array(coordinates)

# Find longitude and latitude ranges
geo_longitude_range = [coordinates[:, 0].min(), coordinates[:, 0].max()]
geo_latitude_range = [coordinates[:, 1].min(), coordinates[:, 1].max()]

# Create unique type-subtype combinations for the dropdown
unique_combinations = df_full.groupby(['updated_type', 'updated_subtype']).size().reset_index().drop(columns=0)

# Create a dictionary for the dropdown menu options
options = {f"{row['updated_type']} - {row['updated_subtype']}": f"{row['updated_type']} | {row['updated_subtype']}" 
           for _, row in unique_combinations.iterrows()}

# # UI Component (without conditional switch button)
# app_ui = ui.page_fluid(
#     # Dropdown menu for type and subtype selection
#     ui.input_select("type_subtype", "Select Type and Subtype: ", options, selected=list(options.keys())[0]),
    
#     # Slider range to pick the hour range
#     ui.input_slider("hour_range", "Select Hour Range:", min=0, max=23, value=(6, 9), step=1),
    
#     # Output for the scatter map
#     ui.output_image("scatter_map")
# )

# UI Component (with conditional switch button)
app_ui = ui.page_fluid(
    # Dropdown menu for type and subtype selection
    ui.input_select("type_subtype", "Select Type and Subtype:", options, selected=list(options.keys())[0]),
    
    # Switch button to toggle between single hour and range of hours
    ui.input_switch("switch_button", "Toggle to switch to single hour", value=False),
    
    # Single hour slider
    ui.output_ui("single_hour_ui"),
    
    # Range of hours slider
    ui.output_ui("range_hour_ui"),
    
    # Output for the scatter map
    ui.output_image("scatter_map")
)

# Server Logic
def server(input: Inputs, output: Outputs, session: Session):
    @output
    @render.ui
    def single_hour_ui():
        if input.switch_button():
            return ui.input_slider("single_hour", "Select a Single Hour:", min=0, max=23, value=12, step=1)
        return None  # Hide this slider when the switch button is toggled

    @output
    @render.ui
    def range_hour_ui():
        if not input.switch_button():
            return ui.input_slider("hour_range", "Select Hour Range:", min=0, max=23, value=(6, 9), step=1)
        return None  # Hide this slider when the switch button is not toggled

    @output
    @render.image
    def scatter_map():
        # Split the selected type and subtype
        selected = input.type_subtype()
        chosen_type, chosen_subtype = selected.split(' - ')
        
        # # Get the selected hour range
        # selected_hour_range = input.hour_range()
        # start_hour, end_hour = selected_hour_range

        # print(f"Chosen type: {chosen_type}")
        # print(f"Chosen subtype: {chosen_subtype}")
        # print(f"Selected hour range: {start_hour} to {end_hour}")

        # # Filter the DataFrame by type, subtype, and hour
        # # Filter the DataFrame by type, subtype, and hour range
        # filtered_df = df_full[
        #     (df_full['updated_type'] == chosen_type) &
        #     (df_full['updated_subtype'] == chosen_subtype) &
        #     (df_full['hour'] >= f"{start_hour:02}:00") &
        #     (df_full['hour'] < f"{end_hour:02}:00")
        # ]

        # Split the selected type and subtype
        selected = input.type_subtype()
        chosen_type, chosen_subtype = selected.split(' - ')

        # Initialize variables
        start_hour, end_hour = None, None
        selected_hour = None

        # Handle switch button toggle
        if input.switch_button(): 
            # Single hour selected
            selected_hour = input.single_hour()
            print(f"Chosen type: {chosen_type}")
            print(f"Chosen subtype: {chosen_subtype}")
            print(f"Selected single hour: {selected_hour}")

            # Filter the DataFrame by type, subtype, and single hour
            filtered_df = df_full[
                (df_full['updated_type'] == chosen_type) &
                (df_full['updated_subtype'] == chosen_subtype) &
                (df_full['hour'] == f"{selected_hour:02}:00")
            ]
        else:  
            selected_hour_range = input.hour_range()
            start_hour, end_hour = selected_hour_range

            print(f"Chosen type: {chosen_type}")
            print(f"Chosen subtype: {chosen_subtype}")
            print(f"Selected hour range: {start_hour} to {end_hour}")

            # Filter the DataFrame by type, subtype, and hour range
            filtered_df = df_full[
                (df_full['updated_type'] == chosen_type) &
                (df_full['updated_subtype'] == chosen_subtype) &
                (df_full['hour'] >= f"{start_hour:02}:00") &
                (df_full['hour'] < f"{end_hour:02}:00")
            ]

        # Sort the bins by alert_counts in descending order and select top 10
        top_alerts = filtered_df.sort_values(by='alert_counts', ascending=False).head(10)

        # Check longitude and latitude ranges for top_alerts
        alerts_longitude_range = [top_alerts['binned_longitude'].min(), top_alerts['binned_longitude'].max()]
        alerts_latitude_range = [top_alerts['binned_latitude'].min(), top_alerts['binned_latitude'].max()]

        # Dynamically set the limits based on the data
        longitude_limits = [
            min(geo_longitude_range[0], alerts_longitude_range[0]),
            max(geo_longitude_range[1], alerts_longitude_range[1])
        ]

        latitude_limits = [
            min(geo_latitude_range[0], alerts_latitude_range[0]),
            max(geo_latitude_range[1], alerts_latitude_range[1])
        ]

        # Create the base map with Chicago neighborhood boundaries
        base_map = alt.Chart(geo_data).mark_geoshape(
            fill=None,  # Transparent fill
            stroke='black',  # Boundary lines
            strokeWidth=1.5  # Thickness of boundary lines
        ).encode(
            tooltip=[alt.Tooltip('properties.NAME:N', title='Neighborhood')]  # Neighborhood tooltip
        ).properties(
            width=600,
            height=600
        ).project(
            type='equirectangular'  # Use equirectangular projection for geographic alignment
        )

        # Create the scatter plot
        scatter_plot = alt.Chart(top_alerts).mark_circle(
            color='red',
            opacity=0.5
        ).encode(
            x=alt.X('binned_longitude:Q',
                    title='Longitude',
                    scale=alt.Scale(domain=longitude_limits)),  # Dynamically set longitude limits
            y=alt.Y('binned_latitude:Q',
                    title='Latitude',
                    scale=alt.Scale(domain=latitude_limits)),  # Dynamically set latitude limits
            size=alt.Size('alert_counts:Q',
                          title='Number of Alerts',
                          scale=alt.Scale(range=[100, 1000])),
            tooltip=[
                alt.Tooltip('binned_latitude:Q', title='Latitude'),
                alt.Tooltip('binned_longitude:Q', title='Longitude'),
                alt.Tooltip('alert_counts:Q', title='Number of Alerts')
            ]
        ).properties(
            width=600,
            height=600
        )

        # Layer the scatter plot on top of the base map
        if input.switch_button(): 
            layered_map = (base_map + scatter_plot).properties(
                title=f"Top 10 Locations for {chosen_type} - {chosen_subtype} Alerts at {selected_hour:02}:00"
            )
        else:
            layered_map = (base_map + scatter_plot).properties(
                title=f"Top 10 Locations for {chosen_type} - {chosen_subtype} Alerts Between {start_hour:02}:00 and {end_hour:02}:00"
            )


        # Save the chart as an image
        output_path = "./scatter_map.png"
        layered_map.save(output_path, format="png")

        # Return the file path to Shiny
        return {"src": output_path, "width": 600, "height": 600}

# Create and run the app
app = App(app_ui, server)