"""
Corridors Router — Continuous green corridor endpoints.

Aggregates connected road segments into planning-actionable corridors.
Includes intervention suggestions and community feedback.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import asyncio

from app.dependencies import get_raster_service, get_road_service, get_aqi_service, get_corridor_service
from app.services.raster_service import RasterService
from app.services.road_service import RoadService
from app.services.aqi_service import AQIService
from app.services.corridor_service import CorridorService
from app.services.intervention_service import get_intervention_service
from app.services.feedback_service import get_feedback_service

router = APIRouter()


# =============================================================================
# REQUEST MODELS
# =============================================================================

class FeedbackRequest(BaseModel):
    """User feedback submission."""
    comment: str

class VoteRequest(BaseModel):
    """Vote submission."""
    upvote: bool = True


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


@router.get("/priority-corridors/stream")
async def stream_corridors(
    priority_threshold: float = Query(default=0.70, ge=0.0, le=1.0),
    min_length: float = Query(default=200.0, ge=0.0),
    include_aqi: bool = Query(default=True),
    corridor_service: CorridorService = Depends(get_corridor_service),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
):
    """
    Stream corridors one-by-one using Server-Sent Events (SSE).
    
    Frontend receives corridors progressively as they're computed,
    avoiding the "loading" feel of waiting for all at once.
    
    Event types:
        - 'status': Progress updates (e.g., "Loading roads...", "Computing priorities...")
        - 'corridor': Individual corridor GeoJSON feature
        - 'complete': Final summary with total count
    """
    async def generate_corridors():
        try:
            # Status: Loading roads
            yield f"event: status\ndata: {json.dumps({'message': 'Loading road network...'})}\n\n"
            await asyncio.sleep(0)  # Allow event loop to send
            
            # Get segments with priority scores
            if include_aqi:
                segments = road_service.sample_with_aqi(raster_service, aqi_service)
                scoring_method = "multi-exposure"
            else:
                segments = road_service.sample_gdi_along_roads(raster_service)
                scoring_method = "gdi"
            
            if segments is None or len(segments) == 0:
                yield f"event: complete\ndata: {json.dumps({'count': 0, 'message': 'No road segments available'})}\n\n"
                return
            
            # Status: Computing corridors
            yield f"event: status\ndata: {json.dumps({'message': f'Aggregating {len(segments)} road segments...'})}\n\n"
            await asyncio.sleep(0)
            
            # Aggregate into corridors
            corridor_service.priority_threshold = priority_threshold
            corridor_service.min_length = min_length
            
            metrics, corridors_gdf = corridor_service.aggregate_corridors(segments, force_refresh=True)
            
            # Convert and stream each corridor
            geojson = corridor_service.corridors_to_geojson(corridors_gdf, metrics)
            features = sorted(
                geojson.get("features", []),
                key=lambda f: f.get("properties", {}).get("mean_priority", 0),
                reverse=True
            )
            
            # Stream corridors one-by-one
            for i, feature in enumerate(features):
                yield f"event: corridor\ndata: {json.dumps(feature)}\n\n"
                await asyncio.sleep(0.05)  # Small delay for visual effect
            
            # Complete
            yield f"event: complete\ndata: {json.dumps({'count': len(features), 'scoring_method': scoring_method})}\n\n"
            
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_corridors(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


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


# =============================================================================
# PROPOSAL ENDPOINTS
# =============================================================================

@router.get("/priority-corridors/{corridor_id}/proposal")
async def get_corridor_proposal(
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
    Get intervention proposal for a specific corridor.
    
    Returns:
        - corridor_type: Classification based on dominant exposure
        - suggested_interventions: Context-appropriate intervention list
        - exposure_breakdown: Heat, pollution, and green deficit scores
    
    Uses rule-based classification (no ML):
        - Heat dominant → "Heat Mitigation"
        - Pollution dominant → "Air Quality Buffer"
        - Green deficit dominant → "Green Connectivity"
        - Mixed → "Multi-Benefit"
    """
    try:
        # Get segments with priority scores
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
        
        # Get exposure scores
        # mean_heat is already normalized (0-1), higher = hotter
        # mean_ndvi needs inversion: low NDVI = high green deficit
        # mean_aqi is PM2.5 in μg/m³, normalize to 0-1 (assume 0-300 range)
        
        heat_score = target_metrics.mean_heat if target_metrics.mean_heat is not None else 0.5
        
        # Green deficit = 1 - normalized NDVI (inverted)
        ndvi_norm = target_metrics.mean_ndvi if target_metrics.mean_ndvi is not None else 0.5
        green_deficit_score = 1.0 - ndvi_norm
        
        # Normalize AQI (PM2.5): 0 = good, 300+ = hazardous
        aqi_raw = target_metrics.mean_aqi if target_metrics.mean_aqi is not None else 50
        pollution_score = min(1.0, aqi_raw / 300.0)
        
        # Generate proposal
        intervention_service = get_intervention_service()
        proposal = intervention_service.generate_proposal(
            corridor_id=corridor_id,
            heat_score=heat_score,
            pollution_score=pollution_score,
            green_deficit_score=green_deficit_score
        )
        
        # Include corridor metrics in response
        result = intervention_service.proposal_to_dict(proposal)
        result["corridor_metrics"] = {
            "length_m": target_metrics.length_m,
            "segment_count": target_metrics.segment_count,
            "mean_priority": target_metrics.mean_priority
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# COMMUNITY FEEDBACK ENDPOINTS
# =============================================================================

@router.post("/priority-corridors/{corridor_id}/feedback")
async def add_corridor_feedback(
    corridor_id: str,
    request: FeedbackRequest
) -> Dict[str, Any]:
    """
    Submit feedback for a corridor.
    
    No authentication required (MVP).
    
    Args:
        corridor_id: Target corridor
        comment: User feedback text
    
    Returns:
        Created feedback object
    """
    try:
        feedback_service = get_feedback_service()
        feedback = feedback_service.add_feedback(corridor_id, request.comment)
        
        return {
            "success": True,
            "feedback": {
                "id": feedback.id,
                "corridor_id": feedback.corridor_id,
                "comment": feedback.comment,
                "timestamp": feedback.timestamp,
                "votes": feedback.votes
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/priority-corridors/{corridor_id}/feedback")
async def get_corridor_feedback(
    corridor_id: str,
    limit: int = Query(default=10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get feedback for a corridor.
    
    Returns feedback sorted by votes (highest first).
    """
    try:
        feedback_service = get_feedback_service()
        feedback_list = feedback_service.get_feedback(corridor_id, sort_by_votes=True, limit=limit)
        
        return {
            "corridor_id": corridor_id,
            "feedback": [
                {
                    "id": f.id,
                    "comment": f.comment,
                    "timestamp": f.timestamp,
                    "votes": f.votes
                }
                for f in feedback_list
            ],
            "count": len(feedback_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/priority-corridors/{corridor_id}/vote")
async def vote_on_corridor(
    corridor_id: str,
    request: VoteRequest
) -> Dict[str, Any]:
    """
    Vote on a corridor (community support indicator).
    
    Args:
        corridor_id: Target corridor
        upvote: True for 👍, False for 👎
    
    Returns:
        Updated vote counts
    """
    try:
        feedback_service = get_feedback_service()
        votes = feedback_service.vote_corridor(corridor_id, request.upvote)
        
        return {
            "success": True,
            "corridor_id": corridor_id,
            "votes": {
                "upvotes": votes.upvotes,
                "downvotes": votes.downvotes,
                "net": votes.net_votes,
                "support_level": votes.support_level
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/{feedback_id}/vote")
async def vote_on_feedback(
    feedback_id: str,
    request: VoteRequest
) -> Dict[str, Any]:
    """
    Vote on a specific feedback comment.
    
    Args:
        feedback_id: Target feedback ID
        upvote: True for 👍, False for 👎
    
    Returns:
        Updated feedback with new vote count
    """
    try:
        feedback_service = get_feedback_service()
        feedback = feedback_service.vote_on_feedback(feedback_id, request.upvote)
        
        if feedback is None:
            raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")
        
        return {
            "success": True,
            "feedback": {
                "id": feedback.id,
                "comment": feedback.comment,
                "votes": feedback.votes
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/priority-corridors/{corridor_id}/community")
async def get_corridor_community_data(
    corridor_id: str,
    feedback_limit: int = Query(default=5, ge=1, le=20)
) -> Dict[str, Any]:
    """
    Get all community data for a corridor.
    
    Returns votes and top feedback in a single response.
    """
    try:
        feedback_service = get_feedback_service()
        return feedback_service.get_community_data(corridor_id, feedback_limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
