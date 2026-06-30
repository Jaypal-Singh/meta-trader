import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { List, TrendingUp, Network, PieChart, User, Activity, Moon, Sun } from 'lucide-react';
import WatchlistList from './WatchlistList';
import FloatingWindow from './FloatingWindow';
import OrdersPage from '../pages/OrdersPage';
import StrategiesPage from '../pages/StrategiesPage';
import AnalysisPage from '../pages/AnalysisPage';
import BacktestPage from '../pages/BacktestPage';

const Layout = () => {
  const location = useLocation();
  const isChartPage = location.pathname.startsWith('/chart');
  
  // Theme state
  const [isDarkMode, setIsDarkMode] = useState(false);
  
  // Sidebar resize state
  const [sidebarWidth, setSidebarWidth] = useState(350);
  const [isResizing, setIsResizing] = useState(false);
  
  // Floating Windows State
  const [openWindows, setOpenWindows] = useState([]);
  const [activeWindow, setActiveWindow] = useState(null);

  const toggleWindow = (id) => {
    if (openWindows.includes(id)) {
      setOpenWindows(openWindows.filter(w => w !== id));
    } else {
      setOpenWindows([...openWindows, id]);
      setActiveWindow(id);
    }
  };

  const bringToFront = (id) => {
    setActiveWindow(id);
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;
      let newWidth = e.clientX;
      if (newWidth < 250) newWidth = 250;
      if (newWidth > 600) newWidth = 600;
      setSidebarWidth(newWidth);
    };
    const handleMouseUp = () => setIsResizing(false);
    
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  useEffect(() => {
    // Check local storage or system preference on load
    if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      setIsDarkMode(true);
      document.documentElement.classList.add('dark');
    } else {
      setIsDarkMode(false);
      document.documentElement.classList.remove('dark');
    }
  }, []);

  const toggleTheme = () => {
    if (isDarkMode) {
      document.documentElement.classList.remove('dark');
      localStorage.theme = 'light';
      setIsDarkMode(false);
    } else {
      document.documentElement.classList.add('dark');
      localStorage.theme = 'dark';
      setIsDarkMode(true);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[#f8f9fa] dark:bg-[#0f172a] text-gray-900 dark:text-gray-100 overflow-hidden w-full max-w-full font-sans transition-colors duration-200">
      {/* Desktop Header */}
      <header className="hidden md:flex flex-none h-14 bg-[#0f172a] text-white items-center px-6 justify-between border-b border-gray-800 z-50">
        <div className="flex items-center space-x-2">
          <Activity className="text-emerald-500 w-6 h-6" />
          <span className="font-extrabold text-lg tracking-tight">SPIRIT PRO</span>
        </div>
        <div className="flex items-center space-x-8">
          <nav className="flex space-x-8">
            <TopNavItem label="Orders" onClick={() => toggleWindow('orders')} isActive={openWindows.includes('orders')} />
            <TopNavItem label="Strategies" onClick={() => toggleWindow('strategies')} isActive={openWindows.includes('strategies')} />
            <TopNavItem label="Analysis" onClick={() => toggleWindow('analysis')} isActive={openWindows.includes('analysis')} />
            <TopNavItem label="Backtest" onClick={() => toggleWindow('backtest')} isActive={openWindows.includes('backtest')} />
          </nav>
          <button 
            onClick={toggleTheme}
            className="p-2 rounded-full hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
          >
            {isDarkMode ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>
      </header>

      {/* Main Body */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Sidebar (Desktop Only) */}
        <aside 
          style={{ width: sidebarWidth }}
          className="hidden md:flex flex-col border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-[#1e293b] flex-none z-10 shadow-[2px_0_10px_rgba(0,0,0,0.03)] dark:shadow-none relative h-full transition-colors duration-200"
        >
          <WatchlistList />
          {/* Resize Handle */}
          <div 
            className="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-blue-500/50 z-50 transition-colors"
            onMouseDown={() => setIsResizing(true)}
          />
        </aside>

        {/* Content Area */}
        <main className={`flex-1 flex flex-col relative overflow-hidden bg-white dark:bg-[#131722] md:bg-[#131722] transition-colors duration-200 ${!isChartPage ? 'pb-[60px] md:pb-0' : ''}`}>
           <Outlet />
           
           {/* Floating Windows Overlay */}
           {openWindows.includes('orders') && (
             <FloatingWindow 
               id="orders" title="Active Orders & Holdings" 
               onClose={() => toggleWindow('orders')} 
               zIndex={activeWindow === 'orders' ? 100 : 50}
               bringToFront={() => bringToFront('orders')}
             >
               <OrdersPage />
             </FloatingWindow>
           )}
           {openWindows.includes('strategies') && (
             <FloatingWindow 
               id="strategies" title="Trading Strategies" 
               onClose={() => toggleWindow('strategies')} 
               zIndex={activeWindow === 'strategies' ? 100 : 50}
               bringToFront={() => bringToFront('strategies')}
             >
               <StrategiesPage />
             </FloatingWindow>
           )}
           {openWindows.includes('analysis') && (
             <FloatingWindow 
               id="analysis" title="Trade Analysis" 
               onClose={() => toggleWindow('analysis')} 
               zIndex={activeWindow === 'analysis' ? 100 : 50}
               bringToFront={() => bringToFront('analysis')}
             >
               <AnalysisPage />
             </FloatingWindow>
           )}
           {openWindows.includes('backtest') && (
             <FloatingWindow 
               id="backtest" title="Quant Engine Simulator" 
               onClose={() => toggleWindow('backtest')} 
               zIndex={activeWindow === 'backtest' ? 100 : 50}
               bringToFront={() => bringToFront('backtest')}
             >
               <BacktestPage />
             </FloatingWindow>
           )}
        </main>
      </div>

      {/* Mobile Bottom Navigation - Hide on Chart Page */}
      {!isChartPage && (
        <div className="md:hidden absolute bottom-0 w-full h-[60px] bg-white dark:bg-[#1e293b] border-t border-gray-200 dark:border-gray-800 flex justify-around items-center py-2 px-1 z-50 shadow-[0_-4px_10px_rgba(0,0,0,0.05)] transition-colors duration-200">
          <NavItem icon={<List size={20} />} label="Watchlist" onClick={() => {}} isActive={false} />
          <NavItem icon={<TrendingUp size={20} />} label="Order" onClick={() => toggleWindow('orders')} isActive={openWindows.includes('orders')} />
          <NavItem icon={<Network size={20} />} label="Strategies" onClick={() => toggleWindow('strategies')} isActive={openWindows.includes('strategies')} />
          <NavItem icon={<PieChart size={20} />} label="Analysis" onClick={() => toggleWindow('analysis')} isActive={openWindows.includes('analysis')} />
          
          {/* Mobile Theme Toggle masquerading as Profile for now, or just an extra button */}
          <button onClick={toggleTheme} className="flex flex-col items-center p-2 text-[10px] font-bold text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white transition-colors">
            <div className="mb-1">{isDarkMode ? <Sun size={20} /> : <Moon size={20} />}</div>
            <span>Theme</span>
          </button>
        </div>
      )}
    </div>
  );
};

const TopNavItem = ({ label, onClick, isActive }) => (
  <button
    onClick={onClick}
    className={`text-sm font-bold transition-colors border-b-2 px-1 py-[16px] -mb-[1px] flex items-center ${
      isActive ? 'text-blue-400 border-blue-400' : 'text-gray-400 border-transparent hover:text-white'
    }`}
  >
    {label}
  </button>
);

const NavItem = ({ icon, label, onClick, isActive }) => (
  <button
    onClick={onClick}
    className={`flex flex-col items-center p-2 text-[10px] font-bold transition-colors ${
      isActive ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
    }`}
  >
    <div className="mb-1">{icon}</div>
    <span>{label}</span>
  </button>
);

export default Layout;
