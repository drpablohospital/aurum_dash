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

# ============================================
# CONFIGURACIÓN DE LA PÁGINA (TEMA OSCURO PROFESIONAL)
# ============================================
st.set_page_config(
    page_title="AURUM Trading Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado para un look más futurista
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .sidebar .sidebar-content {
        background: #1e2130;
    }
    .Widget>label {
        color: #9ba3c7;
    }
    .stAlert {
        background-color: #1e2130;
        color: white;
        border-left-color: #00c853;
    }
    h1, h2, h3 {
        color: #ffffff;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e2130 0%, #2d3040 100%);
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        border: 1px solid #3d4050;
    }
    .metric-label {
        color: #9ba3c7;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-value {
        color: white;
        font-size: 2rem;
        font-weight: bold;
    }
    .positive {
        color: #00c853;
    }
    .negative {
        color: #ff3d00;
    }
    .telegram-button {
        display: inline-block;
        padding: 12px 24px;
        background: linear-gradient(135deg, #00c853 0%, #00a86b 100%);
        color: white;
        text-decoration: none;
        border-radius: 8px;
        font-weight: bold;
        border: none;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0,200,83,0.3);
    }
    .telegram-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,200,83,0.4);
    }
    .feature-card {
        background: rgba(30,33,48,0.7);
        border-radius: 10px;
        padding: 20px;
        border-left: 4px solid #00c853;
        margin: 10px 0;
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
USERS_FILE = "users_data.json"          # Archivo para almacenar usuarios

# ============================================
# FUNCIONES DE CARGA DE DATOS (BACKTEST)
# ============================================
@st.cache_data
def load_backtest_data():
    """
    Carga los datos de backtesting desde el CSV.
    El CSV debe tener columnas: entry_time, exit_time, side, exit_reason, R, pnl_equity_pct
    """
    try:
        if os.path.exists(BACKTEST_FILE):
            df = pd.read_csv(BACKTEST_FILE)

            # Convertir columnas de tiempo a datetime
            df['entry_time'] = pd.to_datetime(df['entry_time'], utc=True)
            df['exit_time'] = pd.to_datetime(df['exit_time'], utc=True)

            # Convertir a numérico
            df['pnl_equity_pct'] = pd.to_numeric(df['pnl_equity_pct'], errors='coerce')
            df['R'] = pd.to_numeric(df['R'], errors='coerce')

            # Ordenar por tiempo de entrada
            df = df.sort_values('entry_time')

            # Calcular equity curve acumulada
            df['cumulative_equity'] = (1 + df['pnl_equity_pct']/100).cumprod() * 10000  # Capital inicial 10k

            return df
        else:
            st.warning(f"Archivo {BACKTEST_FILE} no encontrado. Usando datos de ejemplo.")
            return create_sample_backtest()
    except Exception as e:
        st.error(f"Error cargando backtest: {e}")
        return create_sample_backtest()

def create_sample_backtest():
    """Crea datos de ejemplo si no hay archivo"""
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
    """Carga el estado del bot (para información de cooldown, etc.)"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

# ============================================
# FUNCIONES DE TRACKING DE USUARIOS (NUEVAS)
# ============================================
def load_users():
    """Carga el diccionario de usuarios desde JSON."""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    """Guarda el diccionario de usuarios."""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def generate_user_id():
    """Genera un ID único aleatorio."""
    return uuid.uuid4().hex

def get_btc_price():
    """Obtiene el precio actual de BTC/USDT desde Binance."""
    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        ticker = exchange.fetch_ticker('BTC/USDT')
        return ticker['last']
    except Exception as e:
        st.warning(f"No se pudo obtener precio BTC: {e}")
        return None

def create_user():
    """Crea un nuevo usuario con estructura inicial vacía."""
    user_id = generate_user_id()
    users = load_users()
    users[user_id] = {
        "id": user_id,
        "history": [],
        "balances": {
            "aurum": 0.0,
            "reserve": 0.0,
            "btc": 0.0
        },
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
    """Ejecuta órdenes DCA pendientes si el precio actual es menor o igual al límite."""
    if btc_price is None:
        return user_data
    for order in user_data["dca_orders"]:
        if not order["executed"] and btc_price <= order["price"]:
            # Comprar BTC
            btc_bought = order["usdt_allocated"] / order["price"]
            user_data["balances"]["btc"] += btc_bought
            order["btc_purchased"] = btc_bought
            order["executed"] = True
            order["usdt_allocated"] = 0.0  # ya no hay USDT asignado
    return user_data

def process_reserve_condition(user_data, btc_price):
    """Si BTC <= 14000, usar toda la reserva para comprar BTC."""
    if btc_price is None:
        return user_data
    if btc_price <= 14000 and user_data["balances"]["reserve"] > 0:
        btc_bought = user_data["balances"]["reserve"] / btc_price
        user_data["balances"]["btc"] += btc_bought
        user_data["balances"]["reserve"] = 0.0
        # Registrar la operación (opcional)
        user_data["history"].append({
            "type": "compra_reserva",
            "amount": btc_bought,
            "price": btc_price,
            "date": datetime.now().isoformat()
        })
    return user_data

def register_income(user_id, amount_usdt):
    """Registra un ingreso y distribuye según reglas."""
    users = load_users()
    if user_id not in users:
        return False, "Usuario no encontrado"

    user = users[user_id]

    # Actualizar historial
    user["history"].append({
        "type": "ingreso",
        "amount": amount_usdt,
        "date": datetime.now().isoformat()
    })

    # Distribución
    aurum_part = amount_usdt * 0.25
    dca_part = amount_usdt * 0.5
    reserve_part = amount_usdt * 0.25

    # Asignar a balances
    user["balances"]["aurum"] += aurum_part
    user["balances"]["reserve"] += reserve_part

    # Asignar a órdenes DCA (proporciones)
    proportions = [0.15, 0.35, 0.50]  # 15%, 35%, 50%
    for i, order in enumerate(user["dca_orders"]):
        alloc = dca_part * proportions[i]
        order["usdt_allocated"] += alloc

    user["total_usdt_invested"] += amount_usdt

    # Intentar ejecutar órdenes DCA y reserva con precio actual
    btc_price = get_btc_price()
    if btc_price:
        user = process_dca_orders(user, btc_price)
        user = process_reserve_condition(user, btc_price)

    users[user_id] = user
    save_users(users)
    return True, "Ingreso registrado correctamente"

def register_withdraw(user_id, amount_usdt):
    """Registra un egreso, restando primero de reserva, luego aurum, luego BTC."""
    users = load_users()
    if user_id not in users:
        return False, "Usuario no encontrado"

    user = users[user_id]
    btc_price = get_btc_price()
    if btc_price is None:
        return False, "No se puede obtener precio BTC para calcular egreso"

    # Calcular valor total actual
    total_value = (user["balances"]["aurum"] +
                   user["balances"]["reserve"] +
                   user["balances"]["btc"] * btc_price)

    if amount_usdt > total_value:
        return False, f"Saldo insuficiente. Disponible: ${total_value:.2f}"

    # Restar de reserva primero
    remaining = amount_usdt
    if user["balances"]["reserve"] >= remaining:
        user["balances"]["reserve"] -= remaining
        remaining = 0
    else:
        remaining -= user["balances"]["reserve"]
        user["balances"]["reserve"] = 0

        # Luego de aurum
        if user["balances"]["aurum"] >= remaining:
            user["balances"]["aurum"] -= remaining
            remaining = 0
        else:
            remaining -= user["balances"]["aurum"]
            user["balances"]["aurum"] = 0

            # Finalmente vender BTC
            if remaining > 0:
                btc_to_sell = remaining / btc_price
                if user["balances"]["btc"] >= btc_to_sell:
                    user["balances"]["btc"] -= btc_to_sell
                    remaining = 0
                else:
                    # No debería ocurrir por la validación inicial, pero por si acaso
                    return False, "Error inesperado en cálculo de egreso"

    # Registrar en historial
    user["history"].append({
        "type": "egreso",
        "amount": amount_usdt,
        "date": datetime.now().isoformat()
    })
    user["total_usdt_invested"] -= amount_usdt

    users[user_id] = user
    save_users(users)
    return True, f"Egreso de ${amount_usdt:.2f} realizado"

def get_user_summary(user_id):
    """Obtiene resumen actualizado de un usuario (con precios actuales)."""
    users = load_users()
    if user_id not in users:
        return None
    user = users[user_id]
    btc_price = get_btc_price()
    if btc_price:
        user = process_dca_orders(user, btc_price)
        user = process_reserve_condition(user, btc_price)
        # Guardar cambios después de ejecutar órdenes
        users[user_id] = user
        save_users(users)

    # Calcular valor total
    total_usdt = (user["balances"]["aurum"] +
                  user["balances"]["reserve"] +
                  user["balances"]["btc"] * btc_price if btc_price else 0)

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
# FUNCIONES DE MÉTRICAS
# ============================================
def calculate_metrics(df):
    """Calcula métricas de rendimiento a partir del DataFrame de backtest"""
    if df.empty:
        return {}

    total_trades = len(df)
    winning_trades = df[df['pnl_equity_pct'] > 0]
    losing_trades = df[df['pnl_equity_pct'] < 0]

    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    avg_win = winning_trades['pnl_equity_pct'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['pnl_equity_pct'].mean() if not losing_trades.empty else 0

    total_profit = winning_trades['pnl_equity_pct'].sum() if not winning_trades.empty else 0
    total_loss = abs(losing_trades['pnl_equity_pct'].sum()) if not losing_trades.empty else 1
    profit_factor = total_profit / total_loss if total_loss > 0 else 0

    # Calcular drawdown máximo
    cumulative = df['cumulative_equity']
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()

    # Sharpe ratio (asumiendo 252 días de trading)
    returns = df['pnl_equity_pct'] / 100
    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

    # Distribución por razón de salida
    exit_reason_counts = df['exit_reason'].value_counts()

    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "exit_reason_counts": exit_reason_counts.to_dict(),
        "avg_R": df['R'].mean()
    }

# ============================================
# FUNCIONES DE GRÁFICOS (CON FONDO NEGRO)
# ============================================
def create_equity_chart(df):
    """Crea gráfico de evolución de capital con drawdown (fondo negro)"""
    if df.empty:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Evolución del Capital', 'Drawdown'),
        vertical_spacing=0.12,
        row_heights=[0.7, 0.3]
    )

    # Curva de capital
    fig.add_trace(
        go.Scatter(
            x=df['exit_time'],
            y=df['cumulative_equity'],
            name='Capital',
            line=dict(color='#00c853', width=2),
            mode='lines',
            hovertemplate='Fecha: %{x}<br>Capital: $%{y:,.2f}<extra></extra>'
        ),
        row=1, col=1
    )

    # Drawdown
    rolling_max = df['cumulative_equity'].cummax()
    drawdown = (df['cumulative_equity'] - rolling_max) / rolling_max * 100

    fig.add_trace(
        go.Scatter(
            x=df['exit_time'],
            y=drawdown,
            name='Drawdown',
            line=dict(color='#ff3d00', width=1),
            fill='tozeroy',
            fillcolor='rgba(255,61,0,0.1)',
            hovertemplate='Fecha: %{x}<br>Drawdown: %{y:.2f}%<extra></extra>'
        ),
        row=2, col=1
    )

    fig.update_layout(
        height=600,
        showlegend=False,
        paper_bgcolor='#000000',      # Fondo exterior negro
        plot_bgcolor='#000000',        # Fondo del área de trazado negro
        font_color='white',             # Texto blanco
        title_font_color='white'
    )

    fig.update_xaxes(gridcolor='#3d4050', gridwidth=1, linecolor='#3d4050', tickfont=dict(color='white'))
    fig.update_yaxes(gridcolor='#3d4050', gridwidth=1, linecolor='#3d4050', tickfont=dict(color='white'))
    fig.update_yaxes(title_text="Capital (USDT)", row=1, col=1, title_font=dict(color='white'))
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1, title_font=dict(color='white'))
    fig.update_xaxes(title_text="Fecha", row=2, col=1, title_font=dict(color='white'))

    return fig

def create_pnl_distribution_chart(df):
    """Crea gráfico de distribución de PnL por trade (fondo negro)"""
    if df.empty:
        return go.Figure()

    colors = ['#00c853' if x > 0 else '#ff3d00' for x in df['pnl_equity_pct']]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df.index,
        y=df['pnl_equity_pct'],
        marker_color=colors,
        text=df['exit_reason'],
        hovertemplate='Trade #%{x}<br>PnL: %{y:.2f}%<br>Razón: %{text}<extra></extra>'
    ))

    fig.update_layout(
        title="PnL por Trade",
        xaxis_title="Número de Trade",
        yaxis_title="PnL %",
        height=400,
        paper_bgcolor='#000000',
        plot_bgcolor='#000000',
        font_color='white',
        title_font_color='white'
    )
    fig.update_xaxes(gridcolor='#3d4050', tickfont=dict(color='white'), title_font=dict(color='white'))
    fig.update_yaxes(gridcolor='#3d4050', tickfont=dict(color='white'), title_font=dict(color='white'))

    return fig

def create_exit_reason_pie(df):
    """Crea gráfico circular de razones de salida (fondo negro)"""
    if df.empty:
        return go.Figure()

    reason_counts = df['exit_reason'].value_counts()

    colors = {'TP': '#00c853', 'SL': '#ff3d00', 'TRAIL': '#ffab00', 'BE': '#2979ff'}
    color_list = [colors.get(r, '#9e9e9e') for r in reason_counts.index]

    fig = go.Figure(data=[go.Pie(
        labels=reason_counts.index,
        values=reason_counts.values,
        hole=0.4,
        marker_colors=color_list,
        textinfo='label+percent',
        insidetextorientation='radial',
        textfont=dict(color='white')
    )])

    fig.update_layout(
        title="Razones de Salida",
        height=300,
        paper_bgcolor='#000000',
        font_color='white',
        showlegend=False
    )

    return fig

# ============================================
# NUEVA FUNCIÓN: LANDING PAGE (PORTADA)
# ============================================
def show_landing_page():
    """Muestra la página de inicio con explicación de la estrategia y enlace a Telegram."""
    
    # Título principal con estilo
    st.markdown("""
    <h1 style='text-align: center; font-size: 4rem; margin-bottom: 0;'>🤖 AURUM</h1>
    <h2 style='text-align: center; color: #00c853; margin-top: 0;'>ORACLE TRADING SYSTEM</h2>
    <p style='text-align: center; font-size: 1.2rem; color: #9ba3c7; max-width: 800px; margin: 20px auto;'>
        Algoritmo de trading de futuros de Bitcoin basado en análisis técnico multicapa 
        y gestión de riesgo dinámica. Señales en tiempo real y backtesting verificado.
    </p>
    """, unsafe_allow_html=True)

    # Botón de Telegram (centrado y llamativo)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div style='text-align: center; margin: 30px 0;'>
            <a href='https://t.me/+-7Ro_KtGxQ8xMzUx' target='_blank' class='telegram-button'>
                📱 ÚNETE AL CANAL DE TELEGRAM
            </a>
            <p style='color: #9ba3c7; margin-top: 10px;'>Señales en vivo, análisis y comunidad</p>
        </div>
        """, unsafe_allow_html=True)

    # Sección: ¿Cómo funciona AURUM?
    st.markdown("---")
    st.header("⚙️ ¿Cómo funciona AURUM?")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class='feature-card'>
            <h3 style='color: #00c853; margin-top: 0;'>📊 Análisis Técnico</h3>
            <p>Combina medias móviles exponenciales (EMA 50/200) en timeframe de 15 minutos y 1 hora, 
            RSI para confirmación de fuerza, y canales Donchian para detectar rupturas.</p>
        </div>
        <div class='feature-card'>
            <h3 style='color: #00c853; margin-top: 0;'>🛡️ Gestión de Riesgo</h3>
            <p>Stop loss dinámico basado en ATR, trailing stop que asegura ganancias, 
            y cooldown tras pérdidas para preservar capital.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class='feature-card'>
            <h3 style='color: #00c853; margin-top: 0;'>🎯 Ejecución Inteligente</h3>
            <p>Las señales se activan solo cuando el precio rompe los niveles clave con buffer de volatilidad, 
            evitando entradas en rangos laterales.</p>
        </div>
        <div class='feature-card'>
            <h3 style='color: #00c853; margin-top: 0;'>📈 Backtesting Real</h3>
            <p>Más de 950 trades analizados desde 2019, con métricas de win rate, profit factor 
            y drawdown que puedes explorar en este dashboard.</p>
        </div>
        """, unsafe_allow_html=True)

    # Sección: Wallet en vivo (legitimidad)
    st.markdown("---")
    st.header("💰 Wallet en Vivo (Prueba de Rendimiento)")
    
    # Obtener datos en tiempo real para mostrar
    btc_price = get_btc_price()
    state = load_state()
    # Intentar obtener equity si hay conexión a Binance (simplificado)
    try:
        exchange = ccxt.binance({'enableRateLimit': True})
        ticker = exchange.fetch_ticker('BTC/USDT')
        btc_price_display = f"${ticker['last']:,.2f}"
    except:
        btc_price_display = "Conectando..."
    
    # Mostrar métricas en tarjetas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card" style="text-align: center;">
            <div class="metric-label">Precio BTC</div>
            <div class="metric-value">{btc_price_display}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        status_text = "🟢 Activo" if not state.get('paused', False) else "🔴 Pausado"
        st.markdown(f"""
        <div class="metric-card" style="text-align: center;">
            <div class="metric-label">Estado del Bot</div>
            <div class="metric-value">{status_text}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Mostrar última métrica del backtest como ejemplo (o real si se puede)
        df = load_backtest_data()
        metrics = calculate_metrics(df)
        st.markdown(f"""
        <div class="metric-card" style="text-align: center;">
            <div class="metric-label">Win Rate (Histórico)</div>
            <div class="metric-value">{metrics.get('win_rate', 0):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card" style="text-align: center;">
            <div class="metric-label">Profit Factor</div>
            <div class="metric-value">{metrics.get('profit_factor', 0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    # Gráfico pequeño de la curva de capital (para impacto visual)
    st.plotly_chart(create_equity_chart(load_backtest_data()), use_container_width=True)

    # Llamada a la acción para explorar el dashboard
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 20px;'>
        <h3 style='color: white;'>Explora el dashboard completo</h3>
        <p style='color: #9ba3c7;'>Usa el menú de la izquierda para ver backtesting detallado, 
        proyecciones históricas y tracking de fondos personales.</p>
    </div>
    """, unsafe_allow_html=True)

# ============================================
# INTERFAZ PRINCIPAL (MODIFICADA)
# ============================================
def main():
    st.sidebar.title("🤖 AURUM")
    st.sidebar.markdown("---")

    # Cargar datos (con cache)
    df = load_backtest_data()
    metrics = calculate_metrics(df)
    state = load_state()

    # Información del bot en sidebar
    st.sidebar.subheader("📡 Estado del Bot")
    if state.get('paused'):
        st.sidebar.warning("🔴 PAUSADO")
    else:
        st.sidebar.success("🟢 ACTIVO")

    st.sidebar.metric("Cooldown", f"{state.get('cooldown_until', 0)} min")
    st.sidebar.metric("Racha pérdidas", state.get('loss_streak', 0))

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Resumen Backtest")
    st.sidebar.metric("Total Trades", metrics.get('total_trades', 0))
    st.sidebar.metric("Win Rate", f"{metrics.get('win_rate', 0):.1f}%")
    st.sidebar.metric("Profit Factor", f"{metrics.get('profit_factor', 0):.2f}")

    # Menú principal (AHORA CON LANDING PAGE)
    menu = ["🏠 Inicio", "📈 Panel Principal", "📜 Backtesting Detallado", "🔮 Proyecciones", "💰 Tracking", "📋 Trades"]
    choice = st.sidebar.radio("Navegación", menu)

    if choice == "🏠 Inicio":
        show_landing_page()
    elif choice == "📈 Panel Principal":
        show_dashboard(df, metrics)
    elif choice == "📜 Backtesting Detallado":
        show_backtesting(df, metrics)
    elif choice == "🔮 Proyecciones":
        show_projections()
    elif choice == "💰 Tracking":
        show_tracking()
    elif choice == "📋 Trades":
        show_trades(df)

# ============================================
# FUNCIONES DE LAS PESTAÑAS (SIN CAMBIOS)
# ============================================
def show_dashboard(df, metrics):
    st.title("📈 Panel Principal")

    # Métricas principales en tarjetas personalizadas
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Win Rate</div>
            <div class="metric-value">{metrics.get('win_rate', 0):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Profit Factor</div>
            <div class="metric-value">{metrics.get('profit_factor', 0):.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Trades</div>
            <div class="metric-value">{metrics.get('total_trades', 0)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        sharpe = metrics.get('sharpe', 0)
        sharpe_class = "positive" if sharpe > 1 else "negative" if sharpe < 0 else ""
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Sharpe Ratio</div>
            <div class="metric-value {sharpe_class}">{sharpe:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    # Gráfico principal
    st.plotly_chart(create_equity_chart(df), use_container_width=True)

    # Dos gráficos secundarios
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(create_pnl_distribution_chart(df), use_container_width=True)
    with col2:
        st.plotly_chart(create_exit_reason_pie(df), use_container_width=True)

def show_backtesting(df, metrics):
    st.title("📜 Backtesting Detallado")

    # Métricas avanzadas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Máx Drawdown", f"{metrics.get('max_drawdown', 0):.2f}%")
    with col2:
        st.metric("Avg Win", f"{metrics.get('avg_win', 0):.2f}%")
    with col3:
        st.metric("Avg Loss", f"{metrics.get('avg_loss', 0):.2f}%")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Avg R Múltiple", f"{metrics.get('avg_R', 0):.2f}")
    with col2:
        st.metric("Trades Ganadores", len(df[df['pnl_equity_pct'] > 0]) if not df.empty else 0)
    with col3:
        st.metric("Trades Perdedores", len(df[df['pnl_equity_pct'] < 0]) if not df.empty else 0)

    # Distribución por razón de salida (usamos st.table para evitar error de React)
    if metrics.get('exit_reason_counts'):
        st.subheader("Distribución por Razón de Salida")
        reason_data = metrics['exit_reason_counts'].copy()
        reason_df = pd.DataFrame({
            'Razón': list(reason_data.keys()),
            'Cantidad': list(reason_data.values())
        })
        reason_df = reason_df.sort_values('Cantidad', ascending=False).reset_index(drop=True)
        st.table(reason_df)

    # Tabla de trades
    st.subheader("Todos los Trades")
    if not df.empty:
        display_df = df[['entry_time', 'exit_time', 'side', 'exit_reason', 'R', 'pnl_equity_pct']].copy()
        display_df['pnl_equity_pct'] = display_df['pnl_equity_pct'].round(2)
        display_df['R'] = display_df['R'].round(2)
        st.dataframe(display_df, use_container_width=True)

def show_projections():
    st.title("🔮 Proyección Histórica")
    st.markdown("Calcula cuánto habrías ganado si hubieras invertido en la estrategia AURUM en una fecha pasada.")

    # Cargar datos (usamos los mismos del backtest)
    df = load_backtest_data()

    if df.empty:
        st.warning("No hay datos de backtesting para realizar proyecciones.")
        return

    # Obtener el rango de fechas disponibles
    min_date = df['entry_time'].min().date()
    max_date = df['exit_time'].max().date()

    col1, col2 = st.columns(2)
    with col1:
        # Selector de fecha de inversión
        investment_date = st.date_input(
            "📅 Fecha de inversión",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
            help="Selecciona la fecha en la que habrías empezado a invertir."
        )
    with col2:
        # Monto inicial
        initial_amount = st.number_input(
            "💰 Monto inicial (USDT)",
            min_value=10.0,
            value=1000.0,
            step=100.0,
            help="Cantidad de USDT que habrías invertido inicialmente."
        )

    if st.button("Calcular proyección", type="primary"):
        # Convertir la fecha seleccionada a datetime con UTC
        investment_datetime = pd.Timestamp(investment_date).tz_localize('UTC')

        # Encontrar el índice del primer trade después de la fecha de inversión
        trades_after = df[df['entry_time'] >= investment_datetime]

        if trades_after.empty:
            st.error("No hay trades después de la fecha seleccionada.")
            return

        # Tomamos el primer trade después de la fecha
        first_trade_idx = trades_after.index[0]

        # Equity en el momento justo antes de ese trade (usamos el valor acumulado hasta el trade anterior)
        if first_trade_idx > 0:
            equity_before = df.loc[first_trade_idx - 1, 'cumulative_equity']
        else:
            # Si es el primer trade, el equity inicial era 10000 (por construcción)
            equity_before = 10000.0

        # Equity al final del período (último valor de cumulative_equity)
        equity_final = df['cumulative_equity'].iloc[-1]

        # Calcular el factor de crecimiento desde el punto de inversión
        growth_factor = equity_final / equity_before

        # Resultados
        final_amount = initial_amount * growth_factor
        profit_usd = final_amount - initial_amount
        profit_pct = (growth_factor - 1) * 100

        # Mostrar resultados con estilo
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Inversión inicial", f"${initial_amount:,.2f}")
        with col2:
            st.metric("Valor final", f"${final_amount:,.2f}", delta=f"${profit_usd:,.2f}")
        with col3:
            st.metric("Rendimiento total", f"{profit_pct:.2f}%")

        # Opcional: gráfico de la evolución desde la fecha de inversión
        st.subheader("📈 Evolución de la inversión")

        # Filtrar trades desde la fecha de inversión
        df_filtered = df[df['entry_time'] >= investment_datetime].copy()
        if not df_filtered.empty:
            # Normalizar la curva para que empiece en initial_amount
            df_filtered['normalized_equity'] = df_filtered['cumulative_equity'] / equity_before * initial_amount

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_filtered['exit_time'],
                y=df_filtered['normalized_equity'],
                mode='lines',
                name='Capital',
                line=dict(color='#00c853', width=2),
                hovertemplate='Fecha: %{x}<br>Capital: $%{y:,.2f}<extra></extra>'
            ))
            fig.update_layout(
                title=f"Evolución desde {investment_date.strftime('%Y-%m-%d')}",
                xaxis_title="Fecha",
                yaxis_title="Capital (USDT)",
                height=400,
                paper_bgcolor='#000000',
                plot_bgcolor='#000000',
                font_color='white'
            )
            fig.update_xaxes(gridcolor='#3d4050', tickfont=dict(color='white'))
            fig.update_yaxes(gridcolor='#3d4050', tickfont=dict(color='white'))

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos suficientes para mostrar la evolución.")

def show_tracking():
    st.title("💰 Tracking de Fondos")

    # Inicializar estado de sesión para el user_id actual
    if "tracking_user_id" not in st.session_state:
        st.session_state.tracking_user_id = None

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔑 Identificación")
        # Generar nuevo usuario
        if st.button("🆕 Generar nuevo usuario"):
            new_id = create_user()
            st.session_state.tracking_user_id = new_id
            st.success(f"Usuario creado con ID: {new_id}")
            st.info("¡Guarda este ID para acceder después!")

        # Ingresar ID existente
        input_id = st.text_input("O ingresar ID existente:", value=st.session_state.tracking_user_id or "")
        if st.button("Cargar usuario"):
            users = load_users()
            if input_id in users:
                st.session_state.tracking_user_id = input_id
                st.success("Usuario cargado")
            else:
                st.error("ID no encontrado")

    # Si hay un usuario activo, mostrar sus datos
    if st.session_state.tracking_user_id:
        user_id = st.session_state.tracking_user_id
        summary = get_user_summary(user_id)

        if summary:
            with col2:
                st.subheader("📊 Resumen actual")
                btc_price = summary['btc_price']
                if btc_price:
                    st.metric("Precio BTC", f"${btc_price:,.2f}")
                else:
                    st.warning("Precio BTC no disponible")

                st.metric("Aurum (USDT)", f"${summary['aurum']:,.2f}")
                st.metric("Reserva (USDT)", f"${summary['reserve']:,.2f}")
                st.metric("BTC acumulado", f"{summary['btc']:.6f}")
                st.metric("Valor total (USDT)", f"${summary['total_usdt']:,.2f}")
                st.metric("Total invertido (neto)", f"${summary['total_invested']:,.2f}")

            # Acciones: ingreso y egreso
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("💰 Registrar ingreso")
                income_amount = st.number_input("Cantidad (USDT)", min_value=0.0, value=100.0, key="income")
                if st.button("Registrar ingreso"):
                    success, msg = register_income(user_id, income_amount)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            with col2:
                st.subheader("💸 Registrar egreso")
                withdraw_amount = st.number_input("Cantidad (USDT)", min_value=0.0, value=10.0, key="withdraw")
                if st.button("Registrar egreso"):
                    success, msg = register_withdraw(user_id, withdraw_amount)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            # Mostrar órdenes DCA
            st.markdown("---")
            st.subheader("📈 Órdenes DCA")
            dca_df = pd.DataFrame(summary['dca_orders'])
            if not dca_df.empty:
                dca_df['estado'] = dca_df['executed'].apply(lambda x: "✅ Ejecutada" if x else "⏳ Pendiente")
                dca_df['USDT asignado'] = dca_df['usdt_allocated'].round(2)
                dca_df['BTC comprado'] = dca_df['btc_purchased'].round(6)
                st.dataframe(dca_df[['price', 'USDT asignado', 'BTC comprado', 'estado']], use_container_width=True)

            # Mostrar historial
            st.markdown("---")
            st.subheader("📋 Historial de movimientos")
            if summary['history']:
                hist_df = pd.DataFrame(summary['history'])
                st.dataframe(hist_df, use_container_width=True)
            else:
                st.info("No hay movimientos registrados.")
        else:
            st.error("Error al cargar datos del usuario")

def show_trades(df):
    st.title("📋 Histórico de Trades")

    if not df.empty:
        # Estadísticas rápidas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Trades", len(df))
        with col2:
            st.metric("Trades Ganadores", len(df[df['pnl_equity_pct'] > 0]))
        with col3:
            st.metric("Trades Perdedores", len(df[df['pnl_equity_pct'] < 0]))

        # Tabla completa con formato
        display_df = df.copy()
        display_df['entry_time'] = display_df['entry_time'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['exit_time'] = display_df['exit_time'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['pnl_equity_pct'] = display_df['pnl_equity_pct'].round(2).astype(str) + '%'
        display_df['R'] = display_df['R'].round(2)

        st.dataframe(
            display_df[['entry_time', 'exit_time', 'side', 'exit_reason', 'R', 'pnl_equity_pct']],
            use_container_width=True,
            height=600
        )
    else:
        st.warning("No hay datos de trades.")

if __name__ == "__main__":
    main()
