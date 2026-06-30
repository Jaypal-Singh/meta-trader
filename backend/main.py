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
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
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

@app.get("/api/status")
async def read_status():
    # Test DB connection
    count = await db.users.count_documents({})
    return {"status": "ok", "message": "MT5 Trading Bot Backend Running", "users_count": count}

frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    @app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(request, exc):
        if exc.status_code == 404 and not request.url.path.startswith("/api/"):
            index_path = os.path.join(frontend_dist, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
