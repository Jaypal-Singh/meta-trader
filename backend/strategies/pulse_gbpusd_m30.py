import pandas as pd
import numpy as np

def calculate_pulse_gbpusd_m30_signals(df, tp_mult=1.5, sl_mult=1.0, symbol="GBPUSD"):
    """
    PULSE ENGINE CUSTOMIZED FOR GBPUSD M30
    
    Logic:
    - EMA 9 and EMA 21 Crossover
    - Trend Filter: EMA 50
    - Buy: EMA 9 crosses ABOVE EMA 21 AND price > EMA 50
    - Sell: EMA 9 crosses BELOW EMA 21 AND price < EMA 50
    """
    df = df.copy()
    
    # Ensure numeric columns
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    if len(df) < 50:
        return df
        
    # ATR (14) for TP/SL
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        abs(df['high'] - df['low']),
        np.maximum(
            abs(df['high'] - df['prev_close']),
            abs(df['low'] - df['prev_close'])
        )
    )
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # EMAs
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # Signals
    df['signal'] = None
    df['tp'] = np.nan
    df['sl'] = np.nan
    
    buy_cond = (
        (df['ema_9'].shift(1) <= df['ema_21'].shift(1)) & 
        (df['ema_9'] > df['ema_21']) & 
        (df['close'] > df['ema_50'])
    )
    
    sell_cond = (
        (df['ema_9'].shift(1) >= df['ema_21'].shift(1)) & 
        (df['ema_9'] < df['ema_21']) & 
        (df['close'] < df['ema_50'])
    )
    
    # Swing High/Low for Stop Loss (Use 8 for M30 swings)
    df['swing_low_8'] = df['low'].rolling(window=8, min_periods=1).min()
    df['swing_high_8'] = df['high'].rolling(window=8, min_periods=1).max()
    
    # Apply Buy
    df.loc[buy_cond, 'signal'] = 'BUY'
    buy_sl = df['swing_low_8'] - (df['atr'] * sl_mult)
    buy_risk = np.maximum(df['close'] - buy_sl, df['atr'] * sl_mult)
    df.loc[buy_cond, 'sl'] = buy_sl
    df.loc[buy_cond, 'tp'] = df['close'] + (buy_risk * tp_mult)
    
    # Apply Sell
    df.loc[sell_cond, 'signal'] = 'SELL'
    sell_sl = df['swing_high_8'] + (df['atr'] * sl_mult)
    sell_risk = np.maximum(sell_sl - df['close'], df['atr'] * sl_mult)
    df.loc[sell_cond, 'sl'] = sell_sl
    df.loc[sell_cond, 'tp'] = df['close'] - (sell_risk * tp_mult)
    
    # Clean up
    df = df.drop(columns=['prev_close', 'tr', 'swing_low_8', 'swing_high_8'], errors='ignore')
    
    return df

def analyze_pulse_gbpusd_m30_exit_conditions(df):
    """
    Exit logic for GBPUSD M30 Pulse.
    """
    if df is None or len(df) < 5:
        return {
            "should_exit_buy": False, "should_exit_sell": False,
            "reason": "Insufficient data",
            "extend_tp_buy": False, "extend_tp_sell": False,
        }
        
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    close = latest['close']
    ema_9 = latest['ema_9'] if 'ema_9' in df.columns else close
    ema_21 = latest['ema_21'] if 'ema_21' in df.columns else close
    
    prev_ema_9 = prev['ema_9'] if 'ema_9' in df.columns else close
    prev_ema_21 = prev['ema_21'] if 'ema_21' in df.columns else close
    
    exit_buy = False
    exit_sell = False
    reasons = []
    
    if prev_ema_9 >= prev_ema_21 and ema_9 < ema_21:
        exit_buy = True
        reasons.append("Trend Reversed (EMA 9 < EMA 21)")
        
    if prev_ema_9 <= prev_ema_21 and ema_9 > ema_21:
        exit_sell = True
        reasons.append("Trend Reversed (EMA 9 > EMA 21)")
        
    return {
        "should_exit_buy": exit_buy,
        "should_exit_sell": exit_sell,
        "reason": " | ".join(reasons) if reasons else "No reversal detected",
        "extend_tp_buy": False,
        "extend_tp_sell": False,
    }
