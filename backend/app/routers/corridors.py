"""
Corridors Router — Continuous green corridor endpoints.

Aggregates connected road segments into planning-actionable corridors.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List

from app.dependencies import get_raster_service, get_road_service, get_aqi_service, get_corridor_service
from app.services.raster_service import RasterService
from app.services.road_service import RoadService
from app.services.aqi_service import AQIService
from app.services.corridor_service import CorridorService

router = APIRouter()


@router.get("/priority-corridors")
async def get_corridors(
    priority_threshold: float = Query(default=0.70, ge=0.0, le=1.0, description="Min priority score for corridor eligibility"),
    min_length: float = Query(default=200.0, ge=0.0, description="Minimum corridor length in meters"),
    include_aqi: bool = Query(default=True, description="Use Multi-Exposure Priority scoring"),
    corridor_service: CorridorService = Depends(get_corridor_service),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get continuous green corridors aggregated from road segments.
    
    A corridor is a connected chain of adjacent high-priority road segments.
    
    Algorithm:
        1. Filter segments with priority_score >= priority_threshold
        2. Build connectivity graph (segments touching/within 10m)
        3. Find connected components using DFS
        4. Aggregate each component into a corridor
        5. Filter out corridors shorter than min_length
        6. Return ranked by mean_priority
    
    Args:
        priority_threshold: Min priority score for segments (0-1, default 0.70)
        min_length: Min corridor length in meters (default 200)
        include_aqi: Use Multi-Exposure Priority (default true)
    
    Returns GeoJSON FeatureCollection with corridor geometries and metrics:
        - corridor_id: UUID
        - length_m: Total length in meters
        - segment_count: Number of aggregated segments
        - mean_priority: Average priority score
        - mean_heat, mean_ndvi, mean_aqi: Component averages (if available)
        - created_at: Timestamp
    """
    try:
        # Get segments with priority scores
        if include_aqi:
            segments = road_service.sample_with_aqi(raster_service, aqi_service)
            scoring_method = "multi-exposure"
        else:
            segments = road_service.sample_gdi_along_roads(raster_service)
            scoring_method = "gdi"
        
        if segments is None or len(segments) == 0:
            return {
                "type": "FeatureCollection",
                "features": [],
                "metadata": {
                    "count": 0,
                    "message": "No road segments available"
                }
            }
        
        # Aggregate into corridors
        corridor_service.priority_threshold = priority_threshold
        corridor_service.min_length = min_length
        
        metrics, corridors_gdf = corridor_service.aggregate_corridors(segments, force_refresh=True)
        
        # Convert to GeoJSON
        geojson = corridor_service.corridors_to_geojson(corridors_gdf, metrics)
        
        # Sort by mean_priority (descending)
        features = sorted(
            geojson.get("features", []),
            key=lambda f: f.get("properties", {}).get("mean_priority", 0),
            reverse=True
        )
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "count": len(features),
                "priority_threshold": priority_threshold,
                "min_length_m": min_length,
                "scoring_method": scoring_method,
                "description": f"{len(features)} corridors aggregated from high-priority segments"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/priority-corridors/{corridor_id}")
async def get_corridor_detail(
    corridor_id: str,
    priority_threshold: float = Query(default=0.70, ge=0.0, le=1.0),
    min_length: float = Query(default=200.0, ge=0.0),
    include_aqi: bool = Query(default=True),
    corridor_service: CorridorService = Depends(get_corridor_service),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific corridor.
    
    Includes:
        - Full geometry (MultiLineString or LineString)
        - All metrics (priority, length, AQI, heat, NDVI)
        - List of segment IDs that compose the corridor
        - Bounds (bbox)
    """
    try:
        # Get segments
        if include_aqi:
            segments = road_service.sample_with_aqi(raster_service, aqi_service)
        else:
            segments = road_service.sample_gdi_along_roads(raster_service)
        
        if segments is None or len(segments) == 0:
            raise HTTPException(status_code=404, detail="No road segments available")
        
        # Aggregate corridors
        corridor_service.priority_threshold = priority_threshold
        corridor_service.min_length = min_length
        
        metrics, corridors_gdf = corridor_service.aggregate_corridors(segments, force_refresh=True)
        
        # Find the requested corridor
        target_metrics = next((m for m in metrics if m.corridor_id == corridor_id), None)
        
        if target_metrics is None:
            raise HTTPException(status_code=404, detail=f"Corridor {corridor_id} not found")
        
        # Get corresponding geometry
        target_row = corridors_gdf[corridors_gdf['corridor_id'] == corridor_id]
        if target_row.empty:
            raise HTTPException(status_code=404, detail=f"Corridor geometry not found")
        
        geom = target_row.iloc[0].geometry
        bounds = geom.bounds  # (minx, miny, maxx, maxy)
        
        return {
            "type": "Feature",
            "geometry": {
                "type": "MultiLineString" if geom.geom_type == "MultiLineString" else "LineString",
                "coordinates": list(geom.coords) if geom.geom_type == "LineString" else [list(line.coords) for line in geom.geoms]
            },
            "properties": {
                "corridor_id": target_metrics.corridor_id,
                "length_m": target_metrics.length_m,
                "segment_count": target_metrics.segment_count,
                "segment_ids": target_metrics.segment_ids,
                "mean_priority": target_metrics.mean_priority,
                "mean_heat": target_metrics.mean_heat,
                "mean_ndvi": target_metrics.mean_ndvi,
                "mean_aqi": target_metrics.mean_aqi,
                "bounds": {
                    "west": bounds[0],
                    "south": bounds[1],
                    "east": bounds[2],
                    "north": bounds[3]
                },
                "created_at": target_metrics.created_at
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/priority-corridors/stats/summary")
async def get_corridors_summary(
    priority_threshold: float = Query(default=0.70, ge=0.0, le=1.0),
    min_length: float = Query(default=200.0, ge=0.0),
    include_aqi: bool = Query(default=True),
    corridor_service: CorridorService = Depends(get_corridor_service),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get summary statistics about all corridors.
    
    Returns aggregated metrics useful for dashboards.
    """
    try:
        # Get segments
        if include_aqi:
            segments = road_service.sample_with_aqi(raster_service, aqi_service)
        else:
            segments = road_service.sample_gdi_along_roads(raster_service)
        
        if segments is None or len(segments) == 0:
            return {
                "corridor_count": 0,
                "total_length_m": 0,
                "total_segments": 0,
                "avg_priority": None
            }
        
        # Aggregate corridors
        corridor_service.priority_threshold = priority_threshold
        corridor_service.min_length = min_length
        
        metrics, corridors_gdf = corridor_service.aggregate_corridors(segments, force_refresh=True)
        
        if len(metrics) == 0:
            return {
                "corridor_count": 0,
                "total_length_m": 0,
                "total_segments": 0,
                "avg_priority": None
            }
        
        total_length = sum(m.length_m for m in metrics)
        total_segments = sum(m.segment_count for m in metrics)
        avg_priority = sum(m.mean_priority for m in metrics) / len(metrics)
        
        # Top corridors
        top_5 = sorted(metrics, key=lambda m: m.mean_priority, reverse=True)[:5]
        
        return {
            "corridor_count": len(metrics),
            "total_length_m": float(total_length),
            "total_segments": total_segments,
            "avg_priority": float(avg_priority),
            "min_priority": float(min(m.mean_priority for m in metrics)),
            "max_priority": float(max(m.mean_priority for m in metrics)),
            "top_corridors": [
                {
                    "corridor_id": m.corridor_id,
                    "length_m": m.length_m,
                    "mean_priority": m.mean_priority,
                    "segment_count": m.segment_count
                }
                for m in top_5
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
