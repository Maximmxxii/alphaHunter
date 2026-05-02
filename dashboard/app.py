"""
dashboard/app.py — Interfaz principal de AlphaHunter en Streamlit

Ejecutar con:
    streamlit run dashboard/app.py

Secciones del dashboard:
    1. Sidebar       : Configuración global (tickers, estrategia, período)
    2. Screener      : Tabla de candidatos que pasan los filtros técnicos
    3. Análisis      : Gráfico de precio + indicadores para un ticker seleccionado
    4. Backtesting   : Curva de equity, trades y métricas de performance
    5. ML Predicción : Probabilidades y señales del modelo XGBoost
    6. Correlación   : Heatmap de correlación entre tickers del portafolio
    7. Polymarket    : Sentimiento macro en tiempo real desde mercados de predicción

Flujo de datos:
    yfinance → data_fetcher → [screener | backtesting | ml] → charts → Streamlit
    Polymarket Gamma API → polymarket.py → gauges + tablas → Streamlit
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import streamlit as st
import pandas as pd

from utils.data_fetcher import get_ohlcv, get_multiple
from utils.polymarket import get_macro_sentiment, get_asset_sentiment, search_financial_markets
from screener.indicators import compute_all
from screener.runner import run_screener
from screener.filters import STRATEGIES as SCREENER_STRATEGIES
from backtesting.engine import run_backtest
from backtesting.metrics import calculate_metrics
from backtesting.strategy import STRATEGIES as BT_STRATEGIES
from backtesting.report import print_report
from ml.trainer import train, load_model
from ml.predictor import predict_ticker, predict_screener_candidates
from ml.evaluator import evaluate, find_optimal_threshold
from dashboard.charts import (
    price_chart, equity_chart, trades_chart,
    correlation_heatmap, ranking_table,
    polymarket_gauges, polymarket_bars, polymarket_markets_table,
)
from utils.alpaca import (
    is_configured, get_account, get_positions, get_orders,
    place_order, close_position, get_portfolio_history,
)
from utils.auto_trader import (
    run_cycle, monitor_stops, get_log as get_trader_log, DEFAULT_CONFIG,
)
from utils.trade_journal import get_all_trades, get_closed_trades, compute_stats, sync_from_alpaca

# ─────────────────────────────────────────────
# Configuración de página
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AlphaHunter",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main { background-color: #0E1117; }
    .stMetric { background-color: #1A1D27; border-radius: 8px; padding: 10px; }
    .stMetric label { color: #888 !important; }
    div[data-testid="metric-container"] { background-color: #1A1D27; border-radius: 8px; padding: 8px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Sidebar — Configuración global
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("📈 AlphaHunter")
    st.caption("Sistema cuantitativo de análisis de mercados")
    st.divider()

    st.subheader("Universo de tickers")
    tickers_input = st.text_area(
        "Un ticker por línea o separados por coma",
        value=(
            "AAPL\nMSFT\nNVDA\nTSLA\nGOOGL\nAMZN\nMETA\nNFLX\nAMD\nINTC\n"
            "CRM\nORCL\nADBE\nQCOM\nAVGO\n"
            "SPY\nQQQ\nIWM\nDIA\nVTI\nVOO\nXLF\nXLE\nXLK\nARKK\n"
            "TQQQ\nSQQQ\nSPXU\nUVXY\n"
            "COIN\nHOOD\nRIVN\nLCID\nPLTR\nSOFI\nMARA\nRIOT\nSMCI\nARM\n"
            "IONQ\nRKLB\nSOUN\nBBAI\n"
            "JPM\nBAC\nGS\nWFC\n"
            "XOM\nCVX\nOXY\n"
            "UNH\nJNJ\nPFE\n"
            "BA\nCAT\nDE\n"
            "BTC-USD\nETH-USD\nSOL-USD\nAVAX-USD\nDOGE-USD\nLINK-USD\nLTC-USD"
        ),
        height=300,
    )
    tickers = [t.strip().upper() for t in tickers_input.replace(',', '\n').splitlines() if t.strip()]

    st.subheader("Configuración")
    period = st.selectbox("Período histórico", ["6mo", "1y", "2y", "3y", "5y"], index=2)
    capital = st.number_input("Capital inicial (USD)", value=10_000, step=1_000)
    stop_loss = st.slider("Stop Loss (%)", 0, 20, 7) / 100

    st.subheader("Estrategias")
    screener_strategy = st.selectbox(
        "Screener", list(SCREENER_STRATEGIES.keys()), index=0
    )
    bt_strategy = st.selectbox(
        "Backtesting", list(BT_STRATEGIES.keys()), index=4
    )

    run_btn = st.button("🚀 Ejecutar análisis", type="primary", use_container_width=True)

st.title("📈 AlphaHunter")
st.caption(f"Universo: {len(tickers)} tickers | Período: {period} | Capital: ${capital:,.0f}")

# ─────────────────────────────────────────────
# Carga de datos (con cache de Streamlit)
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Descargando datos de mercado...")
def load_data(tickers: list, period: str) -> dict:
    return get_multiple(tickers, period=period)

@st.cache_data(ttl=3600, show_spinner="Ejecutando screener...")
def cached_screener(tickers: list, strategy: str, period: str) -> pd.DataFrame:
    return run_screener(tickers=tickers, strategy=strategy, period=period)

# ─────────────────────────────────────────────
# Tabs principales
# ─────────────────────────────────────────────
tab_screener, tab_analisis, tab_backtest, tab_ml, tab_correlacion, tab_poly, tab_broker, tab_historial = st.tabs([
    "🔍 Screener",
    "📊 Análisis técnico",
    "⚙️ Backtesting",
    "🤖 ML Predicción",
    "🔗 Correlación",
    "🎯 Polymarket",
    "🏦 Broker",
    "📒 Historial",
])

# ══════════════════════════════════════════════
# TAB 1 — SCREENER
# ══════════════════════════════════════════════
with tab_screener:
    st.subheader("Screener de candidatos")

    if run_btn or "screener_df" not in st.session_state:
        with st.spinner("Escaneando mercado..."):
            st.session_state.screener_df = cached_screener(tickers, screener_strategy, period)
            st.session_state.data_dict = load_data(tickers, period)

    df_screen = st.session_state.get("screener_df", pd.DataFrame())

    if df_screen.empty:
        st.warning("Ningún ticker pasó los filtros con la estrategia seleccionada.")
    else:
        st.success(f"{len(df_screen)} candidatos encontrados")

        cols = st.columns(4)
        cols[0].metric("Candidatos", len(df_screen))
        cols[1].metric("RSI promedio", f"{df_screen['rsi'].mean():.1f}")
        cols[2].metric("Vol ratio promedio", f"{df_screen['vol_ratio'].mean():.2f}x")
        cols[3].metric("Estrategia", screener_strategy)

        st.dataframe(
            df_screen.style.background_gradient(subset=['vol_ratio'], cmap='Greens')
                           .format({'rsi': '{:.1f}', 'vol_ratio': '{:.2f}x',
                                    'precio': '${:.2f}', 'macd': '{:.4f}'}),
            use_container_width=True,
        )

# ══════════════════════════════════════════════
# TAB 2 — ANÁLISIS TÉCNICO
# ══════════════════════════════════════════════
with tab_analisis:
    st.subheader("Análisis técnico")

    col1, col2 = st.columns([1, 3])
    with col1:
        selected_ticker = st.selectbox("Ticker", tickers, key="analisis_ticker")
        show_period = st.selectbox("Mostrar últimos", ["3mo", "6mo", "1y", "2y"], index=1)

    data_dict = st.session_state.get("data_dict") or load_data(tickers, period)

    if selected_ticker not in data_dict:
        with st.spinner(f"Cargando datos de {selected_ticker}..."):
            data_dict[selected_ticker] = get_ohlcv(selected_ticker, period=period)
            st.session_state["data_dict"] = data_dict

    if selected_ticker in data_dict:
        df_raw = data_dict[selected_ticker]
        df_ind = compute_all(df_raw)

        # Filtrar por período de visualización
        period_days = {"3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
        df_vis = df_ind.tail(period_days.get(show_period, 180))

        st.plotly_chart(price_chart(df_vis, selected_ticker), use_container_width=True)

        # Métricas rápidas
        last = df_ind.iloc[-1]
        prev = df_ind.iloc[-2]
        m = st.columns(5)
        m[0].metric("Precio",   f"${last['Close']:.2f}",
                    f"{(last['Close']/prev['Close']-1)*100:+.2f}%")
        m[1].metric("RSI 14",   f"{last['rsi_14']:.1f}",
                    "sobrevendido" if last['rsi_14'] < 30 else ("sobrecomprado" if last['rsi_14'] > 70 else "normal"))
        m[2].metric("Vol ratio", f"{last['vol_ratio']:.2f}x")
        m[3].metric("MACD",     f"{last['macd']:.4f}")
        m[4].metric("%B Bollinger", f"{last['bb_pct_b']:.2f}")
    else:
        st.warning(f"No hay datos para {selected_ticker}")

# ══════════════════════════════════════════════
# TAB 3 — BACKTESTING
# ══════════════════════════════════════════════
with tab_backtest:
    st.subheader("Backtesting de estrategia")

    bt_ticker = st.selectbox("Ticker", tickers, key="bt_ticker")
    data_dict = st.session_state.get("data_dict") or load_data(tickers, period)

    # Si el ticker no está en el data_dict (ej: se agregó después del último análisis), lo carga
    if bt_ticker not in data_dict:
        with st.spinner(f"Cargando datos de {bt_ticker}..."):
            data_dict[bt_ticker] = get_ohlcv(bt_ticker, period=period)
            st.session_state["data_dict"] = data_dict

    if bt_ticker in data_dict:
        with st.spinner(f"Ejecutando backtest {bt_ticker}..."):
            bt_result = run_backtest(
                data_dict[bt_ticker],
                strategy_name=bt_strategy,
                initial_capital=float(capital),
                stop_loss_pct=stop_loss,
            )
            bt_metrics = calculate_metrics(bt_result)

        # Métricas principales
        m = st.columns(4)
        ret_color = "normal" if bt_metrics['total_return_pct'] >= 0 else "inverse"
        m[0].metric("Retorno total",    f"{bt_metrics['total_return_pct']:+.2f}%")
        m[1].metric("Sharpe ratio",     f"{bt_metrics['sharpe_ratio']:.2f}")
        m[2].metric("Max drawdown",     f"{bt_metrics['max_drawdown_pct']:.2f}%")
        m[3].metric("Win rate",         f"{bt_metrics['win_rate_pct']:.1f}%")

        m2 = st.columns(4)
        m2[0].metric("Capital final",   f"${bt_metrics['final_capital']:,.2f}")
        m2[1].metric("Retorno anual",   f"{bt_metrics['annual_return_pct']:+.2f}%")
        m2[2].metric("Profit factor",   f"{bt_metrics['profit_factor']:.2f}")
        m2[3].metric("Trades totales",  bt_metrics['n_trades'])

        # Gráficos
        st.plotly_chart(
            equity_chart(bt_result['equity_curve'], bt_ticker,
                         float(capital), data_dict[bt_ticker]),
            use_container_width=True,
        )

        if not bt_result['trades'].empty:
            st.plotly_chart(
                trades_chart(bt_result['trades'], bt_ticker),
                use_container_width=True,
            )
            with st.expander("Ver todos los trades"):
                st.dataframe(bt_result['trades'], use_container_width=True)
    else:
        st.warning(f"No hay datos para {bt_ticker}")

# ══════════════════════════════════════════════
# TAB 4 — ML PREDICCIÓN
# ══════════════════════════════════════════════
with tab_ml:
    st.subheader("Predicción ML — XGBoost")

    data_dict = st.session_state.get("data_dict") or load_data(tickers, period)
    df_screen = st.session_state.get("screener_df", pd.DataFrame())

    col_a, col_b = st.columns([2, 1])

    with col_b:
        ml_ticker = st.selectbox("Ticker individual", tickers, key="ml_ticker")

        if ml_ticker not in data_dict:
            with st.spinner(f"Cargando datos de {ml_ticker}..."):
                data_dict[ml_ticker] = get_ohlcv(ml_ticker, period=period)
                st.session_state["data_dict"] = data_dict
        forward_days = st.slider("Horizonte predicción (días)", 3, 20, 5)
        retrain = st.checkbox("Re-entrenar modelo")

        if st.button("Predecir ticker", use_container_width=True):
            with st.spinner(f"Entrenando/cargando modelo {ml_ticker}..."):
                try:
                    if retrain or not os.path.exists(
                        os.path.join('data', 'models', f'{ml_ticker}_model.pkl')
                    ):
                        train_result = train(data_dict[ml_ticker], ml_ticker,
                                             forward_days=forward_days, save=True)
                        opt_t = find_optimal_threshold(train_result, "f1")
                        ml_eval = evaluate(train_result, threshold=opt_t)
                        st.session_state.ml_eval = ml_eval
                        st.session_state.ml_train = train_result

                    pred = predict_ticker(data_dict[ml_ticker], ml_ticker, auto_train=True)
                    st.session_state.ml_pred = pred
                except Exception as e:
                    st.error(f"Error: {e}")

    with col_a:
        pred = st.session_state.get("ml_pred")
        if pred:
            signal_color = {
                "FUERTE_COMPRA": "🟢",
                "COMPRA":        "🟡",
                "NEUTRAL":       "⚪",
                "VENTA":         "🟠",
                "FUERTE_VENTA":  "🔴",
            }.get(pred['señal'], "⚪")

            st.markdown(f"### {signal_color} {pred['ticker']} — {pred['señal']}")

            m = st.columns(3)
            m[0].metric("Probabilidad de subida", f"{pred['prob_sube']:.1%}")
            m[1].metric("Probabilidad de bajada", f"{pred['prob_baja']:.1%}")
            m[2].metric("Precio actual",           f"${pred['precio_actual']}")

            ev = st.session_state.get("ml_eval")
            if ev:
                st.divider()
                st.caption("Métricas del modelo en test set")
                m2 = st.columns(4)
                m2[0].metric("Accuracy",  f"{ev['accuracy']}%")
                m2[1].metric("Precision", f"{ev['precision']}%")
                m2[2].metric("Recall",    f"{ev['recall']}%")
                m2[3].metric("AUC-ROC",   f"{ev['auc_roc']:.3f}")

    # Predicción masiva de candidatos del screener
    if not df_screen.empty:
        st.divider()
        st.subheader("Ranking ML — candidatos del screener")

        if st.button("Predecir todos los candidatos", use_container_width=True):
            with st.spinner("Generando predicciones..."):
                df_ranking = predict_screener_candidates(df_screen, data_dict, auto_train=True)
                st.session_state.df_ranking = df_ranking

        df_ranking = st.session_state.get("df_ranking", pd.DataFrame())
        if not df_ranking.empty:
            st.plotly_chart(ranking_table(df_ranking), use_container_width=True)
            with st.expander("Ver tabla completa"):
                st.dataframe(df_ranking, use_container_width=True)

# ══════════════════════════════════════════════
# TAB 5 — CORRELACIÓN
# ══════════════════════════════════════════════
with tab_correlacion:
    st.subheader("Correlación de retornos diarios")
    st.caption("Valores cercanos a 1.0 = movimiento conjunto | cercanos a -1.0 = movimiento opuesto")

    data_dict = st.session_state.get("data_dict") or load_data(tickers, period)

    if len(data_dict) >= 2:
        st.plotly_chart(correlation_heatmap(data_dict), use_container_width=True)

        # Tabla de correlaciones más altas y más bajas
        returns = pd.DataFrame({
            t: d['Close'].pct_change() for t, d in data_dict.items()
        }).dropna()
        corr = returns.corr()

        pairs = []
        for i in corr.index:
            for j in corr.columns:
                if i < j:
                    pairs.append({"Par": f"{i} / {j}", "Correlación": round(corr.loc[i, j], 3)})
        df_pairs = pd.DataFrame(pairs).sort_values("Correlación", ascending=False)

        col1, col2 = st.columns(2)
        with col1:
            st.caption("Mayor correlación (mueven juntos)")
            st.dataframe(df_pairs.head(5), use_container_width=True, hide_index=True)
        with col2:
            st.caption("Menor correlación (mejor diversificación)")
            st.dataframe(df_pairs.tail(5), use_container_width=True, hide_index=True)
    else:
        st.warning("Se necesitan al menos 2 tickers para calcular correlación.")

# ══════════════════════════════════════════════
# TAB 6 — POLYMARKET
# ══════════════════════════════════════════════
with tab_poly:
    st.subheader("🎯 Polymarket — Sentimiento del Mercado de Predicciones")
    st.caption(
        "Probabilidades implícitas en tiempo real extraídas de Polymarket. "
        "Un mercado de predicciones donde la gente apuesta dinero real sobre eventos futuros. "
        "Mayor probabilidad = mayor consenso del mercado."
    )

    # Cache de 30 minutos para no saturar la API
    @st.cache_data(ttl=1800, show_spinner="Consultando Polymarket...")
    def load_macro_sentiment():
        return get_macro_sentiment()

    @st.cache_data(ttl=1800, show_spinner="Buscando mercados financieros...")
    def load_financial_markets():
        return search_financial_markets(min_volume=500, min_liquidity=200)

    col_refresh, col_info = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Actualizar datos", use_container_width=True):
            st.cache_data.clear()

    with col_info:
        st.info("Datos actualizados cada 30 minutos automáticamente.")

    st.divider()

    # ── Sentimiento macro ─────────────────────────────────────
    st.subheader("Indicadores Macro")

    with st.spinner("Cargando sentimiento macro..."):
        sentiment = load_macro_sentiment()

    if "error" in sentiment:
        st.error(f"Error al conectar con Polymarket: {sentiment['error']}")
    else:
        # Métricas de cabecera
        m = st.columns(3)
        score = sentiment.get("sentiment_score", 0.5)
        score_label = "⚠️ PESIMISTA" if score > 0.6 else ("✅ OPTIMISTA" if score < 0.4 else "↔️ NEUTRAL")
        m[0].metric("Sentimiento general", f"{score:.1%}", score_label)
        m[1].metric("Mercados consultados", sentiment.get("markets_found", 0))
        m[2].metric("Volumen total Polymarket", f"${sentiment.get('total_volume', 0):,.0f}")

        # Gauges
        st.plotly_chart(polymarket_gauges(sentiment), use_container_width=True)

        # Barras horizontales
        st.plotly_chart(polymarket_bars(sentiment), use_container_width=True)

        # Interpretación automática
        st.subheader("Interpretación para AlphaHunter")
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**Señales bajistas activas:**")
            bearish = []
            if (sentiment.get("prob_recession") or 0) > 0.5:
                bearish.append(f"🔴 Recesión: {sentiment['prob_recession']:.1%}")
            if (sentiment.get("prob_sp_crash") or 0) > 0.4:
                bearish.append(f"🔴 Crash S&P: {sentiment['prob_sp_crash']:.1%}")
            if (sentiment.get("prob_btc_crash") or 0) > 0.4:
                bearish.append(f"🔴 Crash BTC: {sentiment['prob_btc_crash']:.1%}")
            if (sentiment.get("prob_fed_hike") or 0) > 0.5:
                bearish.append(f"🔴 Fed sube tasas: {sentiment['prob_fed_hike']:.1%}")
            if bearish:
                for b in bearish:
                    st.markdown(b)
            else:
                st.markdown("✅ Ninguna señal bajista dominante")

        with col_b:
            st.markdown("**Señales alcistas activas:**")
            bullish = []
            if (sentiment.get("prob_fed_cut") or 0) > 0.5:
                bullish.append(f"🟢 Fed recorta tasas: {sentiment['prob_fed_cut']:.1%}")
            if (sentiment.get("prob_btc_100k") or 0) > 0.5:
                bullish.append(f"🟢 BTC > $100K: {sentiment['prob_btc_100k']:.1%}")
            if (sentiment.get("prob_recession") or 1) < 0.3:
                bullish.append(f"🟢 Baja prob. recesión: {sentiment.get('prob_recession', 0):.1%}")
            if bullish:
                for b in bullish:
                    st.markdown(b)
            else:
                st.markdown("⚠️ Ninguna señal alcista dominante")

    st.divider()

    # ── Mercados financieros activos ──────────────────────────
    st.subheader("Mercados Financieros Activos en Polymarket")

    with st.spinner("Cargando mercados..."):
        df_markets = load_financial_markets()

    if df_markets.empty:
        st.warning("No se encontraron mercados financieros activos en este momento.")
    else:
        st.caption(f"{len(df_markets)} mercados encontrados | ordenados por volumen")
        st.plotly_chart(polymarket_markets_table(df_markets), use_container_width=True)

        # Búsqueda de activo específico
        st.divider()
        st.subheader("Sentimiento por Activo")
        asset_input = st.text_input(
            "Buscar activo en Polymarket",
            placeholder="bitcoin, ethereum, gold, oil, nvidia...",
        )

        if asset_input:
            with st.spinner(f"Buscando mercados para '{asset_input}'..."):
                asset_sentiment = get_asset_sentiment(asset_input.lower())

            if asset_sentiment.get("n_markets", 0) == 0:
                st.warning(f"No se encontraron mercados para '{asset_input}' en Polymarket.")
            else:
                mc = st.columns(3)
                mc[0].metric("Prob. sube (mercado)",  f"{asset_sentiment['prob_up']:.1%}")
                mc[1].metric("Prob. baja (mercado)",  f"{asset_sentiment['prob_down']:.1%}")
                mc[2].metric("Mercados encontrados",  asset_sentiment['n_markets'])

                # Divergencia con ML
                ml_pred = st.session_state.get("ml_pred")
                if ml_pred and ml_pred.get("ticker", "").upper() in asset_input.upper():
                    st.divider()
                    st.subheader("⚡ Análisis de Divergencia ML vs Polymarket")
                    div = abs(ml_pred['prob_sube'] - asset_sentiment['prob_up'])
                    col1, col2, col3 = st.columns(3)
                    col1.metric("XGBoost dice",     f"{ml_pred['prob_sube']:.1%} sube")
                    col2.metric("Polymarket dice",  f"{asset_sentiment['prob_up']:.1%} sube")
                    col3.metric("Divergencia",      f"{div:.1%}")

                    if div > 0.20:
                        st.error(
                            "⚠️ **Alta divergencia** — el modelo ML y el mercado de "
                            "predicciones discrepan significativamente. Señal de cautela."
                        )
                    elif div > 0.10:
                        st.warning("↔️ Divergencia moderada — considera esperar confirmación.")
                    else:
                        st.success("✅ Baja divergencia — ambas fuentes coinciden.")

                # Lista de mercados específicos
                if asset_sentiment.get("markets"):
                    with st.expander(f"Ver todos los mercados de '{asset_input}'"):
                        df_asset = pd.DataFrame(asset_sentiment["markets"])
                        st.dataframe(df_asset, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════
# TAB 7 — BROKER (Alpaca Paper Trading)
# ══════════════════════════════════════════════
with tab_broker:
    st.subheader("🏦 Alpaca Paper Trading")

    if not is_configured():
        st.warning(
            "**API keys no configuradas.** Editá el archivo `.env` en la raíz del proyecto:\n\n"
            "```\nALPACA_API_KEY=tu_key\nALPACA_SECRET_KEY=tu_secret\n```\n\n"
            "Obtené las keys en [app.alpaca.markets](https://app.alpaca.markets) "
            "→ Paper Account → API Keys"
        )
        st.stop()

    # ── Cuenta ────────────────────────────────────────────────
    try:
        account = get_account()
    except Exception as e:
        st.error(f"Error conectando con Alpaca: {e}")
        st.stop()

    col_ref = st.columns([1, 5])
    with col_ref[0]:
        if st.button("🔄 Actualizar", use_container_width=True):
            st.rerun()

    st.divider()
    st.subheader("Estado de la cuenta")

    m = st.columns(4)
    m[0].metric("Equity",        f"${account['equity']:,.2f}")
    m[1].metric("Cash",          f"${account['cash']:,.2f}")
    m[2].metric("Buying Power",  f"${account['buying_power']:,.2f}")
    pl_sign = "+" if account['pl_total'] >= 0 else ""
    m[3].metric("P&L del día",   f"{pl_sign}${account['pl_total']:,.2f}")

    # ── Posiciones abiertas ───────────────────────────────────
    st.divider()
    st.subheader("Posiciones abiertas")

    try:
        positions = get_positions()
    except Exception as e:
        st.error(f"Error cargando posiciones: {e}")
        positions = []

    if not positions:
        st.info("No hay posiciones abiertas actualmente.")
    else:
        df_pos = pd.DataFrame(positions)
        df_pos_display = df_pos.rename(columns={
            "symbol": "Ticker", "qty": "Cant.", "side": "Lado",
            "avg_entry_price": "Entrada", "current_price": "Precio actual",
            "market_value": "Valor mercado", "unrealized_pl": "P&L $",
            "unrealized_plpc": "P&L %",
        })

        st.dataframe(
            df_pos_display.style
                .format({
                    "Entrada": "${:.2f}", "Precio actual": "${:.2f}",
                    "Valor mercado": "${:,.2f}", "P&L $": "${:+.2f}",
                    "P&L %": "{:+.1f}%",
                })
                .applymap(lambda v: "color: #00c853" if isinstance(v, (int, float)) and v > 0
                          else ("color: #ff5252" if isinstance(v, (int, float)) and v < 0 else ""),
                          subset=["P&L $", "P&L %"]),
            use_container_width=True,
            hide_index=True,
        )

        # Cerrar posición
        st.caption("Cerrar posición")
        col_close1, col_close2 = st.columns([2, 1])
        with col_close1:
            ticker_to_close = st.selectbox(
                "Ticker", [p["symbol"] for p in positions], key="close_pos_select"
            )
        with col_close2:
            st.write("")
            st.write("")
            if st.button("🔴 Cerrar posición", type="secondary", use_container_width=True):
                try:
                    close_position(ticker_to_close)
                    st.success(f"Posición de {ticker_to_close} cerrada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Nueva orden ───────────────────────────────────────────
    st.divider()
    st.subheader("Nueva orden")

    # Pre-llenar con candidato del screener si hay uno seleccionado
    df_screen = st.session_state.get("screener_df", pd.DataFrame())
    screener_tickers = list(df_screen["ticker"]) if not df_screen.empty else []
    default_ticker = screener_tickers[0] if screener_tickers else ""

    col_o1, col_o2, col_o3 = st.columns(3)
    with col_o1:
        order_symbol = st.text_input("Ticker", value=default_ticker, key="order_symbol").upper()
        order_side = st.radio("Lado", ["buy", "sell"], horizontal=True)
    with col_o2:
        order_mode = st.radio("Cantidad por", ["Notional (USD)", "Acciones"], horizontal=True)
        if order_mode == "Notional (USD)":
            order_notional = st.number_input("Monto USD", min_value=1.0, value=100.0, step=10.0)
            order_qty = None
        else:
            order_qty = st.number_input("Acciones", min_value=0.01, value=1.0, step=0.01)
            order_notional = None
        order_type = st.selectbox("Tipo", ["market", "limit", "stop", "stop_limit"])
    with col_o3:
        limit_price = None
        stop_price = None
        if order_type in ("limit", "stop_limit"):
            limit_price = st.number_input("Límite ($)", min_value=0.01, value=100.0, step=0.01)
        if order_type in ("stop", "stop_limit"):
            stop_price = st.number_input("Stop ($)", min_value=0.01, value=100.0, step=0.01)
        tif = st.selectbox("Time in force", ["day", "gtc"])

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        submit_order = st.button(
            f"{'🟢 Comprar' if order_side == 'buy' else '🔴 Vender'} {order_symbol}",
            type="primary",
            use_container_width=True,
            disabled=not order_symbol,
        )

    if submit_order and order_symbol:
        try:
            final_qty = order_qty
            final_notional = order_notional

            # Alpaca no acepta notional + gtc → convertir a qty usando precio del data_dict
            if order_notional is not None and tif == "gtc":
                precio_ref = None
                data_dict_ref = st.session_state.get("data_dict", {})
                if order_symbol in data_dict_ref:
                    precio_ref = float(data_dict_ref[order_symbol]["Close"].iloc[-1])
                elif order_symbol in [r["ticker"] for r in (df_screen.to_dict("records") if not df_screen.empty else [])]:
                    precio_ref = float(df_screen[df_screen["ticker"] == order_symbol]["precio"].iloc[0])

                if precio_ref and precio_ref > 0:
                    # GTC solo acepta enteros — floor para no exceder el monto
                    final_qty = int(order_notional / precio_ref)
                    final_notional = None
                else:
                    st.warning("No se encontró precio de referencia. Cambiá Time in force a 'day' o ingresá la cantidad en acciones.")
                    st.stop()

            result = place_order(
                symbol=order_symbol,
                qty=final_qty,
                notional=final_notional,
                side=order_side,
                order_type=order_type,
                time_in_force=tif,
                limit_price=limit_price,
                stop_price=stop_price,
            )
            st.success(
                f"Orden enviada — ID: `{result['id'][:8]}...` | "
                f"{result['side'].upper()} {result['symbol']} | Status: {result['status']}"
            )
        except Exception as e:
            st.error(f"Error enviando orden: {e}")

    # Candidatos del screener como acceso rápido
    if screener_tickers:
        st.caption("Candidatos del screener (click para pre-llenar):")
        cols_sc = st.columns(min(len(screener_tickers), 6))
        for i, t in enumerate(screener_tickers[:6]):
            row = df_screen[df_screen["ticker"] == t].iloc[0]
            cols_sc[i].metric(t, f"${row['precio']:.2f}", f"RSI {row['rsi']:.0f}")

    # ── Historial de órdenes ──────────────────────────────────
    st.divider()
    st.subheader("Historial de órdenes")

    order_status_filter = st.radio(
        "Filtrar por estado", ["all", "closed", "open"], horizontal=True
    )

    try:
        orders = get_orders(status=order_status_filter, limit=30)
    except Exception as e:
        st.error(f"Error cargando órdenes: {e}")
        orders = []

    if not orders:
        st.info("No hay órdenes en el historial.")
    else:
        df_orders = pd.DataFrame(orders).drop(columns=["id", "raw"], errors="ignore")
        df_orders.columns = [c.replace("_", " ").title() for c in df_orders.columns]
        st.dataframe(df_orders, use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════
    # AUTO-TRADING
    # ══════════════════════════════════════════════════════════
    st.divider()
    st.subheader("🤖 Auto-Trading")
    st.caption("El motor corre screener + ML + Polymarket y coloca órdenes automáticamente.")

    # ── Configuración ─────────────────────────────────────────
    with st.expander("⚙️ Configuración del auto-trader", expanded=False):
        at_col1, at_col2, at_col3 = st.columns(3)

        with at_col1:
            at_strategy = st.selectbox(
                "Estrategia screener",
                list(SCREENER_STRATEGIES.keys()),
                index=0,
                key="at_strategy",
            )
            at_max_pos = st.number_input(
                "Max posiciones simultáneas", min_value=1, max_value=20,
                value=DEFAULT_CONFIG["max_positions"], key="at_max_pos",
            )

        with at_col2:
            at_pos_size = st.number_input(
                "Monto por posición (USD)", min_value=100, max_value=50_000,
                value=int(DEFAULT_CONFIG["max_position_usd"]), step=500, key="at_pos_size",
            )
            at_ml_threshold = st.slider(
                "Umbral ML mínimo", 0.50, 0.90,
                float(DEFAULT_CONFIG["ml_threshold"]), 0.05, key="at_ml_threshold",
            )

        with at_col3:
            at_sl = st.slider(
                "Stop Loss (%)", 2, 20,
                int(DEFAULT_CONFIG["stop_loss_pct"]), key="at_sl",
            )
            at_tp = st.slider(
                "Take Profit (%)", 5, 50,
                int(DEFAULT_CONFIG["take_profit_pct"]), key="at_tp",
            )

    at_config = {
        **DEFAULT_CONFIG,
        "screener_strategy": at_strategy,
        "max_positions":     at_max_pos,
        "max_position_usd":  at_pos_size,
        "ml_threshold":      at_ml_threshold,
        "stop_loss_pct":     float(at_sl),
        "take_profit_pct":   float(at_tp),
    }

    # ── Acciones manuales ─────────────────────────────────────
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    with btn_col1:
        if st.button("▶️ Ejecutar ciclo ahora", type="primary", use_container_width=True):
            with st.spinner("Corriendo ciclo completo (screener + ML + Polymarket)..."):
                resumen = run_cycle(at_config)
                st.session_state["at_last_resumen"] = resumen
            st.rerun()

    with btn_col2:
        if st.button("🛡️ Revisar stops ahora", use_container_width=True):
            with st.spinner("Chequeando stop loss y take profit..."):
                cerrados = monitor_stops(at_config)
            if cerrados:
                st.warning(f"Cerradas {len(cerrados)} posicion(es): {', '.join(cerrados)}")
            else:
                st.success("Ninguna posición activó SL/TP.")
            st.rerun()

    with btn_col3:
        st.info(
            "Para ejecución automática en terminal:\n"
            "```\npython auto_trader_runner.py\n```"
        )

    # ── Resumen último ciclo ──────────────────────────────────
    resumen = st.session_state.get("at_last_resumen")
    if resumen:
        st.divider()
        st.caption("Último ciclo ejecutado")
        r_cols = st.columns(4)
        r_cols[0].metric("Órdenes colocadas",    resumen.get("ordenes_colocadas", 0))
        r_cols[1].metric("Candidatos analizados", resumen.get("candidatos_analizados", 0))
        r_cols[2].metric("Bloqueados ML",         resumen.get("bloqueados_ml", 0))
        r_cols[3].metric("Posiciones finales",    resumen.get("posiciones_finales", 0))

        if resumen.get("razon") == "contexto_macro_adverso":
            st.error(
                f"Ciclo bloqueado por contexto macro adverso — "
                f"Recesión: {resumen.get('prob_recession', 0):.1%} | "
                f"Crash S&P: {resumen.get('prob_sp_crash', 0):.1%}"
            )

    # ── Log del auto-trader ───────────────────────────────────
    st.divider()
    st.subheader("Log del auto-trader")

    log_entries = get_trader_log()
    if not log_entries:
        st.info("Sin actividad registrada. Ejecutá un ciclo para ver el log.")
    else:
        level_colors = {
            "BUY":   "#00c853",
            "SELL":  "#ff5252",
            "WARN":  "#ffab40",
            "ERROR": "#ff1744",
            "INFO":  "#78909c",
        }
        for entry in log_entries[:50]:
            color = level_colors.get(entry["level"], "#78909c")
            ticker_str = f"**{entry['ticker']}** — " if entry["ticker"] else ""
            st.markdown(
                f"<small style='color:{color}'>[{entry['ts']}] [{entry['level']}]</small> "
                f"{ticker_str}{entry['msg']}",
                unsafe_allow_html=True,
            )

# ══════════════════════════════════════════════
# TAB 8 — HISTORIAL DE TRADES
# ══════════════════════════════════════════════
with tab_historial:
    st.subheader("📒 Historial de Trades")

    all_trades = get_all_trades()

    # ── Sync desde Alpaca ─────────────────────────────────────
    with st.expander("🔄 Sincronizar desde Alpaca", expanded=not all_trades):
        sync_col1, sync_col2, sync_col3 = st.columns([2, 2, 1])
        with sync_col1:
            sync_after = st.text_input(
                "Desde fecha (opcional)",
                placeholder="2026-04-12T00:00:00Z",
                help="ISO timestamp UTC. Vacío = últimos 500 fills.",
                key="sync_after",
            )
        with sync_col2:
            sync_strategy = st.text_input(
                "Estrategia screener usada",
                value="exploratorio",
                help="Alpaca no guarda esto — indicá cuál usaste",
                key="sync_strategy",
            )
        with sync_col3:
            st.write("")
            st.write("")
            sync_btn = st.button("⬇️ Importar fills", type="primary", use_container_width=True, key="sync_btn")

        if sync_btn:
            if not is_configured():
                st.error("Alpaca no configurado (.env)")
            else:
                with st.spinner("Obteniendo fills de Alpaca..."):
                    try:
                        result = sync_from_alpaca(
                            after=sync_after.strip() or None,
                            screener_strategy=sync_strategy.strip() or "desconocido",
                        )
                        st.success(
                            f"✅ Importados: **{result['importados']}** trades cerrados | "
                            f"Abiertos detectados: **{result['abiertos']}** | "
                            f"Ya existían: **{result['ya_existian']}**"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error sincronizando: {e}")

    all_trades = get_all_trades()   # recargar después del posible sync

    if not all_trades:
        st.info(
            "Aún no hay trades registrados. "
            "Usá el botón **Sincronizar desde Alpaca** para importar tu historial real."
        )
        st.stop()

    # ── Filtros ───────────────────────────────────────────────
    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        status_filter = st.radio(
            "Estado", ["Todos", "Cerrados", "Abiertos"], horizontal=True, key="hist_status"
        )
    with filter_col2:
        strategies = sorted({t["screener_strategy"] for t in all_trades})
        strategy_filter = st.multiselect(
            "Estrategia screener", strategies, default=strategies, key="hist_strat"
        )
    with filter_col3:
        if st.button("🔄 Refrescar", use_container_width=True, key="hist_refresh"):
            st.rerun()

    # Aplicar filtros
    filtered = all_trades
    if status_filter == "Cerrados":
        filtered = [t for t in filtered if t["status"] == "closed"]
    elif status_filter == "Abiertos":
        filtered = [t for t in filtered if t["status"] == "open"]
    if strategy_filter:
        filtered = [t for t in filtered if t["screener_strategy"] in strategy_filter]

    if not filtered:
        st.warning("No hay trades con los filtros seleccionados.")
        st.stop()

    # ── Métricas globales (solo cerrados) ─────────────────────
    closed_filtered = [t for t in filtered if t["status"] == "closed"]
    if closed_filtered:
        stats = compute_stats(filtered)
        st.divider()
        st.subheader("Resumen")

        m = st.columns(5)
        m[0].metric("Total trades",   stats["total"])
        m[1].metric(
            "Win rate",
            f"{stats['win_rate']:.1f}%",
            delta=f"{stats['wins']}W / {stats['losses']}L",
        )
        m[2].metric(
            "P&L total",
            f"${stats['pnl_usd_total']:+,.2f}",
            delta=f"Mejor: +{stats['best_trade_pct']:.1f}%",
        )
        m[3].metric("Ganancia media",  f"+{stats['avg_gain_pct']:.2f}%")
        m[4].metric("Pérdida media",   f"{stats['avg_loss_pct']:.2f}%")

        # ── Por estrategia ─────────────────────────────────────
        by_strat = stats.get("by_strategy", {})
        if len(by_strat) > 1:
            st.divider()
            st.subheader("Por estrategia")
            rows = []
            for strat, s in by_strat.items():
                rows.append({
                    "Estrategia":  strat,
                    "Trades":      s["total"],
                    "Wins":        s["wins"],
                    "Win rate":    f"{s['win_rate']:.1f}%",
                    "P&L total $": f"${s['pnl_total']:+,.2f}",
                    "P&L medio %": f"{s['avg_pnl']:+.2f}%",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Tabla detallada ───────────────────────────────────────
    st.divider()
    st.subheader(f"Detalle ({len(filtered)} trades)")

    rows = []
    for t in reversed(filtered):   # más reciente primero
        rows.append({
            "Ticker":        t["ticker"],
            "Estrategia":    t["screener_strategy"],
            "Entrada":       t["entry_time"],
            "Precio entrada":f"${t['entry_price']:.2f}",
            "Qty":           t["qty"],
            "Monto $":       f"${t['monto_usd']:,.0f}",
            "ML prob":       f"{t['ml_prob']:.0%}" if t["ml_prob"] else "—",
            "Estado":        "🟢 Abierto" if t["status"] == "open" else "⚫ Cerrado",
            "Salida":        t["exit_time"] or "—",
            "Precio salida": f"${t['exit_price']:.2f}" if t["exit_price"] else "—",
            "Razón":         t["exit_reason"] or "—",
            "P&L %":         t["pnl_pct"],
            "P&L $":         t["pnl_usd"],
            "Hold (h)":      t["hold_hours"] or "—",
        })

    df_hist = pd.DataFrame(rows)

    def _color_pnl(val):
        if not isinstance(val, (int, float)):
            return ""
        if val > 0:
            return "color: #00c853"
        if val < 0:
            return "color: #ff5252"
        return ""

    st.dataframe(
        df_hist.style
            .applymap(_color_pnl, subset=["P&L %", "P&L $"])
            .format({
                "P&L %": lambda v: f"{v:+.2f}%" if isinstance(v, (int, float)) else v,
                "P&L $": lambda v: f"${v:+,.2f}" if isinstance(v, (int, float)) else v,
            }),
        use_container_width=True,
        hide_index=True,
    )
