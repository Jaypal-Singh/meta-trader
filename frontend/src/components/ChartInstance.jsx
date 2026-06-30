import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, CandlestickSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';
import { ChevronDown, RefreshCw, Activity, BarChart3, X } from 'lucide-react';
import API_URL from '../config/api';

const timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1', 'MN'];
const strategies = ['spirit', 'soul', 'pulse'];

const ChartInstance = ({ symbol, initialStrategy, initialTimeframe, onRemove, showRemove }) => {
  const chartContainerRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeframe, setTimeframe] = useState(initialTimeframe || 'H1');
  const [strategy, setStrategy] = useState(initialStrategy || 'spirit');
  const [currentPrice, setCurrentPrice] = useState(null);
  const [bidAsk, setBidAsk] = useState({ bid: null, ask: null });
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [latestSignal, setLatestSignal] = useState(null);
  const [signalCount, setSignalCount] = useState({ buy: 0, sell: 0 });
  const [accuracy, setAccuracy] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [tradeStatus, setTradeStatus] = useState({ show: false, message: '', type: '' });
  const [showIndicators, setShowIndicators] = useState({ ema21: true, ema50: true, ema200: true, bb: true });
  const [liveRsi, setLiveRsi] = useState(null);
  const [liveMacd, setLiveMacd] = useState(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const markersRef = useRef(null);
  const lastCandleRef = useRef(null); // Track last candle for live tick updates
  // Indicator line series refs
  const ema21Ref = useRef(null);
  const ema50Ref = useRef(null);
  const ema200Ref = useRef(null);
  const bbUpperRef = useRef(null);
  const bbMiddleRef = useRef(null);
  const bbLowerRef = useRef(null);

  const handleTrade = async (type) => {
    const token = localStorage.getItem('token');
    if (!token) {
      setTradeStatus({ show: true, message: 'Please login first', type: 'error' });
      setTimeout(() => setTradeStatus({ show: false }), 3000);
      return;
    }
    const price = type === 'BUY' ? bidAsk.ask : bidAsk.bid;
    if (!price) {
      setTradeStatus({ show: true, message: 'Price not available yet', type: 'error' });
      setTimeout(() => setTradeStatus({ show: false }), 3000);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/orders/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          symbol: symbol,
          order_type: type,
          lot_size: 0.1, // Fixed 0.1 lot for dummy trading
          open_price: price,
          strategy: strategy,
          timeframe: timeframe,
          comment: 'From Chart UI'
        })
      });
      const data = await res.json();
      if (res.ok) {
        setTradeStatus({ show: true, message: `Successfully placed ${type} order for 0.1 lot`, type: 'success' });
      } else {
        setTradeStatus({ show: true, message: data.detail || 'Trade failed', type: 'error' });
      }
    } catch (e) {
      setTradeStatus({ show: true, message: 'Network error connecting to backend', type: 'error' });
    }
    setTimeout(() => setTradeStatus({ show: false, message: '', type: '' }), 4000);
  };

  // Theme observer
  useEffect(() => {
    const observer = new MutationObserver(() => {
      const isDark = document.documentElement.classList.contains('dark');
      if (chartRef.current) {
        chartRef.current.applyOptions({
          layout: {
            background: { type: 'solid', color: isDark ? '#131722' : '#ffffff' },
            textColor: isDark ? '#d1d4dc' : '#333333',
          },
          grid: {
            vertLines: { color: isDark ? 'rgba(42, 46, 57, 0.5)' : 'rgba(0, 0, 0, 0.1)' },
            horzLines: { color: isDark ? 'rgba(42, 46, 57, 0.5)' : 'rgba(0, 0, 0, 0.1)' },
          }
        });
      }
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  // Removed fetchConfig since strategy and timeframe are initialized via props

  // Fetch live price every 1 second AND update the chart's last candle
  // This ensures: header price = chart red line = watchlist price (all bid)
  useEffect(() => {
    let cancelled = false;
    const fetchLivePrice = async () => {
      try {
        const res = await fetch(`${API_URL}/api/trading/live_price?symbol=${symbol}`);
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;

        const livePrice = data.price;
        setCurrentPrice(livePrice);
        setBidAsk({ bid: data.bid, ask: data.ask });

        // Update the chart's last candle with the live tick price
        // This moves the red price line on the Y-axis to match
        if (seriesRef.current && lastCandleRef.current) {
          const candle = { ...lastCandleRef.current };
          candle.close = livePrice;
          // Update high/low if price exceeds current candle range
          if (livePrice > candle.high) candle.high = livePrice;
          if (livePrice < candle.low) candle.low = livePrice;
          lastCandleRef.current = candle;
          seriesRef.current.update(candle);
        }
      } catch (e) { /* ignore */ }
    };
    fetchLivePrice();
    const priceInterval = setInterval(fetchLivePrice, 1000);
    return () => { cancelled = true; clearInterval(priceInterval); };
  }, [symbol]);

  // Main chart effect
  useEffect(() => {
    let intervalId = null;
    let isCancelled = false;

    const fetchData = async () => {
      const response = await fetch(`${API_URL}/api/trading/chart_data?symbol=${symbol}&timeframe=${timeframe}&strategy=${strategy}`);
      if (!response.ok) throw new Error('Failed to fetch chart data');
      return await response.json();
    };

    // MT5 brokers are typically UTC+3. We calculate offset to local browser time.
    const BROKER_UTC_OFFSET = 3 * 3600;
    const BROWSER_UTC_OFFSET = -new Date().getTimezoneOffset() * 60;
    const TIME_OFFSET = BROWSER_UTC_OFFSET - BROKER_UTC_OFFSET;

    const applyOffset = (time) => time + TIME_OFFSET;

    const toCandles = (data) => data.map(d => ({
      time: applyOffset(d.time), open: d.open, high: d.high, low: d.low, close: d.close,
    }));

    const toMarkers = (data) => {
      const markers = [];
      data.forEach(d => {
        if (d.signal === 'BUY') {
          markers.push({ time: applyOffset(d.time), position: 'belowBar', color: '#10B981', shape: 'arrowUp', text: 'BUY', size: 3 });
        } else if (d.signal === 'SELL') {
          markers.push({ time: applyOffset(d.time), position: 'aboveBar', color: '#EF4444', shape: 'arrowDown', text: 'SELL', size: 3 });
        }
      });
      return markers;
    };

    const findLatestSignal = (data) => {
      for (let i = data.length - 1; i >= 0; i--) {
        if (data[i].signal === 'BUY' || data[i].signal === 'SELL') {
          return data[i];
        }
      }
      return null;
    };

    const initChart = async () => {
      try {
        setLoading(true);
        setError(null);
        const resPayload = await fetchData();
        const data = resPayload.data;
        const indicators = resPayload.indicators || {};
        if (isCancelled || !chartContainerRef.current) return;

        setAccuracy(resPayload.accuracy);

        // Set live RSI and MACD values
        if (indicators.rsi && indicators.rsi.length > 0) {
          setLiveRsi(indicators.rsi[indicators.rsi.length - 1].value);
        }
        if (indicators.macd_line && indicators.macd_line.length > 0) {
          const macdVal = indicators.macd_line[indicators.macd_line.length - 1].value;
          const macdSigVal = indicators.macd_signal && indicators.macd_signal.length > 0
            ? indicators.macd_signal[indicators.macd_signal.length - 1].value : 0;
          setLiveMacd({ line: macdVal, signal: macdSigVal, hist: macdVal - macdSigVal });
        }

        // Count signals
        const markers = toMarkers(data);
        setSignalCount({
          buy: markers.filter(m => m.text === 'BUY').length,
          sell: markers.filter(m => m.text === 'SELL').length,
        });

        // Find latest signal
        setLatestSignal(findLatestSignal(data));

        chartContainerRef.current.innerHTML = '';
        const isDark = document.documentElement.classList.contains('dark');

        const chart = createChart(chartContainerRef.current, {
          autoSize: true,
          layout: {
            background: { type: 'solid', color: isDark ? '#131722' : '#ffffff' },
            textColor: isDark ? '#d1d4dc' : '#333333',
          },
          grid: {
            vertLines: { color: isDark ? 'rgba(42, 46, 57, 0.5)' : 'rgba(0, 0, 0, 0.1)' },
            horzLines: { color: isDark ? 'rgba(42, 46, 57, 0.5)' : 'rgba(0, 0, 0, 0.1)' },
          },
          timeScale: {
            timeVisible: true,
            secondsVisible: false,
            rightOffset: 5,
            barSpacing: 10,
            fixLeftEdge: false,
          },
          crosshair: { mode: 0 },
        });
        chartRef.current = chart;

        const series = chart.addSeries(CandlestickSeries, {
          upColor: '#10B981',
          downColor: '#EF4444',
          borderVisible: false,
          wickUpColor: '#10B981',
          wickDownColor: '#EF4444',
        });
        seriesRef.current = series;

        const candles = toCandles(data);
        series.setData(candles);

        // ── EMA INDICATOR LINES (added BEFORE markers so arrows render on top) ──
        // EMA 21 — Fast trend (yellow/gold)
        const ema21Series = chart.addSeries(LineSeries, {
          color: '#FBBF24',
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        if (indicators.ema_21) ema21Series.setData(indicators.ema_21.map(d => ({ time: applyOffset(d.time), value: d.value })));
        ema21Ref.current = ema21Series;

        // EMA 50 — Medium trend (cyan/blue)
        const ema50Series = chart.addSeries(LineSeries, {
          color: '#06B6D4',
          lineWidth: 1.5,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        if (indicators.ema_50) ema50Series.setData(indicators.ema_50.map(d => ({ time: applyOffset(d.time), value: d.value })));
        ema50Ref.current = ema50Series;

        // EMA 200 — Major trend (magenta/pink)
        const ema200Series = chart.addSeries(LineSeries, {
          color: '#A855F7',
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        if (indicators.ema_200) ema200Series.setData(indicators.ema_200.map(d => ({ time: applyOffset(d.time), value: d.value })));
        ema200Ref.current = ema200Series;

        // ── BOLLINGER BANDS ──
        const bbUpperSeries = chart.addSeries(LineSeries, {
          color: 'rgba(59, 130, 246, 0.4)', // Faded blue
          lineWidth: 1,
          lineStyle: 2, // Dashed
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        if (indicators.bb_upper) bbUpperSeries.setData(indicators.bb_upper.map(d => ({ time: applyOffset(d.time), value: d.value })));
        bbUpperRef.current = bbUpperSeries;

        const bbMiddleSeries = chart.addSeries(LineSeries, {
          color: 'rgba(234, 179, 8, 0.6)', // Yellow
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        if (indicators.bb_middle) bbMiddleSeries.setData(indicators.bb_middle.map(d => ({ time: applyOffset(d.time), value: d.value })));
        bbMiddleRef.current = bbMiddleSeries;

        const bbLowerSeries = chart.addSeries(LineSeries, {
          color: 'rgba(59, 130, 246, 0.4)', // Faded blue
          lineWidth: 1,
          lineStyle: 2, // Dashed
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        if (indicators.bb_lower) bbLowerSeries.setData(indicators.bb_lower.map(d => ({ time: applyOffset(d.time), value: d.value })));
        bbLowerRef.current = bbLowerSeries;

        // Hide EMAs or BBs based on active strategy by default
        if (strategy === 'soul') {
          ema21Series.applyOptions({ visible: false });
          ema50Series.applyOptions({ visible: false });
          ema200Series.applyOptions({ visible: false });
          setShowIndicators(prev => ({ ...prev, ema21: false, ema50: false, ema200: false, bb: true }));
        } else {
          bbUpperSeries.applyOptions({ visible: false });
          bbMiddleSeries.applyOptions({ visible: false });
          bbLowerSeries.applyOptions({ visible: false });
          setShowIndicators(prev => ({ ...prev, ema21: true, ema50: true, ema200: true, bb: false }));
        }

        // ── BUY/SELL MARKERS (created AFTER EMA lines so arrows are on top) ──
        markersRef.current = createSeriesMarkers(series, markers);

        // Store the last candle for live tick updates
        if (candles.length > 0) {
          lastCandleRef.current = { ...candles[candles.length - 1] };
        }

        // Scroll to show last ~80 candles (recent area with signals visible)
        chart.timeScale().scrollToPosition(5, false);

        setLastUpdate(new Date());
        setLoading(false);

        // Live polling every 3 seconds for full candle data + signals
        intervalId = setInterval(async () => {
          try {
            const resPayload = await fetchData();
            const newData = resPayload.data;
            const newIndicators = resPayload.indicators || {};
            if (isCancelled || !seriesRef.current) return;

            setAccuracy(resPayload.accuracy);

            // Update live RSI/MACD
            if (newIndicators.rsi && newIndicators.rsi.length > 0) {
              setLiveRsi(newIndicators.rsi[newIndicators.rsi.length - 1].value);
            }
            if (newIndicators.macd_line && newIndicators.macd_line.length > 0) {
              const macdVal = newIndicators.macd_line[newIndicators.macd_line.length - 1].value;
              const macdSigVal = newIndicators.macd_signal && newIndicators.macd_signal.length > 0
                ? newIndicators.macd_signal[newIndicators.macd_signal.length - 1].value : 0;
              setLiveMacd({ line: macdVal, signal: macdSigVal, hist: macdVal - macdSigVal });
            }

            const newCandles = toCandles(newData);
            const newMarkers = toMarkers(newData);

            seriesRef.current.setData(newCandles);

            // Update EMA lines
            if (ema21Ref.current && newIndicators.ema_21) ema21Ref.current.setData(newIndicators.ema_21.map(d => ({ time: applyOffset(d.time), value: d.value })));
            if (ema50Ref.current && newIndicators.ema_50) ema50Ref.current.setData(newIndicators.ema_50.map(d => ({ time: applyOffset(d.time), value: d.value })));
            if (ema200Ref.current && newIndicators.ema_200) ema200Ref.current.setData(newIndicators.ema_200.map(d => ({ time: applyOffset(d.time), value: d.value })));

            // Store updated last candle
            if (newCandles.length > 0) {
              lastCandleRef.current = { ...newCandles[newCandles.length - 1] };
            }

            // Update markers
            try {
              if (markersRef.current && typeof markersRef.current.setMarkers === 'function') {
                markersRef.current.setMarkers(newMarkers);
              }
            } catch (markerErr) {
              // If setMarkers fails, recreate
              try {
                markersRef.current = createSeriesMarkers(seriesRef.current, newMarkers);
              } catch (e) { /* ignore */ }
            }

            setSignalCount({
              buy: newMarkers.filter(m => m.text === 'BUY').length,
              sell: newMarkers.filter(m => m.text === 'SELL').length,
            });
            setLatestSignal(findLatestSignal(newData));
            setLastUpdate(new Date());
          } catch (e) {
            // Silently ignore polling errors
          }
        }, 3000);

      } catch (err) {
        if (!isCancelled) {
          setError(err.message === 'Failed to fetch'
            ? 'Connection timeout. MT5 may be downloading data. Please wait...'
            : err.message);
          setLoading(false);
        }
      }
    };

    initChart();

    return () => {
      isCancelled = true;
      if (intervalId) clearInterval(intervalId);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
        markersRef.current = null;
        lastCandleRef.current = null;
        ema21Ref.current = null;
        ema50Ref.current = null;
        ema200Ref.current = null;
      }
    };
  }, [symbol, timeframe, strategy]);

  // Toggle indicator visibility
  const toggleIndicator = (key) => {
    const newState = !showIndicators[key];
    setShowIndicators(prev => ({ ...prev, [key]: newState }));

    if (key === 'bb') {
      if (bbUpperRef.current) bbUpperRef.current.applyOptions({ visible: newState });
      if (bbMiddleRef.current) bbMiddleRef.current.applyOptions({ visible: newState });
      if (bbLowerRef.current) bbLowerRef.current.applyOptions({ visible: newState });
    } else {
      const refMap = { ema21: ema21Ref, ema50: ema50Ref, ema200: ema200Ref };
      const ref = refMap[key];
      if (ref && ref.current) {
        ref.current.applyOptions({ visible: newState });
      }
    }
  };

  // RSI color helper
  const getRsiColor = (val) => {
    if (val >= 70) return 'text-red-400';
    if (val <= 30) return 'text-emerald-400';
    return 'text-blue-400';
  };

  return (
    <div className="flex flex-col h-full w-full bg-[#f8f9fa] dark:bg-[#0f172a] font-sans transition-colors duration-200">
      {/* Chart Top Controls */}
      <div className="flex-none bg-white dark:bg-[#1e293b] px-4 py-2 flex items-center justify-between border-b border-gray-200 dark:border-gray-800 transition-colors duration-200">
        <div className="flex items-center space-x-3 text-[#0f172a] dark:text-gray-100">
          <div className="flex items-center space-x-2">
             <div className="relative">
                <select className="bg-transparent text-sm font-bold border-none outline-none cursor-pointer appearance-none px-1" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                  <option value="spirit">Spirit</option>
                  <option value="soul">Soul</option>
                  <option value="pulse">Pulse</option>
                </select>
                <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-gray-500" />
             </div>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {/* Custom Timeframe Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center space-x-1 bg-gray-100 dark:bg-[#334155] hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 px-3 py-1 rounded-lg text-xs font-bold transition-colors"
            >
              <span>{timeframe}</span>
              <ChevronDown size={12} />
            </button>
            {isDropdownOpen && (
              <div className="absolute right-0 mt-1 w-24 bg-white dark:bg-[#1e293b] border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl overflow-hidden z-50">
                {timeframes.map(tf => (
                  <div
                    key={tf}
                    onClick={() => { setTimeframe(tf); setIsDropdownOpen(false); }}
                    className={`px-3 py-1.5 text-xs font-bold cursor-pointer hover:bg-gray-100 dark:hover:bg-[#334155] transition-colors ${timeframe === tf ? 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-[#0f172a]' : 'text-gray-600 dark:text-gray-300'}`}
                  >
                    {tf}
                  </div>
                ))}
              </div>
            )}
          </div>
          {showRemove && (
            <button onClick={onRemove} className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 rounded transition-colors">
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Indicator Status Bar */}
      <div className="flex-none bg-white dark:bg-[#0f172a] px-4 py-1.5 flex items-center justify-between border-b border-gray-200 dark:border-gray-800 transition-colors duration-200">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
            <span className="text-[11px] tracking-wider font-bold text-emerald-600 dark:text-emerald-500">
              {strategy === 'soul' ? 'SOUL MEAN REVERSION' : 'SPIRIT'}
            </span>
          </div>
          <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-1.5 py-0.5 rounded">BUY: {signalCount.buy}</span>
          <span className="text-[10px] font-bold text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 px-1.5 py-0.5 rounded">SELL: {signalCount.sell}</span>
          {accuracy && accuracy.total > 0 && (
            <span className="text-[10px] font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 px-1.5 py-0.5 rounded" title={`Wins: ${accuracy.wins} | Losses: ${accuracy.losses}`}>
              ACCURACY: {accuracy.win_rate}%
            </span>
          )}
          {latestSignal && (
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full animate-pulse ${latestSignal.signal === 'BUY'
                ? 'bg-emerald-500 text-white'
                : 'bg-red-500 text-white'
              }`}>
              LATEST: {latestSignal.signal}
            </span>
          )}
        </div>
        <div className="flex items-center space-x-1.5 text-[10px] text-gray-400">
          <RefreshCw size={10} className={lastUpdate ? 'animate-spin-slow' : ''} />
          <span>{lastUpdate ? `${lastUpdate.toLocaleTimeString()}` : 'Loading...'}</span>
        </div>
      </div>

      {/* Indicator Toggle Bar + Live Values */}
      <div className="flex-none bg-gray-50/50 dark:bg-[#1a2332] px-4 py-1.5 flex items-center justify-between border-b border-gray-200 dark:border-gray-800 transition-colors duration-200">
        <div className="flex items-center space-x-2">
          {/* EMA toggles */}
          <button
            onClick={() => toggleIndicator('ema21')}
            className={`flex items-center space-x-1 text-[10px] font-bold px-2 py-0.5 rounded-full transition-all ${showIndicators.ema21
                ? 'bg-yellow-400/20 text-yellow-500 border border-yellow-400/40'
                : 'bg-gray-200 dark:bg-gray-700 text-gray-400 border border-transparent'
              }`}
          >
            <span className="w-2.5 h-0.5 rounded-full" style={{ backgroundColor: showIndicators.ema21 ? '#FBBF24' : '#9CA3AF' }}></span>
            <span>EMA 21</span>
          </button>
          <button
            onClick={() => toggleIndicator('ema50')}
            className={`flex items-center space-x-1 text-[10px] font-bold px-2 py-0.5 rounded-full transition-all ${showIndicators.ema50
                ? 'bg-cyan-400/20 text-cyan-400 border border-cyan-400/40'
                : 'bg-gray-200 dark:bg-gray-700 text-gray-400 border border-transparent'
              }`}
          >
            <span className="w-2.5 h-0.5 rounded-full" style={{ backgroundColor: showIndicators.ema50 ? '#06B6D4' : '#9CA3AF' }}></span>
            <span>EMA 50</span>
          </button>
          <button
            onClick={() => toggleIndicator('ema200')}
            className={`flex items-center space-x-1 text-[10px] font-bold px-2 py-0.5 rounded-full transition-all ${showIndicators.ema200
                ? 'bg-purple-400/20 text-purple-400 border border-purple-400/40'
                : 'bg-gray-200 dark:bg-gray-700 text-gray-400 border border-transparent'
              }`}
          >
            <span className="w-2.5 h-0.5 rounded-full" style={{ backgroundColor: showIndicators.ema200 ? '#A855F7' : '#9CA3AF' }}></span>
            <span>EMA 200</span>
          </button>
          
          {strategy === 'soul' && (
            <button
              onClick={() => toggleIndicator('bb')}
              className={`flex items-center space-x-1 text-[10px] font-bold px-2 py-0.5 rounded-full transition-all ${showIndicators.bb
                  ? 'bg-blue-400/20 text-blue-500 border border-blue-400/40'
                  : 'bg-gray-200 dark:bg-gray-700 text-gray-400 border border-transparent'
                }`}
            >
              <span className="w-2.5 h-0.5 rounded-full" style={{ backgroundColor: showIndicators.bb ? '#3B82F6' : '#9CA3AF' }}></span>
              <span>Bands</span>
            </button>
          )}
        </div>

        {/* Live RSI & MACD & Trade Actions */}
        <div className="flex items-center space-x-3">
          <div className="flex space-x-2 mr-2">
            <button
              onClick={() => handleTrade('SELL')}
              className="bg-[#EF4444] hover:bg-red-500 text-white text-[10px] font-bold px-3 py-1 rounded shadow-sm active:scale-95 transition-all flex items-center space-x-1"
            >
              <span>SELL</span>
              {bidAsk.bid && <span className="font-normal opacity-80">{bidAsk.bid}</span>}
            </button>
            <button
              onClick={() => handleTrade('BUY')}
              className="bg-[#10B981] hover:bg-emerald-500 text-white text-[10px] font-bold px-3 py-1 rounded shadow-sm active:scale-95 transition-all flex items-center space-x-1"
            >
              <span>BUY</span>
              {bidAsk.ask && <span className="font-normal opacity-80">{bidAsk.ask}</span>}
            </button>
          </div>
          {liveRsi !== null && (
            <div className="flex items-center space-x-1">
              <Activity size={10} className="text-gray-400" />
              <span className="text-[10px] text-gray-400 font-medium">RSI:</span>
              <span className={`text-[10px] font-bold ${getRsiColor(liveRsi)}`}>
                {liveRsi.toFixed(1)}
              </span>
            </div>
          )}
          {liveMacd && (
            <div className="flex items-center space-x-1">
              <BarChart3 size={10} className="text-gray-400" />
              <span className="text-[10px] text-gray-400 font-medium">MACD:</span>
              <span className={`text-[10px] font-bold ${liveMacd.hist >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {liveMacd.hist >= 0 ? '+' : ''}{liveMacd.hist.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Chart Area */}
      <div className="flex-1 relative bg-white dark:bg-[#131722] transition-colors duration-200">
        {loading && <div className="absolute inset-0 flex items-center justify-center font-bold text-gray-500 dark:text-gray-400 z-10 bg-white/80 dark:bg-[#131722]/80 backdrop-blur-sm">Loading Data...</div>}
        {error && <div className="absolute inset-0 flex items-center justify-center font-bold text-red-500 px-8 text-center z-10 bg-white/90 dark:bg-[#131722]/90">{error}</div>}
        <div ref={chartContainerRef} style={{ position: 'absolute', inset: 0 }} />
      </div>



      {/* Trade Toast Notification */}
      {tradeStatus.show && (
        <div className={`absolute top-20 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-xl shadow-2xl font-bold text-sm text-white animate-in slide-in-from-top-5 duration-300 ${tradeStatus.type === 'error' ? 'bg-red-500' : 'bg-emerald-500'
          }`}>
          {tradeStatus.message}
        </div>
      )}
    </div>
  );
};

export default ChartInstance;
