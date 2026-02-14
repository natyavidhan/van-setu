"""
Intervention Suggestion Service — Rule-based corridor intervention recommendations.

Maps corridor exposure profiles to context-appropriate interventions.
NO ML, NO black box — simple, deterministic rules.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


# =============================================================================
# INTERVENTION LOOKUP TABLE
# =============================================================================

INTERVENTION_CATALOG = {
    "Heat Mitigation": {
        "description": "Corridors where heat exposure is the dominant concern",
        "interventions": [
            {
                "id": "tree_canopy",
                "name": "Continuous street tree canopy",
                "description": "Dense tree planting along both sides of the corridor to provide shade coverage",
                "icon": "🌳",
                "primary_benefit": "heat_reduction"
            },
            {
                "id": "shaded_walkway",
                "name": "Shaded pedestrian walkways",
                "description": "Covered or tree-lined paths for comfortable walking in hot conditions",
                "icon": "🚶",
                "primary_benefit": "pedestrian_comfort"
            },
            {
                "id": "cool_paving",
                "name": "High-albedo or permeable paving",
                "description": "Light-colored or porous surfaces that reduce heat absorption",
                "icon": "🛤️",
                "primary_benefit": "surface_cooling"
            }
        ]
    },
    "Air Quality Buffer": {
        "description": "Corridors where air pollution is the dominant concern",
        "interventions": [
            {
                "id": "vegetation_buffer",
                "name": "Dense roadside vegetation buffers",
                "description": "Multi-layered planting to filter particulate matter from traffic",
                "icon": "🌿",
                "primary_benefit": "pollution_filtering"
            },
            {
                "id": "green_screen",
                "name": "Green screens or hedges",
                "description": "Vertical green barriers to intercept pollutants near emission sources",
                "icon": "🌲",
                "primary_benefit": "barrier_creation"
            },
            {
                "id": "setback_planting",
                "name": "Setback planting near traffic lanes",
                "description": "Strategic vegetation placement to maximize distance from pollution sources",
                "icon": "🌱",
                "primary_benefit": "exposure_reduction"
            }
        ]
    },
    "Green Connectivity": {
        "description": "Corridors where green space deficit is the dominant concern",
        "interventions": [
            {
                "id": "walking_corridor",
                "name": "Tree-lined walking corridors",
                "description": "Continuous green pathways connecting neighborhoods to parks and amenities",
                "icon": "🚶‍♀️",
                "primary_benefit": "connectivity"
            },
            {
                "id": "cycle_street",
                "name": "Cycle-friendly green streets",
                "description": "Protected cycling lanes with adjacent greenery for safe, pleasant travel",
                "icon": "🚴",
                "primary_benefit": "active_mobility"
            },
            {
                "id": "pocket_green",
                "name": "Pocket greens at intersections",
                "description": "Small green spaces at key junctions for rest and visual appeal",
                "icon": "🌺",
                "primary_benefit": "urban_greening"
            }
        ]
    },
    "Multi-Benefit": {
        "description": "Corridors with multiple environmental concerns requiring integrated solutions",
        "interventions": [
            {
                "id": "mixed_canopy",
                "name": "Mixed tree canopy and shaded paths",
                "description": "Diverse tree species providing both shade and air quality benefits",
                "icon": "🌴",
                "primary_benefit": "multiple"
            },
            {
                "id": "green_corridor",
                "name": "Cycle + pedestrian green corridors",
                "description": "Combined mobility corridor with comprehensive green infrastructure",
                "icon": "🛣️",
                "primary_benefit": "integrated"
            }
        ]
    }
}


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class ExposureProfile:
    """Breakdown of corridor environmental exposure scores."""
    heat_score: float          # Normalized LST/heat exposure (0-1)
    pollution_score: float     # Normalized AQI/PM2.5 exposure (0-1)
    green_deficit_score: float # Normalized NDVI deficit (0-1, higher = less green)
    
    def dominant_exposure(self) -> str:
        """Get the dominant exposure type."""
        scores = {
            "heat": self.heat_score,
            "pollution": self.pollution_score,
            "green_deficit": self.green_deficit_score
        }
        max_score = max(scores.values())
        
        # Check if there's a clear dominant factor (>20% higher than others)
        dominant = [k for k, v in scores.items() if v == max_score]
        others = [v for k, v in scores.items() if k not in dominant]
        
        if others and max_score - max(others) < 0.15:
            return "mixed"
        return dominant[0]


@dataclass
class CorridorProposal:
    """Complete proposal for a corridor including type, interventions, and exposure."""
    corridor_id: str
    corridor_type: str
    corridor_type_description: str
    exposure_breakdown: Dict[str, float]
    suggested_interventions: List[Dict[str, Any]]
    generated_at: str = None
    
    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now().isoformat()


# =============================================================================
# INTERVENTION SERVICE
# =============================================================================

class InterventionService:
    """
    Rule-based intervention suggestion engine.
    
    Maps corridor exposure profiles to appropriate interventions
    using simple, deterministic rules.
    """
    
    def __init__(self):
        self.catalog = INTERVENTION_CATALOG
    
    def classify_corridor(self, exposure: ExposureProfile) -> str:
        """
        Classify corridor type based on dominant exposure.
        
        Rules:
            - heat_score dominant → "Heat Mitigation"
            - pollution_score dominant → "Air Quality Buffer"
            - green_deficit_score dominant → "Green Connectivity"
            - mixed/balanced → "Multi-Benefit"
        """
        dominant = exposure.dominant_exposure()
        
        type_mapping = {
            "heat": "Heat Mitigation",
            "pollution": "Air Quality Buffer",
            "green_deficit": "Green Connectivity",
            "mixed": "Multi-Benefit"
        }
        
        return type_mapping.get(dominant, "Multi-Benefit")
    
    def get_interventions(self, corridor_type: str, max_interventions: int = 3) -> List[Dict[str, Any]]:
        """
        Get suggested interventions for a corridor type.
        
        Args:
            corridor_type: One of the defined corridor types
            max_interventions: Maximum number to return (default 3)
        
        Returns:
            List of intervention dictionaries
        """
        category = self.catalog.get(corridor_type)
        if not category:
            # Fallback to Multi-Benefit
            category = self.catalog["Multi-Benefit"]
        
        interventions = category.get("interventions", [])
        return interventions[:max_interventions]
    
    def generate_proposal(
        self,
        corridor_id: str,
        heat_score: float,
        pollution_score: float,
        green_deficit_score: float
    ) -> CorridorProposal:
        """
        Generate a complete proposal for a corridor.
        
        Args:
            corridor_id: Unique identifier
            heat_score: Normalized heat exposure (0-1)
            pollution_score: Normalized pollution exposure (0-1)
            green_deficit_score: Normalized green deficit (0-1)
        
        Returns:
            CorridorProposal with type, interventions, and breakdown
        """
        # Create exposure profile
        exposure = ExposureProfile(
            heat_score=heat_score,
            pollution_score=pollution_score,
            green_deficit_score=green_deficit_score
        )
        
        # Classify corridor
        corridor_type = self.classify_corridor(exposure)
        
        # Get interventions
        interventions = self.get_interventions(corridor_type)
        
        # Get type description
        type_desc = self.catalog.get(corridor_type, {}).get(
            "description", 
            "Corridor requiring integrated green infrastructure"
        )
        
        return CorridorProposal(
            corridor_id=corridor_id,
            corridor_type=corridor_type,
            corridor_type_description=type_desc,
            exposure_breakdown={
                "heat_score": round(heat_score, 3),
                "pollution_score": round(pollution_score, 3),
                "green_deficit_score": round(green_deficit_score, 3)
            },
            suggested_interventions=interventions
        )
    
    def proposal_to_dict(self, proposal: CorridorProposal) -> Dict[str, Any]:
        """Convert proposal to dictionary for JSON serialization."""
        return asdict(proposal)


# Singleton instance
_intervention_service: Optional[InterventionService] = None

def get_intervention_service() -> InterventionService:
    """Get or create intervention service singleton."""
    global _intervention_service
    if _intervention_service is None:
        _intervention_service = InterventionService()
    return _intervention_service
