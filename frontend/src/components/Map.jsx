/**
 * Map Component — Main Leaflet map with layer controls
 * 
 * Updated to support AQI visualization and Multi-Exposure Priority scoring.
 */
import { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, LayersControl, GeoJSON, useMap, useMapEvents, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { getTileUrl, roadsApi, statsApi, aqiApi, corridorsApi } from '../api';
import CorridorProposalPanel from './CorridorProposalPanel';
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
  const [hoveredCorridor, setHoveredCorridor] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [selectedCorridor, setSelectedCorridor] = useState(null);
  const [showAfterVision, setShowAfterVision] = useState(false);
  const [corridorStatus, setCorridorStatus] = useState(null);

  // Determine which raster layer is active (only one at a time for clarity)
  const activeRaster = activeLayers.gdi ? 'gdi' : activeLayers.lst ? 'lst' : activeLayers.ndvi ? 'ndvi' : null;

  // Load corridors with streaming (progressive loading)
  useEffect(() => {
    if (activeLayers.corridors && !corridors) {
      setLoading(prev => ({ ...prev, corridors: true }));
      setCorridorStatus('Connecting...');
      
      // Initialize empty GeoJSON
      setCorridors({
        type: 'FeatureCollection',
        features: []
      });
      
      // Use streaming endpoint with fetch and callback
      corridorsApi.stream(0.60, 200, true, (event) => {
        if (event.type === 'status') {
          setCorridorStatus(event.data.message);
        } else if (event.type === 'corridor') {
          setCorridors(prev => {
            const newFeatures = [...prev.features, event.data];
            setCorridorStatus(`Loaded ${newFeatures.length} corridors...`);
            return { ...prev, features: newFeatures };
          });
        } else if (event.type === 'complete') {
          console.log(`✅ Loaded ${event.data.count} corridors`);
          setCorridorStatus(null);
          setLoading(prev => ({ ...prev, corridors: false }));
        } else if (event.type === 'error') {
          console.error('Corridor streaming error:', event.data.error);
          setCorridorStatus(null);
          setLoading(prev => ({ ...prev, corridors: false }));
        }
      }).catch(err => {
        console.error('Failed to stream corridors:', err);
        setCorridorStatus(null);
        setLoading(prev => ({ ...prev, corridors: false }));
      });
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

  // Handle corridor hover events
  const handleCorridorHover = useCallback((feature, layer) => {
    layer.on({
      mouseover: (e) => {
        const props = feature.properties;
        setHoveredCorridor(props?.corridor_id);
        setTooltipPos({ x: e.originalEvent.clientX, y: e.originalEvent.clientY });
        // Bring to front on hover
        e.target.bringToFront();
      },
      mouseout: () => {
        setHoveredCorridor(null);
      },
      mousemove: (e) => {
        setTooltipPos({ x: e.originalEvent.clientX, y: e.originalEvent.clientY });
      },
    });
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
        {activeLayers.corridors && corridors && corridors.features && corridors.features.length > 0 && (
          <GeoJSON
            key={`corridors-${corridors.features.length}-${hoveredCorridor || 'none'}-${selectedCorridor?.properties?.corridor_id || ''}`}
            data={corridors}
            style={(feature) => {
              const meanPriority = feature.properties?.mean_priority ?? 0.5;
              const isHovered = hoveredCorridor === feature.properties?.corridor_id;
              const isSelected = selectedCorridor?.properties?.corridor_id === feature.properties?.corridor_id;
              let color;
              if (meanPriority > 0.80) color = '#d73027';
              else if (meanPriority > 0.70) color = '#fc8d59';
              else color = '#fee08b';
              
              // Show green overlay when "after" vision is active for selected corridor
              if (isSelected && showAfterVision) {
                color = '#1a9850';
              }
              
              return {
                color,
                weight: isSelected ? 8 : isHovered ? 7 : 4,
                opacity: isSelected ? 1 : isHovered ? 1 : 0.8,
                dashArray: isSelected && showAfterVision ? '10, 5' : null,
              };
            }}
            onEachFeature={(feature, layer) => {
              handleCorridorHover(feature, layer);
              
              // Click to open proposal panel
              layer.on('click', (e) => {
                // Prevent map click event
                e.originalEvent.stopPropagation();
                setSelectedCorridor(feature);
                setPointData(null); // Close point info panel
              });
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
          {corridorStatus || `Loading ${loading.corridors ? 'corridors' : loading.aqi ? 'AQI stations' : 'roads'}...`}
        </div>
      )}

      {/* Corridor Hover Tooltip */}
      {hoveredCorridor && corridors?.features && (() => {
        const feature = corridors.features.find(f => f.properties?.corridor_id === hoveredCorridor);
        if (!feature) return null;
        const props = feature.properties;
        const priority = props.mean_priority;
        // Risk levels within filtered corridors (all are already high-priority)
        const riskLevel = priority > 0.80 ? 'Critical' : priority > 0.70 ? 'High' : 'Elevated';
        const riskColor = priority > 0.80 ? '#d73027' : priority > 0.70 ? '#fc8d59' : '#fee08b';
        
        return (
          <div 
            className="corridor-tooltip"
            style={{ 
              left: tooltipPos.x + 15, 
              top: tooltipPos.y - 10,
            }}
          >
            <div className="tooltip-header">
              <span className="risk-badge" style={{ background: riskColor }}>
                {riskLevel}
              </span>
              Priority Corridor
            </div>
            <div className="tooltip-content">
              <div className="tooltip-row">
                <span className="tooltip-label">📏 Length</span>
                <span className="tooltip-value">{(props.length_m / 1000).toFixed(2)} km</span>
              </div>
              <div className="tooltip-row">
                <span className="tooltip-label">🔗 Segments</span>
                <span className="tooltip-value">{props.segment_count}</span>
              </div>
              <div className="tooltip-row">
                <span className="tooltip-label">📊 Priority</span>
                <span className="tooltip-value" style={{ color: riskColor }}>
                  {(priority * 100).toFixed(1)}%
                </span>
              </div>
              {props.mean_aqi && (
                <div className="tooltip-row">
                  <span className="tooltip-label">💨 PM2.5</span>
                  <span className="tooltip-value">{Math.round(props.mean_aqi)} μg/m³</span>
                </div>
              )}
              {props.mean_heat && (
                <div className="tooltip-row">
                  <span className="tooltip-label">🌡️ Heat</span>
                  <span className="tooltip-value">{(props.mean_heat * 100).toFixed(0)}%</span>
                </div>
              )}
              {props.mean_ndvi && (
                <div className="tooltip-row">
                  <span className="tooltip-label">🌿 Green</span>
                  <span className="tooltip-value">{(props.mean_ndvi * 100).toFixed(0)}%</span>
                </div>
              )}
            </div>
            <div className="tooltip-hint">Click to view proposal</div>
          </div>
        );
      })()}

      {/* Corridor Proposal Panel */}
      {selectedCorridor && (
        <CorridorProposalPanel
          corridor={selectedCorridor}
          onClose={() => {
            setSelectedCorridor(null);
            setShowAfterVision(false);
          }}
          onShowAfter={setShowAfterVision}
        />
      )}
    </div>
  );
}
