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

# --- TOWN DATABASE (Restored & Permanent) ---
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

# Default Database (Used if no CSV is uploaded)
DEFAULT_POI_DATABASE = {
    "Chernarus": {
        "🛡️ Military": [{"name": "Tisy Radar", "x": 1700, "z": 14000}],
        "🏰 Castles": [{"name": "Devil's Castle", "x": 6800, "z": 11500}],
    }
}

MARKER_ICONS = {
    "Base": "🏠", "Vehicle": "🚗", "Body": "💀", 
    "Loot": "🎒", "POI": "📍", "Enemy": "⚔️"
}

# --- 2. DATA PARSING ENGINES ---
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
                "raw_1": float(v1), "raw_2": float(v2), "raw_3": float(v3),
                "activity": line.strip()[:150] 
            })
    return pd.DataFrame(logs)

def parse_poi_csv(uploaded_csv):
    try:
        df = pd.read_csv(uploaded_csv)
        new_db = {}
        for _, row in df.iterrows():
            m_name = row['map']
            cat = row['category']
            if m_name not in new_db: new_db[m_name] = {}
            if cat not in new_db[m_name]: new_db[m_name][cat] = []
            new_db[m_name][cat].append({
                "name": row['name'], "x": float(row['x']), "z": float(row['z'])
            })
        return new_db
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        return DEFAULT_POI_DATABASE

# --- 3. MATH ---
def transform_coords(raw_x, raw_z, settings, map_size):
    final_x = raw_z if settings['swap_xz'] else raw_x
    final_z = raw_x if settings['swap_xz'] else raw_z
    if settings['invert_z']: final_z = map_size - final_z
    final_x = (final_x * settings['scale_factor']) + settings['off_x']
    final_z = (final_z * settings['scale_factor']) + settings['off_y']
    return final_x, final_z

def reverse_transform(plot_x, plot_z, settings, map_size):
    rx = (plot_x - settings['off_x']) / settings['scale_factor']
    rz = (plot_z - settings['off_y']) / settings['scale_factor']
    if settings['invert_z']: rz = map_size - rz
    game_x = rz if settings['swap_xz'] else rx
    game_z = rx if settings['swap_xz'] else rz
    return game_x, game_z

# --- 4. RENDER ENGINE ---
def render_map(df, map_name, settings, search_term, custom_markers, active_layers, poi_db):
    config = MAP_CONFIG[map_name]
    map_size = config["size"]
    fig = go.Figure()

    # A. Map Image
    try:
        img = Image.open(config["image"])
        fig.add_layout_image(
            dict(source=img, xref="x", yref="y", x=0, y=map_size, 
                 sizex=map_size, sizey=map_size, sizing="stretch", 
                 opacity=1, layer="below")
        )
    except:
        fig.add_shape(type="rect", x0=0, y0=0, x1=map_size, y1=map_size, line=dict(color="RoyalBlue"))

    # B. GRID SYSTEM (Lines & Labels)
    if settings['show_grid']:
        # 1. Draw Grid Lines
        for i in range(0, int(map_size), 1000):
            t_val = (i * settings['scale_factor']) + settings['off_x']
            t_val_y = (i * settings['scale_factor']) + settings['off_y']
            
            # Vertical
            fig.add_shape(type="line", x0=t_val, y0=0, x1=t_val, y1=map_size,
                          line=dict(color="rgba(255, 255, 255, 0.15)", width=1, dash="dot"))
            # Horizontal
            fig.add_shape(type="line", x0=0, y0=t_val_y, x1=map_size, y1=t_val_y,
                          line=dict(color="rgba(255, 255, 255, 0.15)", width=1, dash="dot"))

        # 2. Draw Edge Labels (0, 1, 2... 15)
        grid_labels_x = []
        grid_labels_y = []
        grid_text = []
        
        # Calculate positions (Offset by 500m to center text in grid square)
        for i in range(16): # 0 to 15
            center_pos = (i * 1000) + 500
            t_pos, _ = transform_coords(center_pos, 0, settings, map_size) # Transform X
            _, t_pos_y = transform_coords(0, center_pos, settings, map_size) # Transform Y (actually Z in game)
            
            # Top Edge Numbers
            fig.add_trace(go.Scatter(
                x=[t_pos], y=[map_size - 200], # Slightly inside top edge
                mode='text', text=[str(i)],
                textfont=dict(size=14, color='rgba(255,255,255,0.7)', family="Arial Black"),
                hoverinfo='skip', showlegend=False
            ))
            
            # Left Edge Numbers
            fig.add_trace(go.Scatter(
                x=[200], y=[t_pos_y], # Slightly inside left edge
                mode='text', text=[str(i)],
                textfont=dict(size=14, color='rgba(255,255,255,0.7)', family="Arial Black"),
                hoverinfo='skip', showlegend=False
            ))

    # C. TOWNS (Permanent Layer)
    if settings['show_towns'] and map_name in TOWN_DATA:
        t_x, t_y, t_names = [], [], []
        for town in TOWN_DATA[map_name]:
            tx, ty = transform_coords(town['x'], town['z'], settings, map_size)
            t_x.append(tx); t_y.append(ty); t_names.append(town['name'])
        
        fig.add_trace(go.Scatter(
            x=t_x, y=t_y, 
            mode='markers+text', # TEXT ENABLED
            text=t_names, 
            textposition="top center",
            marker=dict(size=6, color='yellow', line=dict(width=1, color='black')),
            textfont=dict(family="Arial Black", size=11, color="black"), # BLACK TEXT
            hoverinfo='none', name="Towns"
        ))

    # D. STATIC LAYERS (CSV / POI DB)
    if map_name in poi_db:
        for layer_name, locations in poi_db[map_name].items():
            if layer_name in active_layers:
                l_x, l_y, l_txt = [], [], []
                for loc in locations:
                    tx, ty = transform_coords(loc['x'], loc['z'], settings, map_size)
                    l_x.append(tx); l_y.append(ty); l_txt.append(loc['name'])
                
                color = "cyan"
                if "Military" in layer_name: color = "red"
                elif "Castle" in layer_name: color = "purple"
                
                fig.add_trace(go.Scatter(
                    x=l_x, y=l_y, mode='markers',
                    marker=dict(size=8, color=color, symbol='diamond', line=dict(width=1, color='black')),
                    text=l_txt, name=layer_name, hoverinfo='text'
                ))

    # E. CUSTOM MARKERS
    if custom_markers:
        c_x, c_y, c_text = [], [], []
        for m in custom_markers:
            cx, cy = transform_coords(m['x'], m['z'], settings, map_size)
            c_x.append(cx); c_y.append(cy)
            c_text.append(MARKER_ICONS.get(m['type'], "📍"))

        fig.add_trace(go.Scatter(
            x=c_x, y=c_y, mode='text', text=c_text, textfont=dict(size=20),
            name="Custom", hoverinfo="text", hovertext=[m['label'] for m in custom_markers]
        ))

    # F. PLAYERS (LOGS)
    if not df.empty:
        raw_x = df["raw_1"]
        raw_z = df["raw_2"] if settings['use_y_as_z'] else df["raw_3"]
        fx, fz = transform_coords(raw_x, raw_z, settings, map_size)
        
        colors = ['red'] * len(df)
        sizes = [6] * len(df)
        if search_term:
            mask = df['name'].str.contains(search_term, case=False, na=False)
            colors = ['lime' if m else 'rgba(255,0,0,0.3)' for m in mask]
            sizes = [15 if m else 6 for m in mask]

        fig.add_trace(go.Scatter(
            x=fx, y=fz, mode='markers',
            marker=dict(size=sizes, color=colors, line=dict(width=1, color='white')),
            text=df["name"], customdata=df["activity"],
            hovertemplate="<b>%{text}</b><br>%{customdata}<extra></extra>",
            name="Logs"
        ))

    # G. LAYOUT
    fig.update_layout(
        width=900, height=800,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        dragmode="pan" if settings['click_mode'] == "Navigate" else False,
        showlegend=True,
        # LEGEND LOWERED TO 0.85 TO AVOID ZOOM TOOLS
        legend=dict(
            yanchor="top", y=0.85, 
            xanchor="right", x=0.99, 
            bgcolor="rgba(0,0,0,0.5)", 
            font=dict(color="white")
        )
    )
    fig.update_xaxes(visible=False, range=[0, map_size])
    fig.update_yaxes(visible=False, range=[0, map_size])
    
    return fig, map_size

# --- 5. MAIN UI ---
def main():
    st.set_page_config(layout="wide", page_title="DayZ Intel Mapper")
    if 'custom_markers' not in st.session_state: st.session_state['custom_markers'] = []
    
    st.markdown("""
    <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        [data-testid="stSidebar"] { background-color: #262730; }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] div[role="radiogroup"] p, 
        [data-testid="stFileUploader"] small, .streamlit-expanderHeader p {
            color: #cccccc !important;
        }
        .block-container { padding-top: 1rem !important; }
        div[data-baseweb="select"] > div { background-color: #404040 !important; }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("🗺️ Intel Control")
        selected_map = st.selectbox("Map", list(MAP_CONFIG.keys()))
        
        st.write("---")
        uploaded_log = st.file_uploader("1. Upload Logs (.ADM/.RPT)", type=['adm', 'rpt', 'log'])
        uploaded_csv = st.file_uploader("2. Upload POI Database (.CSV)", type=['csv'])
        
        if uploaded_csv:
            current_db = parse_poi_csv(uploaded_csv)
            st.success("✅ Custom Database Loaded")
        else:
            current_db = DEFAULT_POI_DATABASE

        st.markdown("---")
        st.subheader("👁️ Layers")
        available_layers = current_db.get(selected_map, {}).keys()
        active_layers = []
        if available_layers:
            for layer in available_layers:
                if st.checkbox(layer, value=True):
                    active_layers.append(layer)
        
        # Grid & Town Toggles
        show_grid = st.checkbox("Show Grid (0-15)", value=True)
        show_towns = st.checkbox("Show Town Names", value=True)

        st.markdown("---")
        click_mode = st.radio("🖱️ Mouse Mode", ["Navigate", "🎯 Add Marker"], horizontal=True)
        search_term = st.text_input("🔍 Search", placeholder="Player Name...")
        
        with st.expander("⚙️ Calibration"):
            settings = {
                "use_y_as_z": st.checkbox("Fix Ocean Dots", True),
                "swap_xz": st.checkbox("Swap X/Z", False),
                "invert_z": st.checkbox("Invert Vertical", False),
                "off_x": st.slider("X Off", -2000, 2000, 0, 10),
                "off_y": st.slider("Y Off", -2000, 2000, 0, 10),
                "scale_factor": st.slider("Scale", 0.8, 1.2, 1.0, 0.005),
                "click_mode": click_mode,
                "show_grid": show_grid,
                "show_towns": show_towns
            }
            
        if st.session_state['custom_markers']:
            st.markdown("---")
            if st.button("Clear Markers"):
                st.session_state['custom_markers'] = []
                st.rerun()

    col1, col2 = st.columns([0.85, 0.15])
    with col1: st.subheader(f"📍 {selected_map}")
    
    df = parse_log_file(uploaded_log) if uploaded_log else pd.DataFrame()
    fig, map_size = render_map(df, selected_map, settings, search_term, st.session_state['custom_markers'], active_layers, current_db)

    event = st.plotly_chart(
        fig, on_select="rerun", selection_mode="points", use_container_width=True,
        config={'scrollZoom': True, 'displayModeBar': True, 'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'resetScale2d', 'pan2d'], 'displaylogo': False}
    )

    if click_mode == "🎯 Add Marker" and len(event.selection.points) > 0:
        p = event.selection.points[0]
        gx, gz = reverse_transform(p['x'], p['y'], settings, map_size)
        
        @st.dialog("Add Marker")
        def add_marker_dialog():
            st.write(f"Grid: {gx/1000:.1f} / {gz/1000:.1f}")
            m_type = st.selectbox("Type", list(MARKER_ICONS.keys()))
            m_label = st.text_input("Label")
            if st.button("Save"):
                st.session_state['custom_markers'].append({"type": m_type, "label": m_label, "x": gx, "z": gz})
                st.rerun()
        add_marker_dialog()

if __name__ == "__main__":
    main()
