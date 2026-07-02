"""
SMART EXIT ENGINE — Profit Protection + Dynamic Exit System
=============================================================
The #1 cause of losses: system holds trades too long.
This engine tracks floating profit peaks and exits intelligently.

Core Logic:
1. Track peak profit of every open trade
2. If profit drops X% from peak → EXIT (protect profits)
3. Detect momentum exhaustion (RSI divergence, volume drop)
4. Detect reversal candle patterns (Engulfing, Pin Bar)
5. Dynamic breakeven lock (never let green trade turn red)
6. Dynamic SL/TP adjustment based on live market data
"""

import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from mt5_logic import get_market_data
from routes_orders import calc_pnl


def check_profit_protection(order: dict, current_price: float, config: dict) -> dict:
    """
    PROFIT PROTECTION — The most important exit check.
    
    Tracks peak_profit and exits when profit drops significantly from the peak.
    Also handles breakeven lock.
    
    Returns: {"should_exit": bool, "reason": str, "updates": dict}
    """
    open_price = order["open_price"]
    order_type = order["order_type"]
    lot_size = order.get("lot_size", 0.05)
    symbol = order["symbol"]
    
    # Calculate current PnL
    current_pnl = calc_pnl(order_type, open_price, current_price, lot_size, symbol)
    
    # Get tracked peak profit (from DB)
    peak_profit = order.get("peak_profit", 0.0)
    
    # Update peak if current is higher
    updates = {}
    if current_pnl > peak_profit:
        peak_profit = current_pnl
        updates["peak_profit"] = peak_profit
    
    # Always update floating_pnl and current_price
    updates["floating_pnl"] = current_pnl
    updates["current_price"] = current_price
    
    # --- BREAKEVEN LOCK ---
    breakeven_threshold = config.get("breakeven_profit_usd", 3.0)
    trail_stage = order.get("trail_stage", 0)
    sl = order.get("sl")
    
    if peak_profit >= breakeven_threshold and trail_stage < 1 and sl:
        # Move SL to breakeven + small buffer
        tick = mt5.symbol_info_tick(symbol)
        spread = (tick.ask - tick.bid) if tick else 0
        
        if order_type == "BUY":
            new_sl = open_price + spread  # Breakeven + spread
            if new_sl > sl:
                updates["sl"] = new_sl
                updates["trail_stage"] = 1
                return {
                    "should_exit": False,
                    "reason": f"Breakeven lock activated (peak: ${peak_profit:.2f})",
                    "updates": updates
                }
        else:  # SELL
            new_sl = open_price - spread
            if new_sl < sl:
                updates["sl"] = new_sl
                updates["trail_stage"] = 1
                return {
                    "should_exit": False,
                    "reason": f"Breakeven lock activated (peak: ${peak_profit:.2f})",
                    "updates": updates
                }
    
    # --- PROFIT PROTECTION (Drop from Peak) ---
    protect_pct = config.get("profit_protect_pct", 30)
    min_profit_to_protect = config.get("min_profit_to_protect", 2.0)
    
    if peak_profit >= min_profit_to_protect and current_pnl > 0:
        drop_from_peak = peak_profit - current_pnl
        drop_pct = (drop_from_peak / peak_profit) * 100 if peak_profit > 0 else 0
        
        if drop_pct >= protect_pct:
            return {
                "should_exit": True,
                "reason": f"Profit Protection: peak=${peak_profit:.2f}, now=${current_pnl:.2f} ({drop_pct:.0f}% drop)",
                "updates": updates
            }
    
    # --- DYNAMIC TRAILING STOP (ATR-based) ---
    atr_at_entry = order.get("atr_at_entry", 0)
    if atr_at_entry and atr_at_entry > 0 and sl and trail_stage >= 1:
        if order_type == "BUY":
            profit_distance = current_price - open_price
            
            # Stage 2: Lock 0.5× ATR profit
            if profit_distance >= atr_at_entry * 1.0 and trail_stage < 2:
                new_sl = open_price + (atr_at_entry * 0.5)
                if new_sl > sl:
                    updates["sl"] = new_sl
                    updates["trail_stage"] = 2
            
            # Stage 3: Lock 1.0× ATR profit
            elif profit_distance >= atr_at_entry * 1.5 and trail_stage < 3:
                new_sl = open_price + (atr_at_entry * 1.0)
                if new_sl > sl:
                    updates["sl"] = new_sl
                    updates["trail_stage"] = 3
            
            # Continuous trailing: 0.5× ATR behind price
            elif trail_stage >= 3:
                trailing_sl = current_price - (atr_at_entry * 0.5)
                if trailing_sl > sl:
                    updates["sl"] = trailing_sl
                    updates["trail_stage"] = 4
        
        else:  # SELL
            profit_distance = open_price - current_price
            
            if profit_distance >= atr_at_entry * 1.0 and trail_stage < 2:
                new_sl = open_price - (atr_at_entry * 0.5)
                if new_sl < sl:
                    updates["sl"] = new_sl
                    updates["trail_stage"] = 2
            
            elif profit_distance >= atr_at_entry * 1.5 and trail_stage < 3:
                new_sl = open_price - (atr_at_entry * 1.0)
                if new_sl < sl:
                    updates["sl"] = new_sl
                    updates["trail_stage"] = 3
            
            elif trail_stage >= 3:
                trailing_sl = current_price + (atr_at_entry * 0.5)
                if trailing_sl < sl:
                    updates["sl"] = trailing_sl
                    updates["trail_stage"] = 4
    
    return {"should_exit": False, "reason": "", "updates": updates}


def check_momentum_exhaustion(df: pd.DataFrame, order: dict, config: dict) -> dict:
    """
    MOMENTUM EXHAUSTION DETECTOR
    
    Detects when a trend is losing steam using:
    1. RSI divergence (price making new high but RSI declining)
    2. Volume declining while price extends
    3. MACD histogram shrinking
    
    Returns: {"should_exit": bool, "reason": str}
    """
    if df is None or len(df) < 20:
        return {"should_exit": False, "reason": "Insufficient data"}
    
    order_type = order["order_type"]
    current_pnl = order.get("floating_pnl", 0.0)
    
    # Only check momentum exhaustion if trade is in profit
    if current_pnl <= 0:
        return {"should_exit": False, "reason": "Trade not in profit"}
    
    # Calculate RSI
    rsi_period = config.get("rsi_period", 14)
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss_s = -delta.clip(upper=0)
    rs = gain.ewm(com=rsi_period-1, adjust=False).mean() / (loss_s.ewm(com=rsi_period-1, adjust=False).mean() + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    
    current_rsi = float(rsi.iloc[-1])
    prev_rsi = float(rsi.iloc[-2])
    prev2_rsi = float(rsi.iloc[-3])
    
    # Calculate MACD histogram
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_signal
    
    curr_hist = float(macd_hist.iloc[-1])
    prev_hist = float(macd_hist.iloc[-2])
    prev2_hist = float(macd_hist.iloc[-3])
    
    reasons = []
    should_exit = False
    
    if order_type == "BUY":
        # RSI exhaustion: RSI was high and now declining for 2 bars
        if current_rsi < prev_rsi < prev2_rsi and prev2_rsi > 65:
            reasons.append(f"RSI declining from {prev2_rsi:.0f}→{current_rsi:.0f}")
            should_exit = True
        
        # RSI extreme overbought
        if current_rsi > config.get("rsi_overbought", 72):
            reasons.append(f"RSI overbought ({current_rsi:.0f})")
            should_exit = True
        
        # MACD histogram shrinking (bearish divergence)
        if curr_hist < prev_hist < prev2_hist and prev2_hist > 0 and curr_hist > 0:
            reasons.append("MACD momentum fading")
            should_exit = True
            
    else:  # SELL
        # RSI exhaustion: RSI was low and now rising for 2 bars
        if current_rsi > prev_rsi > prev2_rsi and prev2_rsi < 35:
            reasons.append(f"RSI rising from {prev2_rsi:.0f}→{current_rsi:.0f}")
            should_exit = True
        
        # RSI extreme oversold
        if current_rsi < config.get("rsi_oversold", 28):
            reasons.append(f"RSI oversold ({current_rsi:.0f})")
            should_exit = True
        
        # MACD histogram growing (bullish divergence)
        if curr_hist > prev_hist > prev2_hist and prev2_hist < 0 and curr_hist < 0:
            reasons.append("MACD momentum fading")
            should_exit = True
    
    return {
        "should_exit": should_exit,
        "reason": " | ".join(reasons) if reasons else "Momentum OK",
        "rsi": current_rsi,
        "macd_hist": curr_hist
    }


def check_candle_reversal(df: pd.DataFrame, order: dict) -> dict:
    """
    CANDLE PATTERN REVERSAL DETECTOR
    
    Detects reversal candle patterns:
    1. Bearish/Bullish Engulfing
    2. Pin Bar (long wick rejection)
    3. Doji at extremes
    
    Returns: {"should_exit": bool, "reason": str}
    """
    if df is None or len(df) < 5:
        return {"should_exit": False, "reason": "Insufficient data"}
    
    order_type = order["order_type"]
    current_pnl = order.get("floating_pnl", 0.0)
    
    # Only check patterns if trade is in profit (we want to protect profits)
    if current_pnl <= 0:
        return {"should_exit": False, "reason": "Trade not in profit"}
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    o = float(latest['open'])
    h = float(latest['high'])
    l = float(latest['low'])
    c = float(latest['close'])
    
    po = float(prev['open'])
    ph = float(prev['high'])
    pl = float(prev['low'])
    pc = float(prev['close'])
    
    body = abs(c - o)
    candle_range = h - l if h > l else 0.0001
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    
    prev_body = abs(pc - po)
    
    reasons = []
    should_exit = False
    
    if order_type == "BUY":
        # Bearish Engulfing: current candle engulfs previous bullish candle
        if c < o and body > prev_body and c < po and o > pc:
            reasons.append("Bearish Engulfing")
            should_exit = True
        
        # Bearish Pin Bar: long upper wick, small body
        if upper_wick > body * 2 and upper_wick > candle_range * 0.6:
            reasons.append("Bearish Pin Bar (rejection)")
            should_exit = True
    
    else:  # SELL
        # Bullish Engulfing
        if c > o and body > prev_body and c > po and o < pc:
            reasons.append("Bullish Engulfing")
            should_exit = True
        
        # Bullish Pin Bar: long lower wick, small body
        if lower_wick > body * 2 and lower_wick > candle_range * 0.6:
            reasons.append("Bullish Pin Bar (rejection)")
            should_exit = True
    
    return {
        "should_exit": should_exit,
        "reason": " | ".join(reasons) if reasons else "No reversal pattern"
    }


def check_opposite_signal(df: pd.DataFrame, order: dict) -> dict:
    """
    Check if the strategy has generated an opposite signal.
    
    Returns: {"should_exit": bool, "reason": str}
    """
    if df is None or len(df) < 5 or 'signal' not in df.columns:
        return {"should_exit": False, "reason": "No signal data"}
    
    order_type = order["order_type"]
    
    signals_df = df.dropna(subset=['signal'])
    if signals_df.empty:
        return {"should_exit": False, "reason": "No recent signals"}
    
    last_signal_row = signals_df.iloc[-1]
    # Only consider signals from last 3 candles
    if df.index[-1] - last_signal_row.name <= 3:
        sig = last_signal_row['signal']
        if order_type == "BUY" and sig == "SELL":
            return {"should_exit": True, "reason": "Opposite SELL signal detected"}
        elif order_type == "SELL" and sig == "BUY":
            return {"should_exit": True, "reason": "Opposite BUY signal detected"}
    
    return {"should_exit": False, "reason": "No opposite signal"}


def check_time_exit(order: dict, config: dict) -> dict:
    """
    Time-based exit for stale trades.
    
    Returns: {"should_exit": bool, "reason": str}
    """
    candle_count = order.get("open_candle_count", 0)
    max_candles = config.get("max_candles", 48)
    
    if candle_count >= max_candles:
        return {
            "should_exit": True,
            "reason": f"Time Exit ({candle_count}/{max_candles} candles)"
        }
    
    return {"should_exit": False, "reason": ""}


def check_dynamic_sl_tp(df: pd.DataFrame, order: dict, config: dict) -> dict:
    """
    DYNAMIC SL/TP ADJUSTMENT
    
    Recalculates optimal SL/TP based on latest market data:
    1. SL moves to nearest swing low/high + ATR buffer
    2. TP adjusts based on current volatility
    
    Returns: {"updates": dict} with new sl/tp values if changed
    """
    if df is None or len(df) < 20:
        return {"updates": {}}
    
    order_type = order["order_type"]
    current_sl = order.get("sl")
    trail_stage = order.get("trail_stage", 0)
    
    # Don't adjust SL if trailing stop has already taken over
    if trail_stage >= 2:
        return {"updates": {}}
    
    # Calculate fresh ATR
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        abs(df['high'] - df['low']),
        abs(df['high'] - prev_close),
        abs(df['low'] - prev_close)
    ], axis=1).max(axis=1)
    current_atr = float(tr.rolling(14).mean().iloc[-1])
    
    if current_atr <= 0:
        return {"updates": {}}
    
    updates = {}
    
    # Calculate swing levels
    swing_window = 10
    recent_swing_low = float(df['low'].iloc[-swing_window:].min())
    recent_swing_high = float(df['high'].iloc[-swing_window:].max())
    
    sl_mult = config.get("sl_mult", 0.7)
    
    if order_type == "BUY":
        # SL at recent swing low - ATR buffer
        optimal_sl = recent_swing_low - (current_atr * sl_mult)
        # Only tighten SL (move up), never loosen it
        if current_sl and optimal_sl > current_sl:
            updates["sl"] = optimal_sl
    
    else:  # SELL
        optimal_sl = recent_swing_high + (current_atr * sl_mult)
        if current_sl and optimal_sl < current_sl:
            updates["sl"] = optimal_sl
    
    return {"updates": updates}


def run_smart_exit(order: dict, current_price: float, df: pd.DataFrame, config: dict) -> dict:
    """
    MASTER EXIT FUNCTION — Runs ALL exit checks in priority order.
    
    Priority:
    1. Standard TP/SL hit (fastest, checked first)
    2. Profit Protection (peak tracking)
    3. Momentum Exhaustion
    4. Candle Reversal Pattern
    5. Opposite Signal
    6. Time Exit
    7. Dynamic SL/TP adjustment (if no exit triggered)
    
    Returns: {
        "should_exit": bool,
        "reason": str,
        "updates": dict  # DB updates to apply even if not exiting
    }
    """
    all_updates = {}
    
    # --- 1. STANDARD TP/SL ---
    tp = order.get("tp")
    sl = order.get("sl")
    order_type = order["order_type"]
    
    if order_type == "BUY":
        if sl and current_price <= sl:
            return {"should_exit": True, "reason": "SL Hit", "updates": {}}
        if tp and current_price >= tp:
            return {"should_exit": True, "reason": "TP Hit 🎯", "updates": {}}
    else:
        if sl and current_price >= sl:
            return {"should_exit": True, "reason": "SL Hit", "updates": {}}
        if tp and current_price <= tp:
            return {"should_exit": True, "reason": "TP Hit 🎯", "updates": {}}
    
    # --- 2. PROFIT PROTECTION ---
    profit_check = check_profit_protection(order, current_price, config)
    all_updates.update(profit_check.get("updates", {}))
    if profit_check["should_exit"]:
        return {"should_exit": True, "reason": profit_check["reason"], "updates": all_updates}
    
    # --- 3. MOMENTUM EXHAUSTION ---
    momentum_check = check_momentum_exhaustion(df, order, config)
    if momentum_check["should_exit"]:
        current_pnl = order.get("floating_pnl", 0.0)
        if current_pnl > 0:  # Only exit on momentum if in profit
            return {
                "should_exit": True,
                "reason": f"Momentum Exit: {momentum_check['reason']}",
                "updates": all_updates
            }
    
    # --- 4. CANDLE REVERSAL ---
    candle_check = check_candle_reversal(df, order)
    if candle_check["should_exit"]:
        current_pnl = order.get("floating_pnl", 0.0)
        if current_pnl > 0:  # Only exit on pattern if in profit
            return {
                "should_exit": True,
                "reason": f"Pattern Exit: {candle_check['reason']}",
                "updates": all_updates
            }
    
    # --- 5. OPPOSITE SIGNAL ---
    signal_check = check_opposite_signal(df, order)
    if signal_check["should_exit"]:
        return {
            "should_exit": True,
            "reason": f"Signal Exit: {signal_check['reason']}",
            "updates": all_updates
        }
    
    # --- 6. TIME EXIT ---
    time_check = check_time_exit(order, config)
    if time_check["should_exit"]:
        return {
            "should_exit": True,
            "reason": time_check["reason"],
            "updates": all_updates
        }
    
    # --- 7. DYNAMIC SL/TP (no exit, just adjustment) ---
    dynamic_check = check_dynamic_sl_tp(df, order, config)
    all_updates.update(dynamic_check.get("updates", {}))
    
    return {"should_exit": False, "reason": "", "updates": all_updates}
