import asyncio
import pandas as pd
import MetaTrader5 as mt5
from mt5_logic import get_market_data, calculate_indicators
from strategies.pulse import calculate_pulse_signals
from strategies.soul import calculate_soul_signals

def main():
    if not mt5.initialize():
        print("MT5 Init failed", mt5.last_error())
        return

    symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    for sym in symbols:
        df = get_market_data(sym, mt5.TIMEFRAME_M5, 300)
        if df is not None:
            df = calculate_indicators(df, symbol=sym)
            if df is not None and 'signal' in df.columns:
                signals = df.dropna(subset=['signal'])
                print(f"{sym} spirit signals: {len(signals)}")
            else:
                print(f"{sym} spirit signals: 0")
        else:
            print(f"{sym} no data")
            
    mt5.shutdown()

if __name__ == '__main__':
    main()
