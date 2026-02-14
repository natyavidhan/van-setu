# Corridor Aggregation — Quick Reference

## What Was Implemented

The platform now automatically groups connected road segments into continuous "Priority Corridors" — planning-actionable chains of high-priority areas where green infrastructure investment would have maximum impact.

## How It Works

### User Perspective
1. Toggle **"Priority Corridors"** in the sidebar
2. Map loads corridor geometries colored by priority (red=critical, orange=high, yellow=moderate)
3. Click any corridor to see: length, segment count, mean priority, air quality
4. System automatically aggregates connected segments into corridors

### Technical Pipeline
```
Road Segments (with priority scores)
    ↓
Filter: priority_score ≥ 0.70
    ↓
Build Connectivity Graph: 
  (geometries touch/intersect + 10m endpoint tolerance)
    ↓
Find Connected Components: 
  (DFS algorithm identifies clusters)
    ↓
Aggregate Each Component:
  (merge geometries, compute metrics)
    ↓
Filter: length_m ≥ 200
    ↓
Return: Sorted by mean_priority (descending)
```

## Key Files

| File | Purpose | Size |
|------|---------|------|
| [/backend/app/services/corridor_service.py](backend/app/services/corridor_service.py) | Aggregation logic (ConnectivityGraph, CorridorAggregator, CorridorService) | 448 lines |
| [/backend/app/routers/corridors.py](backend/app/routers/corridors.py) | REST API endpoints (/corridors, /corridors/{id}, /corridors/stats/summary) | 254 lines |
| [/backend/app/dependencies.py](backend/app/dependencies.py) | Service initialization (updated) | Modified |
| [/backend/app/main.py](backend/app/main.py) | Router registration (updated) | Modified |
| [/frontend/src/api/index.js](frontend/src/api/index.js) | Frontend API client (updated) | Modified |
| [/frontend/src/components/Map.jsx](frontend/src/components/Map.jsx) | Map rendering (updated) | Modified |
| [/frontend/src/components/Sidebar.jsx](frontend/src/components/Sidebar.jsx) | Layer toggle (label updated) | Modified |

## API Endpoints

### GET /api/v1/corridors
```bash
curl "http://localhost:8000/api/v1/corridors?priority_threshold=0.70&min_length=200&include_aqi=true"
```

**Response:** GeoJSON FeatureCollection with corridors
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "LineString", "coordinates": [...] },
      "properties": {
        "corridor_id": "string",
        "length_m": 450.5,
        "segment_count": 3,
        "mean_priority": 0.75,
        "mean_heat": 35.2,
        "mean_ndvi": 0.42,
        "mean_aqi": 155.8,
        "created_at": "2024-..."
      }
    }
  ],
  "metadata": {
    "count": 42,
    "priority_threshold": 0.70,
    "min_length_m": 200,
    "scoring_method": "multi-exposure",
    "description": "42 corridors aggregated from high-priority segments"
  }
}
```

### GET /api/v1/corridors/{corridor_id}
Returns full corridor details including geometry and composition

### GET /api/v1/corridors/stats/summary
```bash
curl "http://localhost:8000/api/v1/corridors/stats/summary"
```

**Response:** Aggregated statistics
```json
{
  "corridor_count": 42,
  "total_length_m": 15234.5,
  "total_segments": 128,
  "avg_priority": 0.72,
  "min_priority": 0.70,
  "max_priority": 0.89,
  "top_corridors": [...]
}
```

## Configuration

### Default Thresholds
```python
DEFAULT_PRIORITY_THRESHOLD = 0.70      # Min priority to be corridor-eligible
DEFAULT_MIN_CORRIDOR_LENGTH = 200.0    # Meters (filters noise)
CONNECTIVITY_TOLERANCE = 10.0          # Meters (segment adjacency distance)
```

Change these in `/backend/app/services/corridor_service.py` lines 37-40

### Priority Scoring (Multi-Exposure Index)
```
Priority = 0.45 × Heat Stress + 0.35 × (1 - Vegetation) + 0.20 × Air Quality

Where:
- Heat = LST normalized to 0-1 (hotter = higher)
- Vegetation = 1 - NDVI (lower NDVI = higher need)
- Air Quality = AQI normalized (higher AQI = higher pollution)
```

Falls back to GDI weights (0.45/0.35/0.20) when AQI unavailable.

## Frontend Integration

### Using corridorsApi
```javascript
import { corridorsApi } from '../api';

// Load corridors with default thresholds
const response = await corridorsApi.list(0.70, 200, true);

// Get specific corridor details
const detail = await corridorsApi.detail('corridor-id');

// Get summary statistics
const stats = await corridorsApi.summary();
```

### Layer Toggle
The "Priority Corridors" toggle in Sidebar controls visibility:
- When ON: Map loads and displays corridor GeoJSON
- When OFF: Layer is hidden
- State key: `activeLayers.corridors`

## Algorithm Details

### Connectivity Graph
```
ConnectivityGraph._build_graph():
  For each pair of segments (i, j):
    if segment_i.touches(segment_j) OR
       segment_i.intersects(segment_j) OR  
       distance(endpoint_i, endpoint_j) ≤ 10m:
      adjacency[i].add(j)
      adjacency[j].add(i)
```

Uses **Shapely** geometric operations:
- `LineString.touches()` → Endpoints coincide
- `LineString.intersects()` → Any overlap
- Distance calculation for endpoint proximity

### Connected Component Detection
```
ConnectivityGraph.find_connected_components():
  components = []
  visited = set()
  
  for each segment not in visited:
    component = DFS(segment, adjacency, visited)
    components.append(component)
  
  return components
```

**DFS Algorithm:**
- O(V + E) time complexity
- Deterministic (no randomness)
- Produces same output for same input

### Aggregation
```
CorridorAggregator.aggregate():
  1. eligible = filter(segments, priority ≥ threshold)
  2. graph = ConnectivityGraph(eligible, tolerance=10m)
  3. components = graph.find_connected_components()
  4. corridors = [create_corridor(component) for component in components]
  5. return filter(corridors, length ≥ min_length)
```

Where `create_corridor()`:
- Merges geometries: `unary_union(component.geometries)`
- Computes metrics: avg priority, heat, NDVI, AQI
- Returns: CorridorMetrics object

## Testing

### Verify Backend
```bash
# Check imports
cd /home/natya/Desktop/innovateNSUT/backend
source venv/bin/activate
python -c "from app.routers.corridors import router; print('✅')"

# Test service
python -c "from app.services.corridor_service import CorridorService; print('✅')"
```

### Verify Frontend
```bash
# Check API methods exist
cd /home/natya/Desktop/innovateNSUT/frontend
grep -n "corridorsApi" src/api/index.js
```

### Run Application
```bash
# Terminal 1: Backend
cd /home/natya/Desktop/innovateNSUT
source .venv/bin/activate
cd backend && uvicorn app.main:app --port 8000

# Terminal 2: Frontend  
cd /home/natya/Desktop/innovateNSUT/frontend
npm run dev

# Terminal 3: Test API
curl http://localhost:8000/api/v1/corridors | jq '.metadata'
```

## Troubleshooting

### Issue: "Corridor service not initialized"
**Fix:** Ensure `init_services()` is called in main.py lifespan (it is)

### Issue: "No corridors returned"
**Reason:** May be no segments ≥ 0.70 priority, or isolated segments
**Fix:** Lower `priority_threshold` in API call, or check road data is loaded

### Issue: "Map doesn't show corridors"
**Check:** 
1. Toggle "Priority Corridors" in sidebar
2. Open browser console for API errors
3. Verify backend `/api/v1/corridors` returns GeoJSON

### Issue: "Corridors lag the map"
**Reason:** First call computes aggregation (one-time)
**Result:** Subsequent calls use cache (instant)

## Future Enhancements

1. **Persistence**: Store corridors in MongoDB (vs. in-memory)
2. **Export**: GeoJSON, Shapefile, CSV export buttons
3. **Analysis**: Impact calculations (trees, people, emissions)
4. **Recommendations**: Investment prioritization algorithm
5. **Comparison**: Before/after analysis tools

## Support

- See `/CORRIDOR_INTEGRATION_SUMMARY.md` for complete documentation
- Algorithm details in `/backend/app/services/corridor_service.py` (inline comments)
- API schema at `http://localhost:8000/docs` (Swagger UI)

---

**Phase 2: COMPLETE ✅**
