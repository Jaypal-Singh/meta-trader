import React, { useState, useEffect } from 'react';
import { Search, Plus, Filter, Bot } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import API_URL from '../config/api';

const WatchlistList = () => {
  const navigate = useNavigate();
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [autotradeSymbols, setAutotradeSymbols] = useState([]);

  const getToken = () => localStorage.getItem('token');
  const authHeaders = () => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${getToken()}`
  });

  const fetchAutotradeConfig = async () => {
    try {
      const res = await fetch(`${API_URL}/api/trading/autotrade`, {
        headers: authHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setAutotradeSymbols(data.autotrade_symbols || []);
      }
    } catch (err) {
      console.error("Error fetching autotrade config", err);
    }
  };

  const toggleAutotrade = async (e, symbol) => {
    e.stopPropagation(); // prevent navigating to chart
    try {
      const res = await fetch(`${API_URL}/api/trading/autotrade`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ symbol })
      });
      if (res.ok) {
        const data = await res.json();
        setAutotradeSymbols(data.autotrade_symbols || []);
      }
    } catch (err) {
      console.error("Error toggling autotrade", err);
    }
  };

  const fetchWatchlist = async () => {
    try {
      const response = await fetch(`${API_URL}/api/trading/watchlist`);
      if (!response.ok) {
        throw new Error('Failed to fetch from MT5 Backend');
      }
      const data = await response.json();
      setStocks(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAutotradeConfig();
    fetchWatchlist();
    // Poll every 5 seconds, but pause polling if searching
    let interval;
    if (!isSearching) {
      interval = setInterval(fetchWatchlist, 2000);
    }
    return () => clearInterval(interval);
  }, [isSearching]);

  const handleSearch = async (e) => {
    const q = e.target.value;
    setSearchQuery(q);
    if (q.length < 2) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/trading/search?q=${q}`);
      const data = await res.json();
      setSearchResults(data);
    } catch (err) {
      console.error(err);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleAddSymbol = async (symbol) => {
    try {
      await fetch(`${API_URL}/api/trading/watchlist/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol })
      });
      setIsSearching(false);
      setSearchQuery('');
      setSearchResults([]);
      // Instantly refresh data
      await fetchWatchlist();
    } catch (err) {
      console.error("Error adding symbol", err);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#f8f9fa] dark:bg-[#0f172a] transition-colors duration-200">
      {/* Header */}
      <div className="flex-none bg-white dark:bg-[#1e293b] px-4 pt-6 pb-2 transition-colors duration-200">
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-2xl font-bold text-[#0f172a] dark:text-gray-100">Watchlist</h1>
          <div className="flex space-x-4 text-gray-500 dark:text-gray-400">
            <Search size={18} className="cursor-pointer hover:text-gray-800 dark:hover:text-gray-200" onClick={() => setIsSearching(true)} />
          </div>
        </div>
      </div>

      {/* Watchlist Tabs */}
      <div className="flex-none bg-white dark:bg-[#1e293b] border-b border-gray-200 dark:border-gray-800 flex justify-between items-center px-4 pt-3 transition-colors duration-200">
        <div className="flex space-x-6 text-sm font-bold">
          <span className="text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 pb-2 flex items-center">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-600 dark:bg-blue-400 mr-2"></span> Watchlist 1
          </span>
          <span className="text-gray-400 dark:text-gray-500 pb-2">new</span>
        </div>
        <div className="flex space-x-4 pb-2">
          <Plus size={18} className="text-blue-500 dark:text-blue-400 cursor-pointer" />
          <Filter size={18} className="text-gray-400 dark:text-gray-500 cursor-pointer" />
        </div>
      </div>

      {/* Live Banner */}
      <div className="flex-none bg-[#e8f8f5] dark:bg-emerald-900/20 px-4 py-2 flex items-center text-xs font-bold text-emerald-600 dark:text-emerald-400 transition-colors duration-200">
        <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse"></span>
        LIVE - Market data streaming
      </div>

      {/* Stock List */}
      <div className="flex-1 overflow-y-auto bg-white dark:bg-[#1e293b] relative transition-colors duration-200">
        {isSearching && (
          <div className="absolute inset-0 bg-white dark:bg-[#1e293b] z-10 flex flex-col transition-colors duration-200">
            <div className="p-4 border-b border-gray-200 dark:border-gray-800 flex items-center">
              <input 
                type="text" 
                placeholder="Search symbol (e.g. AAPL, EURUSD)"
                className="flex-1 bg-gray-100 dark:bg-[#0f172a] dark:text-white rounded-lg px-4 py-2 text-sm outline-none transition-colors duration-200"
                value={searchQuery}
                onChange={handleSearch}
                autoFocus
              />
              <button 
                onClick={() => setIsSearching(false)}
                className="ml-4 text-sm font-bold text-blue-600 dark:text-blue-400"
              >
                Cancel
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {searchLoading && <div className="p-4 text-center text-sm text-gray-500 dark:text-gray-400">Searching...</div>}
              {searchResults.map((res, i) => (
                <div key={i} className="flex justify-between items-center p-4 border-b border-gray-100 dark:border-gray-800 cursor-pointer hover:bg-gray-50 dark:hover:bg-[#0f172a] transition-colors duration-200" onClick={() => handleAddSymbol(res.name)}>
                  <div>
                    <div className="font-bold text-gray-800 dark:text-gray-200">{res.name}</div>
                    <div className="text-xs text-gray-400 dark:text-gray-500">{res.description}</div>
                  </div>
                  <Plus size={18} className="text-blue-500 dark:text-blue-400" />
                </div>
              ))}
            </div>
          </div>
        )}

        {!isSearching && loading && stocks.length === 0 && (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400 font-bold">Connecting to MetaTrader 5...</div>
        )}
        {error && (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm font-bold m-4 rounded-xl border border-red-100 dark:border-red-900/50">
            MT5 Connection Error: {error}. Make sure MetaTrader 5 is running on this PC.
          </div>
        )}
        {stocks.map((stock, i) => (
          <div 
            key={i} 
            onClick={() => navigate(`/chart/${stock.name}`)}
            className="flex justify-between items-center p-4 border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-[#0f172a] cursor-pointer transition-colors duration-200"
          >
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <span className="font-bold text-gray-800 dark:text-gray-200 text-sm">{stock.name}</span>
                <span className="text-[9px] bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 px-1.5 py-0.5 rounded font-bold">{stock.tag}</span>
              </div>
              <span className="text-xs text-gray-400 dark:text-gray-500 font-medium">{stock.sub}</span>
            </div>
            <div className="flex items-center space-x-4 text-right">
              <div>
                <div className={`font-bold ${stock.up ? 'text-emerald-500' : 'text-red-500'} text-sm mb-0.5 flex items-center justify-end`}>
                  {stock.price}
                  <span className="ml-1 text-[10px]">{stock.up ? '▲' : '▼'}</span>
                </div>
                <span className="text-xs text-gray-400 dark:text-gray-500 font-medium">
                  {stock.change > 0 ? '+' : ''}{stock.change} ({stock.change > 0 ? '+' : ''}{stock.pct}%)
                </span>
              </div>
              <button 
                onClick={(e) => toggleAutotrade(e, stock.name)}
                className={`p-2 rounded-full transition-colors ${
                  autotradeSymbols.includes(stock.name) 
                    ? 'bg-blue-100 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.3)]' 
                    : 'bg-gray-100 text-gray-400 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-500 dark:hover:bg-gray-700'
                }`}
                title={autotradeSymbols.includes(stock.name) ? "Auto-Trade: ON" : "Auto-Trade: OFF"}
              >
                <Bot size={16} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default WatchlistList;
