import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import db
from routes_auth import router as auth_router
from routes_trading import router as trading_router
from routes_orders import router as orders_router
from routes_funds import router as funds_router
from autotrade import auto_trade_loop
import asyncio

app = FastAPI(title="MT5 Trading Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(trading_router, prefix="/api/trading", tags=["Trading"])
app.include_router(orders_router, prefix="/api/orders", tags=["Orders"])
app.include_router(funds_router, prefix="/api/funds", tags=["Funds"])

@app.on_event("startup")
async def startup_event():
    # Run the background bot
    asyncio.create_task(auto_trade_loop())

@app.get("/")
async def read_root():
    # Test DB connection
    count = await db.users.count_documents({})
    return {"status": "ok", "message": "MT5 Trading Bot Backend Running", "users_count": count}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
