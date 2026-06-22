from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
from database import db
from auth import SECRET_KEY
import jwt

router = APIRouter()

def get_current_user(authorization: str = Header(None)):
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

class EditFundsRequest(BaseModel):
    amount: float

@router.get("/")
async def get_funds(username: str = Depends(get_current_user)):
    """Get the user's funds."""
    # Find or create user balance
    funds = await db.funds.find_one({"username": username})
    if not funds:
        funds = {
            "username": username,
            "balance": 100000.0, # Default starting dummy balance
            "used_margin": 0.0
        }
        await db.funds.insert_one(funds)
    
    funds["_id"] = str(funds.get("_id", ""))
    
    # Calculate live used margin from open orders
    open_orders = await db.orders.find({"username": username, "status": "open"}).to_list(1000)
    
    used_margin = 0.0
    floating_pnl = 0.0
    for order in open_orders:
        # Simplistic margin calc: let's assume 1:100 leverage. 
        # contract size: 100,000 for standard lot
        if "XAU" in order["symbol"].upper():
            contract_size = 100
        elif "JPY" in order["symbol"].upper():
            contract_size = 100000
        else:
            contract_size = 100000
        
        # margin = (open_price * lot_size * contract_size) / leverage
        margin = (order["open_price"] * order["lot_size"] * contract_size) / 100
        used_margin += margin
        floating_pnl += order.get("floating_pnl", 0.0)

    # Update the used_margin in db for consistency, though we calculate it dynamically
    await db.funds.update_one(
        {"username": username}, 
        {"$set": {"used_margin": used_margin}}
    )
    
    available_margin = funds["balance"] - used_margin + floating_pnl
    
    return {
        "balance": funds["balance"],
        "used_margin": round(used_margin, 2),
        "floating_pnl": round(floating_pnl, 2),
        "available_margin": round(available_margin, 2),
        "equity": round(funds["balance"] + floating_pnl, 2)
    }

@router.post("/edit")
async def edit_funds(req: EditFundsRequest, username: str = Depends(get_current_user)):
    """Add or set dummy funds."""
    funds = await db.funds.find_one({"username": username})
    if not funds:
        funds = {
            "username": username,
            "balance": req.amount,
            "used_margin": 0.0
        }
        await db.funds.insert_one(funds)
    else:
        await db.funds.update_one(
            {"username": username},
            {"$set": {"balance": req.amount}}
        )
        
    return {"status": "ok", "message": f"Balance updated to {req.amount}"}
