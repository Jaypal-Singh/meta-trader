import MetaTrader5 as mt5
import pandas as pd

def main():
    if not mt5.initialize():
        print("MT5 Init failed", mt5.last_error())
        return

    symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    for sym in symbols:
        info = mt5.symbol_info(sym)
        if info:
            print(f"{sym} found, selected: {info.select}, visible: {info.visible}")
            
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 10)
            if rates is not None and len(rates) > 0:
                print(f"  Got {len(rates)} bars for {sym}")
            else:
                print(f"  Failed to get bars for {sym}: {mt5.last_error()}")
        else:
            print(f"{sym} not found in MT5: {mt5.last_error()}")

    mt5.shutdown()

if __name__ == '__main__':
    main()
