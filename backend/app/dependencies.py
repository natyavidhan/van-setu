"""
Dependencies Module — Shared dependencies to avoid circular imports.
"""
from app.config import get_settings, Settings
from app.services.raster_service import RasterService
from app.services.tile_service import TileService
from app.services.road_service import RoadService
from app.services.aqi_service import AQIService
from app.services.corridor_service import CorridorService

# Global service instances
_raster_service: RasterService | None = None
_tile_service: TileService | None = None
_road_service: RoadService | None = None
_aqi_service: AQIService | None = None
_corridor_service: CorridorService | None = None


def init_services():
    """Initialize all services (called at startup)."""
    global _raster_service, _tile_service, _road_service, _aqi_service, _corridor_service
    settings = get_settings()
    
    # Initialize raster service and load data
    _raster_service = RasterService(settings)
    _raster_service.load_data()
    
    # Initialize tile service
    _tile_service = TileService(_raster_service)
    
    # Initialize road service
    _road_service = RoadService(settings)
    
    # Initialize AQI service and fetch initial data
    _aqi_service = AQIService(settings)
    print("\n📡 Initializing AQI data...")
    _aqi_service.fetch_stations()
    
    # Initialize corridor service (depends on road service)
    _corridor_service = CorridorService(settings)
    print("🔗 Corridor aggregation service initialized")


def cleanup_services():
    """Cleanup services (called at shutdown)."""
    global _raster_service, _tile_service, _road_service, _aqi_service, _corridor_service
    _raster_service = None
    _tile_service = None
    _road_service = None
    _aqi_service = None
    _corridor_service = None


def get_raster_service() -> RasterService:
    """Dependency to get raster service."""
    if _raster_service is None:
        raise RuntimeError("Raster service not initialized")
    return _raster_service


def get_tile_service() -> TileService:
    """Dependency to get tile service."""
    if _tile_service is None:
        raise RuntimeError("Tile service not initialized")
    return _tile_service


def get_road_service() -> RoadService:
    """Dependency to get road service."""
    if _road_service is None:
        raise RuntimeError("Road service not initialized")
    return _road_service


def get_aqi_service() -> AQIService:
    """Dependency to get AQI service."""
    if _aqi_service is None:
        raise RuntimeError("AQI service not initialized")
    return _aqi_service


def get_corridor_service() -> CorridorService:
    """Dependency to get corridor service."""
    if _corridor_service is None:
        raise RuntimeError("Corridor service not initialized")
    return _corridor_service
