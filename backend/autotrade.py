import asyncio
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import random
import pandas as pd
import os
import csv

from database import db
from mt5_logic import calculate_indicators, analyze_exit_conditions, get_market_data, get_higher_tf_trend
from strategies.soul import calculate_soul_signals
from strategies.pulse import calculate_pulse_signals
from strategies.apex import calculate_apex_signals
from routes_orders import calc_pnl, execute_mt5_order, close_mt5_order

# Track the last timestamp traded per symbol to avoid opening duplicate trades
# Structure: {"username_symbol": unix_timestamp}
last_traded_signals = {}

# Track consecutive losses per user for cooldown
# Structure: {"username": {"count": int, "last_loss_time": datetime}}
consecutive_losses = {}

# Track daily PnL per user
# Structure: {"username": {"date": "YYYY-MM-DD", "pnl": float}}
daily_pnl_tracker = {}

# Active symbols to monitor for signals
MONITOR_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
DEFAULT_LOT_SIZE = 0.05

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RISK MANAGEMENT CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MAX_OPEN_TRADES_PER_SYMBOL = 1    # Max 1 trade per symbol at a time
DAILY_LOSS_LIMIT_PCT = 3.0         # Stop trading if daily loss > 3% of balance
CONSECUTIVE_LOSS_COOLDOWN = 3      # After 3 consecutive losses...
COOLDOWN_MINUTES = 15              # ...wait 15 minutes before next trade
MAX_TRADE_AGE_CANDLES = 60         # Close stale trades after 60 candles (60 hours on H1)
FLAT_TRADE_CANDLES = 20            # Close if in profit but flat for 20 candles
MAX_SPREAD_MULTIPLIER = 2.0       # Don't trade if spread > 2× average

# Trailing stop stages (in ATR multiples)
TRAIL_STAGE_1_TRIGGER = 0.5   # Price reaches 0.5× ATR profit → SL to breakeven
TRAIL_STAGE_2_TRIGGER = 1.0   # Price reaches 1.0× ATR profit → SL to +0.5× ATR
TRAIL_STAGE_3_TRIGGER = 1.5   # Price reaches 1.5× ATR profit → SL to +1.0× ATR
TRAIL_CONTINUOUS_OFFSET = 0.5  # After stage 3: always trail at 0.5× ATR behind

CSV_FILE_PATH = "trade_analysis.csv"

def log_trade_to_csv(action: str, order: dict, reason: str = ""):
    """Log trade to CSV for analysis."""
    file_exists = os.path.isfile(CSV_FILE_PATH)
    with open(CSV_FILE_PATH, mode='a', newline='') as f:
        fieldnames = [
            "timestamp", "action", "username", "ticket", "symbol", "order_type", 
            "strategy", "timeframe", "open_price", "close_price", "sl", "tp", 
            "pnl", "net_pnl", "result", "roi_percent", "duration_candles", "reason"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
            
        net_pnl = order.get("pnl", 0.0) + order.get("commission", 0.0) + order.get("swap", 0.0) if action == "CLOSE" else 0.0
        
        result = ""
        roi_percent = 0.0
        if action == "CLOSE":
            result = "PROFIT" if net_pnl > 0 else ("LOSS" if net_pnl < 0 else "BREAKEVEN")
            # Calculate simple price percentage movement (assuming 1:100 leverage equivalence or just raw PNL vs approx margin)
            # Assuming 0.1 lot = 10,000 units. Margin = 100.
            # Let's just use a fixed 100k balance for ROI % or relative to position size.
            roi_percent = round((net_pnl / 1000.0) * 100, 2) # Example: relative to $1000 margin
            
        writer.writerow({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "username": order.get("username"),
            "ticket": order.get("ticket"),
            "symbol": order.get("symbol"),
            "order_type": order.get("order_type"),
            "strategy": order.get("strategy", "unknown"),
            "timeframe": order.get("timeframe", "unknown"),
            "open_price": order.get("open_price"),
            "close_price": order.get("close_price", ""),
            "sl": order.get("sl", ""),
            "tp": order.get("tp", ""),
            "pnl": order.get("pnl", 0.0),
            "net_pnl": net_pnl,
            "result": result,
            "roi_percent": roi_percent,
            "duration_candles": order.get("open_candle_count", 0),
            "reason": reason
        })



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RISK CHECKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def check_max_trades_per_symbol(username: str, symbol: str) -> bool:
    """Returns True if we can open a new trade (under limit)."""
    count = await db.orders.count_documents({
        "username": username,
        "symbol": symbol,
        "status": "open"
    })
    return count < MAX_OPEN_TRADES_PER_SYMBOL


async def check_daily_loss_limit(username: str) -> bool:
    """Returns True if we're within daily loss limit and can trade."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    tracker = daily_pnl_tracker.get(username, {})
    if tracker.get("date") != today:
        # Reset for new day
        daily_pnl_tracker[username] = {"date": today, "pnl": 0.0}
        return True
    
    funds = await db.funds.find_one({"username": username})
    if not funds:
        return True
    
    balance = funds.get("balance", 100000)
    daily_loss = tracker.get("pnl", 0.0)
    max_loss = balance * (DAILY_LOSS_LIMIT_PCT / 100)
    
    if daily_loss < -max_loss:
        print(f"[AutoTrade] ⛔ Daily loss limit hit for {username}: ${daily_loss:.2f} / -${max_loss:.2f}")
        return False
    
    return True


def check_consecutive_loss_cooldown(username: str) -> bool:
    """Returns True. Cooldown logic disabled."""
    return True


def check_spread(symbol: str) -> bool:
    """Returns True if spread is acceptable (not during news/high volatility)."""
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    
    if not tick or not info:
        return False
    
    spread = tick.ask - tick.bid
    
    # Get typical spread from symbol info (in points)
    point = info.point if info.point > 0 else 0.01
    spread_points = spread / point
    typical_spread = info.spread  # MT5's reported typical spread
    
    if typical_spread > 0 and spread_points > typical_spread * MAX_SPREAD_MULTIPLIER:
        print(f"[AutoTrade] ⚠️ High spread on {symbol}: {spread_points:.0f} pts (typical: {typical_spread} pts) — SKIPPING")
        return False
    
    return True


def record_trade_result(username: str, pnl: float):
    """Track wins/losses for consecutive loss cooldown and daily PnL."""
    # Daily PnL tracking
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if username not in daily_pnl_tracker:
        daily_pnl_tracker[username] = {"date": today, "pnl": 0.0}
    if daily_pnl_tracker[username].get("date") != today:
        daily_pnl_tracker[username] = {"date": today, "pnl": 0.0}
    daily_pnl_tracker[username]["pnl"] += pnl
    
    # Consecutive loss tracking
    if username not in consecutive_losses:
        consecutive_losses[username] = {"count": 0, "last_loss_time": None}
    
    if pnl < 0:
        consecutive_losses[username]["count"] += 1
        consecutive_losses[username]["last_loss_time"] = datetime.now(timezone.utc)
    else:
        consecutive_losses[username]["count"] = 0  # Reset on win


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TRADE EXECUTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def execute_trade(username: str, symbol: str, order_type: str, candle: pd.Series, strategy: str, timeframe: str):
    """Executes a trade and saves it to the database."""
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return
        
    open_price = tick.ask if order_type == "BUY" else tick.bid
    
    # Simple margin logic
    funds = await db.funds.find_one({"username": username})
    if not funds:
        await db.funds.insert_one({"username": username, "balance": 100000.0, "equity": 100000.0, "available_margin": 100000.0, "used_margin": 0.0, "floating_pnl": 0.0})
        funds = await db.funds.find_one({"username": username})

    # Store ATR value for trailing stop calculations
    atr_val = float(candle['atr']) if pd.notna(candle.get('atr')) else None
    
    sl_val = float(candle['sl']) if pd.notna(candle['sl']) else None
    tp_val = float(candle['tp']) if pd.notna(candle['tp']) else None

    # Execute trade in MT5
    mt5_result = execute_mt5_order(
        symbol=symbol,
        order_type=order_type,
        lot_size=DEFAULT_LOT_SIZE,
        price=open_price,
        sl=sl_val,
        tp=tp_val,
        comment="Auto BOT v2"
    )
    
    if mt5_result["success"]:
        ticket = mt5_result["ticket"]
        executed_price = mt5_result["price"]
    else:
        print(f"[AutoTrade] ⚠️ MT5 execution failed: {mt5_result['error']}, falling back to dummy trading")
        ticket = str(random.randint(10000000, 99999999))
        executed_price = open_price

    order = {
        "ticket": ticket,
        "username": username,
        "symbol": symbol,
        "order_type": order_type,
        "strategy": strategy,
        "timeframe": timeframe,
        "lot_size": DEFAULT_LOT_SIZE,
        "open_price": executed_price,
        "current_price": executed_price,
        "sl": sl_val,
        "tp": tp_val,
        "original_sl": sl_val,  # Keep original SL
        "atr_at_entry": atr_val,  # ATR at entry time for trailing calculations
        "pnl": 0.0,
        "floating_pnl": 0.0,
        "commission": -0.50, # Simple fixed dummy commission
        "swap": 0.0,
        "status": "open",
        "comment": "Auto BOT v2",
        "open_time": datetime.now(timezone.utc).isoformat(),
        "open_candle_count": 0,  # Track how many candles this trade has been open
        "trail_stage": 0,  # 0=initial, 1=breakeven, 2=+0.5ATR, 3=+1ATR, 4=continuous
        "close_time": None,
        "close_price": None,
    }
    
    await db.orders.insert_one(order)
    log_trade_to_csv("OPEN", order, reason="Signal Entry")
    print(f"[AutoTrade] ✅ Opened {order_type} on {symbol} ({strategy}/{timeframe}) at {open_price} for {username} (Ticket: {ticket}) | SL: {order['sl']} | TP: {order['tp']}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SIGNAL SCANNING WITH RISK CHECKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def scan_for_signals():
    """Scans enabled symbols per user for new GUARDEER PRO v2 signals with risk management."""
    users = await db.users.find().to_list(100)
    
    for user in users:
        username = user.get("username")
        watchlist_config = user.get("watchlist_config", {})
        
        # ── RISK CHECK 1: Daily loss limit ──
        if not await check_daily_loss_limit(username):
            continue
        
        # ── RISK CHECK 2: Consecutive loss cooldown (DISABLED) ──
        # if not check_consecutive_loss_cooldown(username):
        #     continue
            
        for symbol, configs in watchlist_config.items():
            if isinstance(configs, dict):
                configs = [configs]
                
            active_configs = [c for c in configs if c.get("autotrade", False)]
            if not active_configs:
                continue
                
            if symbol == "XAUEUR":
                continue
                
            # MUST select the symbol in MT5 Market Watch to get live ticks and rates
            mt5.symbol_select(symbol, True)
                
            # ── RISK CHECK 3: Max trades per symbol ──
            if not await check_max_trades_per_symbol(username, symbol):
                continue
            
            # ── RISK CHECK 4: Spread check ──
            if not check_spread(symbol):
                continue
            
            for sym_config in active_configs:
                active_strategy = sym_config.get("strategy", "spirit")
                timeframe_str = sym_config.get("timeframe", "H1")
                
                # ── RISK CHECK 5: Timeframe & Noise Filter ──
                if active_strategy in ["soul", "spirit"] and timeframe_str in ["M1", "M5"]:
                    # print(f"[AutoTrade] ⚠️ Skipping {symbol} {active_strategy} on {timeframe_str} (Too much noise)")
                    continue
                
                if active_strategy == "pulse" and timeframe_str in ["M1", "M5"]:
                    # print(f"[AutoTrade] ⚠️ Skipping {symbol} pulse on {timeframe_str} (Spread too high for scalping)")
                    continue
                
                tf_map = {
                    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
                    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
                    "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN": mt5.TIMEFRAME_MN1
                }
                tf = tf_map.get(timeframe_str, mt5.TIMEFRAME_H1)
                
                df = get_market_data(symbol, tf, 300)
                if df is None or len(df) == 0:
                    continue
                    
                if active_strategy == "soul":
                    df = calculate_soul_signals(df)
                elif active_strategy == "pulse":
                    if symbol == "GBPUSD" and timeframe_str == "M30":
                        from strategies.pulse_gbpusd_m30 import calculate_pulse_gbpusd_m30_signals
                        df = calculate_pulse_gbpusd_m30_signals(df)
                    else:
                        df = calculate_pulse_signals(df)
                elif active_strategy == "apex":
                    df = calculate_apex_signals(df)
                else:
                    df = calculate_indicators(df, symbol=symbol)
                    
                if df is None or len(df) == 0:
                    continue
                    
                latest = df.iloc[-1]
                
                # Get all rows with a signal
                signals_df = df.dropna(subset=['signal'])
                if signals_df.empty:
                    continue
                    
                last_signal_row = signals_df.iloc[-1]
                sig = last_signal_row['signal']
                signal_time = int(last_signal_row['raw_time'])
                
                # Check if the signal occurred within the last 5 candles
                # (Spirit and Soul strategies confirm signals retrospectively on prior candles)
                if df.index[-1] - last_signal_row.name <= 5:
                    if pd.notna(sig) and sig in ('BUY', 'SELL'):
                        # ── HTF TREND FILTER for Soul & Spirit ──
                        if active_strategy in ["soul", "spirit"]:
                            htf_trend = get_higher_tf_trend(symbol, tf, mt5)
                            if sig == 'BUY' and htf_trend == -1:
                                print(f"[AutoTrade] ⚠️ Skipping BUY on {symbol} {active_strategy} (HTF is DOWN)")
                                continue
                            if sig == 'SELL' and htf_trend == 1:
                                print(f"[AutoTrade] ⚠️ Skipping SELL on {symbol} {active_strategy} (HTF is UP)")
                                continue
                                
                        key = f"{username}_{symbol}_{active_strategy}_{timeframe_str}"
                        
                        # Check if we already traded this specific signal
                        if last_traded_signals.get(key) != signal_time:
                            last_traded_signals[key] = signal_time
                            
                            # Merge SL/TP from the signal bar with the latest market data
                            trade_candle = latest.copy()
                            trade_candle['sl'] = last_signal_row['sl']
                            trade_candle['tp'] = last_signal_row['tp']
                            
                            await execute_trade(username, symbol, sig, trade_candle, active_strategy, timeframe_str)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART POSITION MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def close_position(order: dict, current_price: float, reason: str):
    """Close a position and update all records."""
    open_price = order["open_price"]
    symbol = order["symbol"]
    ticket = order["ticket"]
    
    # Try closing in MT5
    try:
        mt5_ticket = int(ticket)
        close_result = close_mt5_order(
            symbol=symbol,
            ticket=mt5_ticket,
            order_type=order["order_type"],
            lot_size=order["lot_size"],
            close_price=current_price
        )
        if close_result["success"]:
            actual_close_price = close_result["price"]
        else:
            print(f"[AutoTrade] ⚠️ MT5 close failed: {close_result['error']}")
            actual_close_price = current_price
    except ValueError:
        # Ticket was generated as string for dummy order
        actual_close_price = current_price

    pnl = calc_pnl(order["order_type"], open_price, actual_close_price, order["lot_size"], symbol)
    net_pnl = pnl + order.get("commission", 0) + order.get("swap", 0)
    
    await db.orders.update_one(
        {"_id": order["_id"]},
        {"$set": {
            "status": "closed",
            "close_price": actual_close_price,
            "close_time": datetime.now(timezone.utc).isoformat(),
            "current_price": actual_close_price,
            "pnl": pnl,
            "floating_pnl": 0.0,
            "comment": f"{order.get('comment', '')} | {reason}"
        }}
    )
    
    await db.funds.update_one(
        {"username": order["username"]},
        {"$inc": {"balance": net_pnl}}
    )
    
    # Record result for risk management
    record_trade_result(order["username"], net_pnl)
    
    # Log to CSV
    updated_order = {**order, "close_price": actual_close_price, "pnl": pnl, "status": "closed"}
    updated_order["commission"] = order.get("commission", 0)
    updated_order["swap"] = order.get("swap", 0)
    log_trade_to_csv("CLOSE", updated_order, reason=reason)
    
    emoji = "💰" if net_pnl >= 0 else "🔻"
    print(f"[AutoTrade] {emoji} Closed {order['order_type']} on {symbol} (Ticket: {order['ticket']}) | Reason: {reason} | Net PNL: ${net_pnl:.2f}")


async def manage_open_positions():
    """
    GUARDEER PRO v2.0 — Smart Position Management.
    
    Checks all open orders with multiple exit strategies:
    1. Standard TP/SL hit
    2. Dynamic trailing stop (3 stages)
    3. Smart early exit (RSI/MACD reversal detection)
    4. Time-based exit (stale trade cleanup)
    5. Opposite signal exit
    """
    open_orders = await db.orders.find({"status": "open"}).to_list(1000)
    
    for order in open_orders:
        symbol = order["symbol"]
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            continue
            
        # Current price to close the order
        current_price = tick.bid if order["order_type"] == "BUY" else tick.ask
        tp = order.get("tp")
        sl = order.get("sl")
        open_price = order["open_price"]
        atr_at_entry = order.get("atr_at_entry", 0)
        trail_stage = order.get("trail_stage", 0)
        
        # ── INCREMENT CANDLE COUNT ──
        candle_count = order.get("open_candle_count", 0) + 1
        await db.orders.update_one(
            {"_id": order["_id"]},
            {"$set": {"open_candle_count": candle_count}}
        )
        
        # ════════════════════════════════════════════════════════════
        # EXIT CHECK 1: Standard TP/SL
        # ════════════════════════════════════════════════════════════
        
        close_it = False
        close_reason = "TP/SL Hit"
        
        if order["order_type"] == "BUY":
            if sl and current_price <= sl:
                close_it = True
                close_reason = "SL Hit"
            if tp and current_price >= tp:
                close_it = True
                close_reason = "TP Hit 🎯"
        else:
            if sl and current_price >= sl:
                close_it = True
                close_reason = "SL Hit"
            if tp and current_price <= tp:
                close_it = True
                close_reason = "TP Hit 🎯"
        
        if close_it:
            await close_position(order, current_price, close_reason)
            continue
        
        # ════════════════════════════════════════════════════════════
        # EXIT CHECK 2: Time-Based Exit (stale trades)
        # ════════════════════════════════════════════════════════════
        
        if candle_count >= MAX_TRADE_AGE_CANDLES:
            pnl = calc_pnl(order["order_type"], open_price, current_price, order["lot_size"], symbol)
            # Fix: Only time-exit if trade is losing or flat. If it's in a strong winning trend (stage 2+), let trailing stop handle it!
            if trail_stage < 2:
                await close_position(order, current_price, f"Time Exit ({candle_count} candles, PnL: ${pnl:.2f})")
                continue
        
        # If in profit but flat for too long
        if candle_count >= FLAT_TRADE_CANDLES:
            pnl = calc_pnl(order["order_type"], open_price, current_price, order["lot_size"], symbol)
            if pnl > 0:
                # Check if price hasn't moved much in recent candles
                df = get_market_data(symbol, mt5.TIMEFRAME_H1, FLAT_TRADE_CANDLES + 5)
                if df is not None and len(df) >= FLAT_TRADE_CANDLES:
                    recent_range = df['high'].iloc[-FLAT_TRADE_CANDLES:].max() - df['low'].iloc[-FLAT_TRADE_CANDLES:].min()
                    if atr_at_entry and recent_range < atr_at_entry * 0.5:
                        await close_position(order, current_price, f"Flat Exit (profit secured: ${pnl:.2f})")
                        continue
        
        # ════════════════════════════════════════════════════════════
        # EXIT CHECK 3: Smart Early Exit (Chart Analysis)
        # ════════════════════════════════════════════════════════════
        
        active_strategy = order.get("strategy", "spirit")
        timeframe_str = order.get("timeframe", "H1")
        
        tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1
        }
        tf = tf_map.get(timeframe_str, mt5.TIMEFRAME_H1)
        
        df = get_market_data(symbol, tf, 300)
        if df is not None and len(df) > 0:
            if active_strategy == "soul":
                df_ind = calculate_soul_signals(df)
            elif active_strategy == "pulse":
                if symbol == "GBPUSD" and timeframe_str == "M30":
                    from strategies.pulse_gbpusd_m30 import calculate_pulse_gbpusd_m30_signals
                    df_ind = calculate_pulse_gbpusd_m30_signals(df)
                else:
                    df_ind = calculate_pulse_signals(df)
            elif active_strategy == "apex":
                df_ind = calculate_apex_signals(df)
            else:
                df_ind = calculate_indicators(df, symbol=symbol)
                
            if df_ind is not None and len(df_ind) > 0:
                # ── 3A: Opposite signal detected ──
                latest = df_ind.iloc[-1]
                signals_df = df_ind.dropna(subset=['signal'])
                if not signals_df.empty:
                    last_signal_row = signals_df.iloc[-1]
                    if df_ind.index[-1] - last_signal_row.name <= 5:
                        sig = last_signal_row['signal']
                        if order["order_type"] == "BUY" and sig == "SELL":
                            await close_position(order, current_price, "Trend Reversal (SELL signal)")
                            continue
                        elif order["order_type"] == "SELL" and sig == "BUY":
                            await close_position(order, current_price, "Trend Reversal (BUY signal)")
                            continue
                            
                # ── 3B: RSI/MACD/EMA Pattern-based early exit (Guardeer & Pulse) ──
                exit_analysis = {}
                if active_strategy in ["spirit", "soul"]:
                    # Calculate basic indicators for exit analysis if not present
                    if "ema_21" not in df_ind.columns:
                        # Add basic indicators without modifying signals
                        df_ind['ema_21'] = df_ind['close'].ewm(span=21, adjust=False).mean()
                        df_ind['ema_50'] = df_ind['close'].ewm(span=50, adjust=False).mean()
                        ema_12 = df_ind['close'].ewm(span=12, adjust=False).mean()
                        ema_26 = df_ind['close'].ewm(span=26, adjust=False).mean()
                        df_ind['macd_line'] = ema_12 - ema_26
                        df_ind['macd_signal'] = df_ind['macd_line'].ewm(span=9, adjust=False).mean()
                        df_ind['macd_hist'] = df_ind['macd_line'] - df_ind['macd_signal']
                        delta = df_ind['close'].diff()
                        gain = delta.clip(lower=0)
                        loss = -delta.clip(upper=0)
                        rs = gain.ewm(com=13, adjust=False).mean() / (loss.ewm(com=13, adjust=False).mean() + 1e-10)
                        df_ind['rsi'] = 100 - (100 / (1 + rs))
                    
                    exit_analysis = analyze_exit_conditions(df_ind)
                elif active_strategy == "pulse":
                    if symbol == "GBPUSD" and timeframe_str == "M30":
                        from strategies.pulse_gbpusd_m30 import analyze_pulse_gbpusd_m30_exit_conditions
                        exit_analysis = analyze_pulse_gbpusd_m30_exit_conditions(df_ind)
                    else:
                        from strategies.pulse import analyze_pulse_exit_conditions
                        exit_analysis = analyze_pulse_exit_conditions(df_ind)
                    
                if exit_analysis:
                    if order["order_type"] == "BUY" and exit_analysis.get("should_exit_buy"):
                        pnl = calc_pnl(order["order_type"], open_price, current_price, order["lot_size"], symbol)
                        await close_position(order, current_price, f"Smart Market Exit BUY: {exit_analysis.get('reason', '')} (PnL: ${pnl:.2f})")
                        continue
                    
                    elif order["order_type"] == "SELL" and exit_analysis.get("should_exit_sell"):
                        pnl = calc_pnl(order["order_type"], open_price, current_price, order["lot_size"], symbol)
                        await close_position(order, current_price, f"Smart Market Exit SELL: {exit_analysis.get('reason', '')} (PnL: ${pnl:.2f})")
                        continue
                
                # ── 3C: Dynamic TP Extension (Push TP further when momentum is strong) ──
                if tp and atr_at_entry and atr_at_entry > 0:
                    if order["order_type"] == "BUY" and exit_analysis.get("extend_tp_buy"):
                        new_tp = tp + (atr_at_entry * 0.5)  # Extend TP by 0.5 ATR
                        if new_tp > tp:
                            await db.orders.update_one(
                                {"_id": order["_id"]},
                                {"$set": {"tp": new_tp}}
                            )
                            print(f"[AutoTrade] 🎯 TP Extended for BUY {symbol}: {tp:.2f} → {new_tp:.2f} (Strong momentum)")
                    
                    elif order["order_type"] == "SELL" and exit_analysis.get("extend_tp_sell"):
                        new_tp = tp - (atr_at_entry * 0.5)  # Extend TP by 0.5 ATR
                        if new_tp < tp:
                            await db.orders.update_one(
                                {"_id": order["_id"]},
                                {"$set": {"tp": new_tp}}
                            )
                            print(f"[AutoTrade] 🎯 TP Extended for SELL {symbol}: {tp:.2f} → {new_tp:.2f} (Strong momentum)")
        
        # ════════════════════════════════════════════════════════════
        # MODIFY: Dynamic Trailing Stop (3-Stage + Continuous)
        # ════════════════════════════════════════════════════════════
        
        if atr_at_entry and atr_at_entry > 0 and sl:
            new_sl = sl
            new_stage = trail_stage
            
            if order["order_type"] == "BUY":
                profit_distance = current_price - open_price
                
                # Stage 1: Breakeven
                if profit_distance >= atr_at_entry * TRAIL_STAGE_1_TRIGGER and trail_stage < 1:
                    new_sl = open_price + (tick.ask - tick.bid)  # Breakeven + spread
                    new_stage = 1
                    print(f"[AutoTrade] 🛡️ Stage 1: SL → Breakeven ({new_sl:.2f}) for {symbol} BUY (Ticket: {order['ticket']})")
                
                # Stage 2: +0.5 ATR profit locked
                elif profit_distance >= atr_at_entry * TRAIL_STAGE_2_TRIGGER and trail_stage < 2:
                    new_sl = open_price + (atr_at_entry * 0.5)
                    new_stage = 2
                    print(f"[AutoTrade] 📈 Stage 2: SL → +0.5 ATR ({new_sl:.2f}) for {symbol} BUY (Ticket: {order['ticket']})")
                
                # Stage 3: +1.0 ATR profit locked
                elif profit_distance >= atr_at_entry * TRAIL_STAGE_3_TRIGGER and trail_stage < 3:
                    new_sl = open_price + (atr_at_entry * 1.0)
                    new_stage = 3
                    print(f"[AutoTrade] 🚀 Stage 3: SL → +1.0 ATR ({new_sl:.2f}) for {symbol} BUY (Ticket: {order['ticket']})")
                
                # Continuous trailing: keep SL 1.0 ATR behind current price
                elif trail_stage >= 3:
                    trailing_sl = current_price - (atr_at_entry * TRAIL_CONTINUOUS_OFFSET)
                    if trailing_sl > sl:  # Only move SL up, never down
                        new_sl = trailing_sl
                        new_stage = 4
                
            else:  # SELL
                profit_distance = open_price - current_price
                
                # Stage 1: Breakeven
                if profit_distance >= atr_at_entry * TRAIL_STAGE_1_TRIGGER and trail_stage < 1:
                    new_sl = open_price - (tick.ask - tick.bid)  # Breakeven - spread
                    new_stage = 1
                    print(f"[AutoTrade] 🛡️ Stage 1: SL → Breakeven ({new_sl:.2f}) for {symbol} SELL (Ticket: {order['ticket']})")
                
                # Stage 2: +0.5 ATR profit locked
                elif profit_distance >= atr_at_entry * TRAIL_STAGE_2_TRIGGER and trail_stage < 2:
                    new_sl = open_price - (atr_at_entry * 0.5)
                    new_stage = 2
                    print(f"[AutoTrade] 📈 Stage 2: SL → -0.5 ATR ({new_sl:.2f}) for {symbol} SELL (Ticket: {order['ticket']})")
                
                # Stage 3: +1.0 ATR profit locked
                elif profit_distance >= atr_at_entry * TRAIL_STAGE_3_TRIGGER and trail_stage < 3:
                    new_sl = open_price - (atr_at_entry * 1.0)
                    new_stage = 3
                    print(f"[AutoTrade] 🚀 Stage 3: SL → -1.0 ATR ({new_sl:.2f}) for {symbol} SELL (Ticket: {order['ticket']})")
                
                # Continuous trailing
                elif trail_stage >= 3:
                    trailing_sl = current_price + (atr_at_entry * TRAIL_CONTINUOUS_OFFSET)
                    if trailing_sl < sl:  # Only move SL down, never up
                        new_sl = trailing_sl
                        new_stage = 4
            
            # Apply trailing stop update
            if new_sl != sl or new_stage != trail_stage:
                await db.orders.update_one(
                    {"_id": order["_id"]},
                    {"$set": {"sl": new_sl, "trail_stage": new_stage}}
                )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN BOT LOOP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_trade_loop():
    """Main infinite loop for the background auto trading bot."""
    print("=" * 60)
    print("[AutoTrade] GUARDEER PRO v2.0 Bot Started")
    print("[AutoTrade] Features: Multi-confirmation signals, Dynamic trailing,")
    print("[AutoTrade]           Smart exits, Risk management, HTF filter")
    print("=" * 60)
    
    while True:
        try:
            # 1. Manage existing positions (TP/SL, trailing, smart exits)
            await manage_open_positions()
            
            # 2. Scan for new high-quality signals
            await scan_for_signals()
            
        except Exception as e:
            print(f"[AutoTrade] Error in loop: {e}")
            import traceback
            traceback.print_exc()
            
        # Delay before next scan to prevent CPU exhaustion and respect MT5 rate limits
        await asyncio.sleep(5)
