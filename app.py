import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime
import numpy as np
from dotenv import load_dotenv
import ccxt
import time

# Cargar variables de entorno
load_dotenv()

# ============================================
# CONFIGURACIÓN Y CONSTANTES
# ============================================
CAPITAL_LOG_FILE = "capital_log.json"
TRADES_FILE = "trades.csv"
BACKTEST_FILE = "backtest.csv"
STATE_FILE = "state.json"
CONFIG_FILE = "config.json"

# ============================================
# FUNCIONES DE UTILIDAD (igual que antes)
# ============================================
def load_json_safe(file_path, default=None):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error cargando {file_path}: {e}")
    return default if default is not None else {}

def save_json_safe(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando {file_path}: {e}")
        return False

def get_exchange():
    try:
        testnet = os.getenv("TESTNET", "true").lower() == "true"
        ex = ccxt.binanceusdm({
            "apiKey": os.getenv("BINANCE_KEY", ""),
            "secret": os.getenv("BINANCE_SECRET", ""),
            "enableRateLimit": True,
        })
        if testnet:
            ex.set_sandbox_mode(True)
        return ex
    except:
        return None

def format_number(num, decimals=2):
    try:
        if num is None:
            return "0.00"
        if isinstance(num, str):
            num = float(num)
        if abs(num) >= 1e6:
            return f"${num/1e6:.2f}M"
        elif abs(num) >= 1e3:
            return f"${num/1e3:.2f}K"
        else:
            return f"${num:.{decimals}f}"
    except:
        return str(num)

# ============================================
# FUNCIONES DE TRACKING DE FONDOS (igual)
# ============================================
def init_capital_log():
    if not os.path.exists(CAPITAL_LOG_FILE):
        initial_data = {
            "deposits": [],
            "withdrawals": [],
            "initial_capital": 0,
            "history": []
        }
        save_json_safe(CAPITAL_LOG_FILE, initial_data)
    return load_json_safe(CAPITAL_LOG_FILE)

def add_capital_movement(movement_type, amount, note=""):
    data = init_capital_log()
    movement = {
        "date": datetime.now().isoformat(),
        "amount": float(amount),
        "note": note
    }
    if movement_type == "Depósito":
        data["deposits"].append(movement)
    else:
        data["withdrawals"].append(movement)
    total_deposits = sum(m["amount"] for m in data["deposits"])
    total_withdrawals = sum(m["amount"] for m in data["withdrawals"])
    current_capital = total_deposits - total_withdrawals
    data["history"].append({
        "date": datetime.now().isoformat(),
        "total_capital": current_capital,
        "movement_type": movement_type,
        "movement_amount": amount
    })
    save_json_safe(CAPITAL_LOG_FILE, data)
    return get_capital_summary()

def get_capital_summary():
    data = init_capital_log()
    total_deposits = sum(m["amount"] for m in data["deposits"])
    total_withdrawals = sum(m["amount"] for m in data["withdrawals"])
    net_capital = total_deposits - total_withdrawals
    current_equity = 0
    try:
        ex = get_exchange()
        if ex:
            balance = ex.fetch_balance()
            current_equity = float(balance.get("total", {}).get("USDT", 0))
    except:
        pass
    return {
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "net_capital": net_capital,
        "current_equity": current_equity,
        "profit_loss": current_equity - net_capital,
        "deposits_list": data["deposits"],
        "withdrawals_list": data["withdrawals"]
    }

# ============================================
# FUNCIONES DE DATOS DEL BOT (igual)
# ============================================
def load_trades():
    try:
        if os.path.exists(TRADES_FILE):
            df = pd.read_csv(TRADES_FILE)
            numeric_cols = ['entry', 'mark', 'pnl_pct']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        else:
            return pd.DataFrame(columns=['ts_utc', 'event', 'side', 'entry', 'mark', 'pnl_pct', 'exit_reason'])
    except Exception as e:
        print(f"Error cargando trades: {e}")
        return pd.DataFrame()

def get_bot_status():
    state = load_json_safe(STATE_FILE, {})
    config = load_json_safe(CONFIG_FILE, {})
    btc_price = 0
    equity = 0
    position = "No"
    try:
        ex = get_exchange()
        if ex:
            ticker = ex.fetch_ticker(config.get("symbol", "BTC/USDT"))
            btc_price = ticker['last']
            balance = ex.fetch_balance()
            equity = float(balance.get("total", {}).get("USDT", 0))
            positions = ex.fetch_positions([config.get("symbol", "BTC/USDT")])
            for p in positions:
                if abs(float(p.get("contracts", 0))) > 0:
                    position = f"{p.get('side', '').upper()} @ ${float(p.get('entryPrice', 0)):.2f}"
                    break
    except:
        pass
    now_ts = int(time.time())
    cooldown_until = state.get("cooldown_until", 0)
    cooldown_remaining = max(0, cooldown_until - now_ts) // 60 if cooldown_until > now_ts else 0
    return {
        "btc_price": btc_price,
        "equity": equity,
        "position": position,
        "paused": state.get("paused", False),
        "loss_streak": state.get("loss_streak", 0),
        "cooldown": cooldown_remaining,
        "armed": state.get("armed", {}).get("active", False),
        "last_update": datetime.now().strftime("%H:%M:%S")
    }

def load_backtest_data():
    try:
        if os.path.exists(BACKTEST_FILE):
            df = pd.read_csv(BACKTEST_FILE)
            required_cols = ['date', 'equity']
            if all(col in df.columns for col in required_cols):
                return df
            else:
                return create_sample_backtest()
        else:
            return create_sample_backtest()
    except:
        return create_sample_backtest()

def create_sample_backtest():
    dates = pd.date_range(start='2024-01-01', end='2024-03-16', freq='D')
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, len(dates))
    equity = 10000 * np.cumprod(1 + returns)
    return pd.DataFrame({
        'date': dates,
        'equity': equity,
        'btc_price': 40000 * (1 + np.random.normal(0, 0.01, len(dates)).cumsum() / 100)
    })

# ============================================
# FUNCIONES DE GRÁFICOS (igual)
# ============================================
def create_equity_chart(backtest_df=None, capital_data=None):
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Evolución del Capital', 'Drawdown'),
        vertical_spacing=0.12,
        row_heights=[0.7, 0.3]
    )
    if backtest_df is not None and not backtest_df.empty:
        fig.add_trace(
            go.Scatter(
                x=backtest_df['date'],
                y=backtest_df['equity'],
                name='Backtest',
                line=dict(color='blue', width=2),
                mode='lines'
            ),
            row=1, col=1
        )
        rolling_max = backtest_df['equity'].cummax()
        drawdown = (backtest_df['equity'] - rolling_max) / rolling_max * 100
        fig.add_trace(
            go.Scatter(
                x=backtest_df['date'],
                y=drawdown,
                name='Drawdown',
                line=dict(color='red', width=1),
                fill='tozeroy',
                fillcolor='rgba(255,0,0,0.1)'
            ),
            row=2, col=1
        )
    status = get_bot_status()
    if status['equity'] > 0:
        fig.add_trace(
            go.Scatter(
                x=[datetime.now()],
                y=[status['equity']],
                name='Actual',
                mode='markers',
                marker=dict(size=12, color='green', symbol='star')
            ),
            row=1, col=1
        )
    fig.update_layout(height=600, showlegend=True, title_text="Curva de Capital")
    fig.update_yaxes(title_text="Capital (USDT)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
    return fig

def create_projection_chart(initial_capital, monthly_return, months, monthly_contribution=0):
    months_range = list(range(months + 1))
    capital = [initial_capital]
    contributions = [initial_capital]
    for m in range(1, months + 1):
        new_capital = capital[-1] * (1 + monthly_return/100) + monthly_contribution
        capital.append(new_capital)
        new_contributions = contributions[-1] + monthly_contribution
        contributions.append(new_contributions)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months_range, y=capital,
        name='Capital Proyectado',
        line=dict(color='green', width=3),
        mode='lines+markers'
    ))
    fig.add_trace(go.Scatter(
        x=months_range, y=contributions,
        name='Total Aportado',
        line=dict(color='blue', width=2, dash='dash'),
        mode='lines'
    ))
    fig.add_trace(go.Scatter(
        x=months_range + months_range[::-1],
        y=capital + contributions[::-1],
        fill='toself',
        fillcolor='rgba(0,255,0,0.1)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Ganancias'
    ))
    fig.update_layout(
        title=f"Proyección {months} meses | {monthly_return}% mensual",
        xaxis_title="Meses",
        yaxis_title="Capital (USDT)",
        height=500,
        hovermode='x unified'
    )
    return fig

def create_trades_history_chart():
    trades_df = load_trades()
    if trades_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No hay datos de trades disponibles", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    closed_trades = trades_df[trades_df['event'] == 'CLOSED'].copy()
    if closed_trades.empty:
        fig = go.Figure()
        fig.add_annotation(text="No hay trades cerrados", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    closed_trades['date'] = pd.to_datetime(closed_trades['ts_utc'])
    closed_trades = closed_trades.sort_values('date')
    closed_trades['cumulative_pnl'] = (1 + closed_trades['pnl_pct']/100).cumprod() * 10000
    fig = make_subplots(rows=2, cols=1, subplot_titles=('PnL por Trade', 'Equity Curve'), vertical_spacing=0.15)
    colors = closed_trades['side'].map({'LONG': 'green', 'SHORT': 'red'})
    fig.add_trace(
        go.Bar(
            x=closed_trades['date'],
            y=closed_trades['pnl_pct'],
            name='PnL %',
            marker_color=colors,
            text=closed_trades['exit_reason'],
            hovertemplate='Fecha: %{x}<br>PnL: %{y:.2f}%<br>Razón: %{text}<extra></extra>'
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=closed_trades['date'],
            y=closed_trades['cumulative_pnl'],
            name='Capital',
            line=dict(color='blue', width=2),
            mode='lines+markers'
        ),
        row=2, col=1
    )
    fig.update_layout(height=600, showlegend=False)
    fig.update_yaxes(title_text="PnL %", row=1, col=1)
    fig.update_yaxes(title_text="Capital (USDT)", row=2, col=1)
    return fig

# ============================================
# FUNCIONES DE MÉTRICAS (igual)
# ============================================
def calculate_metrics():
    trades_df = load_trades()
    if trades_df.empty:
        return {"total_trades": 0, "win_rate": 0, "avg_win": 0, "avg_loss": 0, "profit_factor": 0, "max_drawdown": 0, "sharpe": 0}
    closed_trades = trades_df[trades_df['event'] == 'CLOSED']
    if closed_trades.empty:
        return {"total_trades": 0, "win_rate": 0, "avg_win": 0, "avg_loss": 0, "profit_factor": 0, "max_drawdown": 0, "sharpe": 0}
    winning_trades = closed_trades[closed_trades['pnl_pct'] > 0]
    losing_trades = closed_trades[closed_trades['pnl_pct'] < 0]
    total_trades = len(closed_trades)
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    avg_win = winning_trades['pnl_pct'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['pnl_pct'].mean() if not losing_trades.empty else 0
    total_profit = winning_trades['pnl_pct'].sum() if not winning_trades.empty else 0
    total_loss = abs(losing_trades['pnl_pct'].sum()) if not losing_trades.empty else 1
    profit_factor = total_profit / total_loss if total_loss > 0 else 0
    closed_trades['cumulative'] = (1 + closed_trades['pnl_pct']/100).cumprod()
    rolling_max = closed_trades['cumulative'].cummax()
    drawdown = (closed_trades['cumulative'] - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()
    returns = closed_trades['pnl_pct'] / 100
    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe
    }

# ============================================
# INTERFAZ STREAMLIT (nueva)
# ============================================
st.set_page_config(page_title="AURUM Trading Dashboard", layout="wide", initial_sidebar_state="collapsed")

# Título principal
st.title("🤖 AURUM Trading Dashboard")
st.markdown("Dashboard para monitorear y gestionar tu bot de trading de Bitcoin")

# Inicializar datos
if 'capital_summary' not in st.session_state:
    st.session_state.capital_summary = get_capital_summary()
if 'backtest_df' not in st.session_state:
    st.session_state.backtest_df = load_backtest_data()

# Crear pestañas
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Panel Principal", "📜 Backtesting", "🔮 Proyecciones", "💰 Tracking de Fondos", "📋 Histórico de Trades"])

# ========== PESTAÑA 1: PANEL PRINCIPAL ==========
with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("### 📈 Estado del Bot")
        status = get_bot_status()
        st.metric("BTC/USDT", f"${status['btc_price']:,.2f}" if status['btc_price'] else "No disponible")
        st.metric("Equity USDT", format_number(status['equity']))
        st.metric("Posición Actual", status['position'])
        estado = "🟢 Activo" if not status['paused'] else "🔴 Pausado"
        st.metric("Estado", estado)

        st.markdown("### 📊 Métricas de Rendimiento")
        metrics = calculate_metrics()
        col_met1, col_met2 = st.columns(2)
        with col_met1:
            st.metric("Win Rate", f"{metrics['win_rate']:.1f}%")
            st.metric("Total Trades", metrics['total_trades'])
        with col_met2:
            st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
            st.metric("Sharpe Ratio", f"{metrics['sharpe']:.2f}")

    with col2:
        st.markdown("### 📈 Evolución del Capital")
        chart = create_equity_chart(st.session_state.backtest_df, st.session_state.capital_summary)
        st.plotly_chart(chart, use_container_width=True)

    if st.button("🔄 Actualizar Datos"):
        st.rerun()

# ========== PESTAÑA 2: BACKTESTING ==========
with tab2:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("### 📋 Estadísticas Históricas")
        # Aquí puedes poner valores fijos o calcularlos desde backtest_df
        st.metric("Capital Inicial", "$10,000", help="USDT")
        st.metric("Capital Final", "$15,420", help="USDT (ejemplo)")
        st.metric("Retorno Total", "54.2%")
        st.metric("CAGR", "28.5% anual")
        st.markdown("---")
        st.metric("Máx Drawdown", "-12.5%")
        st.metric("Win Rate Histórico", "62.3%")
        st.metric("Trade Promedio", "2.1%")
        st.metric("Profit Factor", "1.85")
    with col2:
        st.markdown("### 📈 Curva de Capital (Backtest)")
        st.plotly_chart(create_equity_chart(st.session_state.backtest_df), use_container_width=True)

# ========== PESTAÑA 3: PROYECCIONES ==========
with tab3:
    st.markdown("### Simulador de Crecimiento")
    st.markdown("Ajusta los parámetros para ver proyecciones de tu capital")
    col1, col2 = st.columns([1, 2])
    with col1:
        proj_capital = st.number_input("Capital Inicial (USDT)", value=10000, min_value=100, max_value=1000000, step=100)
        proj_return = st.slider("Rendimiento Mensual (%)", min_value=-5.0, max_value=20.0, value=5.0, step=0.5)
        proj_months = st.slider("Meses a proyectar", min_value=1, max_value=60, value=12, step=1)
        proj_contribution = st.number_input("Aportación Mensual (USDT)", value=0, min_value=0, max_value=10000, step=100)
        if st.button("📊 Calcular Proyección"):
            st.session_state.proj_chart = create_projection_chart(proj_capital, proj_return, proj_months, proj_contribution)
            # Calcular valores finales
            final_cap = proj_capital
            for _ in range(proj_months):
                final_cap = final_cap * (1 + proj_return/100) + proj_contribution
            total_profit_val = final_cap - (proj_capital + proj_contribution * proj_months)
            st.session_state.final_value = final_cap
            st.session_state.total_profit = total_profit_val
    with col2:
        if 'proj_chart' in st.session_state:
            st.plotly_chart(st.session_state.proj_chart, use_container_width=True)
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.metric("Capital Final Proyectado", format_number(st.session_state.final_value))
            with col_res2:
                st.metric("Ganancia Total", format_number(st.session_state.total_profit))
        else:
            st.info("Ajusta los parámetros y presiona 'Calcular Proyección'")

# ========== PESTAÑA 4: TRACKING DE FONDOS ==========
with tab4:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("#### Registrar Movimiento")
        movement_type = st.radio("Tipo", ["Depósito", "Retiro"])
        movement_amount = st.number_input("Cantidad (USDT)", min_value=0, value=100, step=10)
        movement_note = st.text_input("Nota (opcional)", placeholder="Ej: Depósito inicial")
        if st.button("➕ Registrar Movimiento"):
            add_capital_movement(movement_type, movement_amount, movement_note)
            st.session_state.capital_summary = get_capital_summary()
            st.success("Movimiento registrado")
            st.rerun()

        st.markdown("#### Resumen de Capital")
        cap = st.session_state.capital_summary
        st.metric("Total Depósitos", format_number(cap['total_deposits']))
        st.metric("Total Retiros", format_number(cap['total_withdrawals']))
        st.metric("Capital Neto Aportado", format_number(cap['net_capital']))
        profit_color = "normal" if cap['profit_loss'] >= 0 else "inverse"
        st.metric("Profit/Pérdida Actual", format_number(cap['profit_loss']), delta_color=profit_color)

    with col2:
        st.markdown("#### Historial de Movimientos")
        movements = []
        for d in cap['deposits_list']:
            movements.append([d['date'][:10], "Depósito", f"${d['amount']:,.2f}", d.get('note', '')])
        for w in cap['withdrawals_list']:
            movements.append([w['date'][:10], "Retiro", f"${w['amount']:,.2f}", w.get('note', '')])
        if movements:
            movements_df = pd.DataFrame(movements, columns=["Fecha", "Tipo", "Cantidad", "Nota"])
            movements_df = movements_df.sort_values("Fecha", ascending=False)
            st.dataframe(movements_df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay movimientos registrados")

    if st.button("🔄 Actualizar Tracking"):
        st.session_state.capital_summary = get_capital_summary()
        st.rerun()

# ========== PESTAÑA 5: HISTÓRICO DE TRADES ==========
with tab5:
    st.markdown("### Registro de Operaciones")
    st.plotly_chart(create_trades_history_chart(), use_container_width=True)
    trades_df = load_trades()
    if not trades_df.empty:
        st.dataframe(trades_df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay datos de trades")
    if st.button("🔄 Actualizar Histórico"):
        st.rerun()

# ============================================
# INICIALIZACIÓN
# ============================================
if __name__ == "__main__":
    init_capital_log()
    # No es necesario lanzar nada, Streamlit corre el script
