import React, { useState } from 'react';
import { Settings, ShieldAlert, ShieldCheck } from 'lucide-react';

const TradingControls = () => {
  const [isReal, setIsReal] = useState(false);
  const [lotSize, setLotSize] = useState(0.01);

  return (
    <div className="bg-trading-panel p-6 rounded-xl border border-gray-800 shadow-lg">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-white flex items-center">
          <Settings className="w-5 h-5 mr-2 text-trading-buy" />
          Trading Controls
        </h2>
      </div>

      <div className="space-y-6">
        {/* Real / Dummy Toggle */}
        <div className="flex items-center justify-between p-4 rounded-lg bg-gray-900/50 border border-gray-800">
          <div>
            <p className="text-white font-bold">Trading Mode</p>
            <p className="text-sm text-trading-muted">
              {isReal ? 'Real money is at risk' : 'Safe paper trading'}
            </p>
          </div>
          <button
            onClick={() => setIsReal(!isReal)}
            className={`relative inline-flex h-8 w-16 items-center rounded-full transition-colors focus:outline-none shadow-inner ${
              isReal ? 'bg-trading-sell shadow-[0_0_15px_rgba(239,68,68,0.4)]' : 'bg-trading-muted'
            }`}
          >
            <span
              className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform ${
                isReal ? 'translate-x-9' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Status Alert */}
        {isReal ? (
          <div className="flex items-center p-4 text-sm text-red-200 bg-red-900/20 rounded-lg border border-red-900/50 backdrop-blur-sm">
            <ShieldAlert className="w-5 h-5 mr-3 text-red-500 animate-pulse" />
            <span className="font-semibold tracking-wide">LIVE TRADING ENABLED</span>
          </div>
        ) : (
          <div className="flex items-center p-4 text-sm text-emerald-200 bg-emerald-900/20 rounded-lg border border-emerald-900/50 backdrop-blur-sm">
            <ShieldCheck className="w-5 h-5 mr-3 text-emerald-500" />
            <span className="font-semibold tracking-wide">DUMMY MODE ENABLED</span>
          </div>
        )}

        {/* Lot Size Input */}
        <div>
          <label className="block text-sm font-medium text-trading-muted mb-2">
            Default Lot Size (Volume)
          </label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={lotSize}
            onChange={(e) => setLotSize(parseFloat(e.target.value))}
            className="block w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white font-mono text-lg focus:ring-2 focus:ring-trading-buy focus:border-transparent transition-all"
          />
        </div>
      </div>
    </div>
  );
};

export default TradingControls;
