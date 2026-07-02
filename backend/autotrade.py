"""
GUARDEER PRO v3.0 — AUTO TRADE ENGINE
=======================================
Major overhaul based on analysis of 171 real trades.

Key Changes:
- Symbol-specific configs (no more one-size-fits-all)
- Volume + DOM confirmation before every entry
- Smart Exit Engine (peak profit tracking, momentum exhaustion, candle patterns)
- XAUEUR permanently banned (0% win rate, -$347)
- M1 timeframe removed (consistent losses)
- Dynamic SL/TP based on live market analysis
"""

import asyncio
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import random
import pandas as pd
import os
import csv
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure, AutoReconnect

from database import db
from mt5_logic import get_market_data
from strategies.pulse import calculate_pulse_signals
from strategies.soul import calculate_soul_signals
from strategies.symbol_configs import get_config, get_all_symbols, BANNED_SYMBOLS
from strategies.volume_engine import should_enter_trade
from strategies.smart_exit import run_smart_exit
from routes_orders import calc_pnl, execute_mt5_order, close_mt5_order

# Track the last timestamp traded per symbol to avoid duplicates
last_traded_signals = {}

# Track consecutive losses per user for cooldown
consecutive_losses = {}

# Track daily PnL per user
daily_pnl_tracker = {}

DEFAULT_LOT_SIZE = 0.05

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RISK MANAGEMENT CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MAX_OPEN_TRADES_PER_SYMBOL = 1
DAILY_LOSS_LIMIT_PCT = 3.0

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
            roi_percent = round((net_pnl / 1000.0) * 100, 2)
            
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
    """Returns True if we can open a new trade."""
    count = await db.orders.count_documents({
        "username": username,
        "symbol": symbol,
        "status": "open"
    })
    return count < MAX_OPEN_TRADES_PER_SYMBOL


async def check_daily_loss_limit(username: str) -> bool:
    """Returns True if we're within daily loss limit."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    tracker = daily_pnl_tracker.get(username, {})
    if tracker.get("date") != today:
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


def check_spread(symbol: str, config: dict) -> bool:
    """Returns True if spread is acceptable."""
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    
    if not tick or not info:
        return False
    
    spread = tick.ask - tick.bid
    point = info.point if info.point > 0 else 0.01
    spread_points = spread / point
    
    max_spread = config.get("max_spread_pips", 20)
    
    if spread_points > max_spread:
        print(f"[AutoTrade] ⚠️ High spread on {symbol}: {spread_points:.0f} pts (max: {max_spread}) — SKIPPING")
        return False
    
    return True


def record_trade_result(username: str, pnl: float):
    """Track wins/losses for daily PnL."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if username not in daily_pnl_tracker:
        daily_pnl_tracker[username] = {"date": today, "pnl": 0.0}
    if daily_pnl_tracker[username].get("date") != today:
        daily_pnl_tracker[username] = {"date": today, "pnl": 0.0}
    daily_pnl_tracker[username]["pnl"] += pnl


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TRADE EXECUTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def execute_trade(username: str, symbol: str, order_type: str, candle: pd.Series, config: dict):
    """Executes a trade with symbol-specific config."""
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return
        
    open_price = tick.ask if order_type == "BUY" else tick.bid
    
    # Ensure funds exist
    funds = await db.funds.find_one({"username": username})
    if not funds:
        await db.funds.insert_one({"username": username, "balance": 100000.0, "equity": 100000.0, "available_margin": 100000.0, "used_margin": 0.0, "floating_pnl": 0.0})

    atr_val = float(candle['atr']) if pd.notna(candle.get('atr')) else None
    sl_val = float(candle['sl']) if pd.notna(candle['sl']) else None
    tp_val = float(candle['tp']) if pd.notna(candle['tp']) else None
    
    strategy = config.get("strategy", "pulse")
    timeframe = config.get("timeframe", "H1")

    # Execute in MT5
    mt5_result = execute_mt5_order(
        symbol=symbol,
        order_type=order_type,
        lot_size=DEFAULT_LOT_SIZE,
        price=open_price,
        sl=sl_val,
        tp=tp_val,
        comment="Auto BOT v3"
    )
    
    if mt5_result["success"]:
        ticket = mt5_result["ticket"]
        executed_price = mt5_result["price"]
    else:
        print(f"[AutoTrade] ⚠️ MT5 failed: {mt5_result['error']}, using dummy")
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
        "original_sl": sl_val,
        "atr_at_entry": atr_val,
        "pnl": 0.0,
        "floating_pnl": 0.0,
        "peak_profit": 0.0,          # NEW: Track peak profit for smart exit
        "commission": -0.50,
        "swap": 0.0,
        "status": "open",
        "comment": "Auto BOT v3",
        "open_time": datetime.now(timezone.utc).isoformat(),
        "open_candle_count": 0,
        "trail_stage": 0,
        "close_time": None,
        "close_price": None,
    }
    
    await db.orders.insert_one(order)
    log_trade_to_csv("OPEN", order, reason="Signal Entry")
    print(f"[AutoTrade] ✅ Opened {order_type} on {symbol} ({strategy}/{timeframe}) at {executed_price} (Ticket: {ticket}) | SL: {sl_val} | TP: {tp_val}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SIGNAL SCANNING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def scan_for_signals():
    """Scan all configured symbols for new trade signals."""
    users = await db.users.find().to_list(100)
    
    for user in users:
        username = user.get("username")
        
        # RISK CHECK: Daily loss limit
        if not await check_daily_loss_limit(username):
            continue
        
        # Scan each configured symbol
        for symbol in get_all_symbols():
            config = get_config(symbol)
            if not config:
                continue
            
            # Block banned symbols
            if symbol in BANNED_SYMBOLS:
                continue
            
            # Select symbol in MT5 Market Watch
            mt5.symbol_select(symbol, True)
            
            # RISK CHECK: Max trades per symbol
            if not await check_max_trades_per_symbol(username, symbol):
                continue
            
            # RISK CHECK: Spread
            if not check_spread(symbol, config):
                continue
            
            # Get timeframe from config
            timeframe_str = config.get("timeframe", "H1")
            tf_map = {
                "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
                "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, 
                "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
            }
            tf = tf_map.get(timeframe_str, mt5.TIMEFRAME_H1)
            
            # Get market data
            df = get_market_data(symbol, tf, 300)
            if df is None or len(df) < 50:
                continue
            
            # Calculate signals using Pulse v3 with symbol config
            strategy = config.get("strategy", "pulse")
            if strategy == "pulse":
                df = calculate_pulse_signals(df, config=config)
            elif strategy == "soul":
                df = calculate_soul_signals(df, symbol=symbol)
            else:
                df = calculate_pulse_signals(df, config=config)
            
            if df is None or len(df) == 0:
                continue
            
            latest = df.iloc[-1]
            
            # Get last signal within 5 candles
            signals_df = df.dropna(subset=['signal'])
            if signals_df.empty:
                continue
            
            last_signal_row = signals_df.iloc[-1]
            sig = last_signal_row['signal']
            signal_time = int(last_signal_row['raw_time'])
            
            if df.index[-1] - last_signal_row.name <= 5:
                if pd.notna(sig) and sig in ('BUY', 'SELL'):
                    key = f"{username}_{symbol}_{timeframe_str}"
                    
                    if last_traded_signals.get(key) != signal_time:
                        
                        # VOLUME + DOM CONFIRMATION
                        entry_check = should_enter_trade(df, symbol, sig, config)
                        if not entry_check["allowed"]:
                            print(f"[AutoTrade] 📊 Blocked {sig} on {symbol}: {entry_check['reason']}")
                            continue
                        
                        last_traded_signals[key] = signal_time
                        
                        # Merge SL/TP from signal bar with latest data
                        trade_candle = latest.copy()
                        trade_candle['sl'] = last_signal_row['sl']
                        trade_candle['tp'] = last_signal_row['tp']
                        
                        await execute_trade(username, symbol, sig, trade_candle, config)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SMART POSITION MANAGEMENT (v3)
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
    
    record_trade_result(order["username"], net_pnl)
    
    updated_order = {**order, "close_price": actual_close_price, "pnl": pnl, "status": "closed"}
    updated_order["commission"] = order.get("commission", 0)
    updated_order["swap"] = order.get("swap", 0)
    log_trade_to_csv("CLOSE", updated_order, reason=reason)
    
    emoji = "💰" if net_pnl >= 0 else "🔻"
    print(f"[AutoTrade] {emoji} Closed {order['order_type']} on {symbol} (Ticket: {ticket}) | {reason} | Net: ${net_pnl:.2f}")


async def manage_open_positions():
    """
    GUARDEER PRO v3.0 — Smart Position Management.
    
    Uses the Smart Exit Engine for ALL exit decisions.
    """
    open_orders = await db.orders.find({"status": "open"}).to_list(1000)
    
    for order in open_orders:
        symbol = order["symbol"]
        
        # Get symbol config
        config = get_config(symbol)
        if not config:
            # Symbol not in our configs (might be old trade) — use defaults
            config = {
                "breakeven_profit_usd": 3.0,
                "profit_protect_pct": 30,
                "min_profit_to_protect": 2.0,
                "max_candles": 60,
                "rsi_period": 14,
                "rsi_overbought": 72,
                "rsi_oversold": 28,
                "sl_mult": 0.7,
            }
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            continue
        
        current_price = tick.bid if order["order_type"] == "BUY" else tick.ask
        
        # Increment candle count
        candle_count = order.get("open_candle_count", 0) + 1
        await db.orders.update_one(
            {"_id": order["_id"]},
            {"$set": {"open_candle_count": candle_count}}
        )
        order["open_candle_count"] = candle_count
        
        # Get market data for analysis
        timeframe_str = order.get("timeframe", "H1")
        tf_map = {
            "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe_str, mt5.TIMEFRAME_H1)
        
        df = get_market_data(symbol, tf, 100)
        
        # Calculate indicators on the data for exit analysis
        if df is not None and len(df) > 20:
            strategy = order.get("strategy", "pulse")
            if strategy == "pulse":
                df = calculate_pulse_signals(df, config=config)
            elif strategy == "soul":
                df = calculate_soul_signals(df, symbol=symbol)
            else:
                df = calculate_pulse_signals(df, config=config)
        
        # ═══════════════════════════════════════════════════════════
        # RUN SMART EXIT ENGINE (All-in-one exit decision)
        # ═══════════════════════════════════════════════════════════
        
        exit_result = run_smart_exit(order, current_price, df, config)
        
        # Apply DB updates (peak_profit, floating_pnl, SL adjustments, etc.)
        if exit_result.get("updates"):
            updates = exit_result["updates"]
            if updates:
                await db.orders.update_one(
                    {"_id": order["_id"]},
                    {"$set": updates}
                )
                # Log important SL changes
                if "sl" in updates and updates["sl"] != order.get("sl"):
                    stage = updates.get("trail_stage", order.get("trail_stage", 0))
                    stage_names = {0: "Initial", 1: "Breakeven", 2: "+0.5 ATR", 3: "+1.0 ATR", 4: "Trailing"}
                    print(f"[AutoTrade] 🛡️ SL updated for {symbol} (Ticket: {order['ticket']}): {order.get('sl', 'N/A'):.2f} → {updates['sl']:.2f} ({stage_names.get(stage, 'Unknown')})")
        
        # Exit if Smart Exit says so
        if exit_result["should_exit"]:
            await close_position(order, current_price, exit_result["reason"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN BOT LOOP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_trade_loop():
    """Main infinite loop for the background auto trading bot."""
    print("=" * 60)
    print("[AutoTrade] GUARDEER PRO v3.0 Started")
    print("[AutoTrade] Features: Smart Exit Engine, Volume+DOM Filter,")
    print("[AutoTrade]           Symbol-Specific Configs, Peak Profit Tracking")
    print(f"[AutoTrade] Active Symbols: {', '.join(get_all_symbols())}")
    print(f"[AutoTrade] Banned Symbols: {', '.join(BANNED_SYMBOLS)}")
    print("=" * 60)
    
    db_retry_delay = 5  # Start with normal delay
    MAX_DB_RETRY_DELAY = 60  # Cap at 60 seconds
    
    while True:
        try:
            # 1. Manage existing positions (Smart Exit Engine)
            await manage_open_positions()
            
            # 2. Scan for new signals
            await scan_for_signals()
            
            # Reset retry delay on success
            db_retry_delay = 5
            
        except (ServerSelectionTimeoutError, ConnectionFailure, AutoReconnect) as e:
            # MongoDB transient error — use exponential backoff
            print(f"[AutoTrade] ⚠️ MongoDB connection issue (retrying in {db_retry_delay}s): {e}")
            await asyncio.sleep(db_retry_delay)
            db_retry_delay = min(db_retry_delay * 2, MAX_DB_RETRY_DELAY)
            continue
            
        except Exception as e:
            print(f"[AutoTrade] Error in loop: {e}")
            import traceback
            traceback.print_exc()
            
        # 5 second cycle for fast exit detection
        await asyncio.sleep(5)

