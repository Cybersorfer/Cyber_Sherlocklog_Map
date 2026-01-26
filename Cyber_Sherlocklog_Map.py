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
    }
}

# --- 2. LOG PARSING ENGINE ---
def parse_log_file(uploaded_file):
    logs = []
    content = uploaded_file.getvalue().decode("utf-8", errors='ignore')
    lines = content.split('\n')

    # Regex to capture 3 numbers inside < > brackets
    coord_pattern = re.compile(r"<([0-9\.-]+),\s*([0-9\.-]+),\s*([0-9\.-]+)>")
    name_pattern = re.compile(r'(?:Player|Identity)\s+"([^"]+)"')

    for line in lines:
        coord_match = coord_pattern.search(line)
        if coord_match:
            v1, v2, v3 = coord_match.groups()
            name_match = name_pattern.search(line)
            name = name_match.group(1) if name_match else "Unknown"
            
            logs.append({
                "name": name,
                "raw_1": float(v1),
                "raw_2": float(v2),
                "raw_3": float(v3),
                "details": line[:120]
            })
            
    return pd.DataFrame(logs)

# --- 3. MAP RENDERING ENGINE ---
def render_map(df, map_name, swap_xz, invert_z, use_y_as_z, off_x, off_y, scale_factor):
    config = MAP_CONFIG[map_name]
    # Apply the manual scale factor to the map size definition
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
                y=map_size, 
                sizex=map_size,
                sizey=map_size,
                sizing="stretch",
                opacity=1,
                layer="below"
            )
        )
    except FileNotFoundError:
        st.warning(f"⚠️ Image not found: {img_path}")

    # -- B. Process Coordinates --
    if not df.empty:
        # 1. Select Axes
        x_col = df["raw_1"]
        z_col = df["raw_2"] if use_y_as_z else df["raw_3"]

        # 2. Swap & Invert Logic
        final_x = z_col if swap_xz else x_col
        final_z = x_col if swap_xz else z_col

        if invert_z:
            final_z = map_size - final_z

        # 3. APPLY FINE-TUNING (Offset & Scale)
        # We modify the coordinates themselves to shift them onto the map image
        final_x = (final_x * scale_factor) + off_x
        final_z = (final_z * scale_factor) + off_y

        fig.add_trace(
            go.Scatter(
                x=final_x,
                y=final_z,
                mode='markers',
                marker=dict(size=8, color='red', line=dict(width=1, color='white')),
                text=df["name"],
                hovertemplate="<b>%{text}</b><br>X: %{x:.0f}, Z: %{y:.0f}<extra></extra>"
            )
        )

    # -- C. Lock Axes --
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
        uploaded_file = st.file_uploader("Upload Log", type=['adm', 'rpt', 'log', 'txt'])
        
        st.markdown("---")
        st.header("🔧 Calibrator")
        
        # Standard Toggles
        use_y_as_z = st.checkbox("Fix: Dots in Ocean? (Use 2nd num as North)", value=False)
        swap_xz = st.checkbox("Swap X/Z Axis", value=False)
        invert_z = st.checkbox("Invert Vertical (Flip N/S)", value=False)
        
        st.markdown("---")
        st.subheader("🎯 Fine-Tune Alignment")
        st.caption("Use these sliders to match iZurvive positions.")
        
        # New Sliders for Offset and Scale
        off_x = st.slider("X Offset (Left/Right)", -2000, 2000, 0, step=10)
        off_y = st.slider("Y Offset (Up/Down)", -2000, 2000, 0, step=10)
        scale_factor = st.slider("Scale Factor (Zoom)", 0.8, 1.2, 1.0, step=0.005)

    st.title(f"Server Map: {selected_map}")

    if uploaded_file:
        df = parse_log_file(uploaded_file)
        if not df.empty:
            st.success(f"Loaded {len(df)} points. Calibrate using sidebar if needed.")
            render_map(df, selected_map, swap_xz, invert_z, use_y_as_z, off_x, off_y, scale_factor)
        else:
            st.error("No coordinates found.")
    else:
        st.info("Upload a log file to start.")

if __name__ == "__main__":
    main()
