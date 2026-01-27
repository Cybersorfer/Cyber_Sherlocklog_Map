import streamlit as st
import plotly.graph_objects as go
import re
import pandas as pd
from PIL import Image

# --- 1. CONFIGURATION & DATABASE ---
MAP_CONFIG = {
    "Chernarus": {"size": 15360, "image": "map_chernarus.png"},
    "Livonia": {"size": 12800, "image": "map_livonia.png"},
    "Sakhal": {"size": 8192, "image": "map_sakhal.png"}
}

# Icon Mapping for Markers
MARKER_ICONS = {
    "Base": "🏠",
    "Vehicle": "🚗",
    "Body": "💀",
    "Loot": "🎒",
    "POI": "📍",
    "Enemy": "⚔️"
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
        {"name": "Balota", "x": 4400, "z": 2400}
    ],
    "Livonia": [
        {"name": "Topolin", "x": 6200, "z": 11000},
        {"name": "Brena", "x": 6300, "z": 11800},
        {"name": "Nadbor", "x": 5600, "z": 4500}
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
                "activity": line.strip()[:150] 
            })
    return pd.DataFrame(logs)

# --- 3. COORDINATE MATH ---
def transform_coords(raw_x, raw_z, settings, map_size):
    """Convert Game Coords -> Map Plot Coords"""
    final_x = raw_z if settings['swap_xz'] else raw_x
    final_z = raw_x if settings['swap_xz'] else raw_z
    
    if settings['invert_z']:
        final_z = map_size - final_z
        
    final_x = (final_x * settings['scale_factor']) + settings['off_x']
    final_z = (final_z * settings['scale_factor']) + settings['off_y']
    return final_x, final_z

def reverse_transform(plot_x, plot_z, settings, map_size):
    """Convert Map Plot Coords -> Game Coords (For clicking)"""
    # 1. Reverse Offset & Scale
    rx = (plot_x - settings['off_x']) / settings['scale_factor']
    rz = (plot_z - settings['off_y']) / settings['scale_factor']
    
    # 2. Reverse Invert
    if settings['invert_z']:
        rz = map_size - rz
        
    # 3. Reverse Swap
    game_x = rz if settings['swap_xz'] else rx
    game_z = rx if settings['swap_xz'] else rz
    
    return game_x, game_z

# --- 4. MAP RENDERING ENGINE ---
def render_map(df, map_name, settings, search_term, custom_markers):
    config = MAP_CONFIG[map_name]
    map_size = config["size"]
    
    fig = go.Figure()

    # -- A. Load Map Image --
    try:
        img = Image.open(config["image"])
        fig.add_layout_image(
            dict(source=img, xref="x", yref="y", x=0, y=map_size, 
                 sizex=map_size, sizey=map_size, sizing="stretch", 
                 opacity=1, layer="below")
        )
    except Exception:
        # Fallback grid if image fails
        fig.add_shape(type="rect", x0=0, y0=0, x1=map_size, y1=map_size, 
                      line=dict(color="RoyalBlue"), fillcolor="black")

    # -- B. Plot Towns --
    if settings['show_towns'] and map_name in TOWN_DATA:
        t_x, t_y, t_names = [], [], []
        hits_x, hits_y = [], []
        
        for town in TOWN_DATA[map_name]:
            tx, ty = transform_coords(town['x'], town['z'], settings, map_size)
            t_x.append(tx); t_y.append(ty); t_names.append(town['name'])
            
            if search_term and search_term.lower() in town['name'].lower():
                hits_x.append(tx); hits_y.append(ty)

        fig.add_trace(go.Scatter(
            x=t_x, y=t_y, mode='markers+text', text=t_names, textposition="top center",
            marker=dict(size=6, color='yellow', line=dict(width=1, color='black')),
            textfont=dict(size=10, color="black"), hoverinfo='none', name="Towns"
        ))
        
        if hits_x:
            fig.add_trace(go.Scatter(
                x=hits_x, y=hits_y, mode='markers', 
                marker=dict(size=25, color='rgba(0, 255, 0, 0.4)', line=dict(width=2, color='lime')),
                name="Search Hit", hoverinfo='skip'
            ))

    # -- C. Plot Custom Markers (Icons) --
    if custom_markers:
        c_x, c_y, c_text, c_hover = [], [], [], []
        for m in custom_markers:
            cx, cy = transform_coords(m['x'], m['z'], settings, map_size)
            icon = MARKER_ICONS.get(m['type'], "📍")
            
            c_x.append(cx)
            c_y.append(cy)
            c_text.append(icon) # The Emoji on the map
            c_hover.append(f"{m['type']}: {m['label']}")

        fig.add_trace(go.Scatter(
            x=c_x, y=c_y, mode='text', 
            text=c_text, 
            textfont=dict(size=20), # Large Emojis
            name="Markers",
            textposition="middle center",
            hovertext=c_hover,
            hoverinfo="text"
        ))

    # -- D. Plot Players --
    if not df.empty:
        # Determine X and Z columns based on fix
        raw_x = df["raw_1"]
        raw_z = df["raw_2"] if settings['use_y_as_z'] else df["raw_3"]
        
        final_x, final_z = transform_coords(raw_x, raw_z, settings, map_size)

        fig.add_trace(go.Scatter(
            x=final_x, y=final_z, mode='markers',
            marker=dict(size=6, color='red', line=dict(width=1, color='white')),
            text=df["name"], customdata=df["activity"],
            hovertemplate="<b>%{text}</b><br>%{customdata}<extra></extra>",
            name="Players"
        ))

    # -- E. Layout & Tools --
    fig.update_xaxes(range=[0, map_size], visible=False, fixedrange=False)
    fig.update_yaxes(range=[0, map_size], visible=False, fixedrange=False)

    fig.update_layout(
        width=900, height=800,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        dragmode="pan" if settings['click_mode'] == "Navigate" else False, # Disable pan if in Click Mode
        showlegend=True,
        legend=dict(y=0.99, x=0.99, bgcolor="rgba(0,0,0,0.5)", font=dict(color="white"))
    )
    
    return fig, map_size

# --- 5. MAIN APP ---
def main():
    st.set_page_config(layout="wide", page_title="DayZ Intel Mapper")

    # Session State Init
    if 'custom_markers' not in st.session_state: st.session_state['custom_markers'] = []
    
    # Styling
    st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .block-container { padding-top: 1rem !important; }
        [data-testid="stSidebar"] { background-color: #262730; }
        div[data-baseweb="select"] > div { background-color: #404040 !important; }
    </style>
    """, unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🗺️ Intel Control")
        selected_map = st.selectbox("Map", list(MAP_CONFIG.keys()))
        uploaded_file = st.file_uploader("Upload Logs", type=['adm', 'rpt', 'log'])
        
        st.markdown("---")
        # MODE SWITCHER
        click_mode = st.radio("🖱️ Mouse Mode", ["Navigate", "🎯 Add Marker"], horizontal=True)
        search_term = st.text_input("🔍 Search", placeholder="Town or Player")
        
        st.markdown("---")
        with st.expander("⚙️ Calibration"):
            settings = {
                "use_y_as_z": st.checkbox("Fix Ocean Dots", True),
                "swap_xz": st.checkbox("Swap X/Z", False),
                "invert_z": st.checkbox("Invert Vertical", False),
                "off_x": st.slider("X Off", -2000, 2000, 0, 10),
                "off_y": st.slider("Y Off", -2000, 2000, 0, 10),
                "scale_factor": st.slider("Scale", 0.8, 1.2, 1.0, 0.005),
                "show_towns": st.checkbox("Towns", True),
                "click_mode": click_mode
            }
        
        # Markers List
        if st.session_state['custom_markers']:
            st.markdown("---")
            st.write(f"**Markers ({len(st.session_state['custom_markers'])})**")
            if st.button("Clear All Markers"):
                st.session_state['custom_markers'] = []
                st.rerun()

    # --- MAIN CONTENT ---
    col1, col2 = st.columns([0.85, 0.15])
    with col1:
        st.subheader(f"📍 {selected_map} | Mode: {click_mode}")
    
    # 1. Parse Data
    df = parse_log_file(uploaded_file) if uploaded_file else pd.DataFrame()
    if not df.empty and search_term:
        matches = df[df['name'].str.contains(search_term, case=False, na=False)]
        if not matches.empty: st.info(f"Found {len(matches)} player logs matching search.")

    # 2. Render Map
    fig, map_size = render_map(df, selected_map, settings, search_term, st.session_state['custom_markers'])

    # 3. Display Map with Click Detection
    # 'on_select="rerun"' enables the click interaction
    event = st.plotly_chart(
        fig, 
        on_select="rerun",
        selection_mode="points",
        use_container_width=True,
        config={
            'scrollZoom': True, 
            'displayModeBar': True,
            # Enable the specific tools requested
            'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'resetScale2d', 'pan2d'],
            'displaylogo': False
        }
    )

    # 4. HANDLE CLICKS (Add Marker Logic)
    if click_mode == "🎯 Add Marker" and len(event.selection.points) > 0:
        # Get click coordinates (Plot Coordinates)
        clicked_point = event.selection.points[0]
        plot_x = clicked_point['x']
        plot_y = clicked_point['y']
        
        # Convert back to Game Coordinates
        gx, gz = reverse_transform(plot_x, plot_y, settings, map_size)
        
        # Show Dialog to Add Marker
        @st.dialog("Add New Marker")
        def add_marker_dialog(ix, iz):
            st.write(f"📍 Location: {ix:.0f}, {iz:.0f}")
            m_type = st.selectbox("Type", list(MARKER_ICONS.keys()))
            m_label = st.text_input("Label", placeholder="e.g. Main Base")
            
            if st.button("Save Marker"):
                st.session_state['custom_markers'].append({
                    "type": m_type,
                    "label": m_label,
                    "x": ix,
                    "z": iz
                })
                st.rerun()

        add_marker_dialog(gx, gz)

if __name__ == "__main__":
    main()
