"""
Corridor Aggregation Service — High-Performance Implementation

Algorithm: STRtree Spatial Index + Union-Find
    1. Filter high-priority segments (priority_score >= threshold)
    2. Build STRtree spatial index for O(log n) queries
    3. Query nearby segments using buffered endpoints
    4. Build connectivity using Union-Find (Disjoint Set Union)
    5. Extract connected components in O(n α(n))
    6. Aggregate each component into a corridor
    7. Filter out trivial corridors (< min_length)

Performance:
    - Previous: O(n²) pairwise comparisons = ~900,000 checks for 1343 segments
    - New: O(n log n) spatial queries + O(n α(n)) union-find ≈ 15,000 operations
    - Expected speedup: 50-100x
"""

import numpy as np
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point, mapping
from shapely.ops import unary_union
from shapely import STRtree
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from uuid import uuid4
from datetime import datetime
import time
import hashlib

from app.config import Settings


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_PRIORITY_THRESHOLD = 0.70
DEFAULT_MIN_CORRIDOR_LENGTH = 200.0  # meters
CONNECTIVITY_TOLERANCE = 10.0  # meters (~0.0001 degrees at Delhi's latitude)

# Degree to meter conversion at Delhi's latitude (28.6°N)
# 1 degree ≈ 111,320 * cos(28.6°) ≈ 97,800 meters for longitude
# 1 degree ≈ 111,320 meters for latitude
DEG_TO_M_LAT = 111320
DEG_TO_M_LON = 97800


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class CorridorMetrics:
    """Aggregated metrics for a corridor."""
    corridor_id: str
    segment_ids: List[int]
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
# UNION-FIND (DISJOINT SET UNION) - O(α(n)) operations
# =============================================================================

class UnionFind:
    """
    Union-Find data structure with path compression and union by rank.
    
    Operations are nearly O(1) - technically O(α(n)) where α is the 
    inverse Ackermann function, which is ≤ 4 for any practical input.
    """
    
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.n = n
    
    def find(self, x: int) -> int:
        """Find root with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x: int, y: int) -> bool:
        """Union by rank. Returns True if merged, False if already same set."""
        px, py = self.find(x), self.find(y)
        if px == py:
            return False
        
        # Union by rank
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1
        return True
    
    def get_components(self) -> Dict[int, List[int]]:
        """Get all connected components as {root: [members]}."""
        components = {}
        for i in range(self.n):
            root = self.find(i)
            if root not in components:
                components[root] = []
            components[root].append(i)
        return components


# =============================================================================
# HIGH-PERFORMANCE CORRIDOR AGGREGATOR
# =============================================================================

class FastCorridorAggregator:
    """
    High-performance corridor aggregation using spatial indexing.
    
    Key optimizations:
    1. STRtree for O(log n) spatial queries instead of O(n) scans
    2. Union-Find for O(α(n)) component building instead of O(n) DFS
    3. Vectorized endpoint extraction
    4. Single-pass metric computation
    """
    
    def __init__(
        self,
        priority_threshold: float = DEFAULT_PRIORITY_THRESHOLD,
        min_length: float = DEFAULT_MIN_CORRIDOR_LENGTH,
        connectivity_tolerance: float = CONNECTIVITY_TOLERANCE,
        simple_mode: bool = True
    ):
        self.priority_threshold = priority_threshold
        self.min_length = min_length
        # Convert tolerance from meters to degrees (approximate)
        self.tolerance_deg = connectivity_tolerance / DEG_TO_M_LAT
        self.simple_mode = simple_mode
    
    def aggregate(self, segments: gpd.GeoDataFrame) -> Tuple[List[CorridorMetrics], gpd.GeoDataFrame]:
        """
        Aggregate road segments into corridors using spatial indexing.
        
        Returns:
            Tuple of (corridor_metrics_list, corridor_geodataframe)
        """
        t_start = time.perf_counter()
        
        if segments is None or len(segments) == 0:
            return [], gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
        
        # Step 1: Filter eligible segments
        eligible = self._filter_eligible(segments)
        if len(eligible) == 0:
            print(f"  ℹ️  No segments above threshold {self.priority_threshold}")
            return [], gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
        
        t_filter = time.perf_counter()

        # Step 2: Extract endpoints for spatial indexing
        endpoints, endpoint_to_segment = self._extract_endpoints(eligible)
        t_endpoints = time.perf_counter()
        
        # Step 3: Build spatial index and find connections
        uf = self._build_connectivity(eligible, endpoints, endpoint_to_segment)
        t_connectivity = time.perf_counter()
        
        # Step 4: Extract components and create corridors
        components = uf.get_components()
        t_components = time.perf_counter()
        
        # Step 5: Create corridor objects
        corridors_metrics = []
        corridors_geoms = []
        
        for component_indices in components.values():
            corridor = self._create_corridor(eligible, component_indices)
            if corridor and corridor['metrics'].length_m >= self.min_length:
                corridors_metrics.append(corridor['metrics'])
                corridors_geoms.append(corridor['geometry'])
        
        t_corridors = time.perf_counter()
        
        # Create GeoDataFrame
        if corridors_metrics:
            corridors_gdf = gpd.GeoDataFrame(
                {
                    'corridor_id': [c.corridor_id for c in corridors_metrics],
                    'segment_count': [c.segment_count for c in corridors_metrics],
                    'length_m': [c.length_m for c in corridors_metrics],
                    'mean_priority': [c.mean_priority for c in corridors_metrics],
                    'mean_heat': [c.mean_heat for c in corridors_metrics],
                    'mean_ndvi': [c.mean_ndvi for c in corridors_metrics],
                    'mean_aqi': [c.mean_aqi for c in corridors_metrics],
                },
                geometry=corridors_geoms,
                crs='EPSG:4326'
            )
        else:
            corridors_gdf = gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
        
        t_end = time.perf_counter()
        
        # Performance logging
        total_ms = (t_end - t_start) * 1000
        print(f"  ⚡ Performance breakdown:")
        print(f"     Filter: {(t_filter - t_start)*1000:.1f}ms")
        print(f"     Extract endpoints: {(t_endpoints - t_filter)*1000:.1f}ms")
        print(f"     Build connectivity: {(t_connectivity - t_endpoints)*1000:.1f}ms")
        print(f"     Extract components: {(t_components - t_connectivity)*1000:.1f}ms")
        print(f"     Create corridors: {(t_corridors - t_components)*1000:.1f}ms")
        print(f"     Total: {total_ms:.1f}ms")
        
        filtered_count = len(components) - len(corridors_metrics)
        print(f"  🔍 Found {len(components)} components, kept {len(corridors_metrics)} corridors (filtered {filtered_count} < {self.min_length}m)")
        
        return corridors_metrics, corridors_gdf
    
    def _filter_eligible(self, segments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Filter segments above priority threshold."""
        if 'priority_score' not in segments.columns:
            print("  ⚠️  No priority_score column; using all segments")
            return segments.reset_index(drop=True)
        
        valid = segments[segments['priority_score'].notna()]
        eligible = valid[valid['priority_score'] >= self.priority_threshold].copy()
        eligible = eligible.reset_index(drop=True)  # Reset index for Union-Find
        
        print(f"  📊 {len(eligible)} / {len(valid)} segments above threshold {self.priority_threshold}")
        return eligible
    
    def _extract_endpoints(self, segments: gpd.GeoDataFrame) -> Tuple[List[Point], Dict[int, int]]:
        """
        Extract endpoints from all segments.
        
        Returns:
            - List of Point geometries (endpoints)
            - Dict mapping endpoint_index -> segment_index
        """
        endpoints = []
        endpoint_to_segment = {}
        
        for seg_idx, geom in enumerate(segments.geometry):
            pts = self._get_endpoints(geom)
            for pt in pts:
                endpoint_to_segment[len(endpoints)] = seg_idx
                endpoints.append(Point(pt))
        
        return endpoints, endpoint_to_segment
    
    def _get_endpoints(self, geom) -> List[Tuple[float, float]]:
        """Extract start and end points from a geometry."""
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
    
    def _build_connectivity(
        self, 
        segments: gpd.GeoDataFrame,
        endpoints: List[Point],
        endpoint_to_segment: Dict[int, int]
    ) -> UnionFind:
        """
        Build connectivity graph using STRtree spatial index.
        
        This is the key optimization: instead of O(n²) pairwise comparisons,
        we use STRtree for O(log n) queries per endpoint.
        """
        n_segments = len(segments)
        uf = UnionFind(n_segments)
        
        if len(endpoints) == 0:
            return uf
        
        # Build spatial index from endpoints
        tree = STRtree(endpoints)
        
        # For each endpoint, find nearby endpoints and union their segments
        connections_made = 0
        for ep_idx, endpoint in enumerate(endpoints):
            seg_idx = endpoint_to_segment[ep_idx]
            
            # Query tree for endpoints within tolerance
            # dwithin predicate uses the same units as the geometries (degrees)
            nearby_indices = tree.query(endpoint, predicate='dwithin', distance=self.tolerance_deg)
            
            for nearby_idx in nearby_indices:
                other_seg_idx = endpoint_to_segment[nearby_idx]
                if seg_idx != other_seg_idx:
                    if uf.union(seg_idx, other_seg_idx):
                        connections_made += 1
        
        # Also check for actual geometry intersections (handles T-junctions, etc.)
        # Use STRtree on segment geometries for this
        geom_tree = STRtree(segments.geometry.values)
        
        for seg_idx, geom in enumerate(segments.geometry):
            # Query for potentially intersecting geometries
            candidates = geom_tree.query(geom, predicate='intersects')
            for other_idx in candidates:
                if seg_idx != other_idx:
                    if uf.union(seg_idx, other_idx):
                        connections_made += 1
        
        print(f"  🔗 Made {connections_made} connections using spatial index")
        return uf
    
    def _generate_stable_corridor_id(self, indices: List[int]) -> str:
        """
        Generate a stable corridor ID based on sorted segment indices.
        
        This ensures the same set of segments always produces the same corridor_id,
        making corridors referenceable across API calls.
        """
        sorted_indices = sorted(indices)
        index_str = ",".join(str(i) for i in sorted_indices)
        hash_obj = hashlib.sha256(index_str.encode())
        # Use first 16 chars of hex digest for shorter but unique ID
        return hash_obj.hexdigest()[:16]
    
    def _create_corridor(
        self,
        segments: gpd.GeoDataFrame,
        indices: List[int]
    ) -> Optional[Dict[str, Any]]:
        """Create a corridor from component indices."""
        if len(indices) == 0:
            return None
        
        component = segments.iloc[indices]
        
        # Merge geometries
        geoms = list(component.geometry)
        merged_geom = unary_union(geoms)
        
        # Calculate length in meters
        # Project to UTM Zone 43N for accurate length
        projected = gpd.GeoSeries([merged_geom], crs='EPSG:4326').to_crs('EPSG:32643')
        length_m = projected.iloc[0].length
        
        # Calculate metrics
        mean_priority = component['priority_score'].mean()
        mean_heat = component['heat_norm'].mean() if 'heat_norm' in component.columns else None
        mean_ndvi = component['ndvi_norm'].mean() if 'ndvi_norm' in component.columns else None
        mean_aqi = component['aqi_norm'].mean() if 'aqi_norm' in component.columns else None
        
        # Use stable ID based on segment indices for consistent references
        corridor_id = self._generate_stable_corridor_id(indices)
        
        metrics = CorridorMetrics(
            corridor_id=corridor_id,
            segment_ids=indices,
            length_m=float(length_m),
            mean_priority=float(mean_priority),
            mean_heat=float(mean_heat) if mean_heat is not None and not np.isnan(mean_heat) else None,
            mean_ndvi=float(mean_ndvi) if mean_ndvi is not None and not np.isnan(mean_ndvi) else None,
            mean_aqi=float(mean_aqi) if mean_aqi is not None and not np.isnan(mean_aqi) else None
        )
        
        return {'metrics': metrics, 'geometry': merged_geom}


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
        
        Uses STRtree + Union-Find for optimal connectivity detection.
        """
        if self._cache is not None and not force_refresh:
            return self._cache
        
        print("\n🏗️  Aggregating corridors (STRtree + Union-Find)...")
        print("=" * 60)
        
        aggregator = FastCorridorAggregator(
            priority_threshold=self.priority_threshold,
            min_length=self.min_length,
            simple_mode=False
        )
        
        metrics, gdf = aggregator.aggregate(segments)
        
        self._cache = (metrics, gdf)
        
        print("=" * 60)
        print(f"✨ Corridor aggregation complete: {len(metrics)} corridors\n")
        
        return metrics, gdf
    
    def corridors_to_geojson(
        self, 
        corridors_gdf: gpd.GeoDataFrame, 
        metrics_list: List[CorridorMetrics]
    ) -> Dict[str, Any]:
        """Convert corridors to GeoJSON with metrics."""
        if corridors_gdf is None or len(corridors_gdf) == 0:
            return {"type": "FeatureCollection", "features": []}
        
        features = []
        
        # Create lookup for metrics by corridor_id
        metrics_lookup = {m.corridor_id: m for m in metrics_list}
        
        for _, row in corridors_gdf.iterrows():
            corridor_id = row.get('corridor_id')
            metrics = metrics_lookup.get(corridor_id)
            
            if metrics is None:
                continue
            
            feature = {
                "type": "Feature",
                "geometry": mapping(row.geometry),
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
        
        return {"type": "FeatureCollection", "features": features}
    
    def clear_cache(self):
        """Clear cached corridors."""
        self._cache = None
