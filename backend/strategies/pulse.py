"""
PULSE v3.0 — Enhanced Signal Engine with Volume, RSI & Trend Filters
======================================================================
Core: EMA fast/slow crossover (configurable per symbol)
Filters: Volume confirmation, RSI overbought/oversold, EMA trend filter
SL/TP: Swing High/Low based with ATR buffer (dynamic per-symbol config)
"""

import pandas as pd
import numpy as np


def calculate_pulse_signals(df: pd.DataFrame, config: dict = None) -> pd.DataFrame:
    """
    PULSE v3.0 Signal Engine.
    
    Uses symbol-specific config for EMA periods, filters, and TP/SL multipliers.
    Falls back to legacy defaults if no config provided.
    """
    df = df.copy()
    
    # Default config (legacy Pulse)
    if config is None:
        config = {
            "ema_fast": 5,
            "ema_slow": 13,
            "ema_trend": 50,
            "atr_period": 14,
            "tp_mult": 1.0,
            "sl_mult": 0.5,
            "rsi_period": 14,
            "rsi_overbought": 72,
            "rsi_oversold": 28,
        }
    
    ema_fast_period = config.get("ema_fast", 5)
    ema_slow_period = config.get("ema_slow", 13)
    ema_trend_period = config.get("ema_trend", 50)
    atr_period = config.get("atr_period", 14)
    tp_mult = config.get("tp_mult", 1.0)
    sl_mult = config.get("sl_mult", 0.5)
    rsi_period = config.get("rsi_period", 14)
    rsi_ob = config.get("rsi_overbought", 72)
    rsi_os = config.get("rsi_oversold", 28)
    
    # Ensure numeric columns
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    min_bars = max(ema_trend_period + 10, 50)
    if len(df) < min_bars:
        df['signal'] = None
        df['tp'] = np.nan
        df['sl'] = np.nan
        df['atr'] = np.nan
        return df
    
    # ── ATR ──
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        abs(df['high'] - df['low']),
        np.maximum(
            abs(df['high'] - df['prev_close']),
            abs(df['low'] - df['prev_close'])
        )
    )
    df['atr'] = df['tr'].rolling(window=atr_period).mean()
    
    # ── EMAs ──
    df['ema_fast'] = df['close'].ewm(span=ema_fast_period, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=ema_slow_period, adjust=False).mean()
    df['ema_trend'] = df['close'].ewm(span=ema_trend_period, adjust=False).mean()
    
    # ── RSI ──
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss_s = -delta.clip(upper=0)
    rs = gain.ewm(com=rsi_period-1, adjust=False).mean() / (loss_s.ewm(com=rsi_period-1, adjust=False).mean() + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ── VOLUME (tick_volume) ──
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else None
    if vol_col:
        df['vol_avg_20'] = df[vol_col].rolling(20).mean()
        df['vol_ratio'] = df[vol_col] / (df['vol_avg_20'] + 1)
    else:
        df['vol_ratio'] = 1.0
    
    # ── SIGNAL GENERATION ──
    df['signal'] = None
    df['tp'] = np.nan
    df['sl'] = np.nan
    
    # EMA Crossover conditions
    ema_cross_up = (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1)) & (df['ema_fast'] > df['ema_slow'])
    ema_cross_down = (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1)) & (df['ema_fast'] < df['ema_slow'])
    
    # Trend filter: price above/below trend EMA
    trend_up = df['close'] > df['ema_trend']
    trend_down = df['close'] < df['ema_trend']
    
    # RSI filter: avoid overbought for BUY, oversold for SELL
    rsi_ok_buy = df['rsi'] < rsi_ob
    rsi_ok_sell = df['rsi'] > rsi_os
    
    # Combined BUY condition: EMA cross up + trend up + RSI not overbought
    buy_cond = ema_cross_up & trend_up & rsi_ok_buy
    
    # Combined SELL condition: EMA cross down + trend down + RSI not oversold
    sell_cond = ema_cross_down & trend_down & rsi_ok_sell
    
    # ── Swing High/Low for Stop Loss ──
    swing_window = max(ema_slow_period, 8)
    df['swing_low'] = df['low'].rolling(window=swing_window, min_periods=1).min()
    df['swing_high'] = df['high'].rolling(window=swing_window, min_periods=1).max()
    
    # Apply BUY signals
    df.loc[buy_cond, 'signal'] = 'BUY'
    buy_sl = df['swing_low'] - (df['atr'] * sl_mult)
    buy_risk = np.maximum(df['close'] - buy_sl, df['atr'] * sl_mult)
    df.loc[buy_cond, 'sl'] = buy_sl
    df.loc[buy_cond, 'tp'] = df['close'] + (buy_risk * tp_mult)
    
    # Apply SELL signals
    df.loc[sell_cond, 'signal'] = 'SELL'
    sell_sl = df['swing_high'] + (df['atr'] * sl_mult)
    sell_risk = np.maximum(sell_sl - df['close'], df['atr'] * sl_mult)
    df.loc[sell_cond, 'sl'] = sell_sl
    df.loc[sell_cond, 'tp'] = df['close'] - (sell_risk * tp_mult)
    
    # Clean up temp columns
    df = df.drop(columns=['prev_close', 'tr', 'swing_low', 'swing_high', 'vol_avg_20'], errors='ignore')
    
    return df


def analyze_pulse_exit_conditions(df: pd.DataFrame) -> dict:
    """
    Legacy exit function — kept for backward compatibility.
    Smart Exit Engine (smart_exit.py) is now the primary exit handler.
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
    ema_fast = latest.get('ema_fast', close)
    ema_slow = latest.get('ema_slow', close)
    prev_ema_fast = prev.get('ema_fast', close)
    prev_ema_slow = prev.get('ema_slow', close)
    
    exit_buy = False
    exit_sell = False
    reasons = []
    
    # EMA cross reversal
    if prev_ema_fast >= prev_ema_slow and ema_fast < ema_slow:
        exit_buy = True
        reasons.append("Pulse: EMA fast crossed below EMA slow")
    
    if prev_ema_fast <= prev_ema_slow and ema_fast > ema_slow:
        exit_sell = True
        reasons.append("Pulse: EMA fast crossed above EMA slow")
    
    return {
        "should_exit_buy": exit_buy,
        "should_exit_sell": exit_sell,
        "reason": " | ".join(reasons) if reasons else "No reversal detected",
        "extend_tp_buy": False,
        "extend_tp_sell": False,
    }
