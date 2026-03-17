import gradio as gr
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime, timedelta
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
BACKTEST_FILE = "backtest.csv"  # Tus datos históricos
STATE_FILE = "state.json"
CONFIG_FILE = "config.json"

# ============================================
# FUNCIONES DE UTILIDAD
# ============================================
def load_json_safe(file_path, default=None):
    """Carga JSON de forma segura"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error cargando {file_path}: {e}")
    return default if default is not None else {}

def save_json_safe(file_path, data):
    """Guarda JSON de forma segura"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error guardando {file_path}: {e}")
        return False

def get_exchange():
    """Obtiene conexión a Binance (testnet si está configurada)"""
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
    """Formatea números de forma legible"""
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
# FUNCIONES DE TRACKING DE FONDOS
# ============================================
def init_capital_log():
    """Inicializa el archivo de tracking de fondos"""
    if not os.path.exists(CAPITAL_LOG_FILE):
        initial_data = {
            "deposits": [],  # Lista de depósitos {date, amount, note}
            "withdrawals": [],  # Lista de retiros {date, amount, note}
            "initial_capital": 0,
            "history": []  # Histórico de capital total
        }
        save_json_safe(CAPITAL_LOG_FILE, initial_data)
    return load_json_safe(CAPITAL_LOG_FILE)

def add_capital_movement(movement_type, amount, note=""):
    """Añade un depósito o retiro"""
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

    # Actualizar historial
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
    """Obtiene resumen de capital"""
    data = init_capital_log()

    total_deposits = sum(m["amount"] for m in data["deposits"])
    total_withdrawals = sum(m["amount"] for m in data["withdrawals"])
    net_capital = total_deposits - total_withdrawals

    # Obtener equity actual de Binance si es posible
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
# FUNCIONES DE DATOS DEL BOT
# ============================================
def load_trades():
    """Carga el histórico de trades"""
    try:
        if os.path.exists(TRADES_FILE):
            df = pd.read_csv(TRADES_FILE)
            # Convertir tipos
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
    """Obtiene estado actual del bot"""
    state = load_json_safe(STATE_FILE, {})
    config = load_json_safe(CONFIG_FILE, {})

    # Intentar obtener datos de Binance
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

            # Verificar posición
            positions = ex.fetch_positions([config.get("symbol", "BTC/USDT")])
            for p in positions:
                if abs(float(p.get("contracts", 0))) > 0:
                    position = f"{p.get('side', '').upper()} @ ${float(p.get('entryPrice', 0)):.2f}"
                    break
    except:
        pass

    # Calcular tiempo restante de cooldown
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
    """Carga datos de backtesting"""
    try:
        if os.path.exists(BACKTEST_FILE):
            df = pd.read_csv(BACKTEST_FILE)
            # Asegurar que tiene las columnas necesarias
            required_cols = ['date', 'equity']
            if all(col in df.columns for col in required_cols):
                return df
            else:
                # Si no tiene el formato esperado, crear datos de ejemplo
                return create_sample_backtest()
        else:
            return create_sample_backtest()
    except:
        return create_sample_backtest()

def create_sample_backtest():
    """Crea datos de backtest de ejemplo"""
    dates = pd.date_range(start='2024-01-01', end='2024-03-16', freq='D')
    np.random.seed(42)

    # Simular equity curve
    returns = np.random.normal(0.001, 0.02, len(dates))
    equity = 10000 * np.cumprod(1 + returns)

    return pd.DataFrame({
        'date': dates,
        'equity': equity,
        'btc_price': 40000 * (1 + np.random.normal(0, 0.01, len(dates)).cumsum() / 100)
    })

# ============================================
# FUNCIONES DE GRÁFICOS
# ============================================
def create_equity_chart(backtest_df=None, capital_data=None):
    """Crea gráfico de evolución de capital"""
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Evolución del Capital', 'Drawdown'),
        vertical_spacing=0.12,
        row_heights=[0.7, 0.3]
    )

    if backtest_df is not None and not backtest_df.empty:
        # Backtest data
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

        # Calcular drawdown
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

    # Añadir punto de equity actual
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

    fig.update_layout(
        height=600,
        showlegend=True,
        title_text="Curva de Capital"
    )

    fig.update_yaxes(title_text="Capital (USDT)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)

    return fig

def create_projection_chart(initial_capital, monthly_return, months, monthly_contribution=0):
    """Crea gráfico de proyección"""
    months_range = list(range(months + 1))

    # Calcular proyección
    capital = [initial_capital]
    contributions = [initial_capital]

    for m in range(1, months + 1):
        new_capital = capital[-1] * (1 + monthly_return/100) + monthly_contribution
        capital.append(new_capital)

        new_contributions = contributions[-1] + monthly_contribution
        contributions.append(new_contributions)

    fig = go.Figure()

    # Línea de capital proyectado
    fig.add_trace(go.Scatter(
        x=months_range,
        y=capital,
        name='Capital Proyectado',
        line=dict(color='green', width=3),
        mode='lines+markers'
    ))

    # Línea de contribuciones totales
    fig.add_trace(go.Scatter(
        x=months_range,
        y=contributions,
        name='Total Aportado',
        line=dict(color='blue', width=2, dash='dash'),
        mode='lines'
    ))

    # Área de ganancias
    fig.add_trace(go.Scatter(
        x=months_range + months_range[::-1],
        y=capital + contributions[::-1],
        fill='toself',
        fillcolor='rgba(0,255,0,0.1)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Ganancias',
        showlegend=True
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
    """Crea gráfico de histórico de trades"""
    trades_df = load_trades()

    if trades_df.empty:
        return go.Figure().add_annotation(
            text="No hay datos de trades disponibles",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )

    # Filtrar solo trades cerrados
    closed_trades = trades_df[trades_df['event'] == 'CLOSED'].copy()

    if closed_trades.empty:
        return go.Figure().add_annotation(
            text="No hay trades cerrados",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )

    # Convertir fechas
    closed_trades['date'] = pd.to_datetime(closed_trades['ts_utc'])
    closed_trades = closed_trades.sort_values('date')

    # Calcular equity curve a partir de trades
    closed_trades['cumulative_pnl'] = (1 + closed_trades['pnl_pct']/100).cumprod() * 10000

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('PnL por Trade', 'Equity Curve'),
        vertical_spacing=0.15
    )

    # Colores por side
    colors = closed_trades['side'].map({'LONG': 'green', 'SHORT': 'red'})

    # Gráfico de barras de PnL
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

    # Equity curve
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
# FUNCIONES DE MÉTRICAS
# ============================================
def calculate_metrics():
    """Calcula métricas de rendimiento"""
    trades_df = load_trades()

    if trades_df.empty:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "sharpe": 0
        }

    closed_trades = trades_df[trades_df['event'] == 'CLOSED']

    if closed_trades.empty:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
            "sharpe": 0
        }

    winning_trades = closed_trades[closed_trades['pnl_pct'] > 0]
    losing_trades = closed_trades[closed_trades['pnl_pct'] < 0]

    total_trades = len(closed_trades)
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

    avg_win = winning_trades['pnl_pct'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['pnl_pct'].mean() if not losing_trades.empty else 0

    total_profit = winning_trades['pnl_pct'].sum() if not winning_trades.empty else 0
    total_loss = abs(losing_trades['pnl_pct'].sum()) if not losing_trades.empty else 1
    profit_factor = total_profit / total_loss if total_loss > 0 else 0

    # Calcular drawdown máximo (simplificado)
    closed_trades['cumulative'] = (1 + closed_trades['pnl_pct']/100).cumprod()
    rolling_max = closed_trades['cumulative'].cummax()
    drawdown = (closed_trades['cumulative'] - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()

    # Sharpe ratio aproximado
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
# INTERFAZ GRADIO
# ============================================
def create_dashboard():
    """Crea la interfaz principal"""

    with gr.Blocks(theme=gr.themes.Soft(), title="AURUM Trading Dashboard") as demo:
        gr.Markdown("""
        # 🤖 AURUM Trading Dashboard

        Dashboard para monitorear y gestionar tu bot de trading de Bitcoin
        """)

        with gr.Tabs():
            # ========== PESTAÑA 1: PANEL PRINCIPAL ==========
            with gr.TabItem("📊 Panel Principal"):
                with gr.Row():
                    with gr.Column(scale=1):
                        # Métricas principales
                        status = get_bot_status()

                        gr.Markdown("### 📈 Estado del Bot")
                        with gr.Group():
                            btc_display = gr.Textbox(
                                label="BTC/USDT",
                                value=f"${status['btc_price']:,.2f}" if status['btc_price'] else "No disponible",
                                interactive=False
                            )
                            equity_display = gr.Textbox(
                                label="Equity USDT",
                                value=format_number(status['equity']),
                                interactive=False
                            )
                            position_display = gr.Textbox(
                                label="Posición Actual",
                                value=status['position'],
                                interactive=False
                            )
                            status_display = gr.Textbox(
                                label="Estado",
                                value="🟢 Activo" if not status['paused'] else "🔴 Pausado",
                                interactive=False
                            )

                        gr.Markdown("### 📊 Métricas de Rendimiento")
                        metrics = calculate_metrics()

                        with gr.Row():
                            with gr.Column():
                                win_rate = gr.Number(
                                    label="Win Rate",
                                    value=round(metrics['win_rate'], 1),
                                    info="%"
                                )
                                total_trades = gr.Number(
                                    label="Total Trades",
                                    value=metrics['total_trades']
                                )
                            with gr.Column():
                                profit_factor = gr.Number(
                                    label="Profit Factor",
                                    value=round(metrics['profit_factor'], 2)
                                )
                                sharpe = gr.Number(
                                    label="Sharpe Ratio",
                                    value=round(metrics['sharpe'], 2)
                                )

                    with gr.Column(scale=2):
                        # Gráfico principal
                        backtest_df = load_backtest_data()
                        capital_data = get_capital_summary()
                        equity_chart = gr.Plot(value=create_equity_chart(backtest_df, capital_data))

                with gr.Row():
                    # Botón de actualizar
                    refresh_btn = gr.Button("🔄 Actualizar Datos", variant="primary")

                    # Última actualización
                    update_time = gr.Textbox(
                        label="Última actualización",
                        value=status['last_update'],
                        interactive=False
                    )

            # ========== PESTAÑA 2: BACKTESTING ==========
            with gr.TabItem("📜 Backtesting"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 📋 Estadísticas Históricas")

                        with gr.Group():
                            initial_capital = gr.Number(
                                label="Capital Inicial",
                                value=10000,
                                info="USDT"
                            )
                            final_capital = gr.Number(
                                label="Capital Final",
                                value=15420,
                                info="USDT (ejemplo)"
                            )
                            total_return = gr.Number(
                                label="Retorno Total",
                                value=54.2,
                                info="%"
                            )
                            cagr = gr.Number(
                                label="CAGR",
                                value=28.5,
                                info="% anual"
                            )

                    with gr.Column(scale=2):
                        # Métricas adicionales
                        with gr.Row():
                            with gr.Column():
                                max_dd = gr.Number(
                                    label="Máx Drawdown",
                                    value=-12.5,
                                    info="%"
                                )
                                win_rate_hist = gr.Number(
                                    label="Win Rate Histórico",
                                    value=62.3,
                                    info="%"
                                )
                            with gr.Column():
                                avg_trade = gr.Number(
                                    label="Trade Promedio",
                                    value=2.1,
                                    info="%"
                                )
                                profit_factor_hist = gr.Number(
                                    label="Profit Factor",
                                    value=1.85
                                )

                with gr.Row():
                    gr.Markdown("### 📈 Curva de Capital (Backtest)")
                    backtest_chart = gr.Plot(value=create_equity_chart(backtest_df))

            # ========== PESTAÑA 3: PROYECCIONES ==========
            with gr.TabItem("🔮 Proyecciones"):
                gr.Markdown("### Simulador de Crecimiento")
                gr.Markdown("Ajusta los parámetros para ver proyecciones de tu capital")

                with gr.Row():
                    with gr.Column(scale=1):
                        proj_capital = gr.Number(
                            label="Capital Inicial (USDT)",
                            value=10000,
                            minimum=100,
                            maximum=1000000
                        )
                        proj_return = gr.Slider(
                            label="Rendimiento Mensual (%)",
                            minimum=-5,
                            maximum=20,
                            value=5,
                            step=0.5
                        )
                        proj_months = gr.Slider(
                            label="Meses a proyectar",
                            minimum=1,
                            maximum=60,
                            value=12,
                            step=1
                        )
                        proj_contribution = gr.Number(
                            label="Aportación Mensual (USDT)",
                            value=0,
                            minimum=0,
                            maximum=10000
                        )

                        calculate_proj = gr.Button("📊 Calcular Proyección", variant="primary")

                    with gr.Column(scale=2):
                        proj_chart = gr.Plot()

                with gr.Row():
                    with gr.Column():
                        final_value = gr.Number(
                            label="Capital Final Proyectado",
                            value=0,
                            info="USDT"
                        )
                        total_profit = gr.Number(
                            label="Ganancia Total",
                            value=0,
                            info="USDT"
                        )

            # ========== PESTAÑA 4: TRACKING DE FONDOS ==========
            with gr.TabItem("💰 Tracking de Fondos"):
                gr.Markdown("### Gestión de Capital")

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("#### Registrar Movimiento")

                        movement_type = gr.Radio(
                            choices=["Depósito", "Retiro"],
                            label="Tipo",
                            value="Depósito"
                        )
                        movement_amount = gr.Number(
                            label="Cantidad (USDT)",
                            minimum=0,
                            value=100
                        )
                        movement_note = gr.Textbox(
                            label="Nota (opcional)",
                            placeholder="Ej: Depósito inicial, retiro de ganancias..."
                        )

                        add_movement_btn = gr.Button("➕ Registrar Movimiento", variant="primary")

                        gr.Markdown("#### Resumen de Capital")

                        total_deposits = gr.Number(
                            label="Total Depósitos",
                            value=0,
                            info="USDT"
                        )
                        total_withdrawals = gr.Number(
                            label="Total Retiros",
                            value=0,
                            info="USDT"
                        )
                        net_capital = gr.Number(
                            label="Capital Neto Aportado",
                            value=0,
                            info="USDT"
                        )
                        current_profit = gr.Number(
                            label="Profit/Pérdida Actual",
                            value=0,
                            info="USDT"
                        )

                    with gr.Column(scale=2):
                        gr.Markdown("#### Historial de Movimientos")
                        movements_history = gr.Dataframe(
                            headers=["Fecha", "Tipo", "Cantidad", "Nota"],
                            interactive=False
                        )

                refresh_capital_btn = gr.Button("🔄 Actualizar Tracking", variant="secondary")

            # ========== PESTAÑA 5: HISTÓRICO DE TRADES ==========
            with gr.TabItem("📋 Histórico de Trades"):
                gr.Markdown("### Registro de Operaciones")

                trades_chart = gr.Plot(value=create_trades_history_chart())

                trades_table = gr.Dataframe(
                    value=load_trades(),
                    interactive=False,
                    height=400
                )

                refresh_trades_btn = gr.Button("🔄 Actualizar Histórico", variant="secondary")

        # ========== FUNCIONES DE ACTUALIZACIÓN ==========
        def refresh_all():
            """Actualiza todos los datos"""
            status = get_bot_status()
            metrics = calculate_metrics()
            capital = get_capital_summary()
            backtest_df = load_backtest_data()

            return [
                f"${status['btc_price']:,.2f}" if status['btc_price'] else "No disponible",
                format_number(status['equity']),
                status['position'],
                "🟢 Activo" if not status['paused'] else "🔴 Pausado",
                round(metrics['win_rate'], 1),
                metrics['total_trades'],
                round(metrics['profit_factor'], 2),
                round(metrics['sharpe'], 2),
                create_equity_chart(backtest_df, capital),
                status['last_update'],
                capital['total_deposits'],
                capital['total_withdrawals'],
                capital['net_capital'],
                capital['profit_loss']
            ]

        def update_projections(capital, ret, months, contribution):
            """Actualiza las proyecciones"""
            chart = create_projection_chart(capital, ret, months, contribution)

            # Calcular valores finales
            final_cap = capital
            for _ in range(months):
                final_cap = final_cap * (1 + ret/100) + contribution

            total_profit_val = final_cap - (capital + contribution * months)

            return chart, final_cap, total_profit_val

        def add_movement_and_refresh(m_type, amount, note):
            """Añade movimiento y actualiza vista"""
            add_capital_movement(m_type, amount, note)
            capital = get_capital_summary()

            # Crear dataframe para historial
            movements = []
            for d in capital['deposits_list']:
                movements.append([d['date'][:10], "Depósito", f"${d['amount']:,.2f}", d.get('note', '')])
            for w in capital['withdrawals_list']:
                movements.append([w['date'][:10], "Retiro", f"${w['amount']:,.2f}", w.get('note', '')])

            movements_df = pd.DataFrame(movements, columns=["Fecha", "Tipo", "Cantidad", "Nota"])
            movements_df = movements_df.sort_values("Fecha", ascending=False)

            return [
                capital['total_deposits'],
                capital['total_withdrawals'],
                capital['net_capital'],
                capital['profit_loss'],
                movements_df
            ]

        # Conectar botones con funciones
        refresh_btn.click(
            fn=refresh_all,
            inputs=[],
            outputs=[
                btc_display, equity_display, position_display, status_display,
                win_rate, total_trades, profit_factor, sharpe,
                equity_chart, update_time,
                total_deposits, total_withdrawals, net_capital, current_profit
            ]
        )

        calculate_proj.click(
            fn=update_projections,
            inputs=[proj_capital, proj_return, proj_months, proj_contribution],
            outputs=[proj_chart, final_value, total_profit]
        )

        add_movement_btn.click(
            fn=add_movement_and_refresh,
            inputs=[movement_type, movement_amount, movement_note],
            outputs=[total_deposits, total_withdrawals, net_capital, current_profit, movements_history]
        )

        refresh_capital_btn.click(
            fn=lambda: add_movement_and_refresh("Depósito", 0, ""),
            inputs=[],
            outputs=[total_deposits, total_withdrawals, net_capital, current_profit, movements_history]
        )

        refresh_trades_btn.click(
            fn=lambda: (create_trades_history_chart(), load_trades()),
            inputs=[],
            outputs=[trades_chart, trades_table]
        )

        # Inicializar tracking al cargar
        demo.load(
            fn=lambda: add_movement_and_refresh("Depósito", 0, ""),
            inputs=[],
            outputs=[total_deposits, total_withdrawals, net_capital, current_profit, movements_history]
        )

    return demo

# ============================================
# INICIALIZACIÓN
# ============================================
if __name__ == "__main__":
    # Inicializar archivos necesarios
    init_capital_log()

    # Crear y lanzar dashboard
    demo = create_dashboard()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False  # Cambiar a True si quieres link público temporal
    )
