#!/bin/bash

# Test the complete flow from KML upload to results

set -e

echo "=== Testing Complete Entmoot Flow ==="
echo ""

# Step 1: Check backend health
echo "1. Checking backend health..."
curl -s http://localhost:8000/health | jq .
echo ""

# Step 2: Upload KML file (using existing file)
echo "2. Uploading KML file..."
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/upload \
  -F "file=@data/uploads/151d0edb-21e0-4afb-bf32-c3133a54e798/Test property boundary.kml")
UPLOAD_ID=$(echo $UPLOAD_RESPONSE | jq -r .upload_id)
echo "Upload ID: $UPLOAD_ID"
echo ""

# Step 3: Create project with configuration
echo "3. Creating project..."
PROJECT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "upload_id": "'$UPLOAD_ID'",
    "project_name": "Test Flow",
    "assets": [
      {
        "type": "buildings",
        "quantity": 1,
        "width": 50,
        "length": 50,
        "height": 20
      }
    ],
    "constraints": {
      "setback_distance": 10,
      "min_distance_between_assets": 15,
      "max_slope": 15
    },
    "road_design": {
      "min_width": 24,
      "surface_type": "paved"
    },
    "optimization_weights": {
      "cost": 30,
      "buildable_area": 25,
      "accessibility": 25,
      "environmental_impact": 10,
      "aesthetics": 10
    }
  }')
PROJECT_ID=$(echo $PROJECT_RESPONSE | jq -r .project_id)
echo "Project ID: $PROJECT_ID"
echo ""

# Step 4: Poll status until complete
echo "4. Polling status..."
for i in {1..60}; do
  STATUS_RESPONSE=$(curl -s http://localhost:8000/api/v1/projects/$PROJECT_ID/status)
  STATUS=$(echo $STATUS_RESPONSE | jq -r .status)
  PROGRESS=$(echo $STATUS_RESPONSE | jq -r .progress)

  echo "   Status: $STATUS, Progress: $PROGRESS%"

  if [ "$STATUS" == "completed" ]; then
    echo "   ✅ Optimization completed!"
    break
  elif [ "$STATUS" == "failed" ]; then
    echo "   ❌ Optimization failed!"
    echo $STATUS_RESPONSE | jq .
    exit 1
  fi

  sleep 1
done
echo ""

# Step 5: Fetch results
echo "5. Fetching results..."
RESULTS=$(curl -s http://localhost:8000/api/v1/projects/$PROJECT_ID/results)

# Check if we got results
if echo $RESULTS | jq -e .project_id > /dev/null 2>&1; then
  echo "✅ Results retrieved successfully!"
  echo ""

  # Extract key data
  echo "Results Summary:"
  echo "  Project: $(echo $RESULTS | jq -r .project_name)"
  echo "  Bounds:"
  echo "    North: $(echo $RESULTS | jq -r .bounds.north)"
  echo "    South: $(echo $RESULTS | jq -r .bounds.south)"
  echo "    East: $(echo $RESULTS | jq -r .bounds.east)"
  echo "    West: $(echo $RESULTS | jq -r .bounds.west)"
  echo ""
  echo "  Assets Placed: $(echo $RESULTS | jq -r '.alternatives[0].metrics.assets_placed')"
  echo "  First Asset Position:"
  echo "    Latitude: $(echo $RESULTS | jq -r '.alternatives[0].assets[0].position.latitude')"
  echo "    Longitude: $(echo $RESULTS | jq -r '.alternatives[0].assets[0].position.longitude')"
  echo ""

  # Verify coordinates are in Austin, TX range
  LAT=$(echo $RESULTS | jq -r '.alternatives[0].assets[0].position.latitude')
  LON=$(echo $RESULTS | jq -r '.alternatives[0].assets[0].position.longitude')

  if (( $(echo "$LAT > 30.0 && $LAT < 30.5" | bc -l) )) && (( $(echo "$LON > -98.0 && $LON < -97.5" | bc -l) )); then
    echo "✅ Coordinates are in Austin, TX range!"
  else
    echo "❌ Coordinates are NOT in Austin, TX range!"
    echo "   Expected: lat ~30.25, lon ~-97.74"
    echo "   Got: lat $LAT, lon $LON"
  fi
else
  echo "❌ Failed to retrieve results!"
  echo $RESULTS | jq .
  exit 1
fi

echo ""
echo "=== Test Complete ==="
