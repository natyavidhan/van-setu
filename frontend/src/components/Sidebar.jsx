/**
 * Sidebar Component — Layer controls and statistics
 * 
 * Updated to support AQI layer toggle and Multi-Exposure Priority scoring.
 */
import { useState, useEffect } from 'react';
import { statsApi, layersApi, aqiApi } from '../api';
import './Sidebar.css';

/**
 * Toggle switch component
 */
function Toggle({ checked, onChange, label, color }) {
  return (
    <label className="toggle-row">
      <div className="toggle-label">
        {color && <span className="layer-indicator" style={{ backgroundColor: color }} />}
        {label}
      </div>
      <div className={`toggle-switch ${checked ? 'active' : ''}`} onClick={onChange}>
        <div className="toggle-knob" />
      </div>
    </label>
  );
}

/**
 * Stats card component
 */
function StatCard({ title, value, unit, icon }) {
  return (
    <div className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div className="stat-content">
        <div className="stat-value">
          {typeof value === 'number' ? value.toFixed(2) : value || '—'}
          {unit && <span className="stat-unit">{unit}</span>}
        </div>
        <div className="stat-title">{title}</div>
      </div>
    </div>
  );
}

/**
 * Main Sidebar component
 */
export default function Sidebar({ activeLayers, setActiveLayers }) {
  const [stats, setStats] = useState(null);
  const [aqiStatus, setAqiStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({
    layers: true,
    rasters: true,
    vectors: true,
    stats: true,
  });

  // Fetch stats on mount
  useEffect(() => {
    setLoading(true);
    Promise.all([
      statsApi.all(),
      aqiApi.status()
    ])
      .then(([statsRes, aqiRes]) => {
        setStats(statsRes.data);
        setAqiStatus(aqiRes.data);
      })
      .catch(err => console.error('Failed to load stats:', err))
      .finally(() => setLoading(false));
  }, []);

  const toggleLayer = (layer) => {
    setActiveLayers(prev => ({
      ...prev,
      [layer]: !prev[layer]
    }));
  };

  const toggleSection = (section) => {
    setExpanded(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  return (
    <aside className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="logo">
          <span className="logo-icon">🌿</span>
          <div className="logo-text">
            <h1>Green Corridor</h1>
            <span className="subtitle">Delhi NCT Analysis</span>
          </div>
        </div>
      </div>

      {/* Layer Controls */}
      <div className="sidebar-section">
        <div 
          className="section-header"
          onClick={() => toggleSection('layers')}
        >
          <h3>📊 Data Layers</h3>
          <span className={`chevron ${expanded.layers ? 'open' : ''}`}>▼</span>
        </div>
        
        {expanded.layers && (
          <div className="section-content">
            {/* Raster layers */}
            <div className="layer-group">
              <div className="group-label">Raster Data</div>
              <Toggle
                label="Vegetation (NDVI)"
                checked={activeLayers.ndvi}
                onChange={() => toggleLayer('ndvi')}
                color="#238b45"
              />
              <Toggle
                label="Temperature (LST)"
                checked={activeLayers.lst}
                onChange={() => toggleLayer('lst')}
                color="#d73027"
              />
              <Toggle
                label="Multi-Exposure Priority"
                checked={activeLayers.gdi}
                onChange={() => toggleLayer('gdi')}
                color="#fee08b"
              />
            </div>

            {/* Vector layers */}
            <div className="layer-group">
              <div className="group-label">Vector Data</div>
              <Toggle
                label="Road Network"
                checked={activeLayers.roads}
                onChange={() => toggleLayer('roads')}
                color="#666"
              />
              <Toggle
                label="Green Corridors"
                checked={activeLayers.corridors}
                onChange={() => toggleLayer('corridors')}
                color="#fc8d59"
              />
              <Toggle
                label="AQI Stations"
                checked={activeLayers.aqi}
                onChange={() => toggleLayer('aqi')}
                color="#7b3294"
              />
            </div>

            {/* OSM Overlay layers */}
            <div className="layer-group">
              <div className="group-label">OSM Overlays</div>
              <Toggle
                label="Roads Overlay"
                checked={activeLayers.osmRoads}
                onChange={() => toggleLayer('osmRoads')}
                color="#888888"
              />
              <Toggle
                label="Parks & Green"
                checked={activeLayers.osmParks}
                onChange={() => toggleLayer('osmParks')}
                color="#2d8b2d"
              />
              <Toggle
                label="Residential"
                checked={activeLayers.osmResidential}
                onChange={() => toggleLayer('osmResidential')}
                color="#c4a484"
              />
            </div>
          </div>
        )}
      </div>

      {/* Statistics */}
      <div className="sidebar-section">
        <div 
          className="section-header"
          onClick={() => toggleSection('stats')}
        >
          <h3>📈 Statistics</h3>
          <span className={`chevron ${expanded.stats ? 'open' : ''}`}>▼</span>
        </div>

        {expanded.stats && (
          <div className="section-content">
            {loading ? (
              <div className="loading-stats">Loading statistics...</div>
            ) : stats ? (
              <div className="stats-grid">
                <StatCard
                  title="Mean NDVI"
                  value={stats.ndvi?.mean}
                  icon="🌿"
                />
                <StatCard
                  title="Mean Temp"
                  value={stats.lst?.mean}
                  unit="°C"
                  icon="🌡️"
                />
                <StatCard
                  title="Mean Priority"
                  value={stats.gdi?.mean}
                  icon="📊"
                />
                <StatCard
                  title="Avg PM2.5"
                  value={aqiStatus?.average_pm25}
                  icon="💨"
                />
              </div>
            ) : (
              <div className="no-stats">No statistics available</div>
            )}
          </div>
        )}
      </div>

      {/* Info Section */}
      <div className="sidebar-section">
        <div 
          className="section-header"
          onClick={() => toggleSection('info')}
        >
          <h3>ℹ️ About</h3>
          <span className={`chevron ${expanded.info ? 'open' : ''}`}>▼</span>
        </div>

        {expanded.info && (
          <div className="section-content">
            <div className="info-text">
              <p>
                <strong>Multi-Exposure Priority Index</strong> combines heat stress, 
                vegetation deficit, and air pollution to identify areas most in need 
                of green infrastructure.
              </p>
              <p className="formula">
                Priority = 0.45 × Heat + 0.35 × (1 - NDVI) + 0.20 × AQI
              </p>
              <p className="formula-note">
                When AQI data is unavailable, falls back to original GDI weights.
              </p>
              <p>
                <strong>Click anywhere</strong> on the map to query layer 
                values at that location.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <p>Urban Green Corridor Platform</p>
        <p className="credits">innovateNSUT 2024</p>
      </div>
    </aside>
  );
}
