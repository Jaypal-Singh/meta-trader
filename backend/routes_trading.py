from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import MetaTrader5 as mt5
import pandas as pd
from mt5_logic import get_market_data, calculate_indicators, calculate_accuracy
import math
from database import db
from auth import SECRET_KEY
import jwt
from fastapi import Header

router = APIRouter()

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

class AutotradeRequest(BaseModel):
    symbol: str

@router.get("/autotrade")
async def get_autotrade_symbols(username: str = Depends(get_current_user)):
    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"autotrade_symbols": user.get("autotrade_symbols", [])}

@router.post("/autotrade")
async def toggle_autotrade_symbol(req: AutotradeRequest, username: str = Depends(get_current_user)):
    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    symbols = user.get("autotrade_symbols", [])
    if req.symbol in symbols:
        symbols.remove(req.symbol)
    else:
        symbols.append(req.symbol)
        
    await db.users.update_one(
        {"username": username},
        {"$set": {"autotrade_symbols": symbols}}
    )
    return {"status": "success", "autotrade_symbols": symbols}

mt5_initialized = False

def ensure_mt5():
    global mt5_initialized
    if not mt5_initialized:
        if mt5.initialize():
            mt5_initialized = True
        else:
            raise HTTPException(status_code=500, detail="Failed to initialize MT5. Ensure MT5 is running.")
            
    # Check if actually connected to a broker
    terminal = mt5.terminal_info()
    if terminal is None or not terminal.connected:
        raise HTTPException(status_code=500, detail="MT5 is open but NOT connected to a trading account. Please go to File -> Open an Account in MT5.")
        
    return True

@router.get("/watchlist")
def get_watchlist():
    ensure_mt5()
    
    # Fetch symbols currently visible in the MT5 Market Watch
    symbols = mt5.symbols_get()
    if not symbols:
        raise HTTPException(status_code=500, detail="No symbols found in MT5")
        
    visible_symbols = [s.name for s in symbols if s.visible]
    
    data = []
    for sym in visible_symbols:
        info = mt5.symbol_info(sym)
        tick = mt5.symbol_info_tick(sym)
        
        if info and tick:
            # Use bid price primarily as MT5 charts are drawn using bid prices. Fallback to last or ask.
            price = tick.bid if getattr(tick, 'bid', 0.0) != 0.0 else (tick.last if getattr(tick, 'last', 0.0) != 0.0 else tick.ask)
            digits = info.digits if info.digits else 2
            
            # Calculate daily change from previous day's close
            change = 0.0
            pct = 0.0
            is_up = True
            try:
                daily_bars = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 2)
                if daily_bars is not None and len(daily_bars) >= 2:
                    prev_close = float(daily_bars[-2][4])  # index 4 = close in structured array
                    change = round(price - prev_close, digits)
                    pct = round((change / prev_close) * 100, 2) if prev_close != 0 else 0.0
                    is_up = change >= 0
            except Exception:
                pass
            
            data.append({
                "name": sym,
                "tag": "LIVE",
                "sub": info.description if info.description else "MetaTrader",
                "price": round(price, digits),
                "change": change,
                "pct": pct,
                "up": is_up
            })
            
    return data

@router.get("/live_price")
def get_live_price(symbol: str):
    """Return the current bid price for a symbol — same source as the watchlist."""
    ensure_mt5()
    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if not info or not tick:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    price = tick.bid if getattr(tick, 'bid', 0.0) != 0.0 else (tick.last if getattr(tick, 'last', 0.0) != 0.0 else tick.ask)
    digits = info.digits if info.digits else 2
    return {"symbol": symbol, "price": round(price, digits), "bid": round(tick.bid, digits), "ask": round(tick.ask, digits)}

@router.get("/search")
def search_symbols(q: str):
    ensure_mt5()
    symbols = mt5.symbols_get()
    if not symbols:
        return []
        
    q_upper = q.upper()
    matches = []
    for s in symbols:
        if q_upper in s.name.upper() or (s.description and q_upper in s.description.upper()):
            matches.append({
                "name": s.name,
                "description": s.description if s.description else "MetaTrader Symbol"
            })
            if len(matches) >= 20: # Limit to 20 results
                break
    return matches

class AddSymbolRequest(BaseModel):
    symbol: str

@router.post("/watchlist/add")
def add_to_watchlist(req: AddSymbolRequest):
    ensure_mt5()
    success = mt5.symbol_select(req.symbol, True)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to add {req.symbol} to Market Watch")
    return {"status": "ok", "message": f"Added {req.symbol}"}

@router.get("/chart_data")
def get_chart_data(symbol: str, timeframe: str = "M5"):
    ensure_mt5()
    
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    
    tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_M5)
    
    df = get_market_data(symbol, tf, 2000)
    if df is None:
        raise HTTPException(status_code=404, detail="Symbol not found or no data available")
        
    df_with_signals = calculate_indicators(df, symbol=symbol)
    if df_with_signals is None:
        raise HTTPException(status_code=500, detail="Failed to calculate indicators")
        
    # Convert DataFrame to list of dicts for JSON serialization
    # Handle NaN values explicitly
    data = []
    ema21_data = []
    ema50_data = []
    ema200_data = []
    rsi_data = []
    macd_data = []
    macd_signal_data = []
    macd_hist_data = []
    
    for _, row in df_with_signals.iterrows():
        # Keep time as integer for lightweight-charts
        time_val = int(row['raw_time'])
        
        # Safely extract signal — it can be None, NaN, or a string
        sig = row['signal']
        if sig is None or (isinstance(sig, float) and math.isnan(sig)):
            sig = None
        elif sig is not None:
            sig = str(sig)  # Ensure it's a clean string 'BUY' or 'SELL'
        
        item = {
            "time": time_val,
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close']),
            "signal": sig
        }
        
        # Add SL/TP only if there is a signal
        if sig in ('BUY', 'SELL'):
            tp_val = float(row['tp']) if pd.notna(row['tp']) else None
            sl_val = float(row['sl']) if pd.notna(row['sl']) else None
            item['tp'] = tp_val
            item['sl'] = sl_val
            
        data.append(item)
        
        # Indicator overlay data for the chart
        if 'ema_21' in row and pd.notna(row['ema_21']):
            ema21_data.append({"time": time_val, "value": round(float(row['ema_21']), 2)})
        if 'ema_50' in row and pd.notna(row['ema_50']):
            ema50_data.append({"time": time_val, "value": round(float(row['ema_50']), 2)})
        if 'ema_200' in row and pd.notna(row['ema_200']):
            ema200_data.append({"time": time_val, "value": round(float(row['ema_200']), 2)})
        if 'rsi' in row and pd.notna(row['rsi']):
            rsi_data.append({"time": time_val, "value": round(float(row['rsi']), 2)})
        if 'macd_line' in row and pd.notna(row['macd_line']):
            macd_data.append({"time": time_val, "value": round(float(row['macd_line']), 4)})
        if 'macd_signal' in row and pd.notna(row['macd_signal']):
            macd_signal_data.append({"time": time_val, "value": round(float(row['macd_signal']), 4)})
        if 'macd_hist' in row and pd.notna(row['macd_hist']):
            macd_hist_data.append({"time": time_val, "value": round(float(row['macd_hist']), 4)})
        
    accuracy = calculate_accuracy(df_with_signals)
    
    return {
        "data": data,
        "accuracy": accuracy,
        "indicators": {
            "ema_21": ema21_data,
            "ema_50": ema50_data,
            "ema_200": ema200_data,
            "rsi": rsi_data,
            "macd_line": macd_data,
            "macd_signal": macd_signal_data,
            "macd_hist": macd_hist_data,
        }
    }
