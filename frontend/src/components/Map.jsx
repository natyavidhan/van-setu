/**
 * Map Component — Main Leaflet map with layer controls
 * 
 * Updated to support AQI visualization and Multi-Exposure Priority scoring.
 */
import { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, LayersControl, GeoJSON, useMap, useMapEvents, CircleMarker, Popup, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { getTileUrl, roadsApi, statsApi, aqiApi, corridorsApi } from '../api';
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
 * Corridor Summary Panel - shows detailed info when a corridor is selected
 * 
 * Displays:
 * - Number of constituent points
 * - Average exposure metrics
 * - Dominant exposure type
 * - Corridor length
 */
function CorridorSummary({ corridorId, corridors, onClose }) {
  const corridor = corridors?.features?.find(
    f => f.properties?.corridor_id === corridorId
  );
  
  if (!corridor) return null;
  
  const props = corridor.properties;
  
  const getPriorityColor = (value) => {
    if (value > 0.75) return '#d73027';
    if (value > 0.6) return '#fc8d59';
    if (value > 0.45) return '#fee08b';
    return '#91cf60';
  };
  
  const exposureLabels = {
    'heat': { icon: '🌡️', label: 'Heat Stress' },
    'green_deficit': { icon: '🌿', label: 'Green Deficit' },
    'air_quality': { icon: '💨', label: 'Air Pollution' },
    'unknown': { icon: '❓', label: 'Unknown' }
  };
  
  const exposure = exposureLabels[props.dominant_exposure] || exposureLabels.unknown;
  
  return (
    <div className="corridor-summary">
      <button className="close-btn" onClick={onClose}>×</button>
      <h4>🛤️ Exposure Corridor</h4>
      
      <div className="corridor-stats">
        <div className="stat-row">
          <span className="stat-label">Points</span>
          <span className="stat-value">{props.num_points}</span>
        </div>
        
        <div className="stat-row">
          <span className="stat-label">Length</span>
          <span className="stat-value">
            {props.corridor_length_m ? `${Math.round(props.corridor_length_m)}m` : 'N/A'}
          </span>
        </div>
        
        <div className="stat-row priority-row">
          <span className="stat-label">Mean Priority</span>
          <span 
            className="stat-value priority"
            style={{ color: getPriorityColor(props.mean_priority) }}
          >
            {props.mean_priority?.toFixed(3) || 'N/A'}
          </span>
        </div>
        
        <div className="stat-row">
          <span className="stat-label">Dominant Exposure</span>
          <span className="stat-value">
            {exposure.icon} {exposure.label}
          </span>
        </div>
      </div>
      
      <div className="corridor-details">
        <h5>Exposure Breakdown</h5>
        <div className="exposure-bars">
          {props.mean_heat !== null && props.mean_heat !== undefined && (
            <div className="exposure-bar">
              <span className="bar-label">🌡️ Heat</span>
              <div className="bar-track">
                <div 
                  className="bar-fill heat"
                  style={{ width: `${props.mean_heat * 100}%` }}
                />
              </div>
              <span className="bar-value">{(props.mean_heat * 100).toFixed(0)}%</span>
            </div>
          )}
          
          {props.mean_ndvi !== null && props.mean_ndvi !== undefined && (
            <div className="exposure-bar">
              <span className="bar-label">🌿 Green</span>
              <div className="bar-track">
                <div 
                  className="bar-fill green"
                  style={{ width: `${props.mean_ndvi * 100}%` }}
                />
              </div>
              <span className="bar-value">{(props.mean_ndvi * 100).toFixed(0)}%</span>
            </div>
          )}
          
          {props.mean_aqi !== null && props.mean_aqi !== undefined && (
            <div className="exposure-bar">
              <span className="bar-label">💨 AQI</span>
              <div className="bar-track">
                <div 
                  className="bar-fill aqi"
                  style={{ width: `${props.mean_aqi * 100}%` }}
                />
              </div>
              <span className="bar-value">{(props.mean_aqi * 100).toFixed(0)}%</span>
            </div>
          )}
        </div>
      </div>
      
      <div className="corridor-note">
        <small>Click corridor again to deselect</small>
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
  
  // New state for aggregated corridors (point-based)
  const [aggregatedCorridors, setAggregatedCorridors] = useState(null);
  const [highPriorityPoints, setHighPriorityPoints] = useState(null);
  const [selectedCorridor, setSelectedCorridor] = useState(null);
  const [corridorConfig, setCorridorConfig] = useState({
    dMax: 30,
    nMin: 5,
    percentile: 85
  });

  // Determine which raster layer is active (only one at a time for clarity)
  const activeRaster = activeLayers.gdi ? 'gdi' : activeLayers.lst ? 'lst' : activeLayers.ndvi ? 'ndvi' : null;

  // Load corridors when toggled (existing road-based corridors)
  useEffect(() => {
    if (activeLayers.corridors && !corridors) {
      setLoading(prev => ({ ...prev, corridors: true }));
      roadsApi.corridors(85, true)  // Include AQI in scoring
        .then(res => setCorridors(res.data))
        .catch(err => console.error('Failed to load corridors:', err))
        .finally(() => setLoading(prev => ({ ...prev, corridors: false })));
    }
  }, [activeLayers.corridors, corridors]);

  // Load aggregated corridors when toggled (new point-based corridors)
  useEffect(() => {
    if (activeLayers.aggregatedCorridors) {
      setLoading(prev => ({ ...prev, aggregatedCorridors: true }));
      const { dMax, nMin, percentile } = corridorConfig;
      
      Promise.all([
        corridorsApi.aggregated(dMax, nMin, percentile),
        corridorsApi.points(percentile, false)
      ])
        .then(([corridorsRes, pointsRes]) => {
          setAggregatedCorridors(corridorsRes.data);
          setHighPriorityPoints(pointsRes.data);
        })
        .catch(err => console.error('Failed to load aggregated corridors:', err))
        .finally(() => setLoading(prev => ({ ...prev, aggregatedCorridors: false })));
    }
  }, [activeLayers.aggregatedCorridors, corridorConfig]);

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
  const corridorStyle = (feature) => {
    const priority = feature.properties?.priority_score ?? feature.properties?.gdi_mean ?? 0.5;
    return {
      color: priority > 0.7 ? '#d73027' : priority > 0.5 ? '#fc8d59' : '#fee08b',
      weight: 4,
      opacity: 0.9,
    };
  };

  /**
   * Style for aggregated corridors (point-based)
   * These are thicker than the original corridors to visually distinguish them
   * Color is based on mean_priority (derived from constituent points)
   */
  const aggregatedCorridorStyle = (feature) => {
    const priority = feature.properties?.mean_priority ?? 0.5;
    const isSelected = selectedCorridor === feature.properties?.corridor_id;
    
    // Color gradient: green (low) -> yellow -> orange -> red (high)
    let color;
    if (priority > 0.75) color = '#d73027';      // Critical - dark red
    else if (priority > 0.6) color = '#fc8d59';  // High - orange
    else if (priority > 0.45) color = '#fee08b'; // Moderate - yellow
    else color = '#91cf60';                      // Low - light green
    
    return {
      color: isSelected ? '#1a1aff' : color,
      weight: isSelected ? 8 : 6,
      opacity: isSelected ? 1 : 0.85,
      lineCap: 'round',
      lineJoin: 'round',
    };
  };

  /**
   * Style for high-priority points used in corridor aggregation
   * Points remain visible underneath corridors
   */
  const getPointStyle = (feature) => {
    const priority = feature.properties?.priority_score ?? 0.5;
    const isInSelectedCorridor = selectedCorridor && 
      aggregatedCorridors?.features?.some(c => 
        c.properties.corridor_id === selectedCorridor &&
        c.properties.point_ids?.includes(feature.properties.point_id)
      );
    
    let fillColor;
    if (priority > 0.75) fillColor = '#d73027';
    else if (priority > 0.6) fillColor = '#fc8d59';
    else if (priority > 0.45) fillColor = '#fee08b';
    else fillColor = '#91cf60';
    
    return {
      radius: isInSelectedCorridor ? 6 : 4,
      fillColor: fillColor,
      color: isInSelectedCorridor ? '#1a1aff' : '#fff',
      weight: isInSelectedCorridor ? 2 : 1,
      opacity: 1,
      fillOpacity: 0.8,
    };
  };

  /**
   * Handle corridor click - highlight corridor and its constituent points
   */
  const handleCorridorClick = useCallback((feature) => {
    const corridorId = feature.properties?.corridor_id;
    if (corridorId) {
      setSelectedCorridor(prev => prev === corridorId ? null : corridorId);
    }
  }, []);

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

        {/* Corridors layer */}
        {activeLayers.corridors && corridors && (
          <GeoJSON
            key="corridors"
            data={corridors}
            style={corridorStyle}
            onEachFeature={(feature, layer) => {
              const props = feature.properties;
              if (props) {
                const priority = props.priority_score ?? props.gdi_mean;
                const aqi = props.aqi_raw;
                layer.bindPopup(`
                  <b>Proposed Green Corridor</b><br/>
                  Road: ${props.name || 'Unnamed'}<br/>
                  Priority Score: ${priority?.toFixed(3) || 'N/A'}<br/>
                  ${aqi ? `PM2.5 AQI: ${Math.round(aqi)}` : ''}<br/>
                  Risk Level: ${priority > 0.7 ? 'Critical' : priority > 0.5 ? 'High' : 'Moderate'}
                `);
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

        {/* 
          HIGH-EXPOSURE CORRIDORS (Point-Based Aggregation)
          
          This layer shows corridors formed by connecting spatially continuous 
          high-priority points. Key characteristics:
          - Corridors are thicker lines to distinguish from individual road segments
          - Color represents mean priority of constituent points
          - Points remain visible underneath
          - Hover to see stats, click to highlight corridor and its points
        */}
        {activeLayers.aggregatedCorridors && aggregatedCorridors && aggregatedCorridors.features && (
          <GeoJSON
            key={`aggregated-corridors-${selectedCorridor || 'none'}`}
            data={aggregatedCorridors}
            style={aggregatedCorridorStyle}
            onEachFeature={(feature, layer) => {
              const props = feature.properties;
              if (props) {
                const priority = props.mean_priority;
                const length = props.corridor_length_m;
                const numPoints = props.num_points;
                const dominantExposure = props.dominant_exposure;
                
                // Format exposure type for display
                const exposureLabels = {
                  'heat': '🌡️ Heat Stress',
                  'green_deficit': '🌿 Green Deficit',
                  'air_quality': '💨 Air Pollution',
                  'unknown': '❓ Unknown'
                };

                // Priority level styling
                const priorityColor = priority > 0.7 ? '#d73027' : priority > 0.5 ? '#fc8d59' : '#91cf60';
                const priorityLabel = priority > 0.7 ? 'Critical' : priority > 0.5 ? 'High' : 'Moderate';
                
                // Bind tooltip for hover display
                layer.bindTooltip(`
                  <div class="corridor-tooltip">
                    <div class="tooltip-header">
                      <span class="tooltip-icon">🛤️</span>
                      <span class="tooltip-title">Exposure Corridor</span>
                      <span class="tooltip-priority" style="background: ${priorityColor}">${priorityLabel}</span>
                    </div>
                    <div class="tooltip-stats">
                      <div class="tooltip-stat">
                        <span class="stat-icon">📍</span>
                        <span class="stat-value">${numPoints}</span>
                        <span class="stat-label">points</span>
                      </div>
                      <div class="tooltip-stat">
                        <span class="stat-icon">📏</span>
                        <span class="stat-value">${length ? Math.round(length) : '—'}</span>
                        <span class="stat-label">meters</span>
                      </div>
                      <div class="tooltip-stat">
                        <span class="stat-icon">📊</span>
                        <span class="stat-value">${priority?.toFixed(2) || '—'}</span>
                        <span class="stat-label">priority</span>
                      </div>
                    </div>
                    <div class="tooltip-exposure">
                      <span class="exposure-label">Dominant:</span>
                      <span class="exposure-value">${exposureLabels[dominantExposure] || dominantExposure}</span>
                    </div>
                    <div class="tooltip-bars">
                      ${props.mean_heat != null ? `
                        <div class="tooltip-bar">
                          <span class="bar-icon">🌡️</span>
                          <div class="bar-track"><div class="bar-fill heat" style="width: ${props.mean_heat * 100}%"></div></div>
                          <span class="bar-pct">${(props.mean_heat * 100).toFixed(0)}%</span>
                        </div>
                      ` : ''}
                      ${props.mean_ndvi != null ? `
                        <div class="tooltip-bar">
                          <span class="bar-icon">🌿</span>
                          <div class="bar-track"><div class="bar-fill green" style="width: ${props.mean_ndvi * 100}%"></div></div>
                          <span class="bar-pct">${(props.mean_ndvi * 100).toFixed(0)}%</span>
                        </div>
                      ` : ''}
                      ${props.mean_aqi != null ? `
                        <div class="tooltip-bar">
                          <span class="bar-icon">💨</span>
                          <div class="bar-track"><div class="bar-fill aqi" style="width: ${props.mean_aqi * 100}%"></div></div>
                          <span class="bar-pct">${(props.mean_aqi * 100).toFixed(0)}%</span>
                        </div>
                      ` : ''}
                    </div>
                    <div class="tooltip-hint">Click to select</div>
                  </div>
                `, {
                  sticky: true,
                  direction: 'top',
                  offset: [0, -10],
                  className: 'corridor-tooltip-container'
                });
                
                // Click to select/highlight corridor
                layer.on('click', () => handleCorridorClick(feature));
              }
            }}
          />
        )}

        {/* 
          HIGH-PRIORITY POINTS 
          
          These are the input points to the corridor aggregation algorithm.
          They remain visible underneath the corridor lines to show:
          - Original point-level data is preserved
          - Which points belong to which corridor
          - Isolated (orphan) points that don't form corridors
        */}
        {activeLayers.aggregatedCorridors && highPriorityPoints && highPriorityPoints.features && (
          highPriorityPoints.features.map((point, idx) => {
            const coords = point.geometry.coordinates;
            const props = point.properties;
            const style = getPointStyle(point);
            
            return (
              <CircleMarker
                key={`hp-point-${idx}`}
                center={[coords[1], coords[0]]}
                {...style}
              >
                <Popup>
                  <div className="point-popup">
                    <b>📍 High-Priority Point</b><br/>
                    {props.road_name && <><b>Road:</b> {props.road_name}<br/></>}
                    <b>Priority:</b> {props.priority_score?.toFixed(3) || 'N/A'}<br/>
                    {props.heat_norm && <><b>Heat:</b> {(props.heat_norm * 100).toFixed(0)}%<br/></>}
                    {props.ndvi_norm && <><b>Vegetation:</b> {(props.ndvi_norm * 100).toFixed(0)}%<br/></>}
                    {props.aqi_norm && <><b>AQI:</b> {(props.aqi_norm * 100).toFixed(0)}%<br/></>}
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

      {/* Corridor Summary Panel - shows when a corridor is selected */}
      {selectedCorridor && aggregatedCorridors && (
        <CorridorSummary 
          corridorId={selectedCorridor}
          corridors={aggregatedCorridors}
          onClose={() => setSelectedCorridor(null)}
        />
      )}

      {/* Point info popup */}
      {pointData && (
        <PointInfo data={pointData} onClose={() => setPointData(null)} />
      )}

      {/* Loading indicators */}
      {(loading.corridors || loading.roads || loading.aqi || loading.aggregatedCorridors) && (
        <div className="loading-indicator">
          Loading {loading.aggregatedCorridors ? 'exposure corridors' : loading.corridors ? 'corridors' : loading.aqi ? 'AQI stations' : 'roads'}...
        </div>
      )}
    </div>
  );
}
