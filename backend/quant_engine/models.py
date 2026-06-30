from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Portfolio(BaseModel):
    portfolio_id: str
    name: str
    initial_balance: float
    current_balance: float
    max_drawdown_limit_percent: float = 5.0  # Kill switch threshold
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QuantOrder(BaseModel):
    """
    STRICT ISOLATION:
    This order model is completely separate from the live MT5 orders.
    It is used exclusively by the Quant Engine for backtesting and isolated portfolio tracking.
    """
    order_id: str
    portfolio_id: str
    symbol: str
    order_type: str # 'BUY' or 'SELL'
    strategy: str
    timeframe: str
    lot_size: float
    open_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    status: str = "open" # 'open', 'closed'
    pnl: float = 0.0
    open_time: datetime = Field(default_factory=datetime.utcnow)
    close_time: Optional[datetime] = None
    close_price: Optional[float] = None
    comment: str = ""
