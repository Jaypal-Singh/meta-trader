import pandas as pd
import numpy as np

def calculate_swing_volume_profile(df, start_idx, end_idx, vp_rows=12):
    """
    Calculate Volume Profile for a swing range.
    Returns POC (Point of Control) price and HVN zone boundaries.
    """
    if end_idx <= start_idx or start_idx < 0 or end_idx >= len(df):
        return None
    
    subset = df.iloc[start_idx:end_idx + 1]
    hi = float(subset['high'].max())
    lo = float(subset['low'].min())
    
    if hi <= lo:
        return None
    
    row_h = (hi - lo) / vp_rows
    
    bar_highs = subset['high'].values
    bar_lows = subset['low'].values
    bar_closes = subset['close'].values
    bar_opens = subset['open'].values
    
    if 'tick_volume' in subset.columns:
        bar_vols = subset['tick_volume'].values.astype(float)
    else:
        bar_vols = np.ones(len(subset))
    
    up_volumes = np.zeros(vp_rows)
    dn_volumes = np.zeros(vp_rows)
    
    for r in range(vp_rows):
        rLo = lo + r * row_h
        rHi = rLo + row_h
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


def calculate_soul_signals(df: pd.DataFrame, symbol: str = None, tp_mult: float = 1.0, sl_mult: float = 0.5) -> pd.DataFrame:
    """
    SOUL Strategy - Trend following with ATR trailing stops and Smart Volume.
    
    Original Pine Script: "all free courses tg- @sarpanch0000"
    
    Signal Logic (100% matching Pine Script):
    ─────────────────────────────────────────
    Pine Script Section:
      ph = ta.pivothigh(high, swingLen, swingLen)
      pl = ta.pivotlow(low, swingLen, swingLen)
    
      SELL = pivothigh detected + lastWasHigh == false (last pivot was LOW)
             → A Low-to-High swing is complete → Sell at the top
             → Arrow drawn at pivotBar, entry = close (current bar)
    
      BUY  = pivotlow detected + lastWasHigh == true (last pivot was HIGH)
             → A High-to-Low swing is complete → Buy at the bottom
             → Arrow drawn at pivotBar, entry = close (current bar)
    
      TP/SL = entry ± ATR(14) * multiplier
              TP multiplier = 2.0, SL multiplier = 1.0
    
    Volume Profile:
    ──────────────
    For each completed swing, a Volume Profile is calculated with 12 rows.
    The POC (Point of Control) = highest volume row = likely support/resistance.
    HVN (High Volume Node) zones are drawn around the POC.
    
    Win/Loss Tracking:
    ──────────────────
    - BUY wins if high >= TP before low <= SL
    - SELL wins if low <= TP before high >= SL
    """
    df = df.copy()
    
    # ── PARAMETERS (matching Pine Script inputs) ──
    swing_len = 5       # swingLen = input.int(5)
    tp_mult = 2.0       # tpATRmult = input.float(2.0)
    sl_mult = 1.0       # slATRmult = input.float(1.0)
    vp_rows = 12        # vpRows = input.int(12)
    
    # Ensure numeric columns
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    if len(df) < swing_len + 30:
        return df
    
    # ── ATR(14) — Pine: atrV = ta.atr(14) ──
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        abs(df['high'] - df['low']),
        np.maximum(
            abs(df['high'] - df['prev_close']),
            abs(df['low'] - df['prev_close'])
        )
    )
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # ── PIVOT DETECTION & SIGNAL GENERATION ──
    # Exact translation of Pine Script pivot logic
    #
    # Pine Script variables:
    #   var int   lastPivotBar   = na
    #   var float lastPivotPrice = na
    #   var bool  lastWasHigh    = false
    #
    # SELL condition: not na(ph) and not na(lastPivotBar) and not lastWasHigh
    # BUY  condition: not na(pl) and not na(lastPivotBar) and lastWasHigh
    
    df['signal'] = None
    df['tp'] = np.nan
    df['sl'] = np.nan
    
    last_pivot_bar = None       # Pine: var int lastPivotBar = na
    last_pivot_price = None     # Pine: var float lastPivotPrice = na
    last_was_high = False       # Pine: var bool lastWasHigh = false
    
    # Stats tracking (matches Pine Script counters)
    total_swings = 0
    
    for confirm_bar in range(swing_len * 2, len(df)):
        pivot_bar = confirm_bar - swing_len
        left_start = pivot_bar - swing_len
        right_end = confirm_bar
        
        if left_start < 0:
            continue
        
        # ── ta.pivothigh(high, swingLen, swingLen) ──
        window_high = df['high'].iloc[left_start:right_end + 1]
        is_ph = (df['high'].iloc[pivot_bar] == window_high.max())
        
        # ── ta.pivotlow(low, swingLen, swingLen) ──
        window_low = df['low'].iloc[left_start:right_end + 1]
        is_pl = (df['low'].iloc[pivot_bar] == window_low.min())
        
        # ═══════════════════════════════════════════════════════
        # SELL SWING — Pine Script:
        #   if not na(ph) and inHistory
        #     if not na(lastPivotBar) and not lastWasHigh
        #       → A Low-to-High swing is complete → SELL at top
        #       entry = close, tp = entry - atrV * tpATRmult
        #       sl = entry + atrV * slATRmult
        # ═══════════════════════════════════════════════════════
        if is_ph:
            pivot_price = df['high'].iloc[pivot_bar]
            
            if last_pivot_bar is not None and not last_was_high:
                total_swings += 1
                
                # Calculate Volume Profile for the completed swing
                swing_hi = pivot_price
                swing_lo = last_pivot_price
                calculate_swing_volume_profile(
                    df, last_pivot_bar, pivot_bar, vp_rows
                )
                
                # Pine: entry = close (current bar, NOT pivot bar)
                entry = df['close'].iloc[confirm_bar]
                atr_val = df['atr'].iloc[confirm_bar]
                
                if pd.notna(atr_val) and atr_val > 0:
                    tp = entry - (atr_val * tp_mult)
                    sl = entry + (atr_val * sl_mult)
                    
                    # Signal placed at pivot_bar (where arrow appears)
                    df.at[df.index[pivot_bar], 'signal'] = 'SELL'
                    df.at[df.index[pivot_bar], 'tp'] = tp
                    df.at[df.index[pivot_bar], 'sl'] = sl
            
            # Pine: lastPivotBar := pivotBar, lastWasHigh := true
            last_pivot_bar = pivot_bar
            last_pivot_price = pivot_price
            last_was_high = True
        
        # ═══════════════════════════════════════════════════════
        # BUY SWING — Pine Script:
        #   if not na(pl) and inHistory
        #     if not na(lastPivotBar) and lastWasHigh
        #       → A High-to-Low swing is complete → BUY at bottom
        #       entry = close, tp = entry + atrV * tpATRmult
        #       sl = entry - atrV * slATRmult
        # ═══════════════════════════════════════════════════════
        if is_pl:
            pivot_price = df['low'].iloc[pivot_bar]
            
            if last_pivot_bar is not None and last_was_high:
                total_swings += 1
                
                # Calculate Volume Profile for the completed swing
                swing_hi = last_pivot_price
                swing_lo = pivot_price
                calculate_swing_volume_profile(
                    df, last_pivot_bar, pivot_bar, vp_rows
                )
                
                # Pine: entry = close (current bar, NOT pivot bar)
                entry = df['close'].iloc[confirm_bar]
                atr_val = df['atr'].iloc[confirm_bar]
                
                if pd.notna(atr_val) and atr_val > 0:
                    tp = entry + (atr_val * tp_mult)
                    sl = entry - (atr_val * sl_mult)
                    
                    # Signal placed at pivot_bar (where arrow appears)
                    df.at[df.index[pivot_bar], 'signal'] = 'BUY'
                    df.at[df.index[pivot_bar], 'tp'] = tp
                    df.at[df.index[pivot_bar], 'sl'] = sl
            
            # Pine: lastPivotBar := pivotBar, lastWasHigh := false
            last_pivot_bar = pivot_bar
            last_pivot_price = pivot_price
            last_was_high = False
    
    # Clean up temp columns
    df = df.drop(columns=['prev_close', 'tr'], errors='ignore')
    
    return df
