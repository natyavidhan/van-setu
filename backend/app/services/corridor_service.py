"""
Corridor Aggregation Service — Group connected road segments into continuous corridors.

Core Algorithm:
    1. Identify high-priority segments (priority_score >= threshold)
    2. Build connectivity graph using geometry touches/intersects
    3. Find connected components using DFS/BFS
    4. Aggregate each component into a corridor
    5. Filter out trivial corridors (< min_length)
    6. Store and cache results

Design Principles:
    - Deterministic and reproducible
    - No segment duplication across corridors
    - Corridor geometry is continuous and meaningful
"""

import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass
from uuid import uuid4
from datetime import datetime
import json

from app.config import Settings


# =============================================================================
# CONFIGURATION
# =============================================================================

# Minimum priority score for a segment to be corridor-eligible (0-1 scale)
DEFAULT_PRIORITY_THRESHOLD = 0.70

# Minimum corridor length in meters to avoid noise
DEFAULT_MIN_CORRIDOR_LENGTH = 200.0

# Geometric tolerance for connectivity (meters)
# Two segments are connected if endpoints within this distance
CONNECTIVITY_TOLERANCE = 10.0


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class CorridorMetrics:
    """Aggregated metrics for a corridor."""
    corridor_id: str
    segment_ids: List[str]
    length_m: float
    mean_priority: float
    mean_heat: Optional[float] = None
    mean_ndvi: Optional[float] = None
    mean_aqi: Optional[float] = None
    segment_count: int = 0
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        self.segment_count = len(self.segment_ids)


# =============================================================================
# CONNECTIVITY GRAPH BUILDER
# =============================================================================

class ConnectivityGraph:
    """Build and manage segment connectivity graph."""
    
    def __init__(self, segments: gpd.GeoDataFrame, tolerance: float = CONNECTIVITY_TOLERANCE):
        """
        Initialize connectivity graph.
        
        Args:
            segments: GeoDataFrame with geometry column
            tolerance: Distance tolerance for connectivity (meters)
        """
        self.segments = segments
        self.tolerance = tolerance
        self.adjacency: Dict[int, Set[int]] = {}
        self._build_graph()
    
    def _get_endpoints(self, geom) -> List[Tuple[float, float]]:
        """Extract start and end points from geometry."""
        if isinstance(geom, MultiLineString):
            points = []
            for line in geom.geoms:
                if len(line.coords) > 0:
                    points.append(line.coords[0])
                    points.append(line.coords[-1])
            return points
        elif isinstance(geom, LineString):
            if len(geom.coords) >= 2:
                return [geom.coords[0], geom.coords[-1]]
        return []
    
    def _segments_connected(self, geom1, geom2) -> bool:
        """
        Check if two geometries are connected.
        
        Two segments are connected if:
        1. They touch/intersect (Shapely)
        2. Their endpoints are within tolerance distance
        """
        # Method 1: Geometric intersection
        if geom1.touches(geom2) or geom1.intersects(geom2):
            return True
        
        # Method 2: Endpoint proximity
        endpoints1 = self._get_endpoints(geom1)
        endpoints2 = self._get_endpoints(geom2)
        
        for ep1 in endpoints1:
            for ep2 in endpoints2:
                # Rough distance in degrees (approximate for Delhi)
                dist_deg = np.sqrt((ep1[0] - ep2[0])**2 + (ep1[1] - ep2[1])**2)
                # Convert degrees to meters (1 degree ≈ 111 km at equator)
                dist_m = dist_deg * 111000
                if dist_m <= self.tolerance:
                    return True
        
        return False
    
    def _build_graph(self):
        """Build adjacency list for segments."""
        n = len(self.segments)
        
        for i in range(n):
            self.adjacency[i] = set()
            geom_i = self.segments.iloc[i].geometry
            
            for j in range(i + 1, n):
                geom_j = self.segments.iloc[j].geometry
                
                if self._segments_connected(geom_i, geom_j):
                    self.adjacency[i].add(j)
                    self.adjacency[j].add(i)
    
    def find_connected_components(self) -> List[List[int]]:
        """
        Find connected components using DFS.
        
        Returns:
            List of connected components, each as a list of segment indices
        """
        visited = set()
        components = []
        
        for node in range(len(self.segments)):
            if node not in visited:
                component = self._dfs(node, visited)
                if component:
                    components.append(component)
        
        return components
    
    def _dfs(self, start: int, visited: Set[int]) -> List[int]:
        """Depth-first search from starting node."""
        stack = [start]
        component = []
        
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            
            visited.add(node)
            component.append(node)
            
            for neighbor in self.adjacency[node]:
                if neighbor not in visited:
                    stack.append(neighbor)
        
        return component


# =============================================================================
# CORRIDOR AGGREGATOR
# =============================================================================

class CorridorAggregator:
    """Aggregate connected segments into corridors."""
    
    def __init__(
        self,
        priority_threshold: float = DEFAULT_PRIORITY_THRESHOLD,
        min_length: float = DEFAULT_MIN_CORRIDOR_LENGTH,
        connectivity_tolerance: float = CONNECTIVITY_TOLERANCE
    ):
        """
        Initialize corridor aggregator.
        
        Args:
            priority_threshold: Min priority_score to be corridor-eligible
            min_length: Min corridor length in meters
            connectivity_tolerance: Distance tolerance for connectivity
        """
        self.priority_threshold = priority_threshold
        self.min_length = min_length
        self.connectivity_tolerance = connectivity_tolerance
    
    def aggregate(self, segments: gpd.GeoDataFrame) -> Tuple[List[CorridorMetrics], gpd.GeoDataFrame]:
        """
        Aggregate road segments into corridors.
        
        Args:
            segments: GeoDataFrame with columns:
                - geometry: LineString or MultiLineString
                - priority_score: [0, 1] priority value
                - (optional) heat_norm, ndvi_norm, aqi_norm
        
        Returns:
            Tuple of:
                - List of CorridorMetrics
                - GeoDataFrame with corridor geometries
        """
        if segments is None or len(segments) == 0:
            return [], gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
        
        # Filter to high-priority segments
        eligible = self._filter_eligible_segments(segments)
        
        if len(eligible) == 0:
            print(f"  ℹ️  No segments above priority threshold {self.priority_threshold}")
            return [], gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
        
        # Build connectivity graph
        print(f"  🔗 Building connectivity graph for {len(eligible)} high-priority segments...")
        graph = ConnectivityGraph(eligible, self.connectivity_tolerance)
        
        # Find connected components
        components = graph.find_connected_components()
        print(f"  🔍 Found {len(components)} potential corridors")
        
        # Aggregate each component
        corridors_metrics = []
        corridors_geoms = []
        
        for component_indices in components:
            # Get segments in this component
            component_segments = eligible.iloc[component_indices]
            
            # Create corridor
            corridor = self._create_corridor(component_segments, segments)
            
            if corridor is not None:
                corridors_metrics.append(corridor['metrics'])
                corridors_geoms.append(corridor['geometry'])
        
        # Filter out trivial corridors
        valid_corridors = [c for c in corridors_metrics if c.length_m >= self.min_length]
        
        filtered_count = len(corridors_metrics) - len(valid_corridors)
        if filtered_count > 0:
            print(f"  🗑️  Filtered out {filtered_count} trivial corridors (< {self.min_length}m)")
        
        print(f"  ✅ Aggregated {len(valid_corridors)} corridors")
        
        # Create GeoDataFrame
        if valid_corridors:
            # Get geometries for valid corridors
            valid_geoms = [
                corridors_geoms[corridors_metrics.index(c)] 
                for c in valid_corridors
            ]
            
            corridors_gdf = gpd.GeoDataFrame(
                {
                    'corridor_id': [c.corridor_id for c in valid_corridors],
                    'segment_count': [c.segment_count for c in valid_corridors],
                    'length_m': [c.length_m for c in valid_corridors],
                    'mean_priority': [c.mean_priority for c in valid_corridors],
                    'mean_heat': [c.mean_heat for c in valid_corridors],
                    'mean_ndvi': [c.mean_ndvi for c in valid_corridors],
                    'mean_aqi': [c.mean_aqi for c in valid_corridors],
                },
                geometry=valid_geoms,
                crs='EPSG:4326'
            )
        else:
            corridors_gdf = gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
        
        return valid_corridors, corridors_gdf
    
    def _filter_eligible_segments(self, segments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Filter segments above priority threshold."""
        if 'priority_score' not in segments.columns:
            print("  ⚠️  No priority_score column; using all segments")
            return segments.copy()
        
        # Remove NaN priorities
        valid = segments[segments['priority_score'].notna()].copy()
        
        # Filter by threshold
        eligible = valid[valid['priority_score'] >= self.priority_threshold].copy()
        
        print(f"  📊 {len(eligible)} / {len(valid)} segments above threshold {self.priority_threshold}")
        
        return eligible
    
    def _create_corridor(
        self,
        component_segments: gpd.GeoDataFrame,
        all_segments: gpd.GeoDataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        Create a corridor from a component of segments.
        
        Returns:
            Dict with 'metrics' and 'geometry', or None if invalid
        """
        if len(component_segments) == 0:
            return None
        
        # Get original indices in all_segments
        segment_indices = component_segments.index.tolist()
        
        # Extract geometries and merge
        geoms = list(component_segments.geometry)
        merged_geom = unary_union(geoms)
        
        # Calculate metrics
        length_m = sum(geom.length for geom in geoms)
        
        mean_priority = component_segments['priority_score'].mean()
        
        # Optional: average other metrics
        mean_heat = component_segments['heat_norm'].mean() if 'heat_norm' in component_segments.columns else None
        mean_ndvi = component_segments['ndvi_norm'].mean() if 'ndvi_norm' in component_segments.columns else None
        mean_aqi = component_segments['aqi_norm'].mean() if 'aqi_norm' in component_segments.columns else None
        
        metrics = CorridorMetrics(
            corridor_id=str(uuid4()),
            segment_ids=segment_indices,
            length_m=float(length_m),
            mean_priority=float(mean_priority),
            mean_heat=float(mean_heat) if mean_heat is not None else None,
            mean_ndvi=float(mean_ndvi) if mean_ndvi is not None else None,
            mean_aqi=float(mean_aqi) if mean_aqi is not None else None
        )
        
        return {
            'metrics': metrics,
            'geometry': merged_geom
        }


# =============================================================================
# CORRIDOR SERVICE (MAIN INTERFACE)
# =============================================================================

class CorridorService:
    """High-level service for corridor aggregation."""
    
    def __init__(
        self,
        settings: Settings,
        priority_threshold: float = DEFAULT_PRIORITY_THRESHOLD,
        min_length: float = DEFAULT_MIN_CORRIDOR_LENGTH
    ):
        """Initialize corridor service."""
        self.settings = settings
        self.priority_threshold = priority_threshold
        self.min_length = min_length
        self._cache: Optional[Tuple[List[CorridorMetrics], gpd.GeoDataFrame]] = None
    
    def aggregate_corridors(
        self,
        segments: gpd.GeoDataFrame,
        force_refresh: bool = False
    ) -> Tuple[List[CorridorMetrics], gpd.GeoDataFrame]:
        """
        Aggregate road segments into continuous corridors.
        
        Args:
            segments: GeoDataFrame with geometry and priority_score
            force_refresh: Force recomputation (skip cache)
        
        Returns:
            Tuple of (corridor_metrics_list, corridor_gdf)
        """
        if self._cache is not None and not force_refresh:
            return self._cache
        
        print("\n🏗️  Aggregating corridors from road segments...")
        print("=" * 60)
        
        aggregator = CorridorAggregator(
            priority_threshold=self.priority_threshold,
            min_length=self.min_length
        )
        
        metrics, gdf = aggregator.aggregate(segments)
        
        self._cache = (metrics, gdf)
        
        print(f"=" * 60)
        print(f"✨ Corridor aggregation complete: {len(metrics)} corridors\n")
        
        return metrics, gdf
    
    def corridors_to_geojson(self, corridors_gdf: gpd.GeoDataFrame, metrics_list: List[CorridorMetrics]) -> Dict[str, Any]:
        """Convert corridors to GeoJSON with metrics."""
        if corridors_gdf is None or len(corridors_gdf) == 0:
            return {"type": "FeatureCollection", "features": []}
        
        features = []
        
        for idx, row in corridors_gdf.iterrows():
            corridor_id = row.get('corridor_id')
            
            # Find corresponding metrics
            metrics = next((m for m in metrics_list if m.corridor_id == corridor_id), None)
            
            if metrics is None:
                continue
            
            feature = {
                "type": "Feature",
                "geometry": json.loads(gpd.GeoSeries([row.geometry]).to_json())[0],
                "properties": {
                    "corridor_id": corridor_id,
                    "length_m": float(row['length_m']),
                    "segment_count": int(row['segment_count']),
                    "mean_priority": float(row['mean_priority']),
                    "mean_heat": float(row['mean_heat']) if row['mean_heat'] is not None else None,
                    "mean_ndvi": float(row['mean_ndvi']) if row['mean_ndvi'] is not None else None,
                    "mean_aqi": float(row['mean_aqi']) if row['mean_aqi'] is not None else None,
                    "created_at": metrics.created_at,
                }
            }
            features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features
        }
    
    def clear_cache(self):
        """Clear cached corridors."""
        self._cache = None
