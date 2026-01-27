import streamlit as st
import plotly.graph_objects as go
import re
import pandas as pd
from PIL import Image

# --- 1. CONFIGURATION & LOCATIONS DATABASE ---
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

TOWN_DATA = {
    "Chernarus": [
        {"name": "NWAF", "x": 4600, "z": 10200},
        {"name": "Stary Sobor", "x": 6050, "z": 7750},
        {"name": "Novy Sobor", "x": 7100, "z": 7700},
        {"name": "Vybor", "x": 3750, "z": 8900},
        {"name": "Gorka", "x": 9500, "z": 8850},
        {"name": "Chernogorsk", "x": 6650, "z": 2600},
        {"name": "Elektrozavodsk", "x": 10450, "z": 2300},
        {"name": "Berezino", "x": 12400, "z": 9700},
        {"name": "Zelenogorsk", "x": 2750, "z": 5300},
        {"name": "Severograd", "x": 8400, "z": 13700},
        {"name": "Tisy", "x": 1700, "z": 14000},
        {"name": "Krasnostav", "x": 11200, "z": 12300},
        {"name": "Solnichniy", "x": 13300, "z": 6200},
        {"name": "Kamyshovo", "x": 12000, "z": 3500},
        {"name": "Balota", "x": 4400, "z": 2400},
        {"name": "Kamenka", "x": 1800, "z": 2200},
        {"name": "Myshkino", "x": 2000, "z": 7300},
        {"name": "VMC", "x": 4500, "z": 8300},
        {"name": "Altar", "x": 8100, "z": 9300},
        {"name": "Radio Zenit", "x": 7900, "z": 9700}
    ],
    "Livonia": [
        {"name": "Topolin", "x": 6200, "z": 11000},
        {"name": "Brena", "x": 6300, "z": 11800},
        {"name": "Nadbor", "x": 5600, "z": 4500},
        {"name": "Sitnik", "x": 6300, "z": 2200},
        {"name": "Radunin", "x": 9500, "z": 6800}
    ],
    "Sakhal": []
}

# --- 2. LOG PARSING ENGINE ---
def parse_log_file(uploaded_file):
    logs = []
    content = uploaded_file.getvalue().decode("utf-8", errors='ignore')
    lines = content.split('\n')

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
def render_map(df, map_name, swap_xz, invert_z, use_y_as_z, off_x, off_y, scale_factor, show_towns):
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

    # -- B. Helper Function for Coordinate Transformation --
    def transform_coords(raw_x, raw_z):
        final_x = raw_z if swap_xz else raw_x
        final_z = raw_x if swap_xz else raw_z
        if invert_z:
            final_z = map_size - final_z
        final_x = (final_x * scale_factor) + off_x
        final_z = (final_z * scale_factor) + off_y
        return final_x, final_z

    # -- C. Plot Towns --
    if show_towns and map_name in TOWN_DATA:
        towns = TOWN_DATA[map_name]
        t_x, t_y, t_names = [], [], []
        
        for town in towns:
            tx, ty = transform_coords(town['x'], town['z'])
            t_x.append(tx)
            t_y.append(ty)
            t_names.append(town['name'])

        fig.add_trace(go.Scatter(
            x=t_x,
            y=t_y,
            mode='markers+text',
            text=t_names,
            textposition="top center",
            marker=dict(size=8, color='yellow', line=dict(width=1, color='black')),
            textfont=dict(family="Arial Black", size=12, color="black"),
            hoverinfo='skip',
            name="Locations"
        ))

    # -- D. Plot Log Data --
    if not df.empty:
        raw_x_col = df["raw_1"]
        raw_z_col = df["raw_2"] if use_y_as_z else df["raw_3"]
        
        final_x = raw_z_col if swap_xz else raw_x_col
        final_z = raw_x_col if swap_xz else raw_z_col
        
        if invert_z:
            final_z = map_size - final_z
            
        final_x = (final_x * scale_factor) + off_x
        final_z = (final_z * scale_factor) + off_y

        fig.add_trace(
            go.Scatter(
                x=final_x,
                y=final_z,
                mode='markers',
                marker=dict(size=8, color='red', line=dict(width=1, color='white')),
                text=df["name"],
                hovertemplate="<b>%{text}</b><br>X: %{x:.0f}, Z: %{y:.0f}<extra></extra>",
                name="Logs"
            )
        )

    # -- E. Lock Axes & Dark Theme --
    fig.update_xaxes(range=[0, map_size], visible=False, showgrid=False)
    fig.update_yaxes(range=[0, map_size], visible=False, showgrid=False)

    fig.update_layout(
        width=900,
        height=900,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        plot_bgcolor="#0e1117",  # Plot area background
        paper_bgcolor="#0e1117", # Whole figure background (Removes white border)
        dragmode="pan",
        showlegend=False
    )

    # -- F. Render with Scroll Zoom Enabled --
    st.plotly_chart(
        fig, 
        use_container_width=True, 
        config={
            'scrollZoom': True,       # Enables Mouse Wheel Zoom
            'displayModeBar': False,  # Hides the floating toolbar for cleaner look
            'staticPlot': False
        }
    )

# --- 4. MAIN INTERFACE ---
def main():
    st.set_page_config(layout="wide", page_title="DayZ Log Mapper")

    # --- ENHANCED DARK THEME CSS ---
    st.markdown("""
    <style>
        /* Main Background */
        .stApp {
            background-color: #0e1117;
            color: #fafafa;
        }
        
        /* Remove Top White Gap (Streamlit Padding) */
        .block-container {
            padding-top: 2rem !important; 
            padding-bottom: 0rem !important;
        }

        /* Sidebar Background */
        [data-testid="stSidebar"] {
            background-color: #262730;
            color: #fafafa;
        }
        
        /* Button Styling */
        .stButton>button {
            color: #ffffff;
            background-color: #4CAF50;
            border: none;
        }
        .stButton>button:hover {
            color: #ffffff;
            background-color: #45a049;
        }
        
        /* Widgets Text Color */
        .stSelectbox label, .stCheckbox label, .stSlider label {
            color: #fafafa !important;
        }
        
        /* FILE UPLOADER DARK THEME */
        [data-testid="stFileUploader"] {
            background-color: #262730; 
            border-radius: 5px;
            padding: 10px;
        }
        [data-testid="stFileUploader"] section {
            background-color: #363940 !important;
        }
        [data-testid="stFileUploader"] div, [data-testid="stFileUploader"] span, [data-testid="stFileUploader"] small {
            color: #fafafa !important;
        }
        
        /* Input Box Styling */
        div[data-baseweb="select"] > div {
            background-color: #404040 !important;
            color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.title("🗺️ Settings")
        
        if st.button("🔄 Refresh Map"):
            st.rerun()
            
        st.markdown("---")
        
        selected_map = st.selectbox("Map", list(MAP_CONFIG.keys()))
        uploaded_file = st.file_uploader("Upload Log", type=['adm', 'rpt', 'log', 'txt'])
        
        st.markdown("---")
        st.header("🔧 Calibrator")
        
        use_y_as_z = st.checkbox("Fix: Dots in Ocean? (Use 2nd num as North)", value=True)
        swap_xz = st.checkbox("Swap X/Z Axis", value=False)
        invert_z = st.checkbox("Invert Vertical (Flip N/S)", value=False)
        
        st.markdown("---")
        st.subheader("🎯 Fine-Tune Alignment")
        
        off_x = st.slider("X Offset (Left/Right)", -2000, 2000, -20, step=10)
        off_y = st.slider("Y Offset (Up/Down)", -2000, 2000, -20, step=10)
        scale_factor = st.slider("Scale Factor (Zoom)", 0.8, 1.2, 1.0, step=0.005)
        
        st.markdown("---")
        st.subheader("👁️ View Options")
        show_towns = st.checkbox("Show Town Names", value=True)

    st.title(f"Server Map: {selected_map}")

    if uploaded_file:
        df = parse_log_file(uploaded_file)
        if not df.empty:
            st.success(f"Loaded {len(df)} points.")
            render_map(df, selected_map, swap_xz, invert_z, use_y_as_z, off_x, off_y, scale_factor, show_towns)
        else:
            st.error("No coordinates found.")
    else:
        render_map(pd.DataFrame(), selected_map, swap_xz, invert_z, use_y_as_z, off_x, off_y, scale_factor, show_towns)
        st.info("Upload a log file to start.")

if __name__ == "__main__":
    main()
