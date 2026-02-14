"""
AQI Service Tests — Verify AQI integration is working correctly.

Run with: pytest tests/test_aqi.py -v
"""
import pytest
import sys
sys.path.insert(0, '/home/natya/Desktop/innovateNSUT/backend')

from app.services.aqi_service import (
    AQIService, 
    AQIStation, 
    normalize_aqi, 
    compute_multi_exposure_priority,
    haversine_distance
)
from app.config import Settings


class TestAQINormalization:
    """Test AQI normalization logic."""
    
    def test_aqi_below_threshold_returns_zero(self):
        """AQI below 50 should have no penalty (normalized to 0)."""
        assert normalize_aqi(30) == 0.0
        assert normalize_aqi(50) == 0.0
        assert normalize_aqi(0) == 0.0
    
    def test_aqi_above_ceiling_returns_one(self):
        """AQI above 300 should have max penalty (normalized to 1)."""
        assert normalize_aqi(300) == 1.0
        assert normalize_aqi(500) == 1.0
        assert normalize_aqi(999) == 1.0
    
    def test_aqi_midpoint(self):
        """AQI of 175 (midpoint between 50 and 300) should be ~0.5."""
        result = normalize_aqi(175)
        assert 0.45 < result < 0.55  # Allow small tolerance
    
    def test_aqi_typical_values(self):
        """Test normalization of typical Delhi AQI values."""
        # 100 = Moderate → ~0.2
        assert 0.15 < normalize_aqi(100) < 0.25
        
        # 200 = Poor → ~0.6
        assert 0.55 < normalize_aqi(200) < 0.65
        
        # 250 = Very Poor → ~0.8
        assert 0.75 < normalize_aqi(250) < 0.85
    
    def test_aqi_none_returns_none(self):
        """None AQI should return None."""
        assert normalize_aqi(None) is None


class TestMultiExposurePriority:
    """Test the multi-exposure priority formula."""
    
    def test_all_zeros(self):
        """All zero inputs should give zero priority."""
        result = compute_multi_exposure_priority(0.0, 1.0, 0.0)  # High NDVI = 0 green deficit
        assert result == 0.0
    
    def test_all_maxed(self):
        """Max heat, zero vegetation, max AQI should give 1.0."""
        result = compute_multi_exposure_priority(1.0, 0.0, 1.0)
        assert result == 1.0
    
    def test_weights_sum_to_one(self):
        """Verify weights: 0.45 heat + 0.35 green_deficit + 0.20 AQI = 1.0"""
        # All components at 1.0
        result = compute_multi_exposure_priority(1.0, 0.0, 1.0)  # ndvi=0 means green_deficit=1
        assert result == pytest.approx(1.0)
    
    def test_fallback_without_aqi(self):
        """Without AQI, should use original GDI formula."""
        # With AQI=None, should use 0.6*heat + 0.4*green_deficit
        result = compute_multi_exposure_priority(0.5, 0.5, None)
        expected = 0.6 * 0.5 + 0.4 * 0.5  # 0.6 heat + 0.4 green_deficit (ndvi=0.5 → deficit=0.5)
        assert result == pytest.approx(expected)
    
    def test_aqi_contributes_20_percent(self):
        """AQI should contribute 20% of the final score."""
        # heat=0, green_deficit=0 (high NDVI=1), only AQI
        result = compute_multi_exposure_priority(0.0, 1.0, 1.0)
        assert result == pytest.approx(0.20)  # Only AQI weight


class TestHaversineDistance:
    """Test distance calculations."""
    
    def test_same_point_is_zero(self):
        """Distance from point to itself is 0."""
        dist = haversine_distance(28.6, 77.2, 28.6, 77.2)
        assert dist == 0.0
    
    def test_known_distance(self):
        """Test known distance between two Delhi locations."""
        # Anand Vihar to ITO is approximately 8km
        dist = haversine_distance(28.6469, 77.3164, 28.6289, 77.2405)
        assert 7 < dist < 9  # km


class TestAQIService:
    """Test the AQI service."""
    
    @pytest.fixture
    def service(self):
        """Create an AQI service instance."""
        settings = Settings()
        return AQIService(settings)
    
    def test_fetch_returns_stations(self, service):
        """Fetch should return stations (either from API or fallback)."""
        stations = service.fetch_stations(force_refresh=True)
        assert len(stations) > 0
        assert all(isinstance(s, AQIStation) for s in stations)
    
    def test_stations_have_required_fields(self, service):
        """All stations should have valid coordinates and PM2.5."""
        stations = service.fetch_stations()
        for s in stations:
            assert s.latitude is not None
            assert s.longitude is not None
            assert 28.3 < s.latitude < 29.0  # Delhi bounds
            assert 76.7 < s.longitude < 77.5  # Delhi bounds
            assert s.pm25 is not None or s.pm10 is not None
    
    def test_stations_to_geojson(self, service):
        """GeoJSON output should be valid."""
        service.fetch_stations()
        geojson = service.stations_to_geojson()
        
        assert geojson["type"] == "FeatureCollection"
        assert "features" in geojson
        assert len(geojson["features"]) > 0
        
        for feature in geojson["features"]:
            assert feature["type"] == "Feature"
            assert "geometry" in feature
            assert feature["geometry"]["type"] == "Point"
            assert "properties" in feature
            assert "aqi_raw" in feature["properties"]
            assert "aqi_norm" in feature["properties"]
    
    def test_get_aqi_at_point(self, service):
        """Should return AQI for any point in Delhi."""
        service.fetch_stations()
        result = service.get_aqi_at_point(77.21, 28.63)  # Central Delhi
        
        assert "aqi_raw" in result
        assert "aqi_norm" in result
        assert "station" in result
        assert "distance_km" in result
        assert result["aqi_raw"] > 0
        assert 0 <= result["aqi_norm"] <= 1


class TestFallbackData:
    """Test that fallback data is comprehensive."""
    
    def test_fallback_stations_cover_delhi(self):
        """Fallback should have stations across Delhi."""
        settings = Settings()
        service = AQIService(settings)
        stations = service._get_fallback_stations()
        
        # Should have at least 5 stations
        assert len(stations) >= 5
        
        # Check geographic spread
        lats = [s.latitude for s in stations]
        lons = [s.longitude for s in stations]
        
        # Should span at least 0.1 degrees in each direction
        assert max(lats) - min(lats) > 0.1
        assert max(lons) - min(lons) > 0.1
    
    def test_fallback_has_realistic_values(self):
        """Fallback AQI values should be realistic for Delhi."""
        settings = Settings()
        service = AQIService(settings)
        stations = service._get_fallback_stations()
        
        for s in stations:
            # Delhi typically has PM2.5 between 50-300
            assert s.pm25 is None or 50 <= s.pm25 <= 300


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
