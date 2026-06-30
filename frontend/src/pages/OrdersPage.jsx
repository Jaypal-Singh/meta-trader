import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, SlidersHorizontal, LayoutList, RefreshCw,
  Loader2, TrendingUp, CheckCircle2, X
} from 'lucide-react';
import API_URL from '../config/api';

const API_BASE = `${API_URL}/api/orders`;
const getToken = () => localStorage.getItem('token');
const authHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${getToken()}`
});

// ─── Format Helpers ──────────────────────────────────────────────
const formatPrice = (price, symbol) => {
  if (price == null) return '—';
  if (symbol?.includes('JPY')) return price.toFixed(3);
  if (symbol?.includes('XAU')) return price.toFixed(2);
  return price.toFixed(5);
};

const formatPnl = (pnl) => {
  if (pnl == null) return '$0.00';
  const sign = pnl >= 0 ? '+' : '';
  return `${sign}$${pnl.toFixed(2)}`;
};

const formatPnlPct = (pnl, openPrice, lotSize) => {
  if (!openPrice || !lotSize) return '0.00%';
  // Rough percentage for display
  const invested = openPrice * lotSize * 100; // simplified
  if (invested === 0) return '0.00%';
  const pct = (pnl / invested) * 100;
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
};

const formatDate = (isoString) => {
  if (!isoString) return '—';
  const d = new Date(isoString);
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
};

// Group orders by date
const groupByDate = (orders) => {
  const groups = {};
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  orders.forEach(order => {
    const orderDate = new Date(order.open_time);
    orderDate.setHours(0, 0, 0, 0);

    let label;
    if (orderDate.getTime() === today.getTime()) {
      label = 'TODAY';
    } else if (orderDate.getTime() === yesterday.getTime()) {
      label = 'YESTERDAY';
    } else {
      label = orderDate.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase();
    }

    if (!groups[label]) groups[label] = [];
    groups[label].push(order);
  });

  return groups;
};

// Get symbol type tag
const getSymbolTag = (symbol) => {
  if (symbol?.includes('XAU')) return 'COMMODITY';
  if (symbol?.includes('JPY') || symbol?.includes('USD') || symbol?.includes('EUR') || symbol?.includes('GBP')) return 'FOREX';
  if (symbol?.includes('SP') || symbol?.includes('NAS') || symbol?.includes('DJ')) return 'INDEX';
  return 'CFD';
};

// ─── Time Filter Chips ──────────────────────────────────────────
const timeFilters = ['This Week', 'All', 'Today', 'Last 7 Days', 'Last 30 Days'];


// ─── Order Card (matching reference design) ─────────────────────
const OrderCard = ({ order, isOpen, onExit }) => {
  const isBuy = order.order_type === 'BUY';
  const pnl = isOpen ? order.floating_pnl : order.pnl;
  const isProfit = pnl >= 0;
  const netPnl = pnl + (order.commission || 0) + (order.swap || 0);
  const tag = getSymbolTag(order.symbol);
  const currentOrClosePrice = isOpen ? order.current_price : order.close_price;

  return (
    <div className="bg-white dark:bg-[#1e293b] mx-4 mb-3 rounded-2xl border border-gray-100 dark:border-gray-700/40 shadow-sm overflow-hidden transition-all duration-200">
      {/* Top Section: Symbol + Price */}
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-start justify-between">
          {/* Left: Symbol Info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center space-x-2 mb-1">
              <h3 className="text-base font-extrabold text-gray-900 dark:text-white tracking-tight truncate">
                {order.symbol}
              </h3>
              <span className="flex-shrink-0 text-[9px] font-bold bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-1.5 py-0.5 rounded">
                {tag}
              </span>
              <span className="flex-shrink-0 text-[9px] font-bold text-emerald-600 dark:text-emerald-400">
                EXECUTED
              </span>
            </div>
            <p className="text-[11px] text-gray-400 dark:text-gray-500 font-medium mb-1.5">
              SPOT · {tag} {order.strategy && `· STRATEGY: ${order.strategy.toUpperCase()}`} {order.timeframe && `· TF: ${order.timeframe}`}
            </p>
            <div className="flex items-center space-x-2">
              <span className={`text-[11px] font-bold px-2 py-0.5 rounded
                ${isBuy
                  ? 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10'
                  : 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10'
                }`}
              >
                {order.order_type}
              </span>
              <span className="text-[11px] text-gray-400 dark:text-gray-500 font-medium">
                • {order.lot_size} Lot
              </span>
            </div>
          </div>

          {/* Right: Price + P&L */}
          <div className="text-right flex-shrink-0 ml-3">
            <p className="text-base font-extrabold text-gray-900 dark:text-white">
              ${formatPrice(currentOrClosePrice, order.symbol)}
            </p>
            <p className={`text-xs font-bold ${isProfit ? 'text-emerald-500' : 'text-red-500'}`}>
              {formatPnl(pnl)} ({formatPnlPct(pnl, order.open_price, order.lot_size)})
            </p>
          </div>
        </div>
      </div>

      {/* Details Row: AVG, QTY, NET P&L */}
      <div className="px-4 pb-3">
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-gray-50 dark:bg-[#0f172a]/50 rounded-xl px-3 py-2.5">
            <p className="text-[9px] uppercase tracking-wider text-gray-400 dark:text-gray-500 font-bold mb-0.5">AVG</p>
            <p className="text-xs font-bold text-gray-700 dark:text-gray-200 font-mono">
              ${formatPrice(order.open_price, order.symbol)}
            </p>
          </div>
          <div className="bg-gray-50 dark:bg-[#0f172a]/50 rounded-xl px-3 py-2.5">
            <p className="text-[9px] uppercase tracking-wider text-gray-400 dark:text-gray-500 font-bold mb-0.5">LOTS</p>
            <p className="text-xs font-bold text-gray-700 dark:text-gray-200 font-mono">
              {order.lot_size}
            </p>
          </div>
          <div className="bg-gray-50 dark:bg-[#0f172a]/50 rounded-xl px-3 py-2.5">
            <p className="text-[9px] uppercase tracking-wider text-gray-400 dark:text-gray-500 font-bold mb-0.5">NET P&L</p>
            <p className={`text-xs font-bold font-mono ${netPnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
              {formatPnl(netPnl)}
            </p>
          </div>
        </div>
      </div>

      {/* SL/TP Row */}
      {(order.sl || order.tp) && (
        <div className="px-4 pb-3">
          <div className="grid grid-cols-2 gap-2">
            {order.sl && (
              <div className="flex items-center space-x-1.5 text-[10px]">
                <span className="w-1.5 h-1.5 rounded-full bg-red-400"></span>
                <span className="text-gray-400 font-medium">SL:</span>
                <span className="font-bold text-gray-600 dark:text-gray-300 font-mono">{formatPrice(order.sl, order.symbol)}</span>
              </div>
            )}
            {order.tp && (
              <div className="flex items-center space-x-1.5 text-[10px]">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span className="text-gray-400 font-medium">TP:</span>
                <span className="font-bold text-gray-600 dark:text-gray-300 font-mono">{formatPrice(order.tp, order.symbol)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Commission + Swap (small text) */}
      {(order.commission || order.swap || order.comment) && (
        <div className="px-4 pb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-gray-400 dark:text-gray-500">
          {order.commission !== undefined && <span>Commission: {formatPnl(order.commission)}</span>}
          {order.swap !== undefined && <span>Swap: {formatPnl(order.swap)}</span>}
          {order.comment && <span className="truncate w-full mt-1">• {order.comment}</span>}
        </div>
      )}

      {/* Dates & Status Footer */}
      <div className="px-4 pb-3 pt-1 flex flex-col space-y-1 text-[10px] text-gray-400 dark:text-gray-500">
        <div>
          <span>Opened: {new Date(order.open_time).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} at {formatDate(order.open_time)}</span>
        </div>
        {!isOpen && order.close_time && (
          <div className="flex items-center justify-between mt-1">
            <span>Closed: {new Date(order.close_time).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} at {formatDate(order.close_time)}</span>
            <span className={`font-bold ${pnl >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
              {pnl >= 0 ? '✓ Profit' : '✗ Loss'}
            </span>
          </div>
        )}
      </div>

      {/* Action Buttons — only for open orders */}
      {isOpen && (
        <div className="px-4 pb-4 pt-1 flex space-x-3">
          <button className="flex-1 bg-blue-500 hover:bg-blue-600 text-white font-bold text-sm py-3 rounded-xl transition-all active:scale-[0.97] shadow-sm">
            Modify
          </button>
          <button
            onClick={() => onExit && onExit(order)}
            className="flex-1 bg-red-500 hover:bg-red-600 text-white font-bold text-sm py-3 rounded-xl transition-all active:scale-[0.97] shadow-sm"
          >
            Exit
          </button>
        </div>
      )}
    </div>
  );
};


// ─── Main Orders Page ────────────────────────────────────────────
const OrdersPage = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('open');
  const [timeFilter, setTimeFilter] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [orders, setOrders] = useState([]);
  const [summary, setSummary] = useState({ open_count: 0, closed_count: 0, total_open_pnl: 0, total_closed_pnl: 0 });
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState(null);
  const [showSearch, setShowSearch] = useState(false);

  const token = getToken();

  const fetchOrders = useCallback(async () => {
    if (!token) {
      setError('Not logged in');
      setLoading(false);
      return;
    }
    try {
      const [ordersRes, summaryRes] = await Promise.all([
        fetch(`${API_BASE}/?status=${activeTab}`, { headers: authHeaders() }),
        fetch(`${API_BASE}/summary`, { headers: authHeaders() }),
      ]);

      if (ordersRes.status === 401 || summaryRes.status === 401) {
        setError('Session expired. Please login again.');
        setLoading(false);
        return;
      }

      const ordersData = await ordersRes.json();
      const summaryData = await summaryRes.json();
      setOrders(ordersData);
      setSummary(summaryData);
      setError(null);
    } catch (err) {
      setError('Failed to connect to server');
    } finally {
      setLoading(false);
    }
  }, [activeTab, token]);

  useEffect(() => {
    setLoading(true);
    fetchOrders();
  }, [fetchOrders]);

  // Auto-refresh open orders every 5s
  useEffect(() => {
    if (activeTab !== 'open') return;
    const interval = setInterval(fetchOrders, 5000);
    return () => clearInterval(interval);
  }, [activeTab, fetchOrders]);

  const handleExit = async (order) => {
    // Close at current_price (simulated)
    try {
      await fetch(`${API_BASE}/${order.ticket}/close`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ close_price: order.current_price })
      });
      await fetchOrders();
    } catch (e) { /* ignore */ }
  };

  // Filter by time
  const filterByTime = (orders) => {
    if (timeFilter === 'All') return orders;
    const now = new Date();
    let cutoff;
    switch (timeFilter) {
      case 'Today':
        cutoff = new Date(now); cutoff.setHours(0, 0, 0, 0); break;
      case 'This Week':
        cutoff = new Date(now); cutoff.setDate(cutoff.getDate() - cutoff.getDay()); cutoff.setHours(0, 0, 0, 0); break;
      case 'Last 7 Days':
        cutoff = new Date(now); cutoff.setDate(cutoff.getDate() - 7); break;
      case 'Last 30 Days':
        cutoff = new Date(now); cutoff.setDate(cutoff.getDate() - 30); break;
      default: return orders;
    }
    return orders.filter(o => new Date(o.open_time) >= cutoff);
  };

  // Filter by search
  const filterBySearch = (orders) => {
    if (!searchQuery.trim()) return orders;
    const q = searchQuery.toUpperCase();
    return orders.filter(o => o.symbol.includes(q) || o.ticket.includes(q));
  };

  const filteredOrders = filterBySearch(filterByTime(orders));
  const groupedOrders = groupByDate(filteredOrders);
  const dateGroups = Object.keys(groupedOrders);

  return (
    <div className="flex flex-col h-full w-full bg-gray-50 dark:bg-[#0f172a] transition-colors duration-200">

      {/* ─── Header ─── */}
      <div className="flex-none bg-white dark:bg-[#1e293b] border-b border-gray-100 dark:border-gray-800">
        {/* Title Row */}
        <div className="flex items-center justify-between px-4 pt-5 pb-3">
          <h1 className="text-xl font-extrabold text-gray-900 dark:text-white">
            {activeTab === 'open' ? 'Open Orders' : 'Closed Orders'}
          </h1>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowSearch(!showSearch)}
              className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
            >
              <SlidersHorizontal size={18} />
            </button>
            <button className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors">
              <LayoutList size={18} />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="px-4 pb-3">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search e.g. XAUUSD, EURUSD"
              className="w-full pl-9 pr-4 py-2.5 bg-gray-50 dark:bg-[#0f172a] border border-gray-200 dark:border-gray-700 rounded-xl text-sm text-gray-700 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 transition-all"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="px-4 pb-3 flex space-x-0">
          <TabPill
            active={activeTab === 'open'}
            onClick={() => setActiveTab('open')}
            label="Open"
            count={summary.open_count}
          />
          <TabPill
            active={activeTab === 'closed'}
            onClick={() => setActiveTab('closed')}
            label="Closed"
            count={summary.closed_count}
          />
        </div>

        {/* Time Filter Chips */}
        <div className="px-4 pb-3 flex space-x-2 overflow-x-auto no-scrollbar">
          {timeFilters.map(tf => (
            <button
              key={tf}
              onClick={() => setTimeFilter(tf)}
              className={`flex-shrink-0 text-xs font-bold px-3.5 py-1.5 rounded-full border transition-all
                ${timeFilter === tf
                  ? 'bg-blue-500 text-white border-blue-500 shadow-sm'
                  : 'bg-white dark:bg-[#1e293b] text-gray-500 dark:text-gray-400 border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-500/50'
                }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Order Count & Total PNL ─── */}
      <div className="flex-none px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <p className="text-[11px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider">
            {filteredOrders.length} {activeTab === 'open' ? 'ORDERS OPEN' : 'TRADES CLOSED'}
          </p>
          <div className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-bold flex items-center space-x-1">
            <span className="text-gray-500">TOTAL {activeTab === 'open' ? 'FLOATING' : 'PNL'}:</span>
            <span className={
              (activeTab === 'open' ? summary.total_open_pnl : summary.total_closed_pnl) >= 0 
                ? 'text-emerald-500' 
                : 'text-red-500'
            }>
              {formatPnl(activeTab === 'open' ? summary.total_open_pnl : summary.total_closed_pnl)}
            </span>
          </div>
        </div>
        <button
          onClick={fetchOrders}
          className="text-gray-400 hover:text-blue-500 transition-colors"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      {/* ─── Orders List ─── */}
      <div className="flex-1 overflow-y-auto pb-4">
        {loading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={24} className="animate-spin text-blue-500" />
            <span className="ml-2 text-sm text-gray-500 dark:text-gray-400 font-bold">Loading orders...</span>
          </div>
        )}

        {error && (
          <div className="mx-4 p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm font-bold rounded-xl border border-red-100 dark:border-red-900/50">
            {error}
          </div>
        )}

        {!loading && !error && filteredOrders.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 space-y-4">
            <div className="w-16 h-16 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
              {activeTab === 'open'
                ? <TrendingUp size={28} className="text-gray-300 dark:text-gray-600" />
                : <CheckCircle2 size={28} className="text-gray-300 dark:text-gray-600" />
              }
            </div>
            <div className="text-center">
              <p className="text-sm font-bold text-gray-500 dark:text-gray-400">
                {activeTab === 'open' ? 'No Open Positions' : 'No Trade History'}
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                {searchQuery
                  ? `No results for "${searchQuery}"`
                  : activeTab === 'open'
                    ? 'Your active trades will appear here'
                    : 'Your closed trades will appear here'
                }
              </p>
            </div>
          </div>
        )}

        {!loading && !error && dateGroups.map(dateLabel => (
          <div key={dateLabel}>
            {/* Date Group Header */}
            <div className="px-5 py-2 flex items-center space-x-2">
              <div className="w-1 h-4 bg-blue-500 rounded-full"></div>
              <span className="text-[11px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider">
                {dateLabel}
              </span>
            </div>

            {/* Cards */}
            {groupedOrders[dateLabel].map(order => (
              <OrderCard
                key={order.ticket}
                order={order}
                isOpen={activeTab === 'open'}
                onExit={handleExit}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};


// ─── Tab Pill ────────────────────────────────────────────────────
const TabPill = ({ active, onClick, label, count }) => (
  <button
    onClick={onClick}
    className={`flex items-center justify-center space-x-1.5 px-5 py-2.5 text-sm font-bold rounded-full transition-all mr-2
      ${active
        ? 'bg-blue-500 text-white shadow-md shadow-blue-500/20'
        : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
      }`}
  >
    <span>{label}</span>
    {count > 0 && (
      <span className={`text-[10px] font-extrabold
        ${active ? 'text-blue-100' : 'text-gray-400 dark:text-gray-500'}`}
      >
        ({count})
      </span>
    )}
  </button>
);


export default OrdersPage;
