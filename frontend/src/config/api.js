// Central API configuration
// In development: uses http://localhost:8000
// In production (Vercel): uses your AWS VPS IP from environment variable

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

if (!window.__fetchOverridden) {
  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
      let [resource, config] = args;
      if (!config) config = {};
      if (!config.headers) config.headers = {};
      
      if (config.headers instanceof Headers) {
          config.headers.append('Bypass-Tunnel-Reminder', 'true');
          config.headers.append('ngrok-skip-browser-warning', 'true');
      } else {
          config.headers['Bypass-Tunnel-Reminder'] = 'true';
          config.headers['ngrok-skip-browser-warning'] = 'true';
      }
      return originalFetch(resource, config);
  };
  window.__fetchOverridden = true;
}

export default API_URL;
