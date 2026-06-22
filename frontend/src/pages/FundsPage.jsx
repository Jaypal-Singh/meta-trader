import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Wallet, DollarSign, PlusCircle, ArrowUpRight, TrendingUp, Edit2, Loader2, RefreshCw } from 'lucide-react';
import API_URL from '../config/api';

const API_BASE = `${API_URL}/api/funds`;
const getToken = () => localStorage.getItem('token');
const authHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${getToken()}`
});

const formatMoney = (val) => {
  if (val == null) return '$0.00';
  const sign = val < 0 ? '-' : '';
  return `${sign}$${Math.abs(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const FundsPage = () => {
  const navigate = useNavigate();
  const [funds, setFunds] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editAmount, setEditAmount] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchFunds = useCallback(async () => {
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
      if (!res.ok) throw new Error('Failed to fetch funds');
      const data = await res.json();
      setFunds(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchFunds();
    // Refresh every 5 seconds for live PnL and margin updates
    const interval = setInterval(fetchFunds, 5000);
    return () => clearInterval(interval);
  }, [fetchFunds]);

  const handleEditFunds = async (e) => {
    e.preventDefault();
    const amount = parseFloat(editAmount);
    if (isNaN(amount) || amount < 0) return;

    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/edit`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ amount })
      });
      if (res.ok) {
        await fetchFunds();
        setIsEditing(false);
        setEditAmount('');
      } else {
        throw new Error('Failed to update balance');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading && !funds) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-gray-50 dark:bg-[#0f172a]">
        <Loader2 size={32} className="animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full bg-gray-50 dark:bg-[#0f172a] transition-colors duration-200">
      
      {/* ─── Header ─── */}
      <div className="flex-none bg-white dark:bg-[#1e293b] border-b border-gray-100 dark:border-gray-800">
        <div className="flex items-center justify-between px-6 pt-6 pb-4">
          <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white flex items-center gap-2">
            <Wallet className="text-blue-500" size={24} />
            Funds
          </h1>
          <button
            onClick={fetchFunds}
            className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {error && (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm font-bold rounded-xl border border-red-100 dark:border-red-900/50">
            {error}
          </div>
        )}

        {funds && (
          <>
            {/* Main Equity Card */}
            <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-3xl p-6 text-white shadow-lg shadow-blue-500/20 relative overflow-hidden">
              <div className="absolute top-0 right-0 -mr-8 -mt-8 opacity-10">
                <Wallet size={160} />
              </div>
              <p className="text-blue-100 font-semibold tracking-wide uppercase text-xs mb-1">Total Equity</p>
              <h2 className="text-4xl font-black font-mono tracking-tight mb-6">
                {formatMoney(funds.equity)}
              </h2>

              <div className="flex items-center gap-4">
                <button
                  onClick={() => setIsEditing(true)}
                  className="bg-white text-blue-700 hover:bg-blue-50 font-bold py-2.5 px-5 rounded-xl shadow-sm transition-all flex items-center gap-2 text-sm"
                >
                  <Edit2 size={16} />
                  Edit Balance
                </button>
                <button
                  onClick={() => setIsEditing(true)}
                  className="bg-blue-500/20 hover:bg-blue-500/30 text-white font-bold py-2.5 px-5 rounded-xl transition-all flex items-center gap-2 text-sm backdrop-blur-sm"
                >
                  <PlusCircle size={16} />
                  Add Dummy Funds
                </button>
              </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-4">
              <MetricCard 
                title="Available Margin" 
                value={formatMoney(funds.available_margin)} 
                icon={<DollarSign size={20} />} 
                color="emerald"
              />
              <MetricCard 
                title="Used Margin" 
                value={formatMoney(funds.used_margin)} 
                icon={<Wallet size={20} />} 
                color="blue"
              />
              <MetricCard 
                title="Total Balance" 
                value={formatMoney(funds.balance)} 
                icon={<CheckCircle2 size={20} />} 
                color="gray"
              />
              <MetricCard 
                title="Floating P&L" 
                value={formatMoney(funds.floating_pnl)} 
                icon={funds.floating_pnl >= 0 ? <TrendingUp size={20} /> : <TrendingDown size={20} />} 
                color={funds.floating_pnl >= 0 ? 'emerald' : 'red'}
              />
            </div>
          </>
        )}
      </div>

      {/* Edit Modal */}
      {isEditing && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-white dark:bg-[#1e293b] rounded-2xl w-full max-w-sm overflow-hidden shadow-2xl">
            <div className="p-5 border-b border-gray-100 dark:border-gray-800 flex justify-between items-center">
              <h3 className="font-bold text-lg text-gray-900 dark:text-white">Edit Dummy Balance</h3>
              <button onClick={() => setIsEditing(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleEditFunds} className="p-5">
              <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
                New Balance Amount ($)
              </label>
              <input
                type="number"
                step="0.01"
                required
                className="w-full bg-gray-50 dark:bg-[#0f172a] border border-gray-200 dark:border-gray-700 rounded-xl px-4 py-3 text-gray-900 dark:text-white font-mono text-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. 100000"
                value={editAmount}
                onChange={(e) => setEditAmount(e.target.value)}
              />
              <div className="mt-6 flex gap-3">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="flex-1 py-3 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-bold rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 py-3 bg-blue-500 hover:bg-blue-600 text-white font-bold rounded-xl shadow-md transition-colors flex justify-center items-center"
                >
                  {saving ? <Loader2 size={20} className="animate-spin" /> : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

const MetricCard = ({ title, value, icon, color }) => {
  const colorMap = {
    emerald: 'text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10',
    blue: 'text-blue-500 bg-blue-50 dark:bg-blue-500/10',
    gray: 'text-gray-500 bg-gray-50 dark:bg-gray-500/10',
    red: 'text-red-500 bg-red-50 dark:bg-red-500/10',
  };

  return (
    <div className="bg-white dark:bg-[#1e293b] rounded-2xl p-4 border border-gray-100 dark:border-gray-800 shadow-sm">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-xl ${colorMap[color]}`}>
          {icon}
        </div>
        <h3 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{title}</h3>
      </div>
      <p className="text-xl font-black text-gray-900 dark:text-white font-mono tracking-tight">{value}</p>
    </div>
  );
};

// Dummy icons that might be missing from import
const TrendingDown = ({ size, className }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"></polyline><polyline points="17 18 23 18 23 12"></polyline></svg>;
const CheckCircle2 = ({ size, className }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path><path d="m9 12 2 2 4-4"></path></svg>;
const X = ({ size, className }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>;

export default FundsPage;
