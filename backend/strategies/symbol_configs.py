"""
SYMBOL CONFIGS — Per-Symbol Optimized Trading Parameters
=========================================================
Each symbol gets its own tuned parameters based on analysis of 171 real trades.

XAUUSD/pulse/H1 = 69% WR, +$103 (BEST)
GBPUSD needs wider stops due to GBP volatility
EURUSD is tighter, needs quick entries/exits
USDJPY has unique pip calculation (÷100)
"""

SYMBOL_CONFIGS = {
    "XAUUSD": {
        "strategy": "pulse",
        "timeframe": "H1",
        "ema_fast": 5,
        "ema_slow": 13,
        "ema_trend": 50,          # Trend filter EMA
        "atr_period": 14,
        "tp_mult": 1.5,           # Wider TP for Gold's volatility
        "sl_mult": 0.7,           # Tighter SL (data shows Gold reverses fast)
        "rsi_period": 14,
        "rsi_overbought": 72,     # Don't BUY above this
        "rsi_oversold": 28,       # Don't SELL below this
        "min_volume_mult": 1.2,   # Volume must be 1.2× avg to confirm signal
        "max_spread_pips": 35,    # Gold spread tolerance (in points)
        "breakeven_profit_usd": 5.0,   # Move SL to breakeven at $5 profit
        "profit_protect_pct": 30,      # Exit if profit drops 30% from peak
        "min_profit_to_protect": 3.0,  # Only protect profits above $3
        "max_candles": 48,             # Max hold time (48 H1 candles = 2 days)
        "contract_size": 100,          # 100 oz per lot
    },
    "EURUSD": {
        "strategy": "pulse",
        "timeframe": "M15",
        "ema_fast": 5,
        "ema_slow": 13,
        "ema_trend": 50,
        "atr_period": 14,
        "tp_mult": 1.2,
        "sl_mult": 0.5,
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "min_volume_mult": 1.5,   # Needs stronger volume confirm (low volatility pair)
        "max_spread_pips": 15,
        "breakeven_profit_usd": 1.0,
        "profit_protect_pct": 40,
        "min_profit_to_protect": 0.5,
        "max_candles": 40,
        "contract_size": 100000,
    },
    "GBPUSD": {
        "strategy": "pulse",
        "timeframe": "M30",
        "ema_fast": 9,            # Slightly slower for GBP volatility
        "ema_slow": 21,
        "ema_trend": 50,
        "atr_period": 14,
        "tp_mult": 1.5,
        "sl_mult": 1.0,
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "min_volume_mult": 1.3,
        "max_spread_pips": 20,
        "breakeven_profit_usd": 1.5,
        "profit_protect_pct": 35,
        "min_profit_to_protect": 0.8,
        "max_candles": 40,
        "contract_size": 100000,
    },
    "USDJPY": {
        "strategy": "pulse",
        "timeframe": "M15",
        "ema_fast": 5,
        "ema_slow": 13,
        "ema_trend": 50,
        "atr_period": 14,
        "tp_mult": 1.2,
        "sl_mult": 0.5,
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "min_volume_mult": 1.5,
        "max_spread_pips": 15,
        "breakeven_profit_usd": 1.0,
        "profit_protect_pct": 40,
        "min_profit_to_protect": 0.5,
        "max_candles": 40,
        "contract_size": 100000,
    },
}

# Banned symbols — never trade these
BANNED_SYMBOLS = {"XAUEUR", "AUDUSD"}

def get_config(symbol: str) -> dict:
    """Get trading config for a symbol. Returns None if symbol is banned or not configured."""
    if symbol in BANNED_SYMBOLS:
        return None
    return SYMBOL_CONFIGS.get(symbol)

def get_all_symbols() -> list:
    """Get list of all tradeable symbols."""
    return list(SYMBOL_CONFIGS.keys())
