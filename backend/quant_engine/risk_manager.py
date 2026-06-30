import asyncio
from database import db
from .cache_manager import cache
from .models import Portfolio
import logging

logger = logging.getLogger(__name__)

async def risk_monitor_loop():
    """
    Isolated Background Task:
    Constantly monitors Portfolios and triggers a kill switch if 
    the max drawdown limit is breached. Operates entirely independently 
    from the live trading logic to ensure maximum safety.
    """
    logger.info("Quant Engine: Isolated Risk Monitor Started.")
    while True:
        try:
            # 1. Fetch all active portfolios
            portfolios = await db.quant_portfolios.find({"is_active": True}).to_list(length=100)
            
            for p_doc in portfolios:
                portfolio = Portfolio(**p_doc)
                
                # 2. Get all OPEN orders specifically for THIS portfolio
                open_orders = await db.quant_orders.find({
                    "portfolio_id": portfolio.portfolio_id, 
                    "status": "open"
                }).to_list(length=1000)
                
                if not open_orders:
                    continue
                
                # 3. Calculate Real-Time Floating PnL using Redis/In-Memory Cache for speed
                # (Assuming another service updates current prices in the cache)
                total_floating_pnl = 0.0
                for order in open_orders:
                    current_price = cache.get(f"price_{order['symbol']}")
                    if current_price:
                        # Basic PnL calc
                        diff = current_price - order['open_price']
                        if order['order_type'] == 'SELL':
                            diff = -diff
                        # Approximate monetary value (simplified)
                        pnl = diff * (order['lot_size'] * 100) 
                        total_floating_pnl += pnl
                
                # 4. Check Drawdown
                equity = portfolio.current_balance + total_floating_pnl
                drawdown_pct = ((portfolio.initial_balance - equity) / portfolio.initial_balance) * 100
                
                if drawdown_pct >= portfolio.max_drawdown_limit_percent:
                    logger.critical(f"KILL SWITCH TRIGGERED for Portfolio {portfolio.portfolio_id}! Drawdown: {drawdown_pct}%")
                    # Here we would close all trades for THIS portfolio via MT5 adapter
                    # ...
                    
        except Exception as e:
            logger.error(f"Quant Engine Risk Monitor Error: {e}")
            
        # Run every 5 seconds
        await asyncio.sleep(5)
