import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login.jsx';
import Dashboard from './pages/Dashboard.jsx';
import ChartPage from './pages/ChartPage.jsx';
import OrdersPage from './pages/OrdersPage.jsx';
import FundsPage from './pages/FundsPage.jsx';

import Layout from './components/Layout.jsx';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-100 font-sans selection:bg-blue-500 selection:text-white">
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<Login />} />
          
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/chart/:symbol" element={<ChartPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/funds" element={<FundsPage />} />
          </Route>
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;

