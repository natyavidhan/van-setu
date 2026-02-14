/**
 * API Service — centralized API calls to the backend
 * 
 * Updated to support AQI integration for Multi-Exposure Priority scoring.
 */
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

/**
 * Layer endpoints
 */
export const layersApi = {
  list: () => api.get('/layers'),
  get: (layerId) => api.get(`/layers/${layerId}`),
};

/**
 * Statistics endpoints
 */
export const statsApi = {
  all: () => api.get('/stats'),
  layer: (layerId) => api.get(`/stats/${layerId}`),
  histogram: (layerId, bins = 50) => api.get(`/stats/${layerId}/histogram`, { params: { bins } }),
  point: (lat, lng) => api.get('/point', { params: { lat, lng } }),
};

/**
 * Roads endpoints
 */
export const roadsApi = {
  simple: () => api.get('/roads/simple'),
  withGdi: (includeAqi = true) => api.get('/roads', { params: { include_aqi: includeAqi } }),
  corridors: (percentile = 85, includeAqi = true) => api.get('/corridors', { 
    params: { percentile, include_aqi: includeAqi } 
  }),
};

/**
 * AQI endpoints
 */
export const aqiApi = {
  stations: () => api.get('/aqi/stations'),
  status: () => api.get('/aqi/status'),
  atPoint: (lat, lng) => api.get('/aqi/point', { params: { lat, lng } }),
  refresh: () => api.post('/aqi/refresh'),
};

/**
 * Corridors endpoints (aggregated priority corridors)
 */
export const corridorsApi = {
  list: (threshold = 0.70, minLength = 200, includeAqi = true) => 
    api.get('/corridors', { 
      params: { 
        priority_threshold: threshold, 
        min_length: minLength,
        include_aqi: includeAqi 
      } 
    }),
  detail: (corridorId) => api.get(`/corridors/${corridorId}`),
  summary: () => api.get('/corridors/stats/summary'),
};

/**
 * Get tile URL template for Leaflet
 */
export const getTileUrl = (layer) => {
  return `${API_BASE}/tiles/${layer}/{z}/{x}/{y}.png`;
};

export default api;
