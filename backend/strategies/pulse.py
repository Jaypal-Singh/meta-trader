import pandas as pd
import numpy as np

def calculate_pulse_signals(df, tp_mult=1.5, sl_mult=1.0, symbol="EURUSD"):
    """
    PULSE SCALPING ENGINE (Super Fast - M1 / M5 optimized)
    
    Logic:
    - EMA 5 and EMA 13 Crossover (Extremely fast)
    - Buy: EMA 5 crosses ABOVE EMA 13
    - Sell: EMA 5 crosses BELOW EMA 13
    - Fully Vectorized for maximum performance (0 latency)
    """
    df = df.copy()
    
    # Ensure numeric columns
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    if len(df) < 20:
        return df
        
    # ── ATR (14) for TP/SL ──
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        abs(df['high'] - df['low']),
        np.maximum(
            abs(df['high'] - df['prev_close']),
            abs(df['low'] - df['prev_close'])
        )
    )
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # ── Super Fast EMAs ──
    df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema_13'] = df['close'].ewm(span=13, adjust=False).mean()
    
    # ── SIGNAL GENERATION (Vectorized for speed) ──
    df['signal'] = None
    df['tp'] = np.nan
    df['sl'] = np.nan
    
    # Condition: EMA 5 crosses ABOVE EMA 13
    buy_cond = (df['ema_5'].shift(1) <= df['ema_13'].shift(1)) & (df['ema_5'] > df['ema_13'])
    
    # Condition: EMA 5 crosses BELOW EMA 13
    sell_cond = (df['ema_5'].shift(1) >= df['ema_13'].shift(1)) & (df['ema_5'] < df['ema_13'])
    
    # ── Swing High/Low for Stop Loss ──
    df['swing_low_5'] = df['low'].rolling(window=5, min_periods=1).min()
    df['swing_high_5'] = df['high'].rolling(window=5, min_periods=1).max()
    
    # Apply Buy Signals
    df.loc[buy_cond, 'signal'] = 'BUY'
    # SL: Recent swing low - small buffer
    buy_sl = df['swing_low_5'] - (df['atr'] * 0.5)
    buy_risk = np.maximum(df['close'] - buy_sl, df['atr'] * 0.5) # Min risk = 0.5 ATR
    df.loc[buy_cond, 'sl'] = buy_sl
    df.loc[buy_cond, 'tp'] = df['close'] + (buy_risk * tp_mult)
    
    # Apply Sell Signals
    df.loc[sell_cond, 'signal'] = 'SELL'
    # SL: Recent swing high + small buffer
    sell_sl = df['swing_high_5'] + (df['atr'] * 0.5)
    sell_risk = np.maximum(sell_sl - df['close'], df['atr'] * 0.5)
    df.loc[sell_cond, 'sl'] = sell_sl
    df.loc[sell_cond, 'tp'] = df['close'] - (sell_risk * tp_mult)

    # Clean up temp columns
    df = df.drop(columns=['prev_close', 'tr', 'swing_low_5', 'swing_high_5'], errors='ignore')
    
    return df

def analyze_pulse_exit_conditions(df):
    """
    PULSE - Dynamic Smart Exit Logic
    Watches the fast EMA 5 vs EMA 13 for momentum exhaustion or sudden reversal.
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
    ema_5 = latest['ema_5'] if 'ema_5' in df.columns else close
    ema_13 = latest['ema_13'] if 'ema_13' in df.columns else close
    
    prev_ema_5 = prev['ema_5'] if 'ema_5' in df.columns else close
    prev_ema_13 = prev['ema_13'] if 'ema_13' in df.columns else close
    
    exit_buy = False
    exit_sell = False
    reasons = []
    
    # If we are in a BUY and momentum completely reverses (EMA 5 crosses back BELOW EMA 13)
    if prev_ema_5 >= prev_ema_13 and ema_5 < ema_13:
        exit_buy = True
        reasons.append("Pulse Momentum Reversed (EMA 5 < EMA 13)")
        
    # If we are in a SELL and momentum completely reverses (EMA 5 crosses back ABOVE EMA 13)
    if prev_ema_5 <= prev_ema_13 and ema_5 > ema_13:
        exit_sell = True
        reasons.append("Pulse Momentum Reversed (EMA 5 > EMA 13)")
        
    # Optional: If price drops significantly below EMA 13 while in a BUY, maybe cut early
    if close < ema_13 * 0.9995:
        exit_buy = True
        if "Price broke below EMA 13 support" not in reasons:
            reasons.append("Price broke below EMA 13 support")
            
    if close > ema_13 * 1.0005:
        exit_sell = True
        if "Price broke above EMA 13 resistance" not in reasons:
            reasons.append("Price broke above EMA 13 resistance")
            
    return {
        "should_exit_buy": exit_buy,
        "should_exit_sell": exit_sell,
        "reason": " | ".join(reasons) if reasons else "No reversal detected",
        "extend_tp_buy": False, # Pulse doesn't extend TP natively yet
        "extend_tp_sell": False,
    }
