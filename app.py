import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime
import numpy as np
import time

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
</style>
""", unsafe_allow_html=True)

# ============================================
# CONSTANTES
# ============================================
CAPITAL_LOG_FILE = "capital_log.json"
BACKTEST_FILE = "backtest.csv"
STATE_FILE = "state.json"
CONFIG_FILE = "config.json"

# ============================================
# FUNCIONES DE CARGA DE DATOS
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
# INTERFAZ PRINCIPAL
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

    # Menú principal
    menu = ["📈 Panel Principal", "📜 Backtesting Detallado", "🔮 Proyecciones", "💰 Tracking", "📋 Trades"]
    choice = st.sidebar.radio("Navegación", menu)

    if choice == "📈 Panel Principal":
        show_dashboard(df, metrics)
    elif choice == "📜 Backtesting Detallado":
        show_backtesting(df, metrics)
    elif choice == "🔮 Proyecciones":
        show_projections()
    elif choice == "💰 Tracking":
        show_tracking()
    elif choice == "📋 Trades":
        show_trades(df)

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

    # Distribución por razón de salida
    if metrics.get('exit_reason_counts'):
        st.subheader("Distribución por Razón de Salida")
        # Crear una copia explícita y asegurar tipos de datos simples
        reason_data = metrics['exit_reason_counts'].copy()
        reason_df = pd.DataFrame({
            'Razón': list(reason_data.keys()),
            'Cantidad': list(reason_data.values())
        })
        # Ordenar por cantidad descendente para mejor visualización
        reason_df = reason_df.sort_values('Cantidad', ascending=False).reset_index(drop=True)
        # Mostrar con st.table en lugar de st.dataframe (más simple, menos reactivo)
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
        # (asumimos que la inversión se hace justo antes de ese trade)
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
            # Normalizar la curva para que empiece en 1 (o en initial_amount)
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
    st.info("Funcionalidad de tracking en desarrollo. Por ahora puedes ver el archivo JSON.")

    if os.path.exists(CAPITAL_LOG_FILE):
        with open(CAPITAL_LOG_FILE, 'r') as f:
            data = json.load(f)
        st.json(data)
    else:
        st.write("No hay datos de tracking. Se creará un archivo al registrar movimientos.")

        # Formulario simple para registrar
        with st.form("movement_form"):
            movement_type = st.selectbox("Tipo", ["Depósito", "Retiro"])
            amount = st.number_input("Cantidad (USDT)", min_value=0.0, value=100.0)
            note = st.text_input("Nota")
            submitted = st.form_submit_button("Registrar")

            if submitted:
                # Crear estructura inicial
                data = {
                    "deposits": [],
                    "withdrawals": [],
                    "history": []
                }
                movement = {
                    "date": datetime.now().isoformat(),
                    "amount": amount,
                    "note": note
                }
                if movement_type == "Depósito":
                    data["deposits"].append(movement)
                else:
                    data["withdrawals"].append(movement)

                with open(CAPITAL_LOG_FILE, 'w') as f:
                    json.dump(data, f, indent=2)
                st.success("Movimiento registrado!")
                st.rerun()

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
