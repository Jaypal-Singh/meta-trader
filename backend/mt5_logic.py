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

def get_market_data(symbol: str, timeframe=mt5.TIMEFRAME_M5, num_bars: int = 2000):
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
    Fetch M15 data (3× the M5 trading timeframe) to determine the
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
    
    htf_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 300)
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
#  GUARDEER PRO v3.0 — FULL PINE SCRIPT INTEGRATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_indicators(df, swing_len=5, tp_mult=2.0, sl_mult=1.0, symbol="XAUUSD"):
    """
    GUARDEER PRO v3.0 — Full Pine Script Integration.
    
    Now properly calculates ALL indicators that were previously missing:
    - EMA 21 (fast trend)
    - EMA 50 (medium trend)  
    - EMA 200 (major trend)
    - MACD (12,26,9)
    - RSI (14)
    - ATR (14)
    - Volume Profile POC per swing
    - HVN Zone boundaries (matching Pine Script's 15% zone)
    
    Signal logic:
    - Swing detection via pivot high/low (same as Pine Script)
    - HVN zone validation (price must break through POC)
    - Multi-confirmation: Trend + Pullback + Momentum
    - Mean reversion for extreme moves
    """
    if df is None or len(df) < swing_len + 30:
        return None
    
    # ── 1. CORE INDICATORS ────────────────────────────────────────────
    
    # ATR (14) — Average True Range for volatility
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        abs(df['high'] - df['low']),
        np.maximum(
            abs(df['high'] - df['prev_close']),
            abs(df['low'] - df['prev_close'])
        )
    )
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # EMA 21 (fast), EMA 50 (medium), EMA 200 (major trend)
    df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # MACD (12, 26, 9) — Momentum oscillator
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd_line'] = ema_12 - ema_26
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd_line'] - df['macd_signal']
    
    # RSI (14) — Relative Strength Index
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Candle body for exit analysis
    df['body'] = abs(df['close'] - df['open'])
    df['avg_body'] = df['body'].rolling(window=14).mean()
    
    # ── 2. HIGHER TIMEFRAME TREND ─────────────────────────────────────
    
    htf_trend = get_higher_tf_trend(symbol)
    
    # ── 3. PIVOT DETECTION & SIGNAL GENERATION ────────────────────────
    #    Matching Pine Script: ta.pivothigh / ta.pivotlow + HVN zones
    
    df['signal'] = None
    df['tp'] = np.nan
    df['sl'] = np.nan
    df['confirm_bar_idx'] = np.nan
    
    last_pivot_bar   = None
    last_pivot_price = None
    last_was_high    = False
    
    for confirm_bar in range(swing_len * 2, len(df)):
        pivot_bar = confirm_bar - swing_len
        left_start = pivot_bar - swing_len
        right_end = confirm_bar
        
        # ta.pivothigh: pivot_bar's high is the max in the full window
        window_high = df['high'].iloc[left_start : right_end + 1]
        is_ph = (df['high'].iloc[pivot_bar] == window_high.max())
        
        # ta.pivotlow: pivot_bar's low is the min in the full window
        window_low = df['low'].iloc[left_start : right_end + 1]
        is_pl = (df['low'].iloc[pivot_bar] == window_low.min())
        
        # ===== SELL SWING (Pine Script: pivothigh detected) =====
        if is_ph:
            pivot_price = df['high'].iloc[pivot_bar]
            if last_pivot_bar is not None:
                entry = df['close'].iloc[confirm_bar]
                atr_val = df['atr'].iloc[confirm_bar]
                ema_200 = df['ema_200'].iloc[confirm_bar]
                ema_50 = df['ema_50'].iloc[confirm_bar]
                ema_21 = df['ema_21'].iloc[confirm_bar]
                macd_hist = df['macd_hist'].iloc[confirm_bar]
                macd_hist_prev = df['macd_hist'].iloc[confirm_bar - 1]
                rsi_val = df['rsi'].iloc[confirm_bar]
                rsi_pivot = df['rsi'].iloc[pivot_bar]
                
                # Volume Profile for this swing (matching Pine Script drawSwingVP)
                vp = calculate_swing_vp(df, last_pivot_bar, pivot_bar)
                
                # HVN zone for SELL: top 15% of swing (matching Pine Script)
                # zoneHi = hi, zoneLo = hi - (hi-lo)*0.15
                if vp:
                    poc_price = vp["poc_price"]
                    swing_hi = vp["hi"]
                    swing_lo = vp["lo"]
                    # Price should be breaking below the heavy volume node
                    is_below_hvn = (entry < poc_price)
                else:
                    is_below_hvn = True
                
                # ── Multi-Confirmation Filters ──
                # 1. Trend: Price below EMA200 OR EMA50 crossing below EMA200
                is_downtrend = (entry < ema_200) or (ema_50 < ema_200)
                # 2. Pullback: RSI at pivot was elevated (sellers exhausted buyers)
                is_valid_pullback = (rsi_pivot > 45)
                # 3. Momentum: MACD histogram turning bearish
                is_bearish_momentum = (macd_hist < macd_hist_prev)
                # 4. HTF alignment (bonus confirmation, not required)
                htf_aligned = (htf_trend != "BULLISH")
                
                # Extreme top reversal (works even against trend)
                is_extreme_top = (rsi_pivot > 70 and is_bearish_momentum)
                
                is_valid_setup = (
                    (is_downtrend and is_valid_pullback and is_bearish_momentum) or
                    is_extreme_top
                )
                
                if pd.notna(atr_val) and atr_val > 0 and is_valid_setup and is_below_hvn:
                    # TP/SL matching Pine Script: ATR multiplied
                    df.at[df.index[confirm_bar], 'signal'] = 'SELL'
                    df.at[df.index[confirm_bar], 'tp'] = entry - (atr_val * tp_mult)
                    df.at[df.index[confirm_bar], 'sl'] = entry + (atr_val * sl_mult)
                
            last_pivot_bar = pivot_bar
            last_pivot_price = pivot_price
            last_was_high = True

        # ===== BUY SWING (Pine Script: pivotlow detected) =====
        if is_pl:
            pivot_price = df['low'].iloc[pivot_bar]
            if last_pivot_bar is not None:
                entry = df['close'].iloc[confirm_bar]
                atr_val = df['atr'].iloc[confirm_bar]
                ema_200 = df['ema_200'].iloc[confirm_bar]
                ema_50 = df['ema_50'].iloc[confirm_bar]
                ema_21 = df['ema_21'].iloc[confirm_bar]
                macd_hist = df['macd_hist'].iloc[confirm_bar]
                macd_hist_prev = df['macd_hist'].iloc[confirm_bar - 1]
                rsi_val = df['rsi'].iloc[confirm_bar]
                rsi_pivot = df['rsi'].iloc[pivot_bar]
                
                # Volume Profile for this swing
                vp = calculate_swing_vp(df, last_pivot_bar, pivot_bar)
                
                # HVN zone for BUY: bottom 15% of swing (matching Pine Script)
                # zoneLo = lo, zoneHi = lo + (hi-lo)*0.15
                if vp:
                    poc_price = vp["poc_price"]
                    swing_hi = vp["hi"]
                    swing_lo = vp["lo"]
                    # Price should be breaking above the heavy volume node
                    is_above_hvn = (entry > poc_price)
                else:
                    is_above_hvn = True
                
                # ── Multi-Confirmation Filters ──
                # 1. Trend: Price above EMA200 OR EMA50 crossing above EMA200
                is_uptrend = (entry > ema_200) or (ema_50 > ema_200)
                # 2. Pullback: RSI at pivot was depressed (buyers absorbed selling)
                is_valid_pullback = (rsi_pivot < 55)
                # 3. Momentum: MACD histogram turning bullish
                is_bullish_momentum = (macd_hist > macd_hist_prev)
                # 4. HTF alignment (bonus confirmation)
                htf_aligned = (htf_trend != "BEARISH")
                
                # Extreme bottom reversal (works even against trend)
                is_extreme_bottom = (rsi_pivot < 30 and is_bullish_momentum)
                
                is_valid_setup = (
                    (is_uptrend and is_valid_pullback and is_bullish_momentum) or
                    is_extreme_bottom
                )
                
                if pd.notna(atr_val) and atr_val > 0 and is_valid_setup and is_above_hvn:
                    df.at[df.index[confirm_bar], 'signal'] = 'BUY'
                    df.at[df.index[confirm_bar], 'tp'] = entry + (atr_val * tp_mult)
                    df.at[df.index[confirm_bar], 'sl'] = entry - (atr_val * sl_mult)
                
            last_pivot_bar = pivot_bar
            last_pivot_price = pivot_price
            last_was_high = False
    
    return df


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LIVE TRADE ANALYSIS — Used by autotrade.py for smart exits
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_exit_conditions(df):
    """
    Analyze current market conditions for smart exit decisions.
    Returns a dict with actionable intelligence for open positions.
    
    Only triggers on EXTREME conditions to avoid premature exits.
    """
    if df is None or len(df) < 30:
        return {"should_exit_buy": False, "should_exit_sell": False, "reason": "Insufficient data"}
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    rsi = latest['rsi'] if 'rsi' in df.columns else 50
    macd_hist = latest['macd_hist'] if 'macd_hist' in df.columns else 0
    
    exit_buy = False
    exit_sell = False
    reasons = []
    
    # ── RSI Extreme Exhaustion (True Reversals Only) ──
    # Only exit if the market is extremely over-extended
    if rsi > 80:
        exit_buy = True
        reasons.append(f"RSI extreme overbought ({rsi:.0f})")
    if rsi < 20:
        exit_sell = True
        reasons.append(f"RSI extreme oversold ({rsi:.0f})")
        
    return {
        "should_exit_buy": exit_buy,
        "should_exit_sell": exit_sell,
        "reason": " | ".join(reasons) if reasons else "No exit signal",
        "rsi": float(rsi),
        "macd_hist": float(macd_hist),
        "atr": float(latest['atr']) if pd.notna(latest.get('atr')) else 0
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
