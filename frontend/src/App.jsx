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
    corridors: true,  // Green corridors - default on
    aqi: false,  // AQI stations layer
    // OSM overlay layers (translucent)
    osmRoads: false,     // OSM roads overlay
    osmParks: false,     // OSM parks/green spaces overlay
    osmResidential: false, // OSM residential areas overlay
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
