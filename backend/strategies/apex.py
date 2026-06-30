import pandas as pd
import numpy as np
import ta

def calculate_apex_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apex Strategy (M5 Scalper) for LIVE TRADING
    - EMA 50 Trend Filter
    - RSI 14 Momentum Entry
    """
    if len(df) == 0: 
        return df
        
    df = df.copy()
    
    # Calculate Indicators
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    
    # Generate Signals
    df['signal'] = 0
    df.loc[(df['close'] > df['ema50']) & (df['rsi'] < 40), 'signal'] = 1
    df.loc[(df['close'] < df['ema50']) & (df['rsi'] > 60), 'signal'] = -1
    
    df['signal'] = df['signal'].replace(0, np.nan).ffill().fillna(0)
    return df
