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
  list: (threshold = 0.60, minLength = 200, includeAqi = true) => 
    api.get('/priority-corridors', { 
      params: { 
        priority_threshold: threshold, 
        min_length: minLength,
        include_aqi: includeAqi 
      } 
    }),
  
  /**
   * Stream corridors one-by-one using fetch with ReadableStream.
   * Calls onEvent callback for each SSE event.
   */
  stream: async (threshold = 0.60, minLength = 200, includeAqi = true, onEvent) => {
    const params = new URLSearchParams({
      priority_threshold: threshold,
      min_length: minLength,
      include_aqi: includeAqi
    });
    
    const response = await fetch(`${API_BASE}/priority-corridors/stream?${params}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer
      
      let eventType = null;
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ') && eventType) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent({ type: eventType, data });
          } catch (e) {
            console.warn('Failed to parse SSE data:', line);
          }
          eventType = null;
        }
      }
    }
  },
  
  detail: (corridorId) => api.get(`/priority-corridors/${corridorId}`),
  summary: () => api.get('/priority-corridors/stats/summary'),
  
  // Proposal endpoints
  proposal: (corridorId) => api.get(`/priority-corridors/${corridorId}/proposal`),
  
  // Community feedback endpoints
  getFeedback: (corridorId, limit = 10) => 
    api.get(`/priority-corridors/${corridorId}/feedback`, { params: { limit } }),
  addFeedback: (corridorId, comment) => 
    api.post(`/priority-corridors/${corridorId}/feedback`, { comment }),
  voteCorridor: (corridorId, upvote = true) => 
    api.post(`/priority-corridors/${corridorId}/vote`, { upvote }),
  voteFeedback: (feedbackId, upvote = true) => 
    api.post(`/feedback/${feedbackId}/vote`, { upvote }),
  getCommunity: (corridorId, feedbackLimit = 5) => 
    api.get(`/priority-corridors/${corridorId}/community`, { params: { feedback_limit: feedbackLimit } }),
};

/**
 * Get tile URL template for Leaflet
 */
export const getTileUrl = (layer) => {
  return `${API_BASE}/tiles/${layer}/{z}/{x}/{y}.png`;
};

export default api;
