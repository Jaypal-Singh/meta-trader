import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { List, TrendingUp, Wallet, PieChart, User, Activity, Moon, Sun } from 'lucide-react';
import WatchlistList from './WatchlistList';

const Layout = () => {
  const location = useLocation();
  const isChartPage = location.pathname.startsWith('/chart');
  
  // Theme state
  const [isDarkMode, setIsDarkMode] = useState(false);

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
          <span className="font-extrabold text-lg tracking-tight">GUARDEER PRO</span>
        </div>
        <div className="flex items-center space-x-8">
          <nav className="flex space-x-8">
            <TopNavItem to="/dashboard" label="Watchlist" />
            <TopNavItem to="/orders" label="Orders" />
            <TopNavItem to="/funds" label="Funds" />
            <TopNavItem to="/profile" label="Profile" />
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
        <aside className="hidden md:flex w-[350px] flex-col border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-[#1e293b] flex-none z-10 shadow-[2px_0_10px_rgba(0,0,0,0.03)] dark:shadow-none relative h-full transition-colors duration-200">
          <WatchlistList />
        </aside>

        {/* Content Area */}
        <main className={`flex-1 flex flex-col relative overflow-hidden bg-white dark:bg-[#131722] md:bg-[#131722] transition-colors duration-200 ${!isChartPage ? 'pb-[60px] md:pb-0' : ''}`}>
           <Outlet />
        </main>
      </div>

      {/* Mobile Bottom Navigation - Hide on Chart Page */}
      {!isChartPage && (
        <div className="md:hidden absolute bottom-0 w-full h-[60px] bg-white dark:bg-[#1e293b] border-t border-gray-200 dark:border-gray-800 flex justify-around items-center py-2 px-1 z-50 shadow-[0_-4px_10px_rgba(0,0,0,0.05)] transition-colors duration-200">
          <NavItem to="/dashboard" icon={<List size={20} />} label="Watchlist" />
          <NavItem to="/orders" icon={<TrendingUp size={20} />} label="Order" />
          <NavItem to="/funds" icon={<Wallet size={20} />} label="Funds" />
          <NavItem to="/portfolio" icon={<PieChart size={20} />} label="Portfolio" />
          
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

const TopNavItem = ({ to, label }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `text-sm font-bold transition-colors border-b-2 px-1 py-[16px] -mb-[1px] flex items-center ${
        isActive ? 'text-blue-400 border-blue-400' : 'text-gray-400 border-transparent hover:text-white'
      }`
    }
  >
    {label}
  </NavLink>
);

const NavItem = ({ to, icon, label }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `flex flex-col items-center p-2 text-[10px] font-bold transition-colors ${
        isActive ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
      }`
    }
  >
    <div className="mb-1">{icon}</div>
    <span>{label}</span>
  </NavLink>
);

export default Layout;
