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

    # Regex to find coordinates <X, Y, Z>
    coord_pattern = re.compile(r"<([0-9\.-]+),\s*([0-9\.-]+),\s*([0-9\.-]+)>")
    # Regex to find Player Name
    name_pattern = re.compile(r'(?:Player|Identity)\s+"([^"]+)"')

    for line in lines:
        coord_match = coord_pattern.search(line)
        if coord_match:
            v1, v2, v3 = coord_match.groups()
            name_match = name_pattern.search(line)
            name = name_match.group(1) if name_match else "Unknown"
            
            # Clean up the line to use as "Activity" description
            clean_activity = line.strip()[:150] # Take first 150 chars
            
            logs.append({
                "name": name,
                "raw_1": float(v1),
                "raw_2": float(v2),
                "raw_3": float(v3),
                "activity": clean_activity 
            })
            
    return pd.DataFrame(logs)

# --- 3. MAP RENDERING ENGINE ---
def render_map(df, map_name, settings, search_term, custom_markers):
    config = MAP_CONFIG[map_name]
    map_size = config["size"]
    img_path = config["image"]
    
    # Unpack settings
    swap_xz = settings['swap_xz']
    invert_z = settings['invert_z']
    use_y_as_z = settings['use_y_as_z']
    off_x = settings['off_x']
    off_y = settings['off_y']
    scale_factor = settings['scale_factor']
    show_towns = settings['show_towns']

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

    # -- B. Helper: Coordinate Transformation --
    def transform_coords(raw_x, raw_z):
        final_x = raw_z if swap_xz else raw_x
        final_z = raw_x if swap_xz else raw_z
        if invert_z:
            final_z = map_size - final_z
        final_x = (final_x * scale_factor) + off_x
        final_z = (final_z * scale_factor) + off_y
        return final_x, final_z

    # -- C. Plot Towns (Toggleable) --
    if map_name in TOWN_DATA:
        towns = TOWN_DATA[map_name]
        t_x, t_y, t_names = [], [], []
        
        search_hits_x = []
        search_hits_y = []

        for town in towns:
            tx, ty = transform_coords(town['x'], town['z'])
            t_x.append(tx)
            t_y.append(ty)
            t_names.append(town['name'])
            
            # SEARCH LOGIC: Check if town matches search term
            if search_term and search_term.lower() in town['name'].lower():
                search_hits_x.append(tx)
                search_hits_y.append(ty)

        if show_towns:
            fig.add_trace(go.Scatter(
                x=t_x,
                y=t_y,
                mode='markers+text',
                text=t_names,
                textposition="top center",
                marker=dict(size=8, color='yellow', line=dict(width=1, color='black')),
                textfont=dict(family="Arial Black", size=12, color="black"),
                hoverinfo='none',
                name="Towns" # Legend Item
            ))
            
        # Plot Search Highlights (Big Green Circles)
        if search_hits_x:
            fig.add_trace(go.Scatter(
                x=search_hits_x,
                y=search_hits_y,
                mode='markers',
                marker=dict(size=25, color='rgba(0, 255, 0, 0.3)', line=dict(width=2, color='lime')),
                name="Search Result",
                hoverinfo='skip'
            ))

    # -- D. Plot Custom Markers --
    if custom_markers:
        c_x, c_y, c_names = [], [], []
        for m in custom_markers:
            cx, cy = transform_coords(m['x'], m['z'])
            c_x.append(cx)
            c_y.append(cy)
            c_names.append(m['label'])
            
        fig.add_trace(go.Scatter(
            x=c_x,
            y=c_y,
            mode='markers+text',
            text=c_names,
            textposition="bottom center",
            marker=dict(size=12, symbol="star", color='cyan', line=dict(width=1, color='blue')),
            textfont=dict(color='cyan', size=11),
            name="Custom Markers",
            hovertemplate="<b>%{text}</b><extra></extra>"
        ))

    # -- E. Plot Log Data (Players) --
    if not df.empty:
        raw_x_col = df["raw_1"]
        raw_z_col = df["raw_2"] if use_y_as_z else df["raw_3"]
        
        final_x = raw_z_col if swap_xz else raw_x_col
        final_z = raw_x_col if swap_xz else raw_z_col
        
        if invert_z:
            final_z = map_size - final_z
            
        final_x = (final_x * scale_factor) + off_x
        final_z = (final_z * scale_factor) + off_y
        
        # Prepare detailed hover text
        # storing activity in customdata to use in hovertemplate
        
        fig.add_trace(
            go.Scatter(
                x=final_x,
                y=final_z,
                mode='markers',
                marker=dict(size=7, color='red', line=dict(width=1, color='white')),
                text=df["name"],
                customdata=df["activity"], # Passing full activity text
                # HOVER TEMPLATE: Shows Name, Coords, AND Activity
                hovertemplate="<b>%{text}</b><br>X: %{x:.0f}, Z: %{y:.0f}<br><i>%{customdata}</i><extra></extra>",
                name="Players"
            )
        )

    # -- F. Lock Axes & Layout --
    fig.update_xaxes(range=[0, map_size], visible=False, showgrid=False, fixedrange=False)
    fig.update_yaxes(range=[0, map_size], visible=False, showgrid=False, fixedrange=False)

    fig.update_layout(
        width=900,
        height=850,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        plot_bgcolor="#0e1117",  
        paper_bgcolor="#0e1117", 
        dragmode="pan",          # Default to panning
        showlegend=True,         # SHOW LEGEND so user can toggle layers
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(0,0,0,0.5)",
            font=dict(color="white")
        )
    )

    # -- G. Render --
    st.plotly_chart(
        fig, 
        use_container_width=True, 
        config={
            'scrollZoom': True,       # ENABLE MOUSE ZOOM
            'displayModeBar': True,   # SHOW TOOLS
            'displaylogo': False,
            'modeBarButtonsToRemove': ['select2d', 'lasso2d', 'autoScale2d'] # Clean up tools
        }
    )

# --- 4. MAIN INTERFACE ---
def main():
    st.set_page_config(layout="wide", page_title="DayZ Log Mapper")

    # Initialize Session State for Custom Markers
    if 'custom_markers' not in st.session_state:
        st.session_state['custom_markers'] = []

    # CSS Styling
    st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
        [data-testid="stSidebar"] { background-color: #262730; color: #fafafa; }
        .stButton>button { color: #ffffff; background-color: #4CAF50; border: none; }
        div[data-baseweb="select"] > div { background-color: #404040 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.title("🗺️ Control Panel")
        
        selected_map = st.selectbox("Select Map", list(MAP_CONFIG.keys()))
        uploaded_file = st.file_uploader("📂 Upload .ADM / .RPT / .LOG", type=['adm', 'rpt', 'log', 'txt'])
        
        st.markdown("---")
        st.subheader("🔍 Search")
        search_term = st.text_input("Find Town or Player", placeholder="e.g. Novy or Survivor")
        
        st.markdown("---")
        with st.expander("📍 Custom Markers (Add Tools)"):
            c_name = st.text_input("Label", "Base")
            c_x = st.number_input("X Coord", value=0)
            c_z = st.number_input("Z Coord", value=0)
            if st.button("Add Marker"):
                st.session_state['custom_markers'].append({"label": c_name, "x": c_x, "z": c_z})
                st.success(f"Added {c_name}")
            
            if st.button("Clear All Custom Markers"):
                st.session_state['custom_markers'] = []
                st.rerun()

        st.markdown("---")
        with st.expander("⚙️ Calibration & Settings"):
            use_y_as_z = st.checkbox("Fix: Dots in Ocean?", value=True)
            swap_xz = st.checkbox("Swap X/Z Axis", value=False)
            invert_z = st.checkbox("Invert Vertical", value=False)
            off_x = st.slider("X Offset", -2000, 2000, -20, step=10)
            off_y = st.slider("Y Offset", -2000, 2000, -20, step=10)
            scale_factor = st.slider("Zoom Scale", 0.8, 1.2, 1.0, step=0.005)
            show_towns = st.checkbox("Show Town Names", value=True)
            
            settings = {
                "use_y_as_z": use_y_as_z, "swap_xz": swap_xz, "invert_z": invert_z,
                "off_x": off_x, "off_y": off_y, "scale_factor": scale_factor,
                "show_towns": show_towns
            }

    # Main Area
    if uploaded_file:
        df = parse_log_file(uploaded_file)
        if not df.empty:
            st.success(f"Loaded {len(df)} activities.")
            
            # Filter DataFrame if Searching for Player
            if search_term:
                 # Case insensitive search in Name
                 matches = df[df['name'].str.contains(search_term, case=False, na=False)]
                 if not matches.empty:
                     st.info(f"Found {len(matches)} logs for '{search_term}'")
                     # We still pass full DF to see context, but you could pass 'matches' to isolate
        else:
            st.error("No coordinates found in file.")
    else:
        df = pd.DataFrame()

    render_map(df, selected_map, settings, search_term, st.session_state['custom_markers'])

if __name__ == "__main__":
    main()
