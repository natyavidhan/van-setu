"""
Intervention Service — Corridor Classification & Green Intervention Suggestions

This service classifies corridors based on their dominant exposure type and
suggests appropriate green infrastructure interventions.

HOW INTERVENTION SUGGESTIONS ARE DERIVED:
=========================================

1. EXPOSURE SHARE CALCULATION:
   - Total = mean_heat + mean_aqi + mean_green_deficit
   - heat_share = mean_heat / Total
   - pollution_share = mean_aqi / Total  
   - green_share = mean_green_deficit / Total

2. CLASSIFICATION RULES (deterministic):
   - heat_dominated: heat_share >= 0.45
   - pollution_dominated: pollution_share >= 0.40
   - green_deficit: green_share >= 0.35
   - mixed_exposure: none of the above

3. INTERVENTION MAPPING:
   Each corridor type maps to specific, evidence-based green interventions
   suitable for that exposure profile.

This approach ensures:
- Deterministic, reproducible results
- No machine learning or complex models
- Clear rationale for each suggestion
- Actionable recommendations for urban planners
"""

from typing import Dict, List, Tuple, Optional


# Static mapping: corridor type -> recommended interventions
# Based on urban greening best practices for each exposure type
INTERVENTION_MAP: Dict[str, Dict] = {
    "heat_dominated": {
        "interventions": [
            "Street tree canopy",
            "Shaded pedestrian walkways"
        ],
        "rationale": "This corridor experiences high surface heat exposure with limited shade. Street trees and shaded walkways provide direct cooling through evapotranspiration and shade.",
        "icon": "🌡️",
        "color": "#d73027"
    },
    "pollution_dominated": {
        "interventions": [
            "Dense vegetation buffers",
            "Green screens along sidewalks"
        ],
        "rationale": "Air quality is the primary concern along this corridor. Dense vegetation acts as a natural filter, trapping particulate matter and improving breathability.",
        "icon": "💨",
        "color": "#7b3294"
    },
    "green_deficit": {
        "interventions": [
            "Pocket green spaces",
            "Cycle lanes with greening"
        ],
        "rationale": "This corridor lacks vegetation connectivity. Adding pocket parks and green cycle lanes improves ecological corridors and pedestrian experience.",
        "icon": "🌿",
        "color": "#1a9850"
    },
    "mixed_exposure": {
        "interventions": [
            "Combined tree planting and shading",
            "Multi-functional green infrastructure"
        ],
        "rationale": "This corridor faces multiple environmental challenges. A combined approach with diverse vegetation addresses heat, air quality, and greenery simultaneously.",
        "icon": "🌳",
        "color": "#fc8d59"
    }
}

# Classification thresholds
HEAT_THRESHOLD = 0.45      # heat_share >= 0.45 → heat_dominated
POLLUTION_THRESHOLD = 0.40  # pollution_share >= 0.40 → pollution_dominated
GREEN_THRESHOLD = 0.35      # green_share >= 0.35 → green_deficit


def classify_corridor(
    mean_heat: Optional[float],
    mean_aqi: Optional[float],
    mean_ndvi: Optional[float]
) -> Tuple[str, Dict]:
    """
    Classify a corridor based on its dominant exposure type.
    
    Args:
        mean_heat: Normalized heat exposure [0, 1]
        mean_aqi: Normalized AQI exposure [0, 1]
        mean_ndvi: Normalized vegetation index [0, 1]
        
    Returns:
        Tuple of (corridor_type, intervention_info)
    """
    # Handle missing values with defaults
    heat = mean_heat if mean_heat is not None else 0.0
    aqi = mean_aqi if mean_aqi is not None else 0.0
    
    # Green deficit = inverse of NDVI (low vegetation = high deficit)
    green_deficit = (1.0 - mean_ndvi) if mean_ndvi is not None else 0.5
    
    # Calculate total exposure
    total = heat + aqi + green_deficit
    
    # Avoid division by zero
    if total < 0.001:
        return "mixed_exposure", INTERVENTION_MAP["mixed_exposure"]
    
    # Calculate exposure shares
    heat_share = heat / total
    pollution_share = aqi / total
    green_share = green_deficit / total
    
    # Apply classification rules (in priority order)
    if heat_share >= HEAT_THRESHOLD:
        corridor_type = "heat_dominated"
    elif pollution_share >= POLLUTION_THRESHOLD:
        corridor_type = "pollution_dominated"
    elif green_share >= GREEN_THRESHOLD:
        corridor_type = "green_deficit"
    else:
        corridor_type = "mixed_exposure"
    
    return corridor_type, INTERVENTION_MAP[corridor_type]


def enrich_corridor_with_interventions(corridor_properties: Dict) -> Dict:
    """
    Enrich corridor properties with intervention classification and suggestions.
    
    Args:
        corridor_properties: Existing corridor properties dict
        
    Returns:
        Enriched properties dict with intervention data
    """
    # Extract exposure metrics
    mean_heat = corridor_properties.get('heat_norm')
    mean_aqi = corridor_properties.get('aqi_norm')
    mean_ndvi = corridor_properties.get('ndvi_norm')
    
    # Classify and get interventions
    corridor_type, intervention_info = classify_corridor(mean_heat, mean_aqi, mean_ndvi)
    
    # Add new fields without removing existing ones
    enriched = dict(corridor_properties)
    enriched['corridor_type'] = corridor_type
    enriched['corridor_type_icon'] = intervention_info['icon']
    enriched['corridor_type_color'] = intervention_info['color']
    enriched['recommended_interventions'] = intervention_info['interventions']
    enriched['intervention_rationale'] = intervention_info['rationale']
    
    return enriched


def enrich_geojson_corridors(geojson: Dict) -> Dict:
    """
    Enrich all corridors in a GeoJSON FeatureCollection with intervention data.
    
    Args:
        geojson: GeoJSON FeatureCollection
        
    Returns:
        Enriched GeoJSON with intervention data in each feature's properties
    """
    if not geojson or 'features' not in geojson:
        return geojson
    
    enriched_features = []
    for feature in geojson.get('features', []):
        if feature.get('properties'):
            feature['properties'] = enrich_corridor_with_interventions(feature['properties'])
        enriched_features.append(feature)
    
    return {
        **geojson,
        'features': enriched_features
    }
