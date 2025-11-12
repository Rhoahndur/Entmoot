# FEMA National Flood Hazard Layer (NFHL) Integration

This module provides integration with FEMA's National Flood Hazard Layer REST API to fetch floodplain data and determine if properties are in flood hazard areas.

## Features

- **API Client** (`client.py`)
  - Async HTTP requests using httpx
  - Rate limiting with token bucket algorithm
  - Automatic retry with exponential backoff
  - Configurable timeouts (default: 5 seconds)
  - Built-in caching with 30-day TTL
  - Graceful error handling

- **Response Parser** (`parser.py`)
  - Parses ArcGIS REST API responses
  - Converts geometries from ArcGIS format to WKT
  - Extracts flood zones, BFE, and metadata
  - Handles multiple zone types (A, AE, AH, AO, V, VE, X, etc.)
  - Determines highest risk zones

- **Caching Layer** (`cache.py`)
  - In-memory cache (default)
  - Optional Redis backend with automatic fallback
  - 30-day cache TTL (configurable)
  - Cache statistics and management

## Usage

### Basic Query by Point

```python
from entmoot.integrations.fema import FEMAClient

async with FEMAClient() as client:
    # Query floodplain data for a specific location
    result = await client.query_by_point(
        longitude=-122.084,
        latitude=37.422
    )

    if result.in_sfha:
        print(f"Property is in flood zone: {result.highest_risk_zone}")
        print(f"Flood insurance required: {result.insurance_required}")
        print(f"Maximum BFE: {result.get_max_bfe()} feet")
```

### Query by Bounding Box

```python
async with FEMAClient() as client:
    # Query floodplain data for an area
    result = await client.query_by_bbox(
        min_lon=-122.085,
        min_lat=37.421,
        max_lon=-122.083,
        max_lat=37.423
    )

    print(f"Found {len(result.zones)} flood zones")
    print(f"Zone summary: {result.get_zone_summary()}")
```

### Custom Configuration

```python
from entmoot.integrations.fema.client import FEMAClient, FEMAClientConfig

config = FEMAClientConfig(
    timeout=10.0,
    max_retries=5,
    cache_ttl=86400,  # 1 day
    rate_limit_calls=20,
    rate_limit_period=1.0,
)

async with FEMAClient(config) as client:
    result = await client.query_by_point(-122.084, 37.422)
```

### Using Redis Cache

```python
from entmoot.integrations.fema.cache import CacheManager

# Initialize with Redis backend (falls back to in-memory if unavailable)
cache = CacheManager(
    redis_url="redis://localhost:6379/0",
    ttl_seconds=2592000  # 30 days
)

# Get cache statistics
stats = cache.get_stats()
print(f"Cache backend: {stats['backend']}")
print(f"Cache entries: {stats['entries']}")
print(f"Hit rate: {stats['hit_rate_percent']}%")
```

## Data Models

### FloodZone

Represents a FEMA flood zone with geometry and metadata:

- `zone_type`: FloodZoneType enum (A, AE, AH, AO, V, VE, X, etc.)
- `geometry_wkt`: WKT representation of the zone polygon
- `base_flood_elevation`: Base Flood Elevation in feet
- `floodway`: Whether area is in regulatory floodway
- `coastal_zone`: Whether area is in coastal high hazard area
- `effective_date`: Date the flood map became effective

### FloodplainData

Collection of flood zones for a location:

- `zones`: List of FloodZone objects
- `in_sfha`: Whether location is in Special Flood Hazard Area
- `insurance_required`: Whether flood insurance is required
- `highest_risk_zone`: Most restrictive flood zone present
- `get_max_bfe()`: Get maximum BFE across all zones
- `get_zone_summary()`: Get count of each zone type

### RegulatoryConstraint

Generic regulatory constraint model with factory method:

```python
from entmoot.models.regulatory import RegulatoryConstraint

# Create constraint from floodplain data
constraint = RegulatoryConstraint.from_floodplain_data(floodplain_data)

if constraint:
    print(f"Constraint: {constraint.description}")
    print(f"Severity: {constraint.severity}")
    print(f"Requires permit: {constraint.requires_permit}")
```

## FEMA Flood Zone Types

### High-Risk Zones (Special Flood Hazard Areas)
- **A**: 1% annual chance flood, no BFE determined
- **AE**: 1% annual chance flood, BFE determined
- **AH**: Shallow flooding (1-3 feet), BFE determined
- **AO**: Sheet flow flooding, depth determined
- **AR**: Temporarily protected by flood control
- **A99**: Protected by federal flood control
- **V**: Coastal flood with wave action, no BFE
- **VE**: Coastal flood with wave action, BFE determined

### Moderate to Low Risk Zones
- **B/X**: 0.2% annual chance flood or protected by levee
- **C**: Minimal flood risk
- **D**: Undetermined risk

## API Endpoints

The module uses FEMA's National Flood Hazard Layer ArcGIS REST API:

- **Base URL**: `https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer`
- **Flood Zones Layer**: Layer 28
- **Response Format**: JSON
- **Spatial Reference**: EPSG:4326 (WGS84)
- **Max Records**: 2,000 per request

## Error Handling

The client handles errors gracefully:

- **Timeouts**: Automatic retry with exponential backoff
- **Rate Limiting**: Token bucket algorithm prevents API overload
- **API Errors**: Returns empty FloodplainData on failure
- **Invalid Geometries**: Automatically attempts repair
- **Network Issues**: Retries up to max_retries times

## Testing

Comprehensive test suite with 53 tests covering:

- Rate limiting behavior
- Response parsing (all zone types)
- Geometry conversion
- Caching (in-memory and Redis)
- Error handling and retries
- Timeout scenarios
- Mock API responses

Run tests:
```bash
pytest tests/test_integrations/test_fema.py -v
```

Check coverage:
```bash
pytest tests/test_integrations/test_fema.py --cov=src/entmoot/integrations/fema
```

## Coverage

- **client.py**: 89.19%
- **parser.py**: 84.62%
- **regulatory.py**: 98.20%
- **cache.py**: 52.14% (Redis backend not tested without Redis)

Overall FEMA integration coverage: **85%+**

## Dependencies

Required:
- `httpx>=0.25.0` - Async HTTP client

Optional:
- `redis>=5.0.0` - Redis caching backend (falls back to in-memory)

Install:
```bash
pip install httpx
pip install redis  # Optional
```

## Configuration

Environment variables (optional):
- `FEMA_API_KEY` - API key if required (currently not needed)
- `REDIS_URL` - Redis connection URL (default: redis://localhost:6379/0)

## Performance

- **Query Time**: <5 seconds (typically 1-2 seconds)
- **Cache TTL**: 30 days (floodplains change infrequently)
- **Rate Limit**: 10 calls per second (configurable)
- **Timeout**: 5 seconds (configurable)

## Future Enhancements

- Add support for batch queries
- Implement webhook notifications for map updates
- Add GeoJSON export functionality
- Support for historical flood data
- Integration with local jurisdiction data sources
