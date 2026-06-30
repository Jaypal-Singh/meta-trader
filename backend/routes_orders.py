"""
Orders API — Forex-style order management with per-user segregation.
All endpoints require JWT Bearer token. Orders are stored in MongoDB.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import Optional, List
from database import db
from auth import SECRET_KEY
from datetime import datetime, timezone
import jwt
import random
import string
import MetaTrader5 as mt5
import os
import csv

CSV_FILE_PATH = "trade_analysis.csv"

def log_trade_to_csv(action: str, order: dict, reason: str = ""):
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
            "strategy": order.get("strategy", "manual"),
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


router = APIRouter()

# ─── JWT Dependency ──────────────────────────────────────────────────
def get_current_user(authorization: str = Header(None)):
    """Extract username from JWT Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated. Please login first.")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Models ──────────────────────────────────────────────────────────
class CreateOrderRequest(BaseModel):
    symbol: str
    order_type: str  # "BUY" or "SELL"
    lot_size: float = 0.01
    open_price: float
    strategy: Optional[str] = "manual"
    timeframe: Optional[str] = "unknown"
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: Optional[str] = ""

class CloseOrderRequest(BaseModel):
    close_price: float

class ModifyOrderRequest(BaseModel):
    sl: Optional[float] = None
    tp: Optional[float] = None


# ─── Helper ──────────────────────────────────────────────────────────
def generate_ticket() -> str:
    """Generate a unique 8-digit ticket number like MT5."""
    return str(random.randint(10000000, 99999999))

def serialize_order(order: dict) -> dict:
    """Convert MongoDB document to JSON-safe dict."""
    order["_id"] = str(order["_id"])
    return order

def calc_pnl(order_type: str, open_price: float, close_price: float, lot_size: float, symbol: str) -> float:
    """
    Calculate profit/loss for forex order.
    Standard lot = 100,000 units. For XAU pairs, 1 lot = 100 oz.
    """
    if "XAU" in symbol.upper():
        contract_size = 100  # 100 oz per lot for gold
    elif "JPY" in symbol.upper():
        contract_size = 100000
    else:
        contract_size = 100000  # Standard forex lot

    if order_type == "BUY":
        pnl = (close_price - open_price) * lot_size * contract_size
    else:  # SELL
        pnl = (open_price - close_price) * lot_size * contract_size

    # For JPY pairs, divide by 100 for pip value correction
    if "JPY" in symbol.upper() and "XAU" not in symbol.upper():
        pnl = pnl / 100

    return round(pnl, 2)


# ─── MT5 Helpers ─────────────────────────────────────────────────────
def execute_mt5_order(symbol: str, order_type: str, lot_size: float, price: float, sl: Optional[float] = None, tp: Optional[float] = None, comment: str = "") -> dict:
    """Place a real order in MT5 terminal."""
    type_dict = {
        "BUY": mt5.ORDER_TYPE_BUY,
        "SELL": mt5.ORDER_TYPE_SELL
    }
    
    if order_type not in type_dict:
        return {"success": False, "error": f"Invalid order type: {order_type}"}

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": type_dict[order_type],
        "price": float(price),
        "sl": float(sl) if sl else 0.0,
        "tp": float(tp) if tp else 0.0,
        "deviation": 20,
        "magic": 234000,
        "comment": comment[:25] if comment else "Guardeer Auto",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result is None:
        error = mt5.last_error()
        return {"success": False, "error": f"order_send failed, error code: {error}"}
        
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "error": f"order_send failed, retcode={result.retcode} ({result.comment})"}
        
    return {"success": True, "ticket": str(result.order), "price": result.price}

def close_mt5_order(symbol: str, ticket: int, order_type: str, lot_size: float, close_price: float) -> dict:
    """Close a real order in MT5 by placing an opposite deal."""
    type_dict = {
        "BUY": mt5.ORDER_TYPE_SELL,
        "SELL": mt5.ORDER_TYPE_BUY
    }
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": type_dict[order_type],
        "position": ticket,
        "price": float(close_price),
        "deviation": 20,
        "magic": 234000,
        "comment": "Guardeer Close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result is None:
        error = mt5.last_error()
        return {"success": False, "error": f"order_send close failed, error code: {error}"}
        
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"success": False, "error": f"order_send close failed, retcode={result.retcode} ({result.comment})"}
        
    return {"success": True, "price": result.price}

# ─── Endpoints ───────────────────────────────────────────────────────

async def update_live_orders_pnl(username: str):
    """Fetch live MT5 tick data to update current_price and floating_pnl for open orders."""
    open_orders = await db.orders.find({"username": username, "status": "open"}).to_list(1000)
    for order in open_orders:
        symbol = order["symbol"]
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            # If BUY, we close at bid. If SELL, we close at ask.
            current_price = tick.bid if order["order_type"] == "BUY" else tick.ask
            new_pnl = calc_pnl(order["order_type"], order["open_price"], current_price, order["lot_size"], symbol)
            
            await db.orders.update_one(
                {"_id": order["_id"]},
                {"$set": {
                    "current_price": current_price,
                    "floating_pnl": new_pnl
                }}
            )

@router.get("/")
async def get_orders(status: str = "all", username: str = Depends(get_current_user)):
    """
    Get orders for current user.
    Query param: status = 'open' | 'closed' | 'all'
    """
    await update_live_orders_pnl(username)
    
    query = {"username": username}
    if status == "open":
        query["status"] = "open"
    elif status == "closed":
        query["status"] = "closed"

    orders = await db.orders.find(query).sort("open_time", -1).to_list(500)
    return [serialize_order(o) for o in orders]


@router.get("/summary")
async def get_order_summary(username: str = Depends(get_current_user)):
    """Quick summary: total open orders, total P&L, etc."""
    await update_live_orders_pnl(username)
    
    open_orders = await db.orders.find({"username": username, "status": "open"}).to_list(500)
    closed_orders = await db.orders.find({"username": username, "status": "closed"}).to_list(500)

    total_open_pnl = sum(o.get("floating_pnl", 0) for o in open_orders)
    total_closed_pnl = sum(o.get("pnl", 0) for o in closed_orders)

    return {
        "open_count": len(open_orders),
        "closed_count": len(closed_orders),
        "total_open_pnl": round(total_open_pnl, 2),
        "total_closed_pnl": round(total_closed_pnl, 2),
    }


@router.post("/")
async def create_order(req: CreateOrderRequest, username: str = Depends(get_current_user)):
    """Place a new order."""
    if req.order_type not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="order_type must be BUY or SELL")
    if req.lot_size <= 0:
        raise HTTPException(status_code=400, detail="lot_size must be positive")

    # Margin check
    funds = await db.funds.find_one({"username": username})
    if not funds:
        funds = {"username": username, "balance": 100000.0, "used_margin": 0.0}
        await db.funds.insert_one(funds)

    open_orders = await db.orders.find({"username": username, "status": "open"}).to_list(1000)
    current_used_margin = 0.0
    floating_pnl = 0.0
    for o in open_orders:
        contract_sz = 100 if "XAU" in o["symbol"].upper() else 100000
        current_used_margin += (o["open_price"] * o["lot_size"] * contract_sz) / 100
        floating_pnl += o.get("floating_pnl", 0.0)

    available_margin = funds["balance"] - current_used_margin + floating_pnl

    new_contract_sz = 100 if "XAU" in req.symbol.upper() else 100000
    required_margin = (req.open_price * req.lot_size * new_contract_sz) / 100

    if available_margin < required_margin:
        raise HTTPException(status_code=400, detail=f"Insufficient funds. Required: ${required_margin:.2f}, Available: ${available_margin:.2f}")

    # Execute trade in MT5
    mt5_result = execute_mt5_order(
        symbol=req.symbol.upper(),
        order_type=req.order_type.upper(),
        lot_size=req.lot_size,
        price=req.open_price,
        sl=req.sl,
        tp=req.tp,
        comment=req.comment or ""
    )
    
    if mt5_result["success"]:
        ticket = mt5_result["ticket"]
        executed_price = mt5_result["price"]
    else:
        # Fallback to dummy trading if MT5 fails or is not connected
        print(f"MT5 execution failed: {mt5_result['error']}, falling back to dummy trading")
        ticket = generate_ticket()
        executed_price = req.open_price

    order = {
        "ticket": ticket,
        "username": username,
        "symbol": req.symbol.upper(),
        "order_type": req.order_type.upper(),
        "strategy": req.strategy,
        "timeframe": req.timeframe,
        "lot_size": req.lot_size,
        "open_price": executed_price,
        "current_price": executed_price,
        "sl": req.sl,
        "tp": req.tp,
        "pnl": 0.0,
        "floating_pnl": 0.0,
        "commission": round(-req.lot_size * 7, 2),  # $7 per lot commission
        "swap": 0.0,
        "status": "open",
        "comment": req.comment or "",
        "open_time": datetime.now(timezone.utc).isoformat(),
        "close_time": None,
        "close_price": None,
        "open_candle_count": 0,
    }

    result = await db.orders.insert_one(order)
    order["_id"] = str(result.inserted_id)
    log_trade_to_csv("OPEN", order, reason="Manual Entry")
    return order


@router.put("/{ticket}/close")
async def close_order(ticket: str, req: CloseOrderRequest, username: str = Depends(get_current_user)):
    """Close an open order."""
    order = await db.orders.find_one({"ticket": ticket, "username": username})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] == "closed":
        raise HTTPException(status_code=400, detail="Order is already closed")

    # Try closing in MT5
    try:
        mt5_ticket = int(ticket)
        close_result = close_mt5_order(
            symbol=order["symbol"],
            ticket=mt5_ticket,
            order_type=order["order_type"],
            lot_size=order["lot_size"],
            close_price=req.close_price
        )
        if close_result["success"]:
            actual_close_price = close_result["price"]
        else:
            print(f"MT5 close failed: {close_result['error']}")
            actual_close_price = req.close_price
    except ValueError:
        # Ticket was generated as string for dummy order
        actual_close_price = req.close_price

    pnl = calc_pnl(order["order_type"], order["open_price"], actual_close_price, order["lot_size"], order["symbol"])

    await db.orders.update_one(
        {"ticket": ticket, "username": username},
        {"$set": {
            "status": "closed",
            "close_price": actual_close_price,
            "close_time": datetime.now(timezone.utc).isoformat(),
            "current_price": actual_close_price,
            "pnl": pnl,
            "floating_pnl": 0.0,
        }}
    )

    # Update funds balance
    net_pnl = pnl + order.get("commission", 0) + order.get("swap", 0)
    await db.funds.update_one(
        {"username": username},
        {"$inc": {"balance": net_pnl}}
    )

    updated = await db.orders.find_one({"ticket": ticket, "username": username})
    log_trade_to_csv("CLOSE", updated, reason="Manual Close")
    return serialize_order(updated)


@router.put("/{ticket}/modify")
async def modify_order(ticket: str, req: ModifyOrderRequest, username: str = Depends(get_current_user)):
    """Modify SL/TP of an open order."""
    order = await db.orders.find_one({"ticket": ticket, "username": username})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] == "closed":
        raise HTTPException(status_code=400, detail="Cannot modify closed order")

    update_fields = {}
    if req.sl is not None:
        update_fields["sl"] = req.sl
    if req.tp is not None:
        update_fields["tp"] = req.tp

    if update_fields:
        await db.orders.update_one(
            {"ticket": ticket, "username": username},
            {"$set": update_fields}
        )

    updated = await db.orders.find_one({"ticket": ticket, "username": username})
    return serialize_order(updated)


@router.delete("/{ticket}")
async def delete_order(ticket: str, username: str = Depends(get_current_user)):
    """Delete an order (admin/cleanup)."""
    result = await db.orders.delete_one({"ticket": ticket, "username": username})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"status": "ok", "message": f"Order {ticket} deleted"}


