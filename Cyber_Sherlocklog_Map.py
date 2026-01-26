import streamlit as st
import plotly.graph_objects as go
import re
import pandas as pd
from PIL import Image

# --- 1. CONFIGURATION ---
MAP_CONFIG = {
    "Chernarus": {
        "size": 15360,
        "image": "map_chernarus.png" 
    },
    "Livonia": {
        "size": 12800,
        "image": "map_livonia.png"
    },
    "Sakhal": {
        "size": 8192, 
        "image": "map_sakhal.png"
    },
    "Custom": {
        "size": 15360, # Default to Chernarus size
        "image": "map_custom.png"
    }
}

# --- 2. LOG PARSING ENGINE ---
def parse_log_file(uploaded_file):
    logs = []
    content = uploaded_file.getvalue().decode("utf-8", errors='ignore')
    lines = content.split('\n')

    # Regex to capture 3 numbers inside < > brackets
    # Example matches: <1240.5, 120.3, 5000.1>
    coord_pattern = re.compile(r"<([0-9\.-]+),\s*([0-9\.-]+),\s*([0-9\.-]+)>")
    
    # Simple regex for player name
    name_pattern = re.compile(r'(?:Player|Identity)\s+"([^"]+)"')

    for line in lines:
        coord_match = coord_pattern.search(line)
        if coord_match:
            # We capture all three numbers raw
            v1, v2, v3 = coord_match.groups()
            
            name_match = name_pattern.search(line)
            name = name_match.group(1) if name_match else "Unknown"
            
            logs.append({
                "name": name,
                # Store raw values; we map them in the renderer
                "raw_1": float(v1),
                "raw_2": float(v2),
                "raw_3": float(v3),
                "details": line[:120]
            })
            
    return pd.DataFrame(logs)

# --- 3. MAP RENDERING ENGINE ---
def render_map(df, map_name, swap_xz, invert_z, use_y_as_z):
    config = MAP_CONFIG[map_name]
    map_size = config["size"]
    img_path = config["image"]

    fig = go.Figure()

    # -- A. Load Map Image --
    try:
        img = Image.open(img_path)
        fig.add_layout_image(
            dict(
                source=img,
                xref="x",
                yref="y",
                x=0,
                y=map_size, # Top-Left corner of image (Y=Max)
                sizex=map_size,
                sizey=map_size,
                sizing="stretch",
                opacity=1,
                layer="below"
            )
        )
    except FileNotFoundError:
        st.warning(f"⚠️ Image not found: {img_path}. Please place image in folder.")

    # -- B. Process Coordinates based on User Settings --
    if not df.empty:
        # Standard DayZ Log format is usually <X (West/East), Y (Height), Z (North/South)>
        # raw_1 = X, raw_2 = Y (Height), raw_3 = Z (North)
        
        x_col = df["raw_1"]
        
        # If user says "My coordinates are squashed at the bottom", they are likely using Height (raw_2) as North.
        # This toggle fixes that by forcing the parser to use the 3rd number (raw_3) as North.
        if use_y_as_z:
             z_col = df["raw_2"] # Unusual format <X, Z, Y>
        else:
             z_col = df["raw_3"] # Standard format <X, Y, Z>

        # Handle Swapping and Inversion
        final_x = z_col if swap_xz else x_col
        final_z = x_col if swap_xz else z_col

        if invert_z:
            final_z = map_size - final_z

        fig.add_trace(
            go.Scatter(
                x=final_x,
                y=final_z,
                mode='markers',
                marker=dict(size=8, color='red', line=dict(width=1, color='white')),
                text=df["name"],
                customdata=df["details"],
                hovertemplate="<b>%{text}</b><br>X: %{x:.0f}, Z: %{y:.0f}<br>%{customdata}<extra></extra>"
            )
        )

    # -- C. Configure Axes --
    fig.update_xaxes(range=[0, map_size], visible=False, showgrid=False)
    fig.update_yaxes(range=[0, map_size], visible=False, showgrid=False)

    fig.update_layout(
        width=900,
        height=900,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        plot_bgcolor="#1e1e1e",
        dragmode="pan"
    )

    st.plotly_chart(fig, use_container_width=True)

# --- 4. MAIN INTERFACE ---
def main():
    st.set_page_config(layout="wide", page_title="DayZ Log Mapper")
    
    with st.sidebar:
        st.title("🗺️ Settings")
        selected_map = st.selectbox("Map", list(MAP_CONFIG.keys()))
        uploaded_file = st.file_uploader("Upload .ADM / .RPT / .Log", type=['adm', 'rpt', 'log', 'txt'])
        
        st.markdown("---")
        st.header("🔧 Calibrator")
        st.info("Dots in the water? Try these:")
        
        use_y_as_z = st.checkbox("Fix: Dots squashed at bottom? (Use 2nd number as North)", value=False)
        swap_xz = st.checkbox("Swap X and Z Axis", value=False)
        invert_z = st.checkbox("Invert Vertical Axis (Flip N/S)", value=False)

    st.title(f"Server Map: {selected_map}")

    if uploaded_file:
        df = parse_log_file(uploaded_file)
        if not df.empty:
            st.success(f"Loaded {len(df)} entries.")
            render_map(df, selected_map, swap_xz, invert_z, use_y_as_z)
        else:
            st.error("No coordinates found. Check if logs contain format: <x, y, z>")
    else:
        st.info("Upload a log file to begin.")

if __name__ == "__main__":
    main()
