/**
 * Map Component — Main Leaflet map with layer controls
 * 
 * Updated to support AQI visualization and Multi-Exposure Priority scoring.
 */
import { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, LayersControl, GeoJSON, useMap, useMapEvents, CircleMarker, Popup, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { getTileUrl, roadsApi, statsApi, aqiApi } from '../api';
import './Map.css';

// Delhi NCT center and bounds
const DELHI_CENTER = [28.6139, 77.209];
const DELHI_BOUNDS = [
  [28.40, 76.73],  // Southwest
  [28.87, 77.35]   // Northeast
];

/**
 * Custom hook for click-to-query functionality
 */
function ClickHandler({ onPointQuery }) {
  useMapEvents({
    click: (e) => {
      if (onPointQuery) {
        onPointQuery(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
}

/**
 * Legend component for the active layer
 * Updated to reflect Multi-Exposure Priority scoring
 */
function Legend({ activeLayer }) {
  const legends = {
    ndvi: {
      title: 'NDVI',
      colors: ['#f7fcf5', '#c7e9c0', '#74c476', '#238b45', '#00441b'],
      labels: ['Low', '', '', '', 'High'],
    },
    lst: {
      title: 'Temperature',
      colors: ['#4575b4', '#91bfdb', '#fee090', '#fc8d59', '#d73027'],
      labels: ['Cool', '', '', '', 'Hot'],
    },
    gdi: {
      title: 'Multi-Exposure Priority',
      subtitle: 'Heat + Green + Air Quality',
      colors: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
      labels: ['Low', '', '', '', 'High'],
    },
  };

  const legend = legends[activeLayer];
  if (!legend) return null;

  return (
    <div className="map-legend">
      <h4>{legend.title}</h4>
      {legend.subtitle && <span className="legend-subtitle">{legend.subtitle}</span>}
      <div className="legend-gradient">
        {legend.colors.map((color, i) => (
          <div
            key={i}
            className="legend-color"
            style={{ backgroundColor: color }}
          />
        ))}
      </div>
      <div className="legend-labels">
        <span>{legend.labels[0]}</span>
        <span>{legend.labels[4]}</span>
      </div>
    </div>
  );
}

/**
 * Point info popup — shows all layer values including AQI
 */
function PointInfo({ data, onClose }) {
  if (!data) return null;

  const getPriorityColor = (value) => {
    if (value < 0.3) return 'var(--primary-green)';
    if (value < 0.5) return '#91cf60';
    if (value < 0.7) return 'var(--warning-yellow)';
    return 'var(--alert-red)';
  };

  const getAqiColor = (aqi) => {
    if (aqi <= 50) return 'var(--primary-green)';
    if (aqi <= 100) return '#91cf60';
    if (aqi <= 200) return 'var(--warning-yellow)';
    if (aqi <= 300) return '#fc8d59';
    return 'var(--alert-red)';
  };

  const getAqiLabel = (aqi) => {
    if (aqi <= 50) return 'Good';
    if (aqi <= 100) return 'Satisfactory';
    if (aqi <= 200) return 'Moderate';
    if (aqi <= 300) return 'Poor';
    return 'Very Poor';
  };

  // Use priority_score if available, otherwise fall back to gdi
  const priorityValue = data.values.priority_score ?? data.values.gdi;

  return (
    <div className="point-info">
      <button className="close-btn" onClick={onClose}>×</button>
      <h4>📍 Point Analysis</h4>
      <div className="point-coords">
        {data.location.lat.toFixed(4)}°N, {data.location.lng.toFixed(4)}°E
      </div>
      <div className="point-values">
        {data.values.ndvi !== null && (
          <div className="value-row">
            <span className="label">🌿 NDVI</span>
            <span className="value">{data.values.ndvi.toFixed(3)}</span>
            <span className="interpretation">{data.interpretation.vegetation}</span>
          </div>
        )}
        {data.values.lst !== null && (
          <div className="value-row">
            <span className="label">🌡️ LST</span>
            <span className="value">{data.values.lst.toFixed(1)}°C</span>
            <span className="interpretation">{data.interpretation.temperature}</span>
          </div>
        )}
        {data.values.aqi_raw !== null && data.values.aqi_raw !== undefined && (
          <div className="value-row">
            <span className="label">💨 PM2.5</span>
            <span 
              className="value"
              style={{ color: getAqiColor(data.values.aqi_raw) }}
            >
              {Math.round(data.values.aqi_raw)}
            </span>
            <span className="interpretation">
              {getAqiLabel(data.values.aqi_raw)}
              {data.aqi_station && (
                <span className="station-info"> ({data.aqi_station.name})</span>
              )}
            </span>
          </div>
        )}
        {priorityValue !== null && priorityValue !== undefined && (
          <div className="value-row highlight">
            <span className="label">📊 Priority</span>
            <span 
              className="value priority"
              style={{ color: getPriorityColor(priorityValue) }}
            >
              {priorityValue.toFixed(3)}
            </span>
            <span className="interpretation">{data.interpretation.priority}</span>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Main Map component
 */
export default function Map({ activeLayers, onStatsUpdate }) {
  const [corridors, setCorridors] = useState(null);
  const [roads, setRoads] = useState(null);
  const [aqiStations, setAqiStations] = useState(null);
  const [pointData, setPointData] = useState(null);
  const [loading, setLoading] = useState({});
  
  // State for corridor hover highlighting
  const [hoveredCorridor, setHoveredCorridor] = useState(null);

  // Determine which raster layer is active (only one at a time for clarity)
  const activeRaster = activeLayers.gdi ? 'gdi' : activeLayers.lst ? 'lst' : activeLayers.ndvi ? 'ndvi' : null;

  // Load corridors when toggled
  useEffect(() => {
    if (activeLayers.corridors && !corridors) {
      setLoading(prev => ({ ...prev, corridors: true }));
      roadsApi.corridors(85, true)  // Include AQI in scoring
        .then(res => setCorridors(res.data))
        .catch(err => console.error('Failed to load corridors:', err))
        .finally(() => setLoading(prev => ({ ...prev, corridors: false })));
    }
  }, [activeLayers.corridors, corridors]);

  // Load roads when toggled
  useEffect(() => {
    if (activeLayers.roads && !roads) {
      setLoading(prev => ({ ...prev, roads: true }));
      roadsApi.simple()
        .then(res => setRoads(res.data))
        .catch(err => console.error('Failed to load roads:', err))
        .finally(() => setLoading(prev => ({ ...prev, roads: false })));
    }
  }, [activeLayers.roads, roads]);

  // Load AQI stations when toggled
  useEffect(() => {
    if (activeLayers.aqi && !aqiStations) {
      setLoading(prev => ({ ...prev, aqi: true }));
      aqiApi.stations()
        .then(res => setAqiStations(res.data))
        .catch(err => console.error('Failed to load AQI stations:', err))
        .finally(() => setLoading(prev => ({ ...prev, aqi: false })));
    }
  }, [activeLayers.aqi, aqiStations]);

  // Handle point click query
  const handlePointQuery = useCallback(async (lat, lng) => {
    try {
      const res = await statsApi.point(lat, lng);
      setPointData(res.data);
    } catch (err) {
      console.error('Failed to query point:', err);
    }
  }, []);

  // Style for corridors (high priority = red)
  // Now uses priority_score (multi-exposure) instead of just GDI
  // Supports hover highlighting
  const corridorStyle = useCallback((feature) => {
    const priority = feature.properties?.priority_score ?? feature.properties?.gdi_mean ?? 0.5;
    const featureId = feature.properties?.name || feature.id || JSON.stringify(feature.geometry?.coordinates?.[0]);
    const isHovered = hoveredCorridor === featureId;
    
    // Color based on priority
    let color;
    if (priority > 0.7) color = '#d73027';      // Critical - dark red
    else if (priority > 0.5) color = '#fc8d59'; // High - orange
    else color = '#fee08b';                     // Moderate - yellow
    
    return {
      color: isHovered ? '#00ffff' : color,
      weight: isHovered ? 7 : 4,
      opacity: isHovered ? 1 : 0.85,
      lineCap: 'round',
      lineJoin: 'round',
    };
  }, [hoveredCorridor]);

  // Style for roads (subtle gray)
  const roadStyle = {
    color: '#666',
    weight: 1.5,
    opacity: 0.6,
  };

  // Get AQI station color based on PM2.5 value
  const getAqiStationColor = (pm25) => {
    if (pm25 <= 50) return '#1a9850';
    if (pm25 <= 100) return '#91cf60';
    if (pm25 <= 200) return '#fee08b';
    if (pm25 <= 300) return '#fc8d59';
    return '#d73027';
  };

  return (
    <div className="map-container">
      <MapContainer
        center={DELHI_CENTER}
        zoom={11}
        minZoom={10}
        maxZoom={16}
        maxBounds={[
          [28.2, 76.5],
          [29.0, 77.6]
        ]}
      >
        {/* Base map */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />

        {/* NDVI layer */}
        {activeLayers.ndvi && (
          <TileLayer
            url={getTileUrl('ndvi')}
            opacity={0.7}
            zIndex={100}
          />
        )}

        {/* LST layer */}
        {activeLayers.lst && (
          <TileLayer
            url={getTileUrl('lst')}
            opacity={0.7}
            zIndex={101}
          />
        )}

        {/* GDI layer */}
        {activeLayers.gdi && (
          <TileLayer
            url={getTileUrl('gdi')}
            opacity={0.75}
            zIndex={102}
          />
        )}

        {/* Roads layer */}
        {activeLayers.roads && roads && (
          <GeoJSON
            key="roads"
            data={roads}
            style={roadStyle}
          />
        )}

        {/* Corridors layer - with hover highlighting and tooltips */}
        {activeLayers.corridors && corridors && (
          <GeoJSON
            key={`corridors-${hoveredCorridor || 'none'}`}
            data={corridors}
            style={corridorStyle}
            onEachFeature={(feature, layer) => {
              const props = feature.properties;
              if (props) {
                const priority = props.priority_score ?? props.gdi_mean ?? 0.5;
                const aqi = props.aqi_raw;
                const heat = props.heat_norm;
                const ndvi = props.ndvi_norm;
                const aqiNorm = props.aqi_norm;
                const roadName = props.name || 'Unnamed Road';
                const featureId = props.name || feature.id || JSON.stringify(feature.geometry?.coordinates?.[0]);
                
                // Priority level styling
                const priorityColor = priority > 0.7 ? '#d73027' : priority > 0.5 ? '#fc8d59' : '#91cf60';
                const priorityLabel = priority > 0.7 ? 'Critical' : priority > 0.5 ? 'High' : 'Moderate';
                
                // Bind tooltip for hover display
                layer.bindTooltip(`
                  <div class="corridor-tooltip">
                    <div class="tooltip-header">
                      <span class="tooltip-icon">🛤️</span>
                      <span class="tooltip-title">${roadName}</span>
                      <span class="tooltip-priority" style="background: ${priorityColor}">${priorityLabel}</span>
                    </div>
                    <div class="tooltip-stats">
                      <div class="tooltip-stat">
                        <span class="stat-icon">📊</span>
                        <span class="stat-value">${priority?.toFixed(2) || '—'}</span>
                        <span class="stat-label">priority</span>
                      </div>
                      ${aqi ? `
                      <div class="tooltip-stat">
                        <span class="stat-icon">💨</span>
                        <span class="stat-value">${Math.round(aqi)}</span>
                        <span class="stat-label">PM2.5</span>
                      </div>
                      ` : ''}
                    </div>
                    <div class="tooltip-bars">
                      ${heat != null ? `
                        <div class="tooltip-bar">
                          <span class="bar-icon">🌡️</span>
                          <div class="bar-track"><div class="bar-fill heat" style="width: ${heat * 100}%"></div></div>
                          <span class="bar-pct">${(heat * 100).toFixed(0)}%</span>
                        </div>
                      ` : ''}
                      ${ndvi != null ? `
                        <div class="tooltip-bar">
                          <span class="bar-icon">🌿</span>
                          <div class="bar-track"><div class="bar-fill green" style="width: ${ndvi * 100}%"></div></div>
                          <span class="bar-pct">${(ndvi * 100).toFixed(0)}%</span>
                        </div>
                      ` : ''}
                      ${aqiNorm != null ? `
                        <div class="tooltip-bar">
                          <span class="bar-icon">💨</span>
                          <div class="bar-track"><div class="bar-fill aqi" style="width: ${aqiNorm * 100}%"></div></div>
                          <span class="bar-pct">${(aqiNorm * 100).toFixed(0)}%</span>
                        </div>
                      ` : ''}
                    </div>
                  </div>
                `, {
                  sticky: true,
                  direction: 'top',
                  offset: [0, -10],
                  className: 'corridor-tooltip-container'
                });
                
                // Hover events for highlighting
                layer.on('mouseover', () => {
                  setHoveredCorridor(featureId);
                  layer.bringToFront();
                });
                
                layer.on('mouseout', () => {
                  setHoveredCorridor(null);
                });
              }
            }}
          />
        )}

        {/* AQI Stations layer */}
        {activeLayers.aqi && aqiStations && aqiStations.features && (
          aqiStations.features.map((station, idx) => {
            const coords = station.geometry.coordinates;
            const props = station.properties;
            const pm25 = props.pm25 || props.aqi_raw;
            
            return (
              <CircleMarker
                key={`aqi-${idx}`}
                center={[coords[1], coords[0]]}
                radius={8}
                fillColor={getAqiStationColor(pm25)}
                color="#fff"
                weight={2}
                opacity={1}
                fillOpacity={0.8}
              >
                <Popup>
                  <div className="aqi-popup">
                    <b>💨 {props.name}</b><br/>
                    PM2.5: <span style={{color: getAqiStationColor(pm25), fontWeight: 'bold'}}>
                      {pm25 ? Math.round(pm25) : 'N/A'}
                    </span><br/>
                    {props.pm10 && <>PM10: {Math.round(props.pm10)}<br/></>}
                    Source: {props.source}
                  </div>
                </Popup>
              </CircleMarker>
            );
          })
        )}

        {/* Click handler for point queries */}
        <ClickHandler onPointQuery={handlePointQuery} />
      </MapContainer>

      {/* Legend */}
      {activeRaster && <Legend activeLayer={activeRaster} />}

      {/* Point info popup */}
      {pointData && (
        <PointInfo data={pointData} onClose={() => setPointData(null)} />
      )}

      {/* Loading indicators */}
      {(loading.corridors || loading.roads || loading.aqi) && (
        <div className="loading-indicator">
          Loading {loading.corridors ? 'corridors' : loading.aqi ? 'AQI stations' : 'roads'}...
        </div>
      )}
    </div>
  );
}
