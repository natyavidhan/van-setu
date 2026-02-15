"""
FastAPI Application Entry Point

Urban Green Corridor Planning Platform — Backend API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.dependencies import init_services, cleanup_services, get_raster_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Load raster data on startup, cleanup on shutdown.
    """
    settings = get_settings()
    
    print("=" * 60)
    print("🚀 Starting Urban Green Corridor Platform API")
    print("=" * 60)
    
    # Initialize all services
    print("\n📂 Loading raster data...")
    init_services()
    
    raster = get_raster_service()
    print(f"   Raster shape: {raster.shape}")
    print(f"   Bounds: {raster.bounds}")
    
    print("\n✅ API Ready!")
    print(f"   Swagger UI: http://localhost:8000/docs")
    print(f"   API Base: http://localhost:8000{settings.api_prefix}")
    print("=" * 60 + "\n")
    
    yield  # Application runs here
    
    # Cleanup
    print("\n🛑 Shutting down...")
    cleanup_services()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="API for urban green corridor analysis and visualization",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS middleware for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import routers here to avoid circular imports
    from app.routers import layers, tiles, roads, stats, aqi, corridors
    
    # Include routers
    app.include_router(layers.router, prefix=settings.api_prefix, tags=["Layers"])
    app.include_router(tiles.router, prefix=settings.api_prefix, tags=["Tiles"])
    app.include_router(roads.router, prefix=settings.api_prefix, tags=["Roads"])
    app.include_router(stats.router, prefix=settings.api_prefix, tags=["Statistics"])
    app.include_router(aqi.router, prefix=settings.api_prefix, tags=["Air Quality"])
    app.include_router(corridors.router, prefix=settings.api_prefix, tags=["Corridor Aggregation"])
    
    @app.get("/", tags=["Health"])
    async def root():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": "1.0.0"
        }
    
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Detailed health check."""
        raster = get_raster_service()
        return {
            "status": "healthy",
            "raster_loaded": raster is not None and raster.is_loaded,
            "bounds": settings.delhi_bounds
        }
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
