# FEMA Integration Quick Start

## Installation

```bash
pip install httpx
pip install redis  # Optional, for Redis caching
```

## Basic Usage

```python
import asyncio
from entmoot.integrations.fema import FEMAClient

async def check_flood_zone():
    async with FEMAClient() as client:
        # Query a location
        result = await client.query_by_point(
            longitude=-122.084,
            latitude=37.422
        )

        # Check if in flood zone
        if result.in_sfha:
            print(f"⚠️  In flood zone: {result.highest_risk_zone.value}")
            print(f"Max BFE: {result.get_max_bfe()} feet")
        else:
            print("✓ Not in flood zone")

# Run
asyncio.run(check_flood_zone())
```

## Creating Regulatory Constraints

```python
from entmoot.models.regulatory import RegulatoryConstraint

# Convert floodplain data to constraint
constraint = RegulatoryConstraint.from_floodplain_data(result)

if constraint:
    print(f"Severity: {constraint.severity}")
    print(f"Description: {constraint.description}")
    print(f"Requires permit: {constraint.requires_permit}")
```

## Configuration

```python
from entmoot.integrations.fema.client import FEMAClientConfig

config = FEMAClientConfig(
    timeout=10.0,           # Request timeout
    max_retries=3,          # Max retry attempts
    cache_ttl=2592000,      # Cache TTL (30 days)
    rate_limit_calls=20,    # Max calls per period
    rate_limit_period=1.0   # Period in seconds
)

async with FEMAClient(config) as client:
    result = await client.query_by_point(-122.084, 37.422)
```

## Query by Bounding Box

```python
async with FEMAClient() as client:
    result = await client.query_by_bbox(
        min_lon=-122.085,
        min_lat=37.421,
        max_lon=-122.083,
        max_lat=37.423
    )

    print(f"Found {len(result.zones)} zones")
    print(f"Summary: {result.get_zone_summary()}")
```

## Using Redis Cache

```python
from entmoot.integrations.fema.cache import CacheManager

# Automatically falls back to in-memory if Redis unavailable
cache = CacheManager(
    redis_url="redis://localhost:6379/0",
    ttl_seconds=2592000
)

# Use with client
# (Note: client has built-in in-memory cache by default)
```

## Understanding Results

### Flood Zone Types

**High Risk (SFHA - Special Flood Hazard Areas):**
- `A` - 1% annual chance, no BFE
- `AE` - 1% annual chance, BFE determined
- `V/VE` - Coastal with wave action

**Moderate/Low Risk:**
- `X` - 0.2% annual chance or minimal risk
- `B/C` - Minimal risk

### FloodplainData Properties

```python
result.in_sfha              # True if in Special Flood Hazard Area
result.insurance_required   # True if flood insurance required
result.highest_risk_zone    # Most restrictive zone
result.zones               # List of FloodZone objects
result.get_max_bfe()       # Maximum Base Flood Elevation
result.get_zone_summary()  # Count by zone type
```

### FloodZone Properties

```python
zone = result.zones[0]

zone.zone_type              # FloodZoneType enum
zone.base_flood_elevation   # BFE in feet
zone.floodway              # True if in regulatory floodway
zone.coastal_zone          # True if coastal high hazard
zone.effective_date        # Map effective date
zone.is_high_risk()        # True if SFHA zone
zone.requires_flood_insurance()  # True if insurance required
```

## Examples

Run the example script:
```bash
python examples/fema_floodplain_example.py
```

## Error Handling

The client handles errors gracefully:

```python
async with FEMAClient() as client:
    try:
        result = await client.query_by_point(-122.084, 37.422)

        # Check if query succeeded
        if result.zones:
            print("Got flood data")
        else:
            print("No flood zones or API error")

    except Exception as e:
        print(f"Unexpected error: {e}")
        # Client returns empty FloodplainData on most errors
```

## Performance Tips

1. **Enable Caching**: Cache is enabled by default, don't disable it
2. **Batch Queries**: Query multiple locations in sequence (cached responses are instant)
3. **Bounding Box**: Use bbox queries for larger areas
4. **Rate Limiting**: Default 10 calls/sec is usually sufficient

## Testing

Run tests:
```bash
pytest tests/test_integrations/test_fema.py -v
```

Check coverage:
```bash
pytest tests/test_integrations/test_fema.py --cov=src/entmoot/integrations/fema
```

## Documentation

- Full README: `src/entmoot/integrations/fema/README.md`
- Example script: `examples/fema_floodplain_example.py`
- Implementation summary: `STORY_2.6_IMPLEMENTATION_SUMMARY.md`

## Support

For issues or questions:
1. Check the full README for detailed documentation
2. Review the example script for usage patterns
3. Examine test suite for edge cases
