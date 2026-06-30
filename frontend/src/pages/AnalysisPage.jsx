import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Target, Activity, Loader2, RefreshCw } from 'lucide-react';
import API_URL from '../config/api';

const AnalysisPage = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAnalysis = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`${API_URL}/api/trading/trade_analysis`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Failed to fetch analysis data');
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysis();
  }, []);

  // Aggregate Data: Only CLOSED trades.
  // Group by: Symbol -> { Strategy -> { Timeframe -> stats } }
  const aggregated = {};

  const safeData = Array.isArray(data) ? data : [];
  safeData.filter(t => t && t.action === 'CLOSE').forEach(trade => {
    const sym = trade.symbol || 'UNKNOWN';
    const strat = trade.strategy || 'unknown';
    const tf = trade.timeframe || 'unknown';
    const pnl = parseFloat(trade.pnl) || 0;
    
    if (!aggregated[sym]) aggregated[sym] = {};
    if (!aggregated[sym][strat]) aggregated[sym][strat] = {};
    if (!aggregated[sym][strat][tf]) {
      aggregated[sym][strat][tf] = { trades: 0, wins: 0, losses: 0, total_pnl: 0 };
    }
    
    const stats = aggregated[sym][strat][tf];
    stats.trades += 1;
    stats.total_pnl += pnl;
    if (pnl >= 0) stats.wins += 1;
    else stats.losses += 1;
  });

  return (
    <div className="flex flex-col h-full w-full bg-gray-50 dark:bg-[#0f172a] overflow-hidden transition-colors duration-200">
      <div className="flex-none bg-white dark:bg-[#1e293b] px-6 py-5 flex items-center justify-between border-b border-gray-200 dark:border-gray-800 shadow-sm z-10">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white tracking-tight">Strategy Analysis</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400 font-medium mt-1">Discover which strategy and timeframe works best for each stock.</p>
        </div>
        <button 
          onClick={fetchAnalysis}
          className="flex items-center justify-center p-2 rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors"
        >
          <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 md:p-6 pb-24">
        {loading && data.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500">
            <Loader2 size={32} className="animate-spin text-blue-500 mb-4" />
            <p className="font-bold">Analyzing your trade data...</p>
          </div>
        ) : error ? (
          <div className="bg-red-50 dark:bg-red-900/20 text-red-600 p-4 rounded-xl border border-red-200 font-bold">
            Error: {error}
          </div>
        ) : Object.keys(aggregated).length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 space-y-3">
            <Activity size={48} className="text-gray-300 dark:text-gray-700" />
            <p className="font-bold">No closed trades found yet.</p>
            <p className="text-xs">Once the bot closes trades, the analysis will appear here.</p>
          </div>
        ) : (
          <div className="space-y-8">
            {Object.keys(aggregated).map(symbol => (
              <div key={symbol} className="bg-white dark:bg-[#131722] rounded-2xl shadow-sm border border-gray-200 dark:border-gray-800 overflow-hidden">
                <div className="px-6 py-4 bg-gray-50 dark:bg-[#1e293b] border-b border-gray-200 dark:border-gray-800">
                  <h2 className="text-lg font-black text-gray-900 dark:text-white flex items-center space-x-2">
                    <Target size={18} className="text-blue-500" />
                    <span>{symbol}</span>
                  </h2>
                </div>
                <div className="p-4 md:p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {Object.keys(aggregated[symbol]).map(strat => (
                    Object.keys(aggregated[symbol][strat]).map(tf => {
                      const stats = aggregated[symbol][strat][tf];
                      const winRate = stats.trades > 0 ? ((stats.wins / stats.trades) * 100) : 0;
                      const isProfitable = stats.total_pnl >= 0;
                      
                      return (
                        <div key={`${strat}-${tf}`} className="relative p-5 rounded-xl border border-gray-100 dark:border-gray-700/50 bg-gray-50/50 dark:bg-gray-800/30 hover:border-blue-300 dark:hover:border-blue-500/50 transition-colors">
                          <div className="flex justify-between items-start mb-4">
                            <div>
                              <span className="inline-block px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-400 mb-1">
                                {strat}
                              </span>
                              <div className="text-xl font-black text-gray-900 dark:text-white">{tf}</div>
                            </div>
                            <div className={`flex flex-col items-end ${isProfitable ? 'text-emerald-500' : 'text-red-500'}`}>
                              <span className="text-xs font-bold uppercase tracking-wider text-gray-400">NET P&L</span>
                              <span className="text-lg font-black flex items-center">
                                {isProfitable ? '+' : ''}${stats.total_pnl.toFixed(2)}
                              </span>
                            </div>
                          </div>
                          
                          <div className="space-y-2">
                            <div className="flex justify-between text-xs font-bold text-gray-500 dark:text-gray-400">
                              <span>Win Rate</span>
                              <span>{winRate.toFixed(1)}%</span>
                            </div>
                            
                            <div className="h-2 w-full bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden flex">
                               <div 
                                  className="h-full bg-emerald-500 transition-all duration-1000" 
                                  style={{ width: `${winRate}%` }} 
                               />
                               <div 
                                  className="h-full bg-red-500 transition-all duration-1000" 
                                  style={{ width: `${100 - winRate}%` }} 
                               />
                            </div>
                            
                            <div className="flex justify-between text-[10px] font-bold mt-2">
                               <span className="text-emerald-500">{stats.wins} W</span>
                               <span className="text-gray-400">{stats.trades} Trades</span>
                               <span className="text-red-500">{stats.losses} L</span>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalysisPage;
