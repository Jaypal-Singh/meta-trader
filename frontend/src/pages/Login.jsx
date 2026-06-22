import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, User, Activity } from 'lucide-react';
import API_URL from '../config/api';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    
    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      
      if (res.ok) {
        localStorage.setItem('token', data.access_token);
        navigate('/dashboard');
      } else {
        setError(data.detail || 'Login failed');
      }
    } catch (err) {
      setError('Cannot connect to backend server');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-trading-bg bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]">
      <div className="w-full max-w-md md:max-w-lg p-8 space-y-8 bg-trading-panel/80 rounded-2xl shadow-2xl border border-gray-800 backdrop-blur-md">
        <div className="text-center flex flex-col items-center">
          <div className="bg-trading-buy/20 p-3 rounded-full mb-4">
            <Activity className="w-8 h-8 text-trading-buy" />
          </div>
          <h2 className="text-3xl font-extrabold text-white tracking-tight">
            GUARDEER PRO
          </h2>
          <p className="mt-2 text-sm text-trading-muted font-medium">
            Institutional Grade Trading Terminal
          </p>
        </div>
        
        {error && (
          <div className="p-3 text-sm text-red-200 bg-red-900/40 border border-red-900/50 rounded-lg text-center">
            {error}
          </div>
        )}
        
        <form className="mt-8 space-y-6" onSubmit={handleLogin}>
          <div className="space-y-4 rounded-md shadow-sm">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                <User className="w-5 h-5 text-gray-500" />
              </div>
              <input
                type="text"
                required
                className="block w-full pl-10 pr-3 py-3 border border-gray-700 rounded-xl bg-gray-900/50 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-trading-buy focus:border-transparent transition-all duration-300"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            
            <div className="relative">
              <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                <Lock className="w-5 h-5 text-gray-500" />
              </div>
              <input
                type="password"
                required
                className="block w-full pl-10 pr-3 py-3 border border-gray-700 rounded-xl bg-gray-900/50 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-trading-buy focus:border-transparent transition-all duration-300"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className={`group relative flex w-full justify-center py-3.5 px-4 border border-transparent text-sm font-bold rounded-xl text-white transition-all duration-300 ${
                isLoading 
                  ? 'bg-trading-buy/50 cursor-not-allowed' 
                  : 'bg-trading-buy hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)] hover:shadow-[0_0_25px_rgba(16,185,129,0.5)] hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-trading-buy focus:ring-offset-trading-bg'
              }`}
            >
              {isLoading ? 'Authenticating...' : 'Sign In to Terminal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
