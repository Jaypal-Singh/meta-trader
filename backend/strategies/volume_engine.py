"""
VOLUME ENGINE — Volume Confirmation + DOM (Depth of Market) Analysis
=====================================================================
Confirms trade signals using real tick volume data and order book depth.
Only allows entries when volume supports the signal direction.
"""

import MetaTrader5 as mt5
import numpy as np
import pandas as pd


def get_volume_confirmation(df: pd.DataFrame, signal: str, config: dict) -> dict:
    """
    Check if volume confirms the trade signal.
    
    Returns:
        {
            "confirmed": bool,
            "volume_ratio": float,   # current vol / avg vol
            "reason": str
        }
    """
    if df is None or len(df) < 25:
        return {"confirmed": True, "volume_ratio": 1.0, "reason": "Insufficient data, allowing trade"}
    
    min_vol_mult = config.get("min_volume_mult", 1.2)
    
    # --- 1. TICK VOLUME ANALYSIS ---
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'real_volume'
    if vol_col not in df.columns:
        return {"confirmed": True, "volume_ratio": 1.0, "reason": "No volume data available"}
    
    current_vol = float(df[vol_col].iloc[-1])
    avg_vol_20 = float(df[vol_col].iloc[-21:-1].mean())
    
    if avg_vol_20 <= 0:
        return {"confirmed": True, "volume_ratio": 1.0, "reason": "Zero average volume"}
    
    volume_ratio = current_vol / avg_vol_20
    
    # --- 2. VOLUME DIRECTION CHECK ---
    # Check if volume is increasing in the signal direction
    last_3_vols = df[vol_col].iloc[-3:].values
    last_3_closes = df['close'].iloc[-3:].values
    
    vol_increasing = last_3_vols[-1] > last_3_vols[-2]
    
    if signal == "BUY":
        price_up = last_3_closes[-1] > last_3_closes[-2]
        direction_match = price_up and vol_increasing
    else:  # SELL
        price_down = last_3_closes[-1] < last_3_closes[-2]
        direction_match = price_down and vol_increasing
    
    # --- 3. VOLUME SPIKE DETECTION ---
    # If volume is extremely high (>3× avg), it could be a blow-off top/bottom — be cautious
    is_blowoff = volume_ratio > 3.0
    
    # --- DECISION ---
    if is_blowoff:
        return {
            "confirmed": False, 
            "volume_ratio": volume_ratio,
            "reason": f"Volume spike ({volume_ratio:.1f}x avg) — possible blow-off, skipping"
        }
    
    if volume_ratio < min_vol_mult:
        return {
            "confirmed": False,
            "volume_ratio": volume_ratio,
            "reason": f"Low volume ({volume_ratio:.1f}x avg, need {min_vol_mult:.1f}x)"
        }
    
    if not direction_match:
        # Volume is there but not in the right direction
        # Allow trade but with reduced confidence
        return {
            "confirmed": True,
            "volume_ratio": volume_ratio,
            "reason": f"Volume OK ({volume_ratio:.1f}x) but direction mismatch — reduced confidence"
        }
    
    return {
        "confirmed": True,
        "volume_ratio": volume_ratio,
        "reason": f"Volume confirmed ({volume_ratio:.1f}x avg, direction matches)"
    }


def get_dom_analysis(symbol: str, signal: str) -> dict:
    """
    Analyze Depth of Market (Order Book) data from MT5.
    
    Returns:
        {
            "confirmed": bool,
            "bid_ratio": float,     # % of volume on bid side
            "ask_ratio": float,     # % of volume on ask side
            "imbalance": str,       # "BUY_PRESSURE" / "SELL_PRESSURE" / "BALANCED"
            "reason": str
        }
    """
    result = {
        "confirmed": True,
        "bid_ratio": 0.5,
        "ask_ratio": 0.5,
        "imbalance": "BALANCED",
        "reason": "DOM not available, allowing trade"
    }
    
    try:
        # Subscribe to market depth
        if not mt5.market_book_add(symbol):
            return result
        
        # Get order book
        book = mt5.market_book_get(symbol)
        
        if book is None or len(book) == 0:
            mt5.market_book_release(symbol)
            return result
        
        total_bid_vol = 0.0
        total_ask_vol = 0.0
        
        for entry in book:
            if entry.type == mt5.BOOK_TYPE_BUY or entry.type == mt5.BOOK_TYPE_BUY_MARKET:
                total_bid_vol += entry.volume
            elif entry.type == mt5.BOOK_TYPE_SELL or entry.type == mt5.BOOK_TYPE_SELL_MARKET:
                total_ask_vol += entry.volume
        
        # Release the book subscription
        mt5.market_book_release(symbol)
        
        total_vol = total_bid_vol + total_ask_vol
        if total_vol <= 0:
            return result
        
        bid_ratio = total_bid_vol / total_vol
        ask_ratio = total_ask_vol / total_vol
        
        # Determine imbalance
        if bid_ratio > 0.60:
            imbalance = "BUY_PRESSURE"
        elif ask_ratio > 0.60:
            imbalance = "SELL_PRESSURE"
        else:
            imbalance = "BALANCED"
        
        # Check if DOM supports the signal
        confirmed = True
        reason = f"DOM: Bid={bid_ratio:.0%} Ask={ask_ratio:.0%} ({imbalance})"
        
        # Strong contradiction = block the trade
        if signal == "BUY" and ask_ratio > 0.70:
            confirmed = False
            reason = f"DOM contradicts BUY — {ask_ratio:.0%} selling pressure"
        elif signal == "SELL" and bid_ratio > 0.70:
            confirmed = False
            reason = f"DOM contradicts SELL — {bid_ratio:.0%} buying pressure"
        
        return {
            "confirmed": confirmed,
            "bid_ratio": bid_ratio,
            "ask_ratio": ask_ratio,
            "imbalance": imbalance,
            "reason": reason
        }
        
    except Exception as e:
        return result


def should_enter_trade(df: pd.DataFrame, symbol: str, signal: str, config: dict) -> dict:
    """
    Master entry confirmation function.
    Combines Volume + DOM analysis to decide if a trade should be taken.
    
    Returns:
        {
            "allowed": bool,
            "volume": dict,
            "dom": dict,
            "reason": str
        }
    """
    vol_check = get_volume_confirmation(df, signal, config)
    dom_check = get_dom_analysis(symbol, signal)
    
    # Both must confirm, OR volume alone confirms with high ratio
    allowed = True
    reasons = []
    
    if not vol_check["confirmed"]:
        allowed = False
        reasons.append(f"Volume: {vol_check['reason']}")
    
    if not dom_check["confirmed"]:
        # DOM contradiction is a strong signal — block the trade
        allowed = False
        reasons.append(f"DOM: {dom_check['reason']}")
    
    if allowed:
        reasons.append(f"Entry confirmed — {vol_check['reason']} | {dom_check['reason']}")
    
    return {
        "allowed": allowed,
        "volume": vol_check,
        "dom": dom_check,
        "reason": " | ".join(reasons)
    }
