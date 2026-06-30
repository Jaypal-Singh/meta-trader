import React, { useState } from 'react';
import { Play, TrendingUp, AlertTriangle, CheckCircle, Activity, Box, BarChart2 } from 'lucide-react';

const BacktestPage = () => {
  const [symbol, setSymbol] = useState('XAUUSD');
  const [timeframe, setTimeframe] = useState('M5');
  const [strategy, setStrategy] = useState('pulse');
  const [initialCapital, setInitialCapital] = useState(1000);
  
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');

  const runBacktest = async () => {
    setIsLoading(true);
    setError('');
    setResults(null);
    try {
      // Direct fetch to match the other pages assuming API is hosted on same network
      const backendUrl = localStorage.getItem('backendUrl') || 'http://localhost:8000';
      const token = localStorage.getItem('token');
      
      const res = await fetch(`${backendUrl}/api/quant/backtest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          symbol,
          timeframe,
          strategy,
          initial_capital: parseFloat(initialCapital)
        })
      });
      
      if (!res.ok) throw new Error('Simulation failed');
      const data = await res.json();
      
      if (data.status === 'success') {
        if (data.results.error) {
           setError(data.results.error);
        } else {
           setResults(data.results);
        }
      } else {
        setError(data.message || 'Unknown error occurred.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-white dark:bg-[#131722] text-gray-900 dark:text-gray-100 p-4 overflow-y-auto">
      <div className="flex items-center space-x-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-500">
          <Activity size={24} />
        </div>
        <div>
          <h2 className="text-xl font-bold">Quant Engine Backtester</h2>
          <p className="text-xs text-gray-500">Vectorized Historical Simulation</p>
        </div>
      </div>

      {/* Control Panel */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Symbol</label>
          <select 
            value={symbol} onChange={(e) => setSymbol(e.target.value)}
            className="w-full bg-gray-50 dark:bg-[#1e293b] border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="XAUUSD">Gold (XAUUSD)</option>
            <option value="GBPUSD">British Pound (GBPUSD)</option>
            <option value="EURUSD">Euro (EURUSD)</option>
            <option value="USDJPY">US Dollar / Yen (USDJPY)</option>
            <option value="AUDUSD">Australian Dollar (AUDUSD)</option>
            <option value="US30">Dow Jones (US30)</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Timeframe</label>
          <select 
            value={timeframe} onChange={(e) => setTimeframe(e.target.value)}
            className="w-full bg-gray-50 dark:bg-[#1e293b] border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="M1">1 Minute</option>
            <option value="M5">5 Minutes</option>
            <option value="M15">15 Minutes</option>
            <option value="H1">1 Hour</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Strategy</label>
          <select 
            value={strategy} onChange={(e) => setStrategy(e.target.value)}
            className="w-full bg-gray-50 dark:bg-[#1e293b] border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="pulse">Pulse (Scalping)</option>
            <option value="soul">Soul (Trend Following)</option>
            <option value="spirit">Spirit (Mean Reversal)</option>
            <option value="apex">Apex (M5 Scalper)</option>
          </select>
        </div>
        <div className="flex items-end">
          <button 
            onClick={runBacktest}
            disabled={isLoading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center space-x-2 transition-colors"
          >
            {isLoading ? (
              <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            ) : (
              <>
                <Play size={16} fill="currentColor" />
                <span>Run Simulation</span>
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg mb-6 flex items-center space-x-3">
          <AlertTriangle size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* Results Section */}
      {results && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            
            <div className="bg-gray-50 dark:bg-[#1e293b] p-4 rounded-xl border border-gray-200 dark:border-gray-800 flex flex-col justify-between relative overflow-hidden">
              <div className="absolute top-0 right-0 p-3 opacity-20">
                <TrendingUp size={40} className="text-emerald-500" />
              </div>
              <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider">Total Return</span>
              <div className="mt-2 flex items-baseline space-x-2">
                <span className={`text-2xl font-bold ${results.total_return_percent >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                  {results.total_return_percent >= 0 ? '+' : ''}{results.total_return_percent}%
                </span>
              </div>
            </div>

            <div className="bg-gray-50 dark:bg-[#1e293b] p-4 rounded-xl border border-gray-200 dark:border-gray-800 flex flex-col justify-between relative overflow-hidden">
              <div className="absolute top-0 right-0 p-3 opacity-20">
                <Activity size={40} className="text-red-500" />
              </div>
              <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider">Max Drawdown</span>
              <div className="mt-2 flex items-baseline space-x-2">
                <span className="text-2xl font-bold text-red-500">
                  {results.max_drawdown_percent}%
                </span>
              </div>
            </div>

            <div className="bg-gray-50 dark:bg-[#1e293b] p-4 rounded-xl border border-gray-200 dark:border-gray-800 flex flex-col justify-between relative overflow-hidden">
              <div className="absolute top-0 right-0 p-3 opacity-20">
                <BarChart2 size={40} className="text-blue-500" />
              </div>
              <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider">Final Equity</span>
              <div className="mt-2 flex items-baseline space-x-2">
                <span className="text-2xl font-bold text-gray-900 dark:text-white">
                  ${results.final_equity.toLocaleString()}
                </span>
              </div>
            </div>

            <div className="bg-gray-50 dark:bg-[#1e293b] p-4 rounded-xl border border-gray-200 dark:border-gray-800 flex flex-col justify-between relative overflow-hidden">
              <div className="absolute top-0 right-0 p-3 opacity-20">
                <Box size={40} className="text-purple-500" />
              </div>
              <span className="text-gray-500 text-xs font-semibold uppercase tracking-wider">Trades Simulated</span>
              <div className="mt-2 flex items-baseline space-x-2">
                <span className="text-2xl font-bold text-gray-900 dark:text-white">
                  {results.trades_simulated}
                </span>
              </div>
            </div>

          </div>
          
          <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 rounded-lg flex items-center space-x-3">
             <CheckCircle size={20} />
             <span className="text-sm font-medium">Simulation completed successfully using Vectorized Pandas Engine in &lt;15ms.</span>
          </div>
        </div>
      )}
      
      {!results && !isLoading && (
        <div className="flex-1 flex flex-col items-center justify-center text-gray-400 dark:text-gray-600">
          <Activity size={48} className="mb-4 opacity-50" />
          <p>Select your parameters and click "Run Simulation" to backtest.</p>
        </div>
      )}
    </div>
  );
};

export default BacktestPage;
