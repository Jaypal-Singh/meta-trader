import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Plus, Maximize, Minimize } from 'lucide-react';
import ChartInstance from '../components/ChartInstance';
import API_URL from '../config/api';

const ChartPage = () => {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;
        const res = await fetch(`${API_URL}/api/trading/watchlist`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        const symData = data.find(s => s.name === symbol);
        if (symData && symData.configs && symData.configs.length > 0) {
          // Only load the FIRST config by default so the screen isn't cluttered
          setConfigs([symData.configs[0]]);
        } else {
          // Default if no configs
          setConfigs([{ strategy: 'spirit', timeframe: 'H1', id: 'default' }]);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, [symbol]);

  const addInstance = () => {
    setConfigs([...configs, { strategy: 'spirit', timeframe: 'H1', id: Date.now().toString() }]);
  };

  const removeInstance = (index) => {
    setConfigs(configs.filter((_, i) => i !== index));
  };

  const toggleFullscreen = () => {
    const elem = document.getElementById("main-chart-page");
    if (!elem) return;
    if (!document.fullscreenElement) {
      elem.requestFullscreen().catch(err => {
        console.error(`Error attempting to enable full-screen mode: ${err.message}`);
      });
    } else {
      document.exitFullscreen();
    }
  };

  const [isFullscreen, setIsFullscreen] = useState(false);
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  return (
    <div id="main-chart-page" className="flex flex-col h-full bg-gray-50 dark:bg-[#0f172a] transition-colors duration-200">
      {/* Global Header for the Symbol */}
      <div className="flex-none bg-white dark:bg-[#1e293b] px-4 py-3 flex items-center justify-between border-b border-gray-200 dark:border-gray-800 transition-colors duration-200 shadow-sm z-30">
        <div className="flex items-center space-x-3 text-[#0f172a] dark:text-gray-100">
          <ArrowLeft size={24} className="cursor-pointer hover:text-blue-500 transition-colors" onClick={() => navigate('/')} />
          <div>
            <h1 className="text-xl font-black tracking-tight">{symbol}</h1>
            <div className="text-[10px] text-gray-500 dark:text-gray-400 font-medium">MULTI-CHART VIEW</div>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <button 
            onClick={toggleFullscreen}
            className="flex items-center justify-center bg-gray-100 hover:bg-gray-200 dark:bg-[#334155] dark:hover:bg-[#475569] text-gray-700 dark:text-gray-200 p-2 rounded-lg transition-colors"
            title="Toggle Fullscreen"
          >
            {isFullscreen ? <Minimize size={16} /> : <Maximize size={16} />}
          </button>
          <button 
            onClick={addInstance}
            className="flex items-center space-x-1 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-colors shadow-lg shadow-blue-500/20"
          >
            <Plus size={14} /> <span>Add Chart</span>
          </button>
        </div>
      </div>

      {/* Grid of Chart Instances */}
      <div className={`flex-1 overflow-y-auto p-2 ${configs.length > 1 ? (configs.length > 2 ? 'grid grid-cols-1 md:grid-cols-2 gap-2' : 'grid grid-cols-1 md:grid-cols-2 gap-2') : 'flex'}`}>
        {loading ? (
          <div className="flex-1 flex items-center justify-center font-bold text-gray-500">Loading configurations...</div>
        ) : (
          configs.map((conf, index) => (
            <div key={conf.id || index} className={`flex flex-col ${configs.length > 1 ? 'min-h-[400px]' : 'flex-1'} border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm relative bg-white dark:bg-[#131722]`}>
              <ChartInstance 
                symbol={symbol} 
                initialStrategy={conf.strategy} 
                initialTimeframe={conf.timeframe} 
                onRemove={() => removeInstance(index)} 
                showRemove={configs.length > 1}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ChartPage;
