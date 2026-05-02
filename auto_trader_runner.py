"""
auto_trader_runner.py — Runner de auto-trading por terminal

Uso:
    python auto_trader_runner.py                    # ciclo cada 4 horas
    python auto_trader_runner.py --interval 60      # ciclo cada 60 minutos
    python auto_trader_runner.py --once             # un solo ciclo y sale
    python auto_trader_runner.py --stops-only       # solo monitorear stops

Ctrl+C para detener.
"""

import sys
import os
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from utils.auto_trader import run_cycle, monitor_stops, DEFAULT_CONFIG


def is_market_open() -> bool:
    """Lunes-Viernes 09:30-16:00 ET (simplificado, sin feriados)."""
    from datetime import timezone, timedelta
    et = datetime.now(timezone(timedelta(hours=-4)))  # EDT
    if et.weekday() >= 5:   # Sábado=5, Domingo=6
        return False
    if et.hour < 9 or (et.hour == 9 and et.minute < 30):
        return False
    if et.hour >= 16:
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="AlphaHunter Auto Trader")
    parser.add_argument("--interval",    type=int, default=240,  help="Minutos entre ciclos (default: 240)")
    parser.add_argument("--stops-every", type=int, default=15,   help="Minutos entre chequeo de stops (default: 15)")
    parser.add_argument("--once",        action="store_true",    help="Ejecutar un solo ciclo completo y salir")
    parser.add_argument("--stops-only",  action="store_true",    help="Solo monitorear stops, sin abrir posiciones")

    # Config personalizable
    parser.add_argument("--strategy",    default=DEFAULT_CONFIG["screener_strategy"])
    parser.add_argument("--max-pos",     type=int,   default=DEFAULT_CONFIG["max_positions"])
    parser.add_argument("--pos-size",    type=float, default=DEFAULT_CONFIG["max_position_usd"])
    parser.add_argument("--sl",          type=float, default=DEFAULT_CONFIG["stop_loss_pct"],    help="Stop loss %%")
    parser.add_argument("--tp",          type=float, default=DEFAULT_CONFIG["take_profit_pct"],  help="Take profit %%")
    parser.add_argument("--ml-threshold",type=float, default=DEFAULT_CONFIG["ml_threshold"])

    args = parser.parse_args()

    config = {
        **DEFAULT_CONFIG,
        "screener_strategy": args.strategy,
        "max_positions":     args.max_pos,
        "max_position_usd":  args.pos_size,
        "stop_loss_pct":     args.sl,
        "take_profit_pct":   args.tp,
        "ml_threshold":      args.ml_threshold,
    }

    print("=" * 60)
    print("  AlphaHunter Auto Trader")
    print("=" * 60)
    print(f"  Estrategia   : {config['screener_strategy']}")
    print(f"  Max posicion : ${config['max_position_usd']:,.0f}")
    print(f"  Max posiciones: {config['max_positions']}")
    print(f"  Stop Loss    : {config['stop_loss_pct']}%")
    print(f"  Take Profit  : {config['take_profit_pct']}%")
    print(f"  ML threshold : {config['ml_threshold']:.0%}")
    print(f"  Intervalo    : {args.interval} min (ciclo) / {args.stops_every} min (stops)")
    print("=" * 60)
    print("  Ctrl+C para detener")
    print("=" * 60)

    last_cycle = 0
    last_stops = 0

    while True:
        now = time.time()
        market_open = is_market_open()

        # Chequeo de stops (siempre que haya pasado el intervalo)
        if now - last_stops >= args.stops_every * 60:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Chequeando stops...")
            cerrados = monitor_stops(config)
            if cerrados:
                print(f"  Cerradas {len(cerrados)} posicion(es): {cerrados}")
            last_stops = now

        # Ciclo completo de trading (solo en horario de mercado)
        if not args.stops_only:
            if now - last_cycle >= args.interval * 60:
                if market_open:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando ciclo de trading...")
                    resumen = run_cycle(config)
                    print(f"  Ordenes colocadas: {resumen.get('ordenes_colocadas', 0)}")
                else:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Mercado cerrado, esperando...")
                last_cycle = now

        if args.once:
            print("\nModo --once: saliendo.")
            break

        time.sleep(60)  # revisar cada minuto


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAuto trader detenido.")
