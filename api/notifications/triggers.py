"""
Funciones que generan y envían notificaciones según eventos del sistema.

Cada función obtiene todos los tokens registrados y envía en batch.
Si no hay tokens registrados o falla el envío, solo se loguea — nunca crashea.
"""

import logging
from api.notifications.token_store import get_all_tokens
from api.notifications.push_service import send_push_batch

logger = logging.getLogger(__name__)


def _all_tokens() -> list[str]:
    """Devuelve lista plana de todos los tokens registrados."""
    all_data = get_all_tokens()
    tokens = []
    for user_tokens in all_data.values():
        tokens.extend(user_tokens)
    return tokens


def _broadcast(title: str, body: str, data: dict = None) -> None:
    """
    Envía una notificación a todos los dispositivos registrados.
    No lanza excepciones — solo loguea errores.
    """
    tokens = _all_tokens()
    if not tokens:
        logger.debug(f"[Triggers] Sin tokens registrados, notificación omitida: {title}")
        return

    notifications = [
        {"to": token, "title": title, "body": body, "sound": "default", **({"data": data} if data else {})}
        for token in tokens
    ]

    try:
        results = send_push_batch(notifications)
        errors = [r for r in results if r.get("status") == "error" or "error" in r]
        if errors:
            logger.warning(f"[Triggers] {len(errors)} errores al enviar '{title}': {errors}")
    except Exception as e:
        logger.error(f"[Triggers] Error enviando notificación '{title}': {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Triggers de trading
# ─────────────────────────────────────────────────────────────────────────────

def notify_stop_loss(symbol: str, pl_pct: float, amount_saved: float = None) -> None:
    """
    Notifica cuando se activa un stop loss.

    Args:
        symbol:       Ticker cerrado (ej. "MSFT")
        pl_pct:       P&L en porcentaje (negativo, ej. -5.0)
        amount_saved: USD de capital protegido (opcional)
    """
    title = f"🛡️ {symbol} — Stop Loss activado"
    body_parts = [f"Posición cerrada con {pl_pct:+.1f}%. Capital protegido."]
    if amount_saved is not None:
        body_parts.append(f"${amount_saved:,.0f} resguardados.")
    body = " ".join(body_parts)

    _broadcast(
        title=title,
        body=body,
        data={"symbol": symbol, "action": "sl_triggered", "pl_pct": pl_pct},
    )
    logger.info(f"[Triggers] SL notificado — {symbol} {pl_pct:+.1f}%")


def notify_take_profit(symbol: str, pl_pct: float, profit_usd: float = None) -> None:
    """
    Notifica cuando se alcanza el take profit.

    Args:
        symbol:     Ticker cerrado (ej. "NVDA")
        pl_pct:     P&L en porcentaje (positivo, ej. 20.0)
        profit_usd: Ganancia en USD (opcional)
    """
    title = f"🎯 {symbol} — ¡Objetivo alcanzado!"
    profit_str = f" — ${profit_usd:,.0f} ganados" if profit_usd is not None else ""
    body = f"+{pl_pct:.1f}% ganado{profit_str}."

    _broadcast(
        title=title,
        body=body,
        data={"symbol": symbol, "action": "tp_triggered", "pl_pct": pl_pct},
    )
    logger.info(f"[Triggers] TP notificado — {symbol} +{pl_pct:.1f}%")


def notify_trailing_floor_update(symbol: str, new_floor: float, old_floor: float = None) -> None:
    """
    Notifica cuando sube el trailing floor significativamente (buena noticia).
    Solo envía si el floor subió más de un 2% respecto al anterior.

    Args:
        symbol:    Ticker (ej. "MSFT")
        new_floor: Nuevo precio de piso
        old_floor: Piso anterior (para calcular la variación)
    """
    # Solo notificar si subió significativamente (>2%)
    if old_floor is not None:
        if old_floor <= 0:
            return
        pct_change = (new_floor - old_floor) / old_floor * 100
        if pct_change < 2.0:
            logger.debug(f"[Triggers] Floor {symbol} subió {pct_change:.1f}% < 2%, omitiendo notificación")
            return

    title = f"📈 {symbol}: piso de protección actualizado"
    body  = f"Nuevo stop de protección: ${new_floor:,.2f}"

    _broadcast(
        title=title,
        body=body,
        data={"symbol": symbol, "action": "trailing_floor_updated", "new_floor": new_floor},
    )
    logger.info(f"[Triggers] Trailing floor notificado — {symbol} → ${new_floor:.2f}")


# ─────────────────────────────────────────────────────────────────────────────
# Triggers de Smart Money
# ─────────────────────────────────────────────────────────────────────────────

def notify_smart_money_alert(
    source: str,
    politician_or_whale: str,
    ticker: str,
    action: str,
    amount: str = None,
) -> None:
    """
    Notifica nuevas señales de smart money (congresistas o ballenas).

    Args:
        source:               "congress" o "whales"
        politician_or_whale:  Nombre (ej. "McCaul", "Berkshire")
        ticker:               Símbolo (ej. "MSFT")
        action:               Acción (ej. "compró", "aumentó", "vendió")
        amount:               Monto en string (ej. "$15k") — opcional
    """
    if source == "congress":
        title = f"🏛️ Movimiento en el Congreso — {ticker}"
        body_parts = [f"{politician_or_whale} {action} {ticker}"]
        if amount:
            body_parts.append(f"({amount})")
        body_parts.append("¿Seguirlo?")
        body = " ".join(body_parts)
    else:
        # whales / institucionales
        title = f"🐋 Movimiento institucional — {ticker}"
        body_parts = [f"{politician_or_whale} {action} {ticker}"]
        if amount:
            body_parts.append(f"({amount})")
        body = " ".join(body_parts)

    _broadcast(
        title=title,
        body=body,
        data={
            "symbol":  ticker,
            "action":  "smart_money_alert",
            "source":  source,
            "actor":   politician_or_whale,
        },
    )
    logger.info(f"[Triggers] Smart Money notificado — {politician_or_whale} {action} {ticker}")


# ─────────────────────────────────────────────────────────────────────────────
# Triggers de señales
# ─────────────────────────────────────────────────────────────────────────────

def notify_strong_signal(symbol: str, signal_score: int, strategy: str) -> None:
    """
    Notifica cuando hay una señal muy fuerte en el screener.
    Solo envía si signal_score >= 80.

    Args:
        symbol:       Ticker (ej. "NVDA")
        signal_score: Score de 0 a 100
        strategy:     Nombre de la estrategia (ej. "momentum_alcista")
    """
    if signal_score < 80:
        logger.debug(f"[Triggers] Señal {symbol} score={signal_score} < 80, omitiendo notificación")
        return

    title = f"⚡ Señal fuerte — {symbol}"
    body  = f"Score {signal_score}% con estrategia {strategy}. Revisalo."

    _broadcast(
        title=title,
        body=body,
        data={"symbol": symbol, "action": "strong_signal", "score": signal_score, "strategy": strategy},
    )
    logger.info(f"[Triggers] Señal fuerte notificada — {symbol} {signal_score}%")
