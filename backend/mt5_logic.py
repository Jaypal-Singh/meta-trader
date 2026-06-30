import MetaTrader5 as mt5
import pandas as pd
import numpy as np

def init_mt5(account: int, password: str, server: str):
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        return False
        
    authorized = mt5.login(account, password=password, server=server)
    if not authorized:
        print("failed to connect at account #{}, error code: {}".format(account, mt5.last_error()))
        return False
        
    print("Connected to MT5 successfully!")
    return True

def get_market_data(symbol: str, timeframe=mt5.TIMEFRAME_H1, num_bars: int = 2000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['raw_time'] = df['time']
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HIGHER TIMEFRAME TREND FILTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Cache to avoid repeated MT5 calls within the same scan cycle
_htf_cache = {"symbol": None, "time": None, "trend": None}

def get_higher_tf_trend(symbol: str):
    """
    Fetch H4 data (4× the H1 trading timeframe) to determine the
    dominant trend direction. Returns 'BULLISH', 'BEARISH', or 'NEUTRAL'.
    
    Uses EMA 50 vs EMA 200 crossover on the higher timeframe.
    """
    import time as _time
    
    # Cache for 60 seconds to avoid hammering MT5
    now = _time.time()
    if (_htf_cache["symbol"] == symbol and 
        _htf_cache["time"] is not None and 
        now - _htf_cache["time"] < 60):
        return _htf_cache["trend"]
    
    htf_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 300)
    if htf_rates is None or len(htf_rates) < 210:
        _htf_cache.update({"symbol": symbol, "time": now, "trend": "NEUTRAL"})
        return "NEUTRAL"
    
    htf_df = pd.DataFrame(htf_rates)
    ema_50 = htf_df['close'].ewm(span=50, adjust=False).mean()
    ema_200 = htf_df['close'].ewm(span=200, adjust=False).mean()
    
    latest_ema50 = ema_50.iloc[-1]
    latest_ema200 = ema_200.iloc[-1]
    
    # Also check slope of EMA 50 (last 5 bars) for trend strength
    ema50_slope = ema_50.iloc[-1] - ema_50.iloc[-5]
    
    if latest_ema50 > latest_ema200 and ema50_slope > 0:
        trend = "BULLISH"
    elif latest_ema50 < latest_ema200 and ema50_slope < 0:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"
    
    _htf_cache.update({"symbol": symbol, "time": now, "trend": trend})
    return trend


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VOLUME PROFILE (HVN) ENGINE  — Vectorized for speed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_swing_vp(df, start_idx, end_idx, vp_rows=12):
    """
    Calculate Volume Profile for a swing range (matching Pine Script drawSwingVP).
    Returns dict with:
      - poc_price: Point of Control (highest volume level)
      - poc_row: Row index of POC
      - hi / lo: Swing high/low
      - volumes: List of total volumes per row
    Returns None if invalid range.
    """
    if end_idx <= start_idx or start_idx < 0 or end_idx >= len(df):
        return None
        
    subset = df.iloc[start_idx:end_idx + 1]
    hi = float(subset['high'].max())
    lo = float(subset['low'].min())
    
    if hi <= lo:
        return None
        
    row_h = (hi - lo) / vp_rows
    
    # Vectorized volume profile calculation
    bar_highs = subset['high'].values
    bar_lows = subset['low'].values
    # Use tick_volume if available, else fallback to 1.0
    if 'tick_volume' in subset.columns:
        bar_vols = subset['tick_volume'].values.astype(float)
    else:
        bar_vols = np.ones(len(subset))
    bar_closes = subset['close'].values
    bar_opens = subset['open'].values
    
    up_volumes = np.zeros(vp_rows)
    dn_volumes = np.zeros(vp_rows)
    
    for r in range(vp_rows):
        rLo = lo + r * row_h
        rHi = rLo + row_h
        # Which bars overlap this row?
        overlap = (bar_highs >= rLo) & (bar_lows <= rHi)
        is_up = bar_closes >= bar_opens
        
        up_volumes[r] = np.sum(bar_vols[overlap & is_up]) / vp_rows
        dn_volumes[r] = np.sum(bar_vols[overlap & ~is_up]) / vp_rows
    
    total_volumes = up_volumes + dn_volumes
    poc_row = int(np.argmax(total_volumes))
    poc_price = lo + (poc_row + 0.5) * row_h
    
    return {
        "poc_price": poc_price,
        "poc_row": poc_row,
        "hi": hi,
        "lo": lo,
        "row_h": row_h,
        "volumes": total_volumes.tolist(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GUARDEER PRO v2.0 — EXACT PINE SCRIPT TRANSLATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_indicators(df, swing_len=5, tp_mult=2.0, sl_mult=1.0, symbol="XAUUSD"):
    """
    GUARDEER PRO v2.0 — Exact Pine Script Translation.
    
    Signal Logic (100% matching Pine Script):
    ─────────────────────────────────────────
    Pine Script Section 4:
      ph = ta.pivothigh(high, swingLen, swingLen)
      pl = ta.pivotlow(low, swingLen, swingLen)
    
      SELL = pivothigh detected + lastWasHigh == false (last pivot was LOW)
             → Swing from Low to High is complete → Sell at the top
             → Arrow drawn at pivotBar, entry = close (current bar)
    
      BUY  = pivotlow detected + lastWasHigh == true (last pivot was HIGH)
             → Swing from High to Low is complete → Buy at the bottom
             → Arrow drawn at pivotBar, entry = close (current bar)
    
      TP/SL = entry ± ATR(14) * multiplier
    
    NO additional filters. Pine Script uses ONLY pivots + alternation.
    EMA/RSI/MACD are calculated for dashboard display only.
    """
    if df is None or len(df) < swing_len + 30:
        return None
    
    # ── 1. CORE INDICATORS (for dashboard & chart display ONLY) ────
    
    # ATR (14) — Used for TP/SL calculation (matches Pine: ta.atr(14))
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        abs(df['high'] - df['low']),
        np.maximum(
            abs(df['high'] - df['prev_close']),
            abs(df['low'] - df['prev_close'])
        )
    )
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # EMA 21, 50, 200 — For chart overlay display only
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # MACD (12, 26, 9) — For dashboard display only
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd_line'] = ema_12 - ema_26
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd_line'] - df['macd_signal']
    
    # RSI (14) — For dashboard display only
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Candle body — For exit analysis in autotrade
    df['body'] = abs(df['close'] - df['open'])
    df['avg_body'] = df['body'].rolling(window=14).mean()
    
    # ── 2. PIVOT DETECTION & SIGNAL GENERATION ─────────────────────
    #    EXACT translation of Pine Script Section 4.
    #
    #    Pine Script variables:
    #      var int   lastPivotBar   = na
    #      var float lastPivotPrice = na
    #      var bool  lastWasHigh    = false
    #
    #    SELL condition: not na(ph) and not na(lastPivotBar) and not lastWasHigh
    #    BUY  condition: not na(pl) and not na(lastPivotBar) and lastWasHigh
    
    df['signal'] = None
    df['tp'] = np.nan
    df['sl'] = np.nan
    
    last_pivot_bar   = None      # Pine: var int lastPivotBar = na
    last_pivot_price = None      # Pine: var float lastPivotPrice = na
    last_was_high    = False     # Pine: var bool lastWasHigh = false
    
    for confirm_bar in range(swing_len * 2, len(df)):
        pivot_bar = confirm_bar - swing_len
        left_start = pivot_bar - swing_len
        right_end = confirm_bar
        
        if left_start < 0:
            continue
        
        # ── ta.pivothigh(high, swingLen, swingLen) ──
        # pivot_bar's high must be strictly the maximum in the window
        window_high = df['high'].iloc[left_start : right_end + 1]
        is_ph = (df['high'].iloc[pivot_bar] == window_high.max())
        
        # ── ta.pivotlow(low, swingLen, swingLen) ──
        # pivot_bar's low must be strictly the minimum in the window
        window_low = df['low'].iloc[left_start : right_end + 1]
        is_pl = (df['low'].iloc[pivot_bar] == window_low.min())
        
        # ═══════════════════════════════════════════════════════════
        # SELL SWING — Pine Script:
        #   if not na(ph) and inHistory
        #     if not na(lastPivotBar) and not lastWasHigh
        #       → A Low-to-High swing is complete → SELL at the top
        #       entry = close
        #       tp = entry - atrV * tpATRmult
        #       sl = entry + atrV * slATRmult
        # ═══════════════════════════════════════════════════════════
        if is_ph:
            pivot_price = df['high'].iloc[pivot_bar]
            
            if last_pivot_bar is not None and not last_was_high:
                # Pine: hi = pivotPrice, lo = lastPivotPrice
                swing_hi = pivot_price
                swing_lo = last_pivot_price
                
                # Pine: entry = close (current bar, NOT pivot bar)
                entry = df['close'].iloc[confirm_bar]
                atr_val = df['atr'].iloc[confirm_bar]
                
                if pd.notna(atr_val) and atr_val > 0:
                    tp = entry - (atr_val * tp_mult)
                    sl = entry + (atr_val * sl_mult)
                    
                    # Signal placed at pivot_bar (where arrow appears in Pine Script)
                    df.at[df.index[pivot_bar], 'signal'] = 'SELL'
                    df.at[df.index[pivot_bar], 'tp'] = tp
                    df.at[df.index[pivot_bar], 'sl'] = sl
            
            # Pine: lastPivotBar := pivotBar, lastWasHigh := true
            last_pivot_bar = pivot_bar
            last_pivot_price = pivot_price
            last_was_high = True
        
        # ═══════════════════════════════════════════════════════════
        # BUY SWING — Pine Script:
        #   if not na(pl) and inHistory
        #     if not na(lastPivotBar) and lastWasHigh
        #       → A High-to-Low swing is complete → BUY at the bottom
        #       entry = close
        #       tp = entry + atrV * tpATRmult
        #       sl = entry - atrV * slATRmult
        # ═══════════════════════════════════════════════════════════
        if is_pl:
            pivot_price = df['low'].iloc[pivot_bar]
            
            if last_pivot_bar is not None and last_was_high:
                # Pine: hi = lastPivotPrice, lo = pivotPrice
                swing_hi = last_pivot_price
                swing_lo = pivot_price
                
                # Pine: entry = close (current bar, NOT pivot bar)
                entry = df['close'].iloc[confirm_bar]
                atr_val = df['atr'].iloc[confirm_bar]
                
                if pd.notna(atr_val) and atr_val > 0:
                    tp = entry + (atr_val * tp_mult)
                    sl = entry - (atr_val * sl_mult)
                    
                    # Signal placed at pivot_bar (where arrow appears in Pine Script)
                    df.at[df.index[pivot_bar], 'signal'] = 'BUY'
                    df.at[df.index[pivot_bar], 'tp'] = tp
                    df.at[df.index[pivot_bar], 'sl'] = sl
            
            # Pine: lastPivotBar := pivotBar, lastWasHigh := false
            last_pivot_bar = pivot_bar
            last_pivot_price = pivot_price
            last_was_high = False
    
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LIVE TRADE ANALYSIS — Used by autotrade.py for smart exits
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_exit_conditions(df):
    """
    GUARDEER PRO v2.0 — Smart Exit Analysis.
    
    Analyzes the FULL chart to detect when a trade should be closed early.
    Returns actionable signals based on:
    
    1. EMA Crossover Reversal (EMA 21 crosses wrong side of EMA 50)
    2. Price Breaking Key EMA (close below EMA 50 for BUY, above for SELL)
    3. MACD Histogram Reversal (3 consecutive bars flipping direction)
    4. RSI Exhaustion Zones (extreme overbought/oversold)
    5. Momentum Exhaustion (price stalling near recent highs/lows)
    """
    if df is None or len(df) < 30:
        return {
            "should_exit_buy": False, "should_exit_sell": False,
            "reason": "Insufficient data",
            "extend_tp_buy": False, "extend_tp_sell": False,
        }
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3] if len(df) > 2 else prev
    
    close = latest['close']
    rsi = latest['rsi'] if 'rsi' in df.columns else 50
    macd_hist = latest['macd_hist'] if 'macd_hist' in df.columns else 0
    macd_hist_p1 = prev['macd_hist'] if 'macd_hist' in df.columns else 0
    macd_hist_p2 = prev2['macd_hist'] if 'macd_hist' in df.columns else 0
    ema_21 = latest['ema_21'] if 'ema_21' in df.columns else close
    ema_50 = latest['ema_50'] if 'ema_50' in df.columns else close
    ema_200 = latest['ema_200'] if 'ema_200' in df.columns else close
    
    exit_buy = False
    exit_sell = False
    extend_tp_buy = False
    extend_tp_sell = False
    reasons = []
    
    # ── 1. EMA CROSSOVER REVERSAL ──
    # If EMA 21 crosses below EMA 50 → bearish reversal → exit BUY
    prev_ema21 = prev['ema_21'] if 'ema_21' in df.columns else close
    prev_ema50 = prev['ema_50'] if 'ema_50' in df.columns else close
    
    if prev_ema21 >= prev_ema50 and ema_21 < ema_50:
        exit_buy = True
        reasons.append("EMA 21 crossed below EMA 50 (Bearish)")
    
    if prev_ema21 <= prev_ema50 and ema_21 > ema_50:
        exit_sell = True
        reasons.append("EMA 21 crossed above EMA 50 (Bullish)")
    
    # ── 2. PRICE BREAKING KEY EMA ──
    # Close below EMA 50 for BUY = trend weakening
    if close < ema_50 and prev['close'] >= prev_ema50:
        exit_buy = True
        reasons.append(f"Price broke below EMA 50 ({ema_50:.2f})")
    
    if close > ema_50 and prev['close'] <= prev_ema50:
        exit_sell = True
        reasons.append(f"Price broke above EMA 50 ({ema_50:.2f})")
    
    # ── 3. MACD HISTOGRAM REVERSAL (3 consecutive bars) ──
    # If MACD histogram flips from positive to negative for 3 bars
    if macd_hist < 0 and macd_hist_p1 < 0 and macd_hist_p2 > 0:
        exit_buy = True
        reasons.append("MACD Histogram bearish for 2+ bars")
    
    if macd_hist > 0 and macd_hist_p1 > 0 and macd_hist_p2 < 0:
        exit_sell = True
        reasons.append("MACD Histogram bullish for 2+ bars")
    
    # ── 4. RSI EXTREME EXHAUSTION ──
    if rsi > 78:
        exit_buy = True
        reasons.append(f"RSI extreme overbought ({rsi:.0f})")
    if rsi < 22:
        exit_sell = True
        reasons.append(f"RSI extreme oversold ({rsi:.0f})")
    
    # ── 5. DYNAMIC TP EXTENSION (Strong Momentum) ──
    # If RSI is strong (60-75 for buy) and MACD is growing, EXTEND the TP
    if 55 < rsi < 75 and macd_hist > macd_hist_p1 > 0:
        extend_tp_buy = True
    if 25 < rsi < 45 and macd_hist < macd_hist_p1 < 0:
        extend_tp_sell = True
        
    return {
        "should_exit_buy": exit_buy,
        "should_exit_sell": exit_sell,
        "reason": " | ".join(reasons) if reasons else "No exit signal",
        "rsi": float(rsi),
        "macd_hist": float(macd_hist),
        "atr": float(latest['atr']) if pd.notna(latest.get('atr')) else 0,
        "extend_tp_buy": extend_tp_buy,
        "extend_tp_sell": extend_tp_sell,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BACKTEST ACCURACY CALCULATOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_accuracy(df):
    """
    Backtest signals to determine win rate.
    Matches Pine Script's win/loss tracking logic:
    - BUY wins if high >= TP before low <= SL
    - SELL wins if low <= TP before high >= SL
    """
    if df is None or 'signal' not in df.columns:
        return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0}
        
    wins = 0
    losses = 0
    
    # We only test signals that have actual future data
    signals = df.dropna(subset=['signal']).copy()
    
    for idx, row in signals.iterrows():
        signal = row['signal']
        tp = row['tp']
        sl = row['sl']
        
        if pd.isna(tp) or pd.isna(sl):
            continue
        
        # Look ahead starting from the next bar
        future_df = df.loc[idx+1:]
        
        for _, future_row in future_df.iterrows():
            high = future_row['high']
            low = future_row['low']
            
            if signal == 'BUY':
                if low <= sl:
                    losses += 1
                    break
                elif high >= tp:
                    wins += 1
                    break
            elif signal == 'SELL':
                if high >= sl:
                    losses += 1
                    break
                elif low <= tp:
                    wins += 1
                    break
                    
    total = wins + losses
    win_rate = round((wins / total * 100), 2) if total > 0 else 0.0
    
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate
    }
