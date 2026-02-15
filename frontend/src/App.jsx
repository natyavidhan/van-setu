/**
 * App Component — Main application layout
 */
import { useState } from 'react';
import Map from './components/Map';
import Sidebar from './components/Sidebar';
import './App.css';

export default function App() {
  // Layer visibility state
  const [activeLayers, setActiveLayers] = useState({
    ndvi: false,
    lst: false,
    gdi: true,  // Default: show GDI
    roads: false,
    corridors: false,  // Original road-based corridors
    aggregatedCorridors: true,  // NEW: Point-based aggregated corridors (default on)
    aqi: false,  // AQI stations layer
  });

  return (
    <div className="app">
      <Sidebar 
        activeLayers={activeLayers} 
        setActiveLayers={setActiveLayers}
      />
      <main className="main-content">
        <Map 
          activeLayers={activeLayers}
        />
      </main>
    </div>
  );
}
