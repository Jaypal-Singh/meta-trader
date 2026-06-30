import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Network, Loader2, ShieldCheck, Cpu, Target, TrendingUp, Activity, AlertTriangle, Zap, ArrowRightLeft, Shield, BarChart3 } from 'lucide-react';
import API_URL from '../config/api';

const API_BASE = `${API_URL}/api/trading/strategies/performance`;
const getToken = () => localStorage.getItem('token');
const authHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${getToken()}`
});

const StrategiesPage = () => {
  const navigate = useNavigate();
  const [performanceData, setPerformanceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPerformance = useCallback(async () => {
    const token = getToken();
    if (!token) {
      navigate('/login');
      return;
    }
    try {
      const res = await fetch(API_BASE, { headers: authHeaders() });
      if (res.status === 401) {
        localStorage.removeItem('token');
        navigate('/login');
        return;
      }
      if (!res.ok) throw new Error('Failed to fetch strategy performance');
      const data = await res.json();
      setPerformanceData(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchPerformance();
  }, [fetchPerformance]);

  if (loading) {
    return (
      <div className="flex flex-col h-full w-full items-center justify-center bg-gray-50 dark:bg-[#0f172a]">
        <Loader2 size={32} className="animate-spin text-blue-500 mb-4" />
        <p className="text-gray-500 dark:text-gray-400 font-medium">Calculating live performance metrics...</p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">Analyzing the last 1000 candles for your portfolio.</p>
      </div>
    );
  }

  const renderPerformanceTable = (strategyKey) => {
    if (!performanceData || !performanceData[strategyKey] || performanceData[strategyKey].length === 0) {
      return (
        <div className="p-4 text-center text-sm font-medium text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-[#0f172a] rounded-xl border border-dashed border-gray-200 dark:border-gray-800">
          No stocks currently assigned to this strategy. Configure them in your Watchlist.
        </div>
      );
    }

    return (
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800 text-xs uppercase tracking-wider text-gray-400">
              <th className="py-3 px-4 font-bold">Symbol</th>
              <th className="py-3 px-4 font-bold">Timeframe</th>
              <th className="py-3 px-4 font-bold">Bot Status</th>
              <th className="py-3 px-4 font-bold">Win Rate</th>
              <th className="py-3 px-4 font-bold">Trades</th>
            </tr>
          </thead>
          <tbody>
            {performanceData[strategyKey].map((item, idx) => {
              const acc = item.accuracy;
              const hasData = acc && acc.total > 0;
              const winRateColor = !hasData ? 'text-gray-400' : (acc.win_rate >= 50 ? 'text-emerald-500' : 'text-red-500');
              
              return (
                <tr key={idx} className="border-b border-gray-50 dark:border-gray-800/50 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors">
                  <td className="py-3 px-4 font-bold text-gray-900 dark:text-white flex items-center gap-2">
                    {item.symbol}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-[10px] font-bold px-2 py-1 rounded bg-indigo-50 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400">
                      {item.timeframe}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {item.autotrade ? (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-500"><div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>ACTIVE</span>
                    ) : (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-gray-400"><div className="w-1.5 h-1.5 rounded-full bg-gray-400"></div>PAUSED</span>
                    )}
                  </td>
                  <td className={`py-3 px-4 font-bold ${winRateColor}`}>
                    {hasData ? `${acc.win_rate}%` : 'N/A'}
                  </td>
                  <td className="py-3 px-4 text-xs font-semibold text-gray-500 dark:text-gray-400">
                    {hasData ? (
                      <span title={`Wins: ${acc.wins} | Losses: ${acc.losses}`}>
                        {acc.total} (W:{acc.wins}/L:{acc.losses})
                      </span>
                    ) : '-'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full w-full bg-gray-50 dark:bg-[#0f172a] transition-colors duration-200 overflow-y-auto">
      {/* ─── Header ─── */}
      <div className="flex-none bg-white dark:bg-[#1e293b] border-b border-gray-100 dark:border-gray-800">
        <div className="flex items-center justify-between px-6 pt-6 pb-4">
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
            <Target className="text-indigo-500" size={24} />
            Strategies & Performance
          </h1>
        </div>
      </div>

      <div className="flex-1 p-6 space-y-8 max-w-6xl mx-auto w-full">
        {error && (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm font-bold rounded-xl border border-red-100 dark:border-red-900/50">
            {error}
          </div>
        )}

        <div className="mb-4">
          <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed max-w-4xl">
            This dashboard provides detailed documentation on when to use each trading engine and displays live historical performance metrics based on your current Watchlist configuration. To change a stock's strategy, click the gear icon in the Watchlist panel.
          </p>
        </div>

        {/* ─── Spirit Pro Section ─── */}
        <div className="bg-white dark:bg-[#1e293b] rounded-3xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-lg">
          <div className="p-6 border-b border-gray-100 dark:border-gray-800">
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-xl bg-blue-500 text-white shadow-lg shadow-blue-500/30">
                <ShieldCheck size={28} />
              </div>
              <div>
                <h3 className="text-2xl font-extrabold text-gray-900 dark:text-white">Spirit Pro v2.0</h3>
                <span className="text-xs font-bold uppercase tracking-wider text-blue-500 dark:text-blue-400">Trend & Momentum Engine</span>
              </div>
            </div>
            
            <div className="prose dark:prose-invert max-w-none text-sm text-gray-600 dark:text-gray-300">
              <p>
                <strong>Spirit Pro</strong> is a robust trend-following algorithm designed for strong directional markets. It utilizes a combination of moving average crossovers (EMA 21, 50, 200) and MACD momentum confirmation to identify high-probability swing trades.
              </p>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-blue-50 dark:bg-blue-900/10 p-4 rounded-xl border border-blue-100 dark:border-blue-900/30">
                  <h4 className="flex items-center gap-2 font-bold text-blue-700 dark:text-blue-400 mb-2">
                    <TrendingUp size={16} /> When to Use
                  </h4>
                  <ul className="list-disc pl-5 space-y-1 text-blue-600/80 dark:text-blue-300/80 text-xs">
                    <li>Highly trending market conditions.</li>
                    <li>During high-volume sessions (London / New York overlaps).</li>
                    <li>Major currency pairs (EURUSD, GBPUSD) or directional indices.</li>
                    <li>Best timeframes: H1, H4, D1.</li>
                  </ul>
                </div>
                <div className="bg-orange-50 dark:bg-orange-900/10 p-4 rounded-xl border border-orange-100 dark:border-orange-900/30">
                  <h4 className="flex items-center gap-2 font-bold text-orange-700 dark:text-orange-400 mb-2">
                    <AlertTriangle size={16} /> When to Avoid
                  </h4>
                  <ul className="list-disc pl-5 space-y-1 text-orange-600/80 dark:text-orange-300/80 text-xs">
                    <li>Ranging or sideways markets (whipsaw risk).</li>
                    <li>Low liquidity environments (Asian session for some pairs).</li>
                    <li>Extreme news events causing erratic spikes without trend.</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
          
          <div className="p-0">
            {renderPerformanceTable('spirit')}
          </div>
        </div>

        {/* ─── Soul Section ─── */}
        <div className="bg-white dark:bg-[#1e293b] rounded-3xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-lg">
          <div className="p-6 border-b border-gray-100 dark:border-gray-800">
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-xl bg-emerald-500 text-white shadow-lg shadow-emerald-500/30">
                <Cpu size={28} />
              </div>
              <div>
                <h3 className="text-2xl font-extrabold text-gray-900 dark:text-white">Soul</h3>
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-500 dark:text-emerald-400">Swing VP Pro Engine</span>
              </div>
            </div>
            
            <div className="prose dark:prose-invert max-w-none text-sm text-gray-600 dark:text-gray-300">
              <p>
                <strong>Soul</strong> is based on the <strong>Swing VP Pro</strong> algorithm. It detects completed price swings using Pivot High/Low detection and calculates the Volume Profile (Point of Control) for each swing to find High Volume Node (HVN) zones.
              </p>

              {/* How It Works */}
              <div className="mt-4 bg-slate-50 dark:bg-slate-900/30 p-4 rounded-xl border border-slate-200 dark:border-slate-800">
                <h4 className="flex items-center gap-2 font-bold text-slate-700 dark:text-slate-300 mb-3">
                  <Zap size={16} /> How It Works
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400 mb-2 flex items-center gap-1">
                      <span className="w-4 h-4 rounded bg-emerald-500 text-white flex items-center justify-center text-[9px]">▲</span>
                      BUY Signal
                    </p>
                    <ol className="list-decimal pl-5 space-y-1 text-[11px] text-gray-600 dark:text-gray-400">
                      <li>A <strong>Pivot Low</strong> is detected (lowest low in a 5-bar window).</li>
                      <li>The previous pivot must have been a Pivot High (Alternation rule).</li>
                      <li>A High-to-Low swing is now complete.</li>
                      <li>Buy at the bottom (close of the confirmation bar).</li>
                    </ol>
                  </div>
                  <div>
                    <p className="text-xs font-bold text-red-500 dark:text-red-400 mb-2 flex items-center gap-1">
                      <span className="w-4 h-4 rounded bg-red-500 text-white flex items-center justify-center text-[9px]">▼</span>
                      SELL Signal
                    </p>
                    <ol className="list-decimal pl-5 space-y-1 text-[11px] text-gray-600 dark:text-gray-400">
                      <li>A <strong>Pivot High</strong> is detected (highest high in a 5-bar window).</li>
                      <li>The previous pivot must have been a Pivot Low (Alternation rule).</li>
                      <li>A Low-to-High swing is now complete.</li>
                      <li>Sell at the top (close of the confirmation bar).</li>
                    </ol>
                  </div>
                </div>
              </div>

              {/* Anti-Cluster Rules */}
              <div className="mt-4 bg-indigo-50 dark:bg-indigo-900/10 p-4 rounded-xl border border-indigo-100 dark:border-indigo-900/30">
                <h4 className="flex items-center gap-2 font-bold text-indigo-700 dark:text-indigo-400 mb-2">
                  <Shield size={16} /> Anti-Cluster Protection
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="flex items-start gap-2">
                    <ArrowRightLeft size={14} className="text-indigo-500 mt-0.5 flex-shrink-0" />
                    <p className="text-[11px] text-gray-600 dark:text-gray-400"><strong>Swing Alternation:</strong> BUY and SELL signals must alternate. The algorithm strictly requires a Pivot High before a new Pivot Low can trigger a buy.</p>
                  </div>
                </div>
              </div>

              {/* TP/SL */}
              <div className="mt-4 bg-emerald-50 dark:bg-emerald-900/10 p-4 rounded-xl border border-emerald-100 dark:border-emerald-900/30">
                <h4 className="flex items-center gap-2 font-bold text-emerald-700 dark:text-emerald-400 mb-2">
                  <Target size={16} /> Take Profit & Stop Loss
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] text-gray-600 dark:text-gray-400">
                  <div><strong>TP (Take Profit):</strong> Entry ± 2× ATR(14). Dynamic target based on recent volatility.</div>
                  <div><strong>SL (Stop Loss):</strong> Entry ∓ 1× ATR(14). Strict risk management.</div>
                </div>
              </div>

              {/* Indicators */}
              <div className="mt-4 bg-blue-50 dark:bg-blue-900/10 p-4 rounded-xl border border-blue-100 dark:border-blue-900/30">
                <h4 className="flex items-center gap-2 font-bold text-blue-700 dark:text-blue-400 mb-2">
                  <BarChart3 size={16} /> Analytics
                </h4>
                <div className="flex flex-wrap gap-2">
                  <span className="px-2 py-1 rounded-full text-[10px] font-bold bg-blue-400/20 text-blue-600 dark:text-blue-400 border border-blue-300/40">Volume Profile (12 rows)</span>
                  <span className="px-2 py-1 rounded-full text-[10px] font-bold bg-yellow-400/20 text-yellow-600 dark:text-yellow-400 border border-yellow-300/40">Point of Control (POC)</span>
                  <span className="px-2 py-1 rounded-full text-[10px] font-bold bg-purple-400/20 text-purple-600 dark:text-purple-400 border border-purple-300/40">ATR (14)</span>
                </div>
                <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-2">Calculates volume distribution per swing to identify institutional interest levels.</p>
              </div>

            </div>
          </div>
          
          <div className="p-0">
            {renderPerformanceTable('soul')}
          </div>
        </div>

        {/* ─── Pulse Section ─── */}
        <div className="bg-white dark:bg-[#1e293b] rounded-3xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-lg mt-8">
          <div className="p-6 border-b border-gray-100 dark:border-gray-800">
            <div className="flex items-center gap-4 mb-4">
              <div className="p-3 rounded-xl bg-purple-500 text-white shadow-lg shadow-purple-500/30">
                <Zap size={28} />
              </div>
              <div>
                <h3 className="text-2xl font-extrabold text-gray-900 dark:text-white">Pulse</h3>
                <span className="text-xs font-bold uppercase tracking-wider text-purple-500 dark:text-purple-400">Scalping Engine (M5/M15)</span>
              </div>
            </div>
            
            <div className="prose dark:prose-invert max-w-none text-sm text-gray-600 dark:text-gray-300">
              <p>
                <strong>Pulse</strong> is a high-frequency scalping algorithm optimized for short timeframes (M5, M15). It capitalizes on rapid mean-reversion using Bollinger Bands and Fast RSI. It is highly effective on pairs like EURUSD that frequently bounce between ranges.
              </p>

              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-purple-50 dark:bg-purple-900/10 p-4 rounded-xl border border-purple-100 dark:border-purple-900/30">
                  <h4 className="flex items-center gap-2 font-bold text-purple-700 dark:text-purple-400 mb-2">
                    <Target size={16} /> How It Works
                  </h4>
                  <ul className="list-disc pl-5 space-y-1 text-purple-600/80 dark:text-purple-300/80 text-xs">
                    <li><strong>BUY:</strong> Price pierces Lower Bollinger Band & RSI(7) &lt; 30.</li>
                    <li><strong>SELL:</strong> Price pierces Upper Bollinger Band & RSI(7) &gt; 70.</li>
                    <li><strong>TP/SL:</strong> Tight dynamic exits using 1.5x/1.0x ATR.</li>
                    <li>Requires strict signal alternation (Buy → Sell → Buy).</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
          
          <div className="p-0">
            {renderPerformanceTable('pulse')}
          </div>
        </div>

      </div>
    </div>
  );
};

export default StrategiesPage;
