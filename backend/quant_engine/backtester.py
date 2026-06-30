import pandas as pd
import numpy as np
from .cache_manager import cache
import uuid

class FastBacktester:
    """
    Vectorized Backtesting Engine
    Uses Pandas and NumPy to instantly simulate trades over thousands of historical candles.
    Reads data from the high-speed cache instead of the disk/database.
    """
    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe
        
    def load_cached_data(self) -> pd.DataFrame:
        """Loads OHLCV data directly from RAM/Redis"""
        cache_key = f"hist_{self.symbol}_{self.timeframe}"
        raw_data = cache.get(cache_key)
        
        if not raw_data:
            # Fallback mock data if cache misses
            return pd.DataFrame()
            
        df = pd.DataFrame(raw_data)
        df['time'] = pd.to_datetime(df['time'])
        return df

    def run_simulation(self, strategy_func, initial_capital=1000.0) -> dict:
        """
        Runs the mathematical simulation and returns performance metrics.
        No database writes occur here, guaranteeing isolation.
        """
        df = self.load_cached_data()
        if df.empty:
            return {"error": "No historical data in cache."}
            
        # 1. Apply Strategy Vectorized Math
        df = strategy_func(df)
        
        # 2. Simulate Trades (Vectorized)
        # This is highly simplified for demonstration. 
        # QuantDinger uses strict event-driven iteration for exact fills.
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['signal'].shift(1) * df['returns']
        
        df['equity_curve'] = initial_capital * (1 + df['strategy_returns']).cumprod()
        
        # 3. Calculate Enterprise Metrics
        total_return = (df['equity_curve'].iloc[-1] - initial_capital) / initial_capital
        peak = df['equity_curve'].cummax()
        drawdown = (df['equity_curve'] - peak) / peak
        max_drawdown = drawdown.min()
        
        return {
            "backtest_id": str(uuid.uuid4()),
            "total_return_percent": round(total_return * 100, 2),
            "max_drawdown_percent": round(max_drawdown * 100, 2),
            "final_equity": round(df['equity_curve'].iloc[-1], 2),
            "trades_simulated": len(df[df['signal'] != 0])
        }
