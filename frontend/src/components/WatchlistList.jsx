import React, { useState, useEffect } from 'react';
import { Search, Plus, Filter, Bot, Settings, X, Save } from 'lucide-react';
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
  
  // Settings Modal State
  const [activeSettingsSymbol, setActiveSettingsSymbol] = useState(null);
  const [symbolConfigs, setSymbolConfigs] = useState([]);
  const [savingConfig, setSavingConfig] = useState(false);

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
      const response = await fetch(`${API_URL}/api/trading/watchlist`, {
        headers: authHeaders()
      });
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
    // Poll every 5 seconds, but pause polling if searching or editing config
    let interval;
    if (!isSearching && !activeSettingsSymbol) {
      interval = setInterval(fetchWatchlist, 2000);
    }
    return () => clearInterval(interval);
  }, [isSearching, activeSettingsSymbol]);

  const handleSearch = async (e) => {
    const q = e.target.value;
    setSearchQuery(q);
    if (q.length < 2) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/trading/search?q=${q}`, {
        headers: authHeaders()
      });
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
        headers: authHeaders(),
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
  
  const openSettings = (e, stock) => {
    e.stopPropagation();
    setActiveSettingsSymbol(stock.name);
    
    // Group backend flat configs by strategy for the UI
    const initialGrouped = [];
    const stockConfigs = stock.configs && stock.configs.length > 0 ? stock.configs : [{ strategy: 'spirit', timeframe: 'H1', autotrade: false }];
    
    stockConfigs.forEach(c => {
      // Legacy name migration
      const strat = c.strategy === 'guardeer' ? 'spirit' : (c.strategy === 'bbrsi' ? 'soul' : c.strategy);
      const existing = initialGrouped.find(g => g.strategy === strat && g.autotrade === c.autotrade);
      if (existing) {
        if (!existing.timeframes.includes(c.timeframe)) existing.timeframes.push(c.timeframe);
      } else {
        initialGrouped.push({ strategy: strat, timeframes: [c.timeframe], autotrade: c.autotrade || false });
      }
    });
    setSymbolConfigs(initialGrouped);
  };
  
  const saveSettings = async () => {
    setSavingConfig(true);
    try {
      // Flatten UI grouped configs back to backend format
      const flatConfigs = [];
      symbolConfigs.forEach(g => {
        g.timeframes.forEach(tf => {
          flatConfigs.push({ strategy: g.strategy, timeframe: tf, autotrade: g.autotrade });
        });
      });

      await fetch(`${API_URL}/api/trading/watchlist/config`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ 
          symbol: activeSettingsSymbol,
          configs: flatConfigs
        })
      });
      setActiveSettingsSymbol(null);
      await fetchWatchlist();
    } catch (err) {
      console.error("Error saving config", err);
    } finally {
      setSavingConfig(false);
    }
  };

  const addConfig = () => {
    setSymbolConfigs([...symbolConfigs, { strategy: 'spirit', timeframes: ['H1'], autotrade: false }]);
  };

  const removeConfig = (index) => {
    setSymbolConfigs(symbolConfigs.filter((_, i) => i !== index));
  };
  
  const updateConfig = (index, key, value) => {
    const newConfigs = [...symbolConfigs];
    newConfigs[index] = { ...newConfigs[index], [key]: value };
    setSymbolConfigs(newConfigs);
  };

  const toggleTimeframe = (index, tf) => {
    const newConfigs = [...symbolConfigs];
    const current = newConfigs[index].timeframes || [];
    if (current.includes(tf)) {
      if (current.length > 1) { // prevent removing all
         newConfigs[index].timeframes = current.filter(t => t !== tf);
      }
    } else {
      newConfigs[index].timeframes = [...current, tf];
    }
    setSymbolConfigs(newConfigs);
  };

  return (
    <div className="flex flex-col h-full bg-[#f8f9fa] dark:bg-[#0f172a] transition-colors duration-200 relative">
      {/* Settings Modal */}
      {activeSettingsSymbol && (
        <div className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white dark:bg-[#1e293b] w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden border border-gray-100 dark:border-gray-800">
            <div className="flex justify-between items-center p-4 border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-[#0f172a]">
              <h3 className="font-bold text-gray-900 dark:text-white flex items-center">
                <Settings size={18} className="mr-2 text-blue-500" />
                Configure {activeSettingsSymbol}
              </h3>
              <button onClick={() => setActiveSettingsSymbol(null)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors">
                <X size={20} />
              </button>
            </div>
            
            <div className="p-4 space-y-4 max-h-[60vh] overflow-y-auto">
              {symbolConfigs.map((conf, index) => (
                <div key={index} className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg relative bg-white dark:bg-[#1e293b]">
                  <button onClick={() => removeConfig(index)} className="absolute top-2 right-2 text-red-500 hover:text-red-700">
                    <X size={16} />
                  </button>
                  <label className="block text-xs font-bold text-gray-500 mb-1">Strategy</label>
                  <div className="grid grid-cols-4 gap-1 mb-2">
                    {['spirit', 'soul', 'pulse', 'apex'].map(strat => (
                      <button 
                        key={strat}
                        onClick={() => updateConfig(index, 'strategy', strat)}
                        className={`p-1 rounded text-xs font-semibold border ${conf.strategy === strat ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600' : 'border-transparent bg-gray-100 dark:bg-gray-800 text-gray-600'}`}
                      >
                        {strat}
                      </button>
                    ))}
                  </div>
                  <label className="block text-xs font-bold text-gray-500 mb-1">Timeframe (Select Multiple)</label>
                  <div className="grid grid-cols-4 gap-1 mb-2">
                    {['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1', 'MN'].map(tf => (
                      <button 
                        key={tf}
                        onClick={() => toggleTimeframe(index, tf)}
                        className={`p-1 rounded text-xs font-semibold border ${(conf.timeframes || []).includes(tf) ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600' : 'border-transparent bg-gray-100 dark:bg-gray-800 text-gray-600'}`}
                      >
                        {tf}
                      </button>
                    ))}
                  </div>
                  <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-100 dark:border-gray-700">
                     <label className="text-xs font-bold text-gray-600 dark:text-gray-300">Auto-Trade Enable</label>
                     <input type="checkbox" className="w-4 h-4" checked={conf.autotrade || false} onChange={(e) => updateConfig(index, 'autotrade', e.target.checked)} />
                  </div>
                </div>
              ))}
              <button onClick={addConfig} className="w-full py-2 border-2 border-dashed border-gray-300 dark:border-gray-700 text-sm font-bold text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg">
                + Add Strategy
              </button>
            </div>
            
            <div className="p-4 border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-[#0f172a] flex justify-end">
              <button 
                onClick={saveSettings}
                disabled={savingConfig}
                className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold text-sm transition-colors shadow-lg shadow-blue-500/20 disabled:opacity-70"
              >
                {savingConfig ? 'Saving...' : <><Save size={16} className="mr-2" /> Save Config</>}
              </button>
            </div>
          </div>
        </div>
      )}

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
              <div className="flex flex-wrap items-center mt-1 gap-1">
                {(stock.configs || []).map((conf, idx) => {
                  const stratName = conf.strategy === 'guardeer' ? 'spirit' : (conf.strategy === 'bbrsi' ? 'soul' : conf.strategy);
                  return (
                  <span key={idx} className={`text-[9px] font-bold px-1 py-0.5 rounded border ${
                    stratName === 'soul' 
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-900 dark:bg-emerald-900/20 dark:text-emerald-400' 
                      : stratName === 'pulse' ? 'border-purple-200 bg-purple-50 text-purple-600 dark:border-purple-900 dark:bg-purple-900/20 dark:text-purple-400' 
                      : 'border-blue-200 bg-blue-50 text-blue-600 dark:border-blue-900 dark:bg-blue-900/20 dark:text-blue-400'
                  }`}>
                    {stratName.substring(0,3).toUpperCase()} {conf.timeframe}
                  </span>
                )})}
              </div>
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
              <div className="flex space-x-2">
                <button 
                  onClick={(e) => openSettings(e, stock)}
                  className="p-2 bg-gray-100 text-gray-500 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 rounded-full transition-colors"
                  title="Configure Strategy & Timeframe"
                >
                  <Settings size={16} />
                </button>
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
          </div>
        ))}
      </div>
    </div>
  );
};

export default WatchlistList;
