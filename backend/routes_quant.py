from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from quant_engine import FastBacktester
import traceback

router = APIRouter()

class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str
    strategy: str
    initial_capital: float = 1000.0

@router.post("/backtest")
async def run_backtest(req: BacktestRequest):
    try:
        # Fetch real historical data from MT5
        from mt5_logic import get_market_data
        from quant_engine import cache
        import MetaTrader5 as mt5
        
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1
        }
        mt5_tf = tf_map.get(req.timeframe, mt5.TIMEFRAME_H1)
        
        df_hist = get_market_data(req.symbol, mt5_tf, num_bars=5000)
        if df_hist is not None and not df_hist.empty:
            # Convert pandas Timestamp to string to avoid JSON serialization errors
            df_hist['time'] = df_hist['time'].astype(str)
            cache_key = f"hist_{req.symbol}_{req.timeframe}"
            cache.set(cache_key, df_hist.to_dict('records'))
        
        # Instantiate the vector engine
        backtester = FastBacktester(symbol=req.symbol, timeframe=req.timeframe)
        
        # Define strategy mathematically
        def pulse_strategy(df):
            import pandas as pd
            import numpy as np
            if len(df) == 0: return df
            # Pulse (Scalping): Fast EMA Crossover (10 vs 20)
            df['sma1'] = df['close'].rolling(10).mean()
            df['sma2'] = df['close'].rolling(20).mean()
            df['signal'] = np.where(df['sma1'] > df['sma2'], 1, -1)
            return df

        def soul_strategy(df):
            import pandas as pd
            import numpy as np
            if len(df) == 0: return df
            # Soul (Trend): Slow EMA Crossover (50 vs 200) for big moves
            df['sma1'] = df['close'].rolling(50).mean()
            df['sma2'] = df['close'].rolling(200).mean()
            df['signal'] = np.where(df['sma1'] > df['sma2'], 1, -1)
            return df

        def spirit_strategy(df):
            import pandas as pd
            import numpy as np
            if len(df) == 0: return df
            # Spirit (Mean Reversal): Bollinger Bands
            df['sma20'] = df['close'].rolling(20).mean()
            df['std'] = df['close'].rolling(20).std()
            df['upper'] = df['sma20'] + (df['std'] * 2)
            df['lower'] = df['sma20'] - (df['std'] * 2)
            
            # Buy when price crosses below lower band, sell when crosses above upper
            df['signal'] = 0
            df.loc[df['close'] < df['lower'], 'signal'] = 1
            df.loc[df['close'] > df['upper'], 'signal'] = -1
            # Forward fill the signals so it holds the position until reversed
            df['signal'] = df['signal'].replace(0, np.nan).ffill().fillna(0)
            return df

        def apex_strategy(df):
            import pandas as pd
            import numpy as np
            import ta
            if len(df) == 0: return df
            
            # Apex (M5 Scalper): Completely Isolated Logic
            df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)
            df['rsi'] = ta.momentum.rsi(df['close'], window=14)
            
            df['signal'] = 0
            df.loc[(df['close'] > df['ema50']) & (df['rsi'] < 40), 'signal'] = 1
            df.loc[(df['close'] < df['ema50']) & (df['rsi'] > 60), 'signal'] = -1
            
            df['signal'] = df['signal'].replace(0, np.nan).ffill().fillna(0)
            return df
            
        # Select strategy
        strategy_map = {
            "pulse": pulse_strategy,
            "soul": soul_strategy,
            "spirit": spirit_strategy,
            "apex": apex_strategy
        }
        selected_strategy = strategy_map.get(req.strategy.lower(), pulse_strategy)
        
        # Run Vectorized Simulation
        results = backtester.run_simulation(strategy_func=selected_strategy, initial_capital=req.initial_capital)
        
        if "error" in results:
            return {"status": "success", "results": results}
            
        return {"status": "success", "results": results}
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
