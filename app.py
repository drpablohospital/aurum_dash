import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime
import numpy as np
import time
import uuid
import ccxt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================
# CONFIGURACIÓN DE LA PÁGINA (TEMA EXPERIMENTAL)
# ============================================
st.set_page_config(
    page_title="AURUM · BTC/USDT FUTURES TRADING",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------------------------
# CSS BRUTALISTA / MUSEO DE ARTE CONTEMPORÁNEO
# ----------------------------------------------------------------------
st.markdown("""
<style>
    /* RESET DE ESTILOS DE STREAMLIT */
    .stApp {
        background-color: #FFFFFF !important;
    }
    .main > div {
        background-color: #FFFFFF;
    }
    .block-container {
        padding: 2rem 3rem !important;
        max-width: 100% !important;
    }
    
    /* TIPOGRAFÍA */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;700;900&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Inter', 'Helvetica Neue', sans-serif;
    }
    h1, h2, h3, h4 {
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: -0.02em;
        color: #000000 !important;
        margin: 0 0 1rem 0;
        line-height: 1;
    }
    h1 {
        font-size: 4rem;
        border-bottom: 4px solid #000000;
        padding-bottom: 0.5rem;
    }
    h2 {
        font-size: 2.5rem;
        border-bottom: 2px solid #000000;
        padding-bottom: 0.25rem;
    }
    h3 {
        font-size: 1.5rem;
        font-weight: 700;
    }
    p, li, .stMarkdown, .stText {
        font-weight: 300;
        color: #000000;
    }
    .small-caption {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #666666;
    }
    
    /* BARRAS LATERALES Y PANELES */
    .sidebar .sidebar-content {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border-right: 4px solid #FFD600;
    }
    .sidebar .sidebar-content h1,
    .sidebar .sidebar-content h2,
    .sidebar .sidebar-content h3,
    .sidebar .sidebar-content p {
        color: #FFFFFF !important;
    }
    .sidebar .sidebar-content .stMetric label,
    .sidebar .sidebar-content .stMetric value {
        color: #FFFFFF !important;
    }
    
    /* TARJETAS / MÓDULOS DE EXPOSICIÓN */
    .exhibition-panel {
        border: 2px solid #000000;
        padding: 1.5rem;
        margin: 1rem 0;
        background-color: #FFFFFF;
        transition: all 0.1s ease;
    }
    .exhibition-panel:hover {
        background-color: #F2F2F2;
    }
    .exhibition-panel.warning-stripe {
        background: repeating-linear-gradient(
            45deg,
            #FFD600,
            #FFD600 10px,
            #FFFFFF 10px,
            #FFFFFF 20px
        );
        border: 3px solid #000000;
    }
    
    /* BOTONES */
    .stButton button {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #000000 !important;
        border-radius: 0 !important;
        font-weight: 900 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        padding: 0.75rem 2rem !important;
        box-shadow: none !important;
        transition: 0.1s;
    }
    .stButton button:hover {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border-color: #FFD600 !important;
    }
    
    /* INPUTS */
    .stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox select {
        border: none !important;
        border-bottom: 2px solid #000000 !important;
        border-radius: 0 !important;
        background-color: transparent !important;
        padding: 0.5rem 0 !important;
        font-weight: 300;
        box-shadow: none !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-bottom-color: #FFD600 !important;
    }
    
    /* MÉTRICAS PERSONALIZADAS */
    .metric-block {
        border: 2px solid #000000;
        padding: 1rem;
        text-align: center;
    }
    .metric-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #666;
        margin-bottom: 0.25rem;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: 900;
        line-height: 1;
        color: #000;
    }
    .metric-value.positive { color: #000000; }
    .metric-value.negative { color: #FF2D2D; }
    
    /* TABLAS */
    .stDataFrame, .stTable {
        border: 2px solid #000000 !important;
    }
    .stDataFrame th, .stTable th {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.8rem;
        padding: 0.5rem;
        border: none;
    }
    .stDataFrame td, .stTable td {
        border: 1px solid #CCCCCC;
        padding: 0.5rem;
        font-weight: 300;
    }
    
    /* ENLACES / BOTÓN TELEGRAM PERSONALIZADO */
    .telegram-link {
        display: inline-block;
        background-color: #FFD600;
        color: #000000;
        border: 3px solid #000000;
        padding: 1rem 3rem;
        font-weight: 900;
        text-transform: uppercase;
        text-decoration: none;
        letter-spacing: 0.2em;
        transition: 0.1s;
        margin: 2rem 0;
    }
    .telegram-link:hover {
        background-color: #000000;
        color: #FFD600;
        border-color: #FFD600;
    }
    
    /* RAYAS DIAGONALES (CONSTRUCCIÓN) */
    .construction-ribbon {
        background: repeating-linear-gradient(
            45deg,
            #FFD600,
            #FFD600 10px,
            #000000 10px,
            #000000 20px
        );
        color: #FFFFFF;
        font-weight: 900;
        text-align: center;
        padding: 0.5rem;
        margin: 1rem 0;
        font-size: 1.2rem;
        letter-spacing: 0.2em;
    }
    
    /* PÍXEL / TEXTURA (MUY SUTIL) */
    body::after {
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        pointer-events: none;
        background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4" viewBox="0 0 4 4"><path d="M0 0h1v1H0zM2 2h1v1H2z" fill="%23000000" fill-opacity="0.03"/></svg>');
        z-index: 9999;
    }
    
    /* GRIDS ASIMÉTRICOS (VÍA COLUMNAS DE STREAMLIT) */
    .stColumn {
        border-right: 1px dashed #CCCCCC;
        padding-right: 2rem;
    }
    .stColumn:last-child {
        border-right: none;
    }
    
    /* OCULTAR ELEMENTOS POR DEFECTO DE STREAMLIT (RADIOS, CHECKBOX) */
    .stRadio label, .stCheckbox label {
        color: #000000 !important;
    }
    
    /* TOOLTIPS INSTITUCIONALES */
    .stTooltip {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        border-radius: 0 !important;
        font-weight: 300;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# CONSTANTES
# ============================================
CAPITAL_LOG_FILE = "capital_log.json"
BACKTEST_FILE = "backtest.csv"
STATE_FILE = "state.json"
CONFIG_FILE = "config.json"
USERS_FILE = "users_data.json"

# ============================================
# FUNCIONES DE CARGA DE DATOS (BACKTEST)
# ============================================
@st.cache_data
def load_backtest_data():
    try:
        if os.path.exists(BACKTEST_FILE):
            df = pd.read_csv(BACKTEST_FILE)
            df['entry_time'] = pd.to_datetime(df['entry_time'], utc=True)
            df['exit_time'] = pd.to_datetime(df['exit_time'], utc=True)
            df['pnl_equity_pct'] = pd.to_numeric(df['pnl_equity_pct'], errors='coerce')
            df['R'] = pd.to_numeric(df['R'], errors='coerce')
            df = df.sort_values('entry_time')
            df['cumulative_equity'] = (1 + df['pnl_equity_pct']/100).cumprod() * 10000
            return df
        else:
            st.warning("ARCHIVO NO ENCONTRADO · DATOS DE EJEMPLO")
            return create_sample_backtest()
    except Exception as e:
        st.error(f"ERROR DE CARGA: {e}")
        return create_sample_backtest()

def create_sample_backtest():
    dates = pd.date_range(start='2024-01-01', end='2024-03-16', freq='D')
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, len(dates))
    equity = 10000 * np.cumprod(1 + returns)
    return pd.DataFrame({
        'entry_time': dates,
        'exit_time': dates + pd.Timedelta(hours=1),
        'side': np.random.choice(['LONG', 'SHORT'], len(dates)),
        'exit_reason': np.random.choice(['TP', 'SL', 'TRAIL'], len(dates)),
        'R': np.random.uniform(0.5, 3, len(dates)),
        'pnl_equity_pct': returns * 100,
        'cumulative_equity': equity
    })

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

# ============================================
# FUNCIONES DE TRACKING DE USUARIOS
# ============================================
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def generate_user_id():
    return uuid.uuid4().hex

# ============================================
# FUNCIÓN MEJORADA PARA OBTENER PRECIO BTC (CON CACHÉ Y MÚLTIPLES FUENTES)
# ============================================
@st.cache_data(ttl=60)  # Cachea el resultado durante 60 segundos
def get_btc_price():
    """
    Obtiene el precio actual de BTC/USDT probando múltiples fuentes.
    Cachea el resultado durante 60 segundos para no saturar las APIs.
    """
    # Configura una sesión con reintentos
    session = requests.Session()
    retries = Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.mount('http://', HTTPAdapter(max_retries=retries))

    # Lista de fuentes en orden de preferencia
    sources = [
        {
            'name': 'Binance',
            'url': 'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT',
            'parse': lambda data: float(data['price'])
        },
        {
            'name': 'CoinGecko',
            'url': 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
            'parse': lambda data: float(data['bitcoin']['usd'])
        },
        {
            'name': 'Kraken',
            'url': 'https://api.kraken.com/0/public/Ticker?pair=XBTUSD',
            'parse': lambda data: float(data['result']['XXBTZUSD']['c'][0])
        },
        {
            'name': 'CoinCap',
            'url': 'https://api.coincap.io/v2/assets/bitcoin',
            'parse': lambda data: float(data['data']['priceUsd'])
        },
        {
            'name': 'Binance US',
            'url': 'https://api.binance.us/api/v3/ticker/price?symbol=BTCUSDT',
            'parse': lambda data: float(data['price'])
        }
    ]

    for source in sources:
        try:
            response = session.get(source['url'], timeout=10)
            if response.status_code == 200:
                data = response.json()
                price = source['parse'](data)
                print(f"[get_btc_price] Usando {source['name']}: ${price}")
                return price
            else:
                print(f"[get_btc_price] {source['name']} respondió {response.status_code}")
        except Exception as e:
            print(f"[get_btc_price] Error con {source['name']}: {e}")
            continue

    # Si todas fallan
    st.warning("PRECIO BTC · NO DISPONIBLE (FUENTES NO RESPONDEN)")
    return None

def create_user():
    user_id = generate_user_id()
    users = load_users()
    users[user_id] = {
        "id": user_id,
        "history": [],
        "balances": {"aurum": 0.0, "reserve": 0.0, "btc": 0.0},
        "dca_orders": [
            {"price": 50000, "usdt_allocated": 0.0, "btc_purchased": 0.0, "executed": False},
            {"price": 35000, "usdt_allocated": 0.0, "btc_purchased": 0.0, "executed": False},
            {"price": 20000, "usdt_allocated": 0.0, "btc_purchased": 0.0, "executed": False}
        ],
        "total_usdt_invested": 0.0
    }
    save_users(users)
    return user_id

def process_dca_orders(user_data, btc_price):
    if btc_price is None:
        return user_data
    for order in user_data["dca_orders"]:
        if not order["executed"] and btc_price <= order["price"]:
            btc_bought = order["usdt_allocated"] / order["price"]
            user_data["balances"]["btc"] += btc_bought
            order["btc_purchased"] = btc_bought
            order["executed"] = True
            order["usdt_allocated"] = 0.0
    return user_data

def process_reserve_condition(user_data, btc_price):
    if btc_price is None:
        return user_data
    if btc_price <= 14000 and user_data["balances"]["reserve"] > 0:
        btc_bought = user_data["balances"]["reserve"] / btc_price
        user_data["balances"]["btc"] += btc_bought
        user_data["balances"]["reserve"] = 0.0
        user_data["history"].append({
            "type": "compra_reserva",
            "amount": btc_bought,
            "price": btc_price,
            "date": datetime.now().isoformat()
        })
    return user_data

def register_income(user_id, amount_usdt):
    users = load_users()
    if user_id not in users:
        return False, "USUARIO NO ENCONTRADO"
    user = users[user_id]
    user["history"].append({"type": "ingreso", "amount": amount_usdt, "date": datetime.now().isoformat()})
    aurum_part = amount_usdt * 0.25
    dca_part = amount_usdt * 0.5
    reserve_part = amount_usdt * 0.25
    user["balances"]["aurum"] += aurum_part
    user["balances"]["reserve"] += reserve_part
    proportions = [0.15, 0.35, 0.50]
    for i, order in enumerate(user["dca_orders"]):
        order["usdt_allocated"] += dca_part * proportions[i]
    user["total_usdt_invested"] += amount_usdt
    btc_price = get_btc_price()
    if btc_price:
        user = process_dca_orders(user, btc_price)
        user = process_reserve_condition(user, btc_price)
    users[user_id] = user
    save_users(users)
    return True, "INGRESO REGISTRADO"

def register_withdraw(user_id, amount_usdt):
    users = load_users()
    if user_id not in users:
        return False, "USUARIO NO ENCONTRADO"
    user = users[user_id]
    btc_price = get_btc_price()
    if btc_price is None:
        return False, "PRECIO BTC NO DISPONIBLE"
    total_value = user["balances"]["aurum"] + user["balances"]["reserve"] + user["balances"]["btc"] * btc_price
    if amount_usdt > total_value:
        return False, f"SALDO INSUFICIENTE · DISPONIBLE ${total_value:.2f}"
    remaining = amount_usdt
    # reserva
    if user["balances"]["reserve"] >= remaining:
        user["balances"]["reserve"] -= remaining
        remaining = 0
    else:
        remaining -= user["balances"]["reserve"]
        user["balances"]["reserve"] = 0
        # aurum
        if user["balances"]["aurum"] >= remaining:
            user["balances"]["aurum"] -= remaining
            remaining = 0
        else:
            remaining -= user["balances"]["aurum"]
            user["balances"]["aurum"] = 0
            # btc
            if remaining > 0:
                btc_to_sell = remaining / btc_price
                if user["balances"]["btc"] >= btc_to_sell:
                    user["balances"]["btc"] -= btc_to_sell
                    remaining = 0
                else:
                    return False, "ERROR EN CÁLCULO DE EGRESO"
    user["history"].append({"type": "egreso", "amount": amount_usdt, "date": datetime.now().isoformat()})
    user["total_usdt_invested"] -= amount_usdt
    users[user_id] = user
    save_users(users)
    return True, f"EGRESO DE ${amount_usdt:.2f} REALIZADO"

def get_user_summary(user_id):
    users = load_users()
    if user_id not in users:
        return None
    user = users[user_id]
    btc_price = get_btc_price()
    if btc_price:
        user = process_dca_orders(user, btc_price)
        user = process_reserve_condition(user, btc_price)
        users[user_id] = user
        save_users(users)
    total_usdt = user["balances"]["aurum"] + user["balances"]["reserve"] + user["balances"]["btc"] * btc_price if btc_price else 0
    return {
        "id": user_id,
        "aurum": user["balances"]["aurum"],
        "reserve": user["balances"]["reserve"],
        "btc": user["balances"]["btc"],
        "btc_price": btc_price,
        "total_usdt": total_usdt,
        "dca_orders": user["dca_orders"],
        "history": user["history"],
        "total_invested": user["total_usdt_invested"]
    }

# ============================================
# FUNCIONES DE MÉTRICAS Y GRÁFICOS
# ============================================
def calculate_metrics(df):
    if df.empty:
        return {}
    total_trades = len(df)
    winning = df[df['pnl_equity_pct'] > 0]
    losing = df[df['pnl_equity_pct'] < 0]
    win_rate = len(winning) / total_trades * 100 if total_trades else 0
    avg_win = winning['pnl_equity_pct'].mean() if not winning.empty else 0
    avg_loss = losing['pnl_equity_pct'].mean() if not losing.empty else 0
    total_profit = winning['pnl_equity_pct'].sum() if not winning.empty else 0
    total_loss = abs(losing['pnl_equity_pct'].sum()) if not losing.empty else 1
    profit_factor = total_profit / total_loss if total_loss > 0 else 0
    cumulative = df['cumulative_equity']
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    returns = df['pnl_equity_pct'] / 100
    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
    exit_counts = df['exit_reason'].value_counts()
    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "exit_reason_counts": exit_counts.to_dict(),
        "avg_R": df['R'].mean()
    }

def create_equity_chart(df):
    if df.empty:
        return go.Figure()
    fig = make_subplots(rows=2, cols=1, subplot_titles=('CAPITAL EVOLUTION', 'DRAWDOWN'), vertical_spacing=0.12, row_heights=[0.7, 0.3])
    fig.add_trace(go.Scatter(x=df['exit_time'], y=df['cumulative_equity'], mode='lines', line=dict(color='#000000', width=2), name='Capital'), row=1, col=1)
    rolling_max = df['cumulative_equity'].cummax()
    drawdown = (df['cumulative_equity'] - rolling_max) / rolling_max * 100
    fig.add_trace(go.Scatter(x=df['exit_time'], y=drawdown, fill='tozeroy', line=dict(color='#FF2D2D', width=1), name='Drawdown'), row=2, col=1)
    fig.update_layout(height=600, showlegend=False, paper_bgcolor='#FFFFFF', plot_bgcolor='#FFFFFF', font_color='#000000', title_font_color='#000000')
    fig.update_xaxes(gridcolor='#CCCCCC', linecolor='#000000', tickfont=dict(color='#000000'))
    fig.update_yaxes(gridcolor='#CCCCCC', linecolor='#000000', tickfont=dict(color='#000000'))
    return fig

def create_pnl_distribution_chart(df):
    if df.empty:
        return go.Figure()
    colors = ['#000000' if x > 0 else '#FF2D2D' for x in df['pnl_equity_pct']]
    fig = go.Figure(go.Bar(x=df.index, y=df['pnl_equity_pct'], marker_color=colors))
    fig.update_layout(title="PNL POR TRADE", xaxis_title="TRADE #", yaxis_title="PNL %", height=400, paper_bgcolor='#FFFFFF', plot_bgcolor='#FFFFFF', font_color='#000000')
    fig.update_xaxes(gridcolor='#CCCCCC', tickfont=dict(color='#000000'))
    fig.update_yaxes(gridcolor='#CCCCCC', tickfont=dict(color='#000000'))
    return fig

def create_exit_reason_pie(df):
    if df.empty:
        return go.Figure()
    reason_counts = df['exit_reason'].value_counts()
    colors = {'TP': '#000000', 'SL': '#FF2D2D', 'TRAIL': '#FFD600', 'BE': '#CCCCCC'}
    color_list = [colors.get(r, '#CCCCCC') for r in reason_counts.index]
    fig = go.Figure(data=[go.Pie(labels=reason_counts.index, values=reason_counts.values, hole=0.4, marker_colors=color_list, textfont=dict(color='#000000'))])
    fig.update_layout(title="RAZONES DE SALIDA", height=300, paper_bgcolor='#FFFFFF', font_color='#000000', showlegend=False)
    return fig

# ============================================
# PÁGINA DE INICIO (LANDING) CON ESTÉTICA DE MUSEO
# ============================================
def show_landing_page():
    st.markdown("<h1>AURUM · BTC/USDT FUTURES TRADING</h1>", unsafe_allow_html=True)
    st.markdown("<p class='small-caption'>INVIERTE EN FUTUROS DE BTC · ESTRATEGIA AUDITABLE · WALLET TRACKER · SIMULADOR DE RIESGO</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
        st.markdown("<a href='https://t.me/+-7Ro_KtGxQ8xMzUx' target='_blank' class='telegram-link'>📡 ACCESO AL CANAL</a>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='construction-ribbon'>⚡ PROTOTIPO EN DESARROLLO ⚡</div>", unsafe_allow_html=True)
    
    st.markdown("<h2>FUNDAMENTOS DE LA ESTRATEGIA</h2>", unsafe_allow_html=True)
    colA, colB = st.columns(2)
    with colA:
        st.markdown("""
        <div class='exhibition-panel'>
            <h3>📊 ANÁLISIS MULTICAPA</h3>
            <p>El sistema observa el mercado a través de múltiples timeframes (15m / 1h).<br>
            EMAs, RSI, Donchian y ATR se combinan para definir zonas de probabilidad.</p>
        </div>
        <div class='exhibition-panel'>
            <h3>🛡️ GESTIÓN DE RIESGO</h3>
            <p>Stop loss dinámico, trailing profit, cooldown post-pérdida.<br>
            El capital se administra como material escaso.</p>
        </div>
        """, unsafe_allow_html=True)
    with colB:
        st.markdown("""
        <div class='exhibition-panel'>
            <h3>🎯 EJECUCIÓN POR RUPTURA</h3>
            <p>Las señales se activan solo al romper niveles clave con buffer de volatilidad.<br>
            No hay entradas en rangos laterales.</p>
        </div>
        <div class='exhibition-panel'>
            <h3>📈 BACKTESTING · 2019–2026</h3>
            <p>Más de 950 trades analizados. Las curvas de capital y drawdown están disponibles<br>
            en los módulos de este sistema.</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<h2>WALLET EN VIVO · PRUEBA DE RENDIMIENTO</h2>", unsafe_allow_html=True)
    btc_price = get_btc_price()
    state = load_state()
    btc_display = f"${btc_price:,.2f}" if btc_price else "NO DISPONIBLE"
    status_text = "ACTIVO" if not state.get('paused', False) else "PAUSADO"
    df = load_backtest_data()
    metrics = calculate_metrics(df)
    
    cols = st.columns(4)
    with cols[0]:
        st.markdown(f"<div class='metric-block'><div class='metric-label'>PRECIO BTC</div><div class='metric-value'>{btc_display}</div></div>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"<div class='metric-block'><div class='metric-label'>ESTADO</div><div class='metric-value'>{status_text}</div></div>", unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"<div class='metric-block'><div class='metric-label'>WIN RATE (HIST)</div><div class='metric-value'>{metrics.get('win_rate', 0):.1f}%</div></div>", unsafe_allow_html=True)
    with cols[3]:
        st.markdown(f"<div class='metric-block'><div class='metric-label'>PROFIT FACTOR</div><div class='metric-value'>{metrics.get('profit_factor', 0):.2f}</div></div>", unsafe_allow_html=True)
    
    st.plotly_chart(create_equity_chart(df), use_container_width=True)
    
    st.markdown("<div style='text-align: center; padding: 2rem;'><h3>EXPLORE EL SISTEMA COMPLETO</h3><p>MENÚ LATERAL · MÓDULOS INDEPENDIENTES</p></div>", unsafe_allow_html=True)

# ============================================
# FUNCIONES DE LAS PESTAÑAS (CON ESTILOS ACTUALIZADOS)
# ============================================
def show_dashboard(df, metrics):
    st.title("📈 PANEL PRINCIPAL")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f"<div class='metric-block'><div class='metric-label'>WIN RATE</div><div class='metric-value'>{metrics.get('win_rate', 0):.1f}%</div></div>", unsafe_allow_html=True)
    with col2: st.markdown(f"<div class='metric-block'><div class='metric-label'>PROFIT FACTOR</div><div class='metric-value'>{metrics.get('profit_factor', 0):.2f}</div></div>", unsafe_allow_html=True)
    with col3: st.markdown(f"<div class='metric-block'><div class='metric-label'>TOTAL TRADES</div><div class='metric-value'>{metrics.get('total_trades', 0)}</div></div>", unsafe_allow_html=True)
    with col4: 
        sharpe = metrics.get('sharpe', 0)
        cls = "positive" if sharpe > 1 else "negative" if sharpe < 0 else ""
        st.markdown(f"<div class='metric-block'><div class='metric-label'>SHARPE</div><div class='metric-value {cls}'>{sharpe:.2f}</div></div>", unsafe_allow_html=True)
    st.plotly_chart(create_equity_chart(df), use_container_width=True)
    colL, colR = st.columns(2)
    with colL: st.plotly_chart(create_pnl_distribution_chart(df), use_container_width=True)
    with colR: st.plotly_chart(create_exit_reason_pie(df), use_container_width=True)

def show_backtesting(df, metrics):
    st.title("📜 BACKTESTING DETALLADO")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("MÁX DRAWDOWN", f"{metrics.get('max_drawdown', 0):.2f}%")
    with col2: st.metric("AVG WIN", f"{metrics.get('avg_win', 0):.2f}%")
    with col3: st.metric("AVG LOSS", f"{metrics.get('avg_loss', 0):.2f}%")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("AVG R MÚLTIPLE", f"{metrics.get('avg_R', 0):.2f}")
    with col2: st.metric("TRADES GANADORES", len(df[df['pnl_equity_pct'] > 0]) if not df.empty else 0)
    with col3: st.metric("TRADES PERDEDORES", len(df[df['pnl_equity_pct'] < 0]) if not df.empty else 0)
    if metrics.get('exit_reason_counts'):
        st.subheader("DISTRIBUCIÓN POR RAZÓN DE SALIDA")
        reason_df = pd.DataFrame(list(metrics['exit_reason_counts'].items()), columns=['RAZÓN', 'CANTIDAD']).sort_values('CANTIDAD', ascending=False)
        st.table(reason_df)
    st.subheader("TODOS LOS TRADES")
    if not df.empty:
        display_df = df[['entry_time', 'exit_time', 'side', 'exit_reason', 'R', 'pnl_equity_pct']].copy()
        display_df['pnl_equity_pct'] = display_df['pnl_equity_pct'].round(2)
        display_df['R'] = display_df['R'].round(2)
        st.dataframe(display_df, use_container_width=True)

def show_projections():
    st.title("🔮 PROYECCIÓN HISTÓRICA")
    st.markdown("CALCULA LA GANANCIA TEÓRICA DE UNA INVERSIÓN PASADA EN LA ESTRATEGIA")
    df = load_backtest_data()
    if df.empty:
        st.warning("NO HAY DATOS DE BACKTESTING")
        return
    min_date = df['entry_time'].min().date()
    max_date = df['exit_time'].max().date()
    col1, col2 = st.columns(2)
    with col1:
        investment_date = st.date_input("FECHA DE INVERSIÓN", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        initial_amount = st.number_input("MONTO INICIAL (USDT)", min_value=10.0, value=1000.0, step=100.0)
    if st.button("CALCULAR PROYECCIÓN"):
        inv_dt = pd.Timestamp(investment_date).tz_localize('UTC')
        trades_after = df[df['entry_time'] >= inv_dt]
        if trades_after.empty:
            st.error("NO HAY TRADES DESPUÉS DE ESA FECHA")
            return
        first_idx = trades_after.index[0]
        if first_idx > 0:
            equity_before = df.loc[first_idx - 1, 'cumulative_equity']
        else:
            equity_before = 10000.0
        equity_final = df['cumulative_equity'].iloc[-1]
        growth = equity_final / equity_before
        final = initial_amount * growth
        profit_usd = final - initial_amount
        profit_pct = (growth - 1) * 100
        st.markdown("---")
        colA, colB, colC = st.columns(3)
        with colA: st.metric("INVERSIÓN INICIAL", f"${initial_amount:,.2f}")
        with colB: st.metric("VALOR FINAL", f"${final:,.2f}", delta=f"${profit_usd:,.2f}")
        with colC: st.metric("RENDIMIENTO", f"{profit_pct:.2f}%")
        df_filt = df[df['entry_time'] >= inv_dt].copy()
        if not df_filt.empty:
            df_filt['norm'] = df_filt['cumulative_equity'] / equity_before * initial_amount
            fig = go.Figure(go.Scatter(x=df_filt['exit_time'], y=df_filt['norm'], mode='lines', line=dict(color='#000000')))
            fig.update_layout(title="EVOLUCIÓN DE LA INVERSIÓN", xaxis_title="FECHA", yaxis_title="USDT", height=400, paper_bgcolor='#FFFFFF', plot_bgcolor='#FFFFFF', font_color='#000000')
            st.plotly_chart(fig, use_container_width=True)

def show_tracking():
    st.title("💰 TRACKING DE FONDOS")
    if "tracking_user_id" not in st.session_state:
        st.session_state.tracking_user_id = None
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔑 IDENTIFICACIÓN")
        if st.button("🆕 GENERAR NUEVO USUARIO"):
            new_id = create_user()
            st.session_state.tracking_user_id = new_id
            st.success(f"ID: {new_id}")
            st.info("GUARDE ESTE ID PARA ACCESO FUTURO")
        input_id = st.text_input("O INGRESAR ID EXISTENTE:", value=st.session_state.tracking_user_id or "")
        if st.button("CARGAR USUARIO"):
            if input_id in load_users():
                st.session_state.tracking_user_id = input_id
                st.success("USUARIO CARGADO")
            else:
                st.error("ID NO ENCONTRADO")
    if st.session_state.tracking_user_id:
        user_id = st.session_state.tracking_user_id
        summary = get_user_summary(user_id)
        if summary:
            with col2:
                st.subheader("📊 RESUMEN ACTUAL")
                if summary['btc_price']: st.metric("PRECIO BTC", f"${summary['btc_price']:,.2f}")
                st.metric("AURUM (USDT)", f"${summary['aurum']:,.2f}")
                st.metric("RESERVA (USDT)", f"${summary['reserve']:,.2f}")
                st.metric("BTC ACUMULADO", f"{summary['btc']:.6f}")
                st.metric("VALOR TOTAL", f"${summary['total_usdt']:,.2f}")
                st.metric("TOTAL INVERTIDO", f"${summary['total_invested']:,.2f}")
            st.markdown("---")
            colA, colB = st.columns(2)
            with colA:
                st.subheader("💰 REGISTRAR INGRESO")
                income = st.number_input("CANTIDAD (USDT)", min_value=0.0, value=100.0, key="inc")
                if st.button("REGISTRAR INGRESO"):
                    ok, msg = register_income(user_id, income)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
            with colB:
                st.subheader("💸 REGISTRAR EGRESO")
                withdraw = st.number_input("CANTIDAD (USDT)", min_value=0.0, value=10.0, key="with")
                if st.button("REGISTRAR EGRESO"):
                    ok, msg = register_withdraw(user_id, withdraw)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
            st.markdown("---")
            st.subheader("📈 ÓRDENES DCA")
            dca_df = pd.DataFrame(summary['dca_orders'])
            if not dca_df.empty:
                dca_df['estado'] = dca_df['executed'].apply(lambda x: "✅ EJECUTADA" if x else "⏳ PENDIENTE")
                dca_df['USDT'] = dca_df['usdt_allocated'].round(2)
                dca_df['BTC'] = dca_df['btc_purchased'].round(6)
                st.dataframe(dca_df[['price', 'USDT', 'BTC', 'estado']], use_container_width=True)
            st.subheader("📋 HISTORIAL")
            if summary['history']:
                st.dataframe(pd.DataFrame(summary['history']), use_container_width=True)
            else:
                st.info("NO HAY MOVIMIENTOS")

def show_trades(df):
    st.title("📋 HISTÓRICO DE TRADES")
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("TOTAL TRADES", len(df))
        with col2: st.metric("GANADORES", len(df[df['pnl_equity_pct'] > 0]))
        with col3: st.metric("PERDEDORES", len(df[df['pnl_equity_pct'] < 0]))
        display = df.copy()
        display['entry_time'] = display['entry_time'].dt.strftime('%Y-%m-%d %H:%M')
        display['exit_time'] = display['exit_time'].dt.strftime('%Y-%m-%d %H:%M')
        display['pnl_equity_pct'] = display['pnl_equity_pct'].round(2).astype(str) + '%'
        display['R'] = display['R'].round(2)
        st.dataframe(display[['entry_time', 'exit_time', 'side', 'exit_reason', 'R', 'pnl_equity_pct']], use_container_width=True, height=600)
    else:
        st.warning("NO HAY DATOS DE TRADES")

# ============================================
# INTERFAZ PRINCIPAL
# ============================================
def main():
    with st.sidebar:
        st.markdown("<h1 style='color: #FFD600;'>AURUM</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color: #FFFFFF;'>SISTEMA EN PROCESO</p>", unsafe_allow_html=True)
        st.markdown("---")
        df = load_backtest_data()
        metrics = calculate_metrics(df)
        state = load_state()
        st.markdown("<h3 style='color: #FFFFFF;'>📡 ESTADO DEL BOT</h3>", unsafe_allow_html=True)
        if state.get('paused'):
            st.warning("🔴 PAUSADO")
        else:
            st.success("🟢 ACTIVO")
        st.metric("COOLDOWN", f"{state.get('cooldown_until', 0)} min")
        st.metric("RACHA PÉRDIDAS", state.get('loss_streak', 0))
        st.markdown("---")
        st.markdown("<h3 style='color: #FFFFFF;'>📊 RESUMEN BACKTEST</h3>", unsafe_allow_html=True)
        st.metric("TOTAL TRADES", metrics.get('total_trades', 0))
        st.metric("WIN RATE", f"{metrics.get('win_rate', 0):.1f}%")
        st.metric("PROFIT FACTOR", f"{metrics.get('profit_factor', 0):.2f}")
        st.markdown("---")
        menu = ["🏠 INICIO", "📈 PANEL PRINCIPAL", "📜 BACKTESTING", "🔮 PROYECCIONES", "💰 TRACKING", "📋 TRADES"]
        choice = st.radio("NAVEGACIÓN", menu, label_visibility="collapsed")
    
    if choice == "🏠 INICIO":
        show_landing_page()
    elif choice == "📈 PANEL PRINCIPAL":
        show_dashboard(df, metrics)
    elif choice == "📜 BACKTESTING":
        show_backtesting(df, metrics)
    elif choice == "🔮 PROYECCIONES":
        show_projections()
    elif choice == "💰 TRACKING":
        show_tracking()
    elif choice == "📋 TRADES":
        show_trades(df)

if __name__ == "__main__":
    main()
