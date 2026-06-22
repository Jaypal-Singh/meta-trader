// Central API configuration
// In development: uses http://localhost:8000
// In production (Vercel): uses your AWS VPS IP from environment variable

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default API_URL;
