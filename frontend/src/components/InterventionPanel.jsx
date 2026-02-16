/**
 * InterventionPanel — Right-side sliding panel for corridor intervention suggestions
 * 
 * Displays when a corridor is clicked:
 * - Corridor type classification
 * - Recommended green interventions
 * - Human-readable rationale
 * 
 * Designed for clarity, not density. No numbers, equations, or jargon.
 */
import { useEffect, useRef } from 'react';
import './InterventionPanel.css';

// Intervention icons for visual appeal
const INTERVENTION_ICONS = {
  "Street tree canopy": "🌳",
  "Shaded pedestrian walkways": "☂️",
  "Dense vegetation buffers": "🌲",
  "Green screens along sidewalks": "🌿",
  "Pocket green spaces": "🏞️",
  "Cycle lanes with greening": "🚴",
  "Combined tree planting and shading": "🌳",
  "Multi-functional green infrastructure": "🌱"
};

// Type labels for display
const TYPE_LABELS = {
  "heat_dominated": "Heat-Dominated Corridor",
  "pollution_dominated": "Air Quality Corridor",
  "green_deficit": "Green Connectivity Corridor",
  "mixed_exposure": "Multi-Challenge Corridor"
};

export default function InterventionPanel({ corridor, onClose }) {
  const panelRef = useRef(null);
  
  // Focus trap and escape key handler
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);
  
  if (!corridor) return null;
  
  const props = corridor.properties || {};
  const corridorType = props.corridor_type || 'mixed_exposure';
  const interventions = props.recommended_interventions || [];
  const rationale = props.intervention_rationale || '';
  const typeIcon = props.corridor_type_icon || '🛤️';
  const typeColor = props.corridor_type_color || '#fc8d59';
  const roadName = props.name || 'Selected Corridor';
  
  return (
    <div className="intervention-panel" ref={panelRef}>
      {/* Close button */}
      <button 
        className="panel-close-btn" 
        onClick={onClose}
        aria-label="Close panel"
      >
        ✕
      </button>
      
      {/* Header */}
      <div className="panel-header">
        <div className="panel-icon" style={{ background: typeColor }}>
          {typeIcon}
        </div>
        <div className="panel-title">
          <h2>{roadName}</h2>
          <span className="panel-subtitle">Corridor Selected</span>
        </div>
      </div>
      
      {/* Type Badge */}
      <div className="corridor-type-section">
        <div 
          className="corridor-type-badge"
          style={{ borderColor: typeColor, color: typeColor }}
        >
          {TYPE_LABELS[corridorType] || corridorType}
        </div>
      </div>
      
      {/* Interventions */}
      <div className="interventions-section">
        <h3>Suggested Interventions</h3>
        <div className="interventions-list">
          {interventions.map((intervention, idx) => (
            <div key={idx} className="intervention-item">
              <span className="intervention-icon">
                {INTERVENTION_ICONS[intervention] || '🌿'}
              </span>
              <span className="intervention-text">{intervention}</span>
            </div>
          ))}
        </div>
      </div>
      
      {/* Rationale */}
      <div className="rationale-section">
        <h3>Why This Works</h3>
        <p className="rationale-text">{rationale}</p>
      </div>
      
      {/* Footer hint */}
      <div className="panel-footer">
        <span className="footer-hint">Press ESC or click ✕ to return to map</span>
      </div>
    </div>
  );
}
