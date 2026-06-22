import React from 'react';
import WatchlistList from '../components/WatchlistList';
import { Activity } from 'lucide-react';

const Dashboard = () => {
  return (
    <>
      {/* Mobile: Show Watchlist */}
      <div className="md:hidden h-full">
        <WatchlistList />
      </div>

      {/* Desktop: Show Welcome / Placeholder in the main area */}
      <div className="hidden md:flex flex-col h-full items-center justify-center bg-gray-50 dark:bg-[#131722] text-gray-500 dark:text-gray-400 transition-colors duration-200">
        <div className="bg-white dark:bg-[#1e293b] p-6 rounded-full mb-6 shadow-xl border border-gray-200 dark:border-gray-800 transition-colors duration-200">
          <Activity size={48} className="text-emerald-500" />
        </div>
        <h2 className="text-2xl font-bold text-gray-800 dark:text-white mb-2">Welcome to GUARDEER PRO</h2>
        <p className="text-sm font-medium">Select an instrument from the Watchlist to view its chart</p>
      </div>
    </>
  );
};

export default Dashboard;
