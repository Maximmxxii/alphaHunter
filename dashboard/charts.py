"""
dashboard/charts.py — Gráficos interactivos con Plotly

Genera visualizaciones para el dashboard de AlphaHunter:

    - Gráfico de velas (candlestick) con indicadores superpuestos
    - Subgráfico de volumen
    - Subgráfico de RSI con zonas de sobrecompra/sobreventa
    - Subgráfico de MACD con histograma
    - Curva de equity del backtesting vs Buy & Hold
    - Distribución de trades (ganancias/pérdidas)
    - Heatmap de correlación entre tickers
    - Tabla de ranking con color según señal ML
    - Gauges de sentimiento macro Polymarket
    - Barra horizontal de probabilidades Polymarket
    - Tabla de mercados Polymarket con volumen y fecha

Todos los gráficos retornan objetos plotly.graph_objects.Figure
listos para ser renderizados con st.plotly_chart() en Streamlit.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


# --- Paleta de colores AlphaHunter ---
COLORS = {
    "verde":     "#00C896",
    "rojo":      "#FF4B4B",
    "azul":      "#2196F3",
    "amarillo":  "#FFC107",
    "fondo":     "#0E1117",
    "fondo2":    "#1A1D27",
    "texto":     "#FAFAFA",
    "gris":      "#555555",
}


def _base_layout(title: str = "") -> dict:
    """Layout base oscuro para todos los gráficos."""
    return dict(
        title=title,
        paper_bgcolor=COLORS["fondo"],
        plot_bgcolor=COLORS["fondo2"],
        font=dict(color=COLORS["texto"], size=12),
        margin=dict(l=50, r=30, t=50, b=30),
        legend=dict(bgcolor=COLORS["fondo2"], bordercolor=COLORS["gris"]),
        xaxis=dict(gridcolor=COLORS["gris"], showgrid=True),
        yaxis=dict(gridcolor=COLORS["gris"], showgrid=True),
    )


def price_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """
    Gráfico principal: velas + SMA20/50/200 + volumen + RSI + MACD.

    Args:
        df     : DataFrame con indicadores (salida de compute_all)
        ticker : Símbolo del activo para el título

    Returns:
        Figura Plotly con 4 subgráficos: precio, volumen, RSI, MACD
    """
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        subplot_titles=[f"{ticker} — Precio", "Volumen", "RSI (14)", "MACD"],
    )

    # --- Velas ---
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'],
        low=df['Low'],   close=df['Close'],
        name="Precio",
        increasing_line_color=COLORS["verde"],
        decreasing_line_color=COLORS["rojo"],
    ), row=1, col=1)

    # --- Medias móviles ---
    for col, color, name in [
        ('sma_20',  COLORS["azul"],     "SMA 20"),
        ('sma_50',  COLORS["amarillo"], "SMA 50"),
        ('sma_200', COLORS["rojo"],     "SMA 200"),
    ]:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col],
                name=name, line=dict(color=color, width=1.2),
                opacity=0.85,
            ), row=1, col=1)

    # --- Bandas de Bollinger ---
    if 'bb_upper' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['bb_upper'],
            name="BB Upper", line=dict(color=COLORS["gris"], width=1, dash="dot"),
            showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df['bb_lower'],
            name="BB Lower", line=dict(color=COLORS["gris"], width=1, dash="dot"),
            fill='tonexty', fillcolor='rgba(85,85,85,0.1)',
            showlegend=False,
        ), row=1, col=1)

    # --- Volumen ---
    colors_vol = [COLORS["verde"] if c >= o else COLORS["rojo"]
                  for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'],
        name="Volumen", marker_color=colors_vol, opacity=0.7,
    ), row=2, col=1)

    # --- RSI ---
    if 'rsi_14' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['rsi_14'],
            name="RSI 14", line=dict(color=COLORS["azul"], width=1.5),
        ), row=3, col=1)
        # Zonas sobrecompra/sobreventa
        for y_val, color in [(70, COLORS["rojo"]), (30, COLORS["verde"])]:
            fig.add_hline(y=y_val, line_dash="dash",
                          line_color=color, opacity=0.5, row=3, col=1)
        fig.update_yaxes(range=[0, 100], row=3, col=1)

    # --- MACD ---
    if 'macd' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['macd'],
            name="MACD", line=dict(color=COLORS["azul"], width=1.5),
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df['macd_signal'],
            name="Signal", line=dict(color=COLORS["amarillo"], width=1.2),
        ), row=4, col=1)
        colors_hist = [COLORS["verde"] if v >= 0 else COLORS["rojo"]
                       for v in df['macd_hist']]
        fig.add_trace(go.Bar(
            x=df.index, y=df['macd_hist'],
            name="Histograma", marker_color=colors_hist, opacity=0.6,
        ), row=4, col=1)

    fig.update_layout(**_base_layout(f"AlphaHunter — {ticker}"))
    fig.update_xaxes(rangeslider_visible=False)
    return fig


def equity_chart(equity: pd.Series, ticker: str, initial_capital: float, df_price: pd.DataFrame) -> go.Figure:
    """
    Curva de equity del backtest vs estrategia Buy & Hold.

    Args:
        equity          : Serie temporal de capital (salida de engine.run_backtest)
        ticker          : Símbolo del activo
        initial_capital : Capital inicial para normalizar B&H
        df_price        : DataFrame con columna Close para calcular B&H

    Returns:
        Figura con dos curvas: estrategia y Buy & Hold
    """
    # Buy & Hold normalizado al mismo capital inicial
    bh = df_price['Close'].reindex(equity.index).ffill()
    bh_equity = bh / bh.iloc[0] * initial_capital

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=equity.index, y=equity,
        name="Estrategia", line=dict(color=COLORS["verde"], width=2),
        fill='tozeroy', fillcolor='rgba(0,200,150,0.07)',
    ))

    fig.add_trace(go.Scatter(
        x=bh_equity.index, y=bh_equity,
        name="Buy & Hold", line=dict(color=COLORS["gris"], width=1.5, dash="dash"),
    ))

    fig.add_hline(y=initial_capital, line_dash="dot",
                  line_color=COLORS["amarillo"], opacity=0.4)

    fig.update_layout(**_base_layout(f"Curva de Equity — {ticker}"))
    fig.update_yaxes(title_text="Capital (USD)")
    return fig


def trades_chart(trades: pd.DataFrame, ticker: str) -> go.Figure:
    """
    Distribución de retornos por trade (histograma + línea de media).

    Args:
        trades : DataFrame de trades (salida de engine.run_backtest)
        ticker : Símbolo del activo

    Returns:
        Histograma de pnl_pct coloreado por ganancia/pérdida
    """
    if trades.empty:
        fig = go.Figure()
        fig.update_layout(**_base_layout(f"Sin trades — {ticker}"))
        return fig

    colors = [COLORS["verde"] if p > 0 else COLORS["rojo"] for p in trades['pnl_pct']]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=trades.index, y=trades['pnl_pct'],
        name="PnL %", marker_color=colors,
        hovertext=[f"{r['entry_date'].date()} → {r['exit_date'].date()}"
                   for _, r in trades.iterrows()],
    ))
    fig.add_hline(y=0, line_color=COLORS["gris"])
    fig.add_hline(y=trades['pnl_pct'].mean(), line_dash="dash",
                  line_color=COLORS["amarillo"], opacity=0.7,
                  annotation_text=f"Media {trades['pnl_pct'].mean():.2f}%")

    fig.update_layout(**_base_layout(f"Trades — {ticker}"))
    fig.update_yaxes(title_text="Retorno por trade (%)")
    return fig


def correlation_heatmap(data_dict: dict) -> go.Figure:
    """
    Heatmap de correlación de retornos diarios entre tickers.

    Args:
        data_dict: {ticker: DataFrame OHLCV}

    Returns:
        Heatmap de correlación
    """
    returns = pd.DataFrame({
        ticker: df['Close'].pct_change()
        for ticker, df in data_dict.items()
    }).dropna()

    corr = returns.corr()

    fig = go.Figure(go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.index,
        colorscale=[
            [0.0, COLORS["rojo"]],
            [0.5, COLORS["fondo2"]],
            [1.0, COLORS["verde"]],
        ],
        zmid=0,
        text=corr.round(2).values,
        texttemplate="%{text}",
        showscale=True,
    ))

    fig.update_layout(**_base_layout("Correlación de Retornos"))
    return fig


def ranking_table(df_ranking: pd.DataFrame) -> go.Figure:
    """
    Tabla de ranking con colores según señal ML.

    Args:
        df_ranking: DataFrame con columnas ticker, señal, prob_sube, etc.

    Returns:
        Tabla Plotly con colores de fila según señal
    """
    if df_ranking.empty:
        return go.Figure()

    # Color de fondo por señal
    def row_color(señal):
        if "FUERTE_COMPRA" in str(señal):
            return "rgba(0,200,150,0.25)"
        elif "COMPRA" in str(señal):
            return "rgba(0,200,150,0.10)"
        elif "FUERTE_VENTA" in str(señal):
            return "rgba(255,75,75,0.25)"
        elif "VENTA" in str(señal):
            return "rgba(255,75,75,0.10)"
        return "rgba(85,85,85,0.10)"

    cols_show = ['ticker', 'señal', 'prob_sube', 'precio_actual', 'rsi', 'vol_ratio']
    cols_show = [c for c in cols_show if c in df_ranking.columns]
    df_show = df_ranking[cols_show].copy()

    if 'prob_sube' in df_show.columns:
        df_show['prob_sube'] = df_show['prob_sube'].apply(lambda x: f"{x:.1%}")

    fill_colors = [[row_color(r) for r in df_show.get('señal', [])] ]

    fig = go.Figure(go.Table(
        header=dict(
            values=[f"<b>{c.upper()}</b>" for c in df_show.columns],
            fill_color=COLORS["fondo2"],
            font=dict(color=COLORS["verde"], size=13),
            align="center",
        ),
        cells=dict(
            values=[df_show[c] for c in df_show.columns],
            fill_color=fill_colors * len(df_show.columns),
            font=dict(color=COLORS["texto"], size=12),
            align="center",
            height=30,
        ),
    ))

    fig.update_layout(**_base_layout("Ranking AlphaHunter"))
    return fig


# ─────────────────────────────────────────────────────────
# Gráficos de Polymarket
# ─────────────────────────────────────────────────────────

def polymarket_gauges(sentiment: dict) -> go.Figure:
    """
    Gauges circulares con las probabilidades macro de Polymarket.

    Muestra hasta 4 indicadores clave en una fila:
        - Sentimiento general (bearish score)
        - Probabilidad de recesión
        - Probabilidad de recorte Fed
        - Probabilidad de crash cripto

    Args:
        sentiment: Dict retornado por get_macro_sentiment()

    Returns:
        Figura con gauges tipo indicador de aguja
    """
    indicators = [
        ("Sentimiento\nBearish",  sentiment.get("sentiment_score"),   0.5),
        ("Recesión\nEE.UU.",      sentiment.get("prob_recession"),     0.4),
        ("Fed recorta\ntasas",    sentiment.get("prob_fed_cut"),       0.5),
        ("Crash\nCripto",         sentiment.get("prob_btc_crash"),     0.3),
    ]

    fig = make_subplots(
        rows=1, cols=4,
        specs=[[{"type": "indicator"}] * 4],
    )

    for i, (label, value, threshold) in enumerate(indicators, start=1):
        val = value if value is not None else 0.5

        # Color dinámico: rojo si supera threshold, verde si está debajo
        color = COLORS["rojo"] if val > threshold else COLORS["verde"]

        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=round(val * 100, 1),
            number={"suffix": "%", "font": {"color": color, "size": 28}},
            title={"text": label, "font": {"color": COLORS["texto"], "size": 12}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": COLORS["gris"]},
                "bar":  {"color": color, "thickness": 0.3},
                "bgcolor": COLORS["fondo2"],
                "bordercolor": COLORS["gris"],
                "steps": [
                    {"range": [0, 33],  "color": "rgba(0,200,150,0.1)"},
                    {"range": [33, 66], "color": "rgba(255,193,7,0.1)"},
                    {"range": [66, 100],"color": "rgba(255,75,75,0.1)"},
                ],
                "threshold": {
                    "line": {"color": COLORS["amarillo"], "width": 2},
                    "thickness": 0.75,
                    "value": threshold * 100,
                },
            },
        ), row=1, col=i)

    fig.update_layout(
        **_base_layout("Polymarket — Sentimiento Macro"),
        height=280,
    )
    return fig


def polymarket_bars(sentiment: dict) -> go.Figure:
    """
    Barras horizontales con todas las probabilidades macro de Polymarket.

    Visualiza de un vistazo qué escenarios el mercado considera más/menos probables.

    Args:
        sentiment: Dict retornado por get_macro_sentiment()

    Returns:
        Figura de barras horizontales coloreadas por nivel de riesgo
    """
    labels_map = {
        "prob_recession": "Recesión EE.UU.",
        "prob_fed_cut":   "Fed recorta tasas",
        "prob_fed_hike":  "Fed sube tasas",
        "prob_btc_100k":  "Bitcoin > $100K",
        "prob_btc_crash": "Bitcoin crash",
        "prob_sp_crash":  "S&P 500 crash",
        "prob_inflation": "Inflación alta",
    }

    labels, values, colors_bar = [], [], []
    for key, label in labels_map.items():
        val = sentiment.get(key)
        if val is not None:
            labels.append(label)
            values.append(round(val * 100, 1))
            # Rojo si > 60%, amarillo si 40-60%, verde si < 40%
            if val > 0.6:
                colors_bar.append(COLORS["rojo"])
            elif val > 0.4:
                colors_bar.append(COLORS["amarillo"])
            else:
                colors_bar.append(COLORS["verde"])

    if not labels:
        fig = go.Figure()
        fig.update_layout(**_base_layout("Sin datos de Polymarket"))
        return fig

    fig = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation='h',
        marker_color=colors_bar,
        text=[f"{v:.1f}%" for v in values],
        textposition='outside',
        textfont=dict(color=COLORS["texto"]),
    ))

    # Línea de referencia en 50%
    fig.add_vline(x=50, line_dash="dash", line_color=COLORS["gris"],
                  opacity=0.5, annotation_text="50%")

    fig.update_layout(**_base_layout("Probabilidades Macro — Polymarket"), height=320)
    fig.update_xaxes(range=[0, 110], title_text="Probabilidad implícita (%)")
    return fig


def polymarket_markets_table(df_markets: pd.DataFrame) -> go.Figure:
    """
    Tabla interactiva de mercados financieros activos en Polymarket.

    Muestra pregunta, probabilidad Yes/No, volumen y fecha de vencimiento.
    Colorea las filas según si la probabilidad de Yes es alta o baja.

    Args:
        df_markets: DataFrame retornado por search_financial_markets()

    Returns:
        Tabla Plotly con formato visual
    """
    if df_markets.empty:
        fig = go.Figure()
        fig.update_layout(**_base_layout("Sin mercados financieros encontrados"))
        return fig

    df_show = df_markets[['question', 'prob_yes', 'prob_no', 'volume', 'end_date']].copy()
    df_show['volume']   = df_show['volume'].apply(lambda x: f"${x:,.0f}")
    df_show['prob_yes'] = df_show['prob_yes'].apply(lambda x: f"{x:.1%}")
    df_show['prob_no']  = df_show['prob_no'].apply(lambda x: f"{x:.1%}")

    # Color de celda prob_yes según nivel
    prob_vals = df_markets['prob_yes'].tolist()
    prob_colors = []
    for p in prob_vals:
        if p >= 0.70:
            prob_colors.append("rgba(0,200,150,0.3)")
        elif p >= 0.50:
            prob_colors.append("rgba(255,193,7,0.2)")
        else:
            prob_colors.append("rgba(255,75,75,0.2)")

    # Resto de celdas con fondo estándar
    n = len(df_show)
    std_color = ["rgba(26,29,39,0.8)"] * n

    fill_colors = [
        std_color,       # question
        prob_colors,     # prob_yes
        std_color,       # prob_no
        std_color,       # volume
        std_color,       # end_date
    ]

    fig = go.Figure(go.Table(
        columnwidth=[400, 80, 80, 100, 100],
        header=dict(
            values=["<b>MERCADO</b>", "<b>PROB YES</b>", "<b>PROB NO</b>",
                    "<b>VOLUMEN</b>", "<b>VENCE</b>"],
            fill_color=COLORS["fondo2"],
            font=dict(color=COLORS["verde"], size=12),
            align=["left", "center", "center", "right", "center"],
        ),
        cells=dict(
            values=[df_show[c] for c in df_show.columns],
            fill_color=fill_colors,
            font=dict(color=COLORS["texto"], size=11),
            align=["left", "center", "center", "right", "center"],
            height=28,
        ),
    ))

    fig.update_layout(**_base_layout(f"Mercados Financieros en Polymarket ({len(df_show)} activos)"))
    return fig
