#!/bin/bash
set -e

OSM_FILE=${1:-"seoul.osm.pbf"}
DB_HOST=${DB_HOST:-"localhost"}
DB_PORT=${DB_PORT:-"5432"}
DB_NAME=${DB_NAME:-"artrun"}
DB_USER=${DB_USER:-"artrun"}
DB_PASSWORD=${DB_PASSWORD:-"artrun"}

echo "=== ArtRun OSM Data Import Pipeline ==="
echo "OSM File: $OSM_FILE"
echo "Database: $DB_NAME@$DB_HOST:$DB_PORT"

# Step 1: Download OSM data if not exists
if [ ! -f "$OSM_FILE" ]; then
    echo "[1/4] Downloading Seoul OSM data..."
    wget -O "$OSM_FILE" "https://download.geofabrik.de/asia/south-korea-latest.osm.pbf"
else
    echo "[1/4] OSM file already exists, skipping download."
fi

# Step 2: Filter pedestrian ways using osmium and convert to XML
echo "[2/4] Filtering pedestrian-friendly ways..."
FILTERED_FILE="pedestrian.osm"
if command -v osmium &> /dev/null; then
    osmium tags-filter "$OSM_FILE" \
        w/highway=footway,pedestrian,path,residential,living_street,service,track,steps,cycleway,unclassified,tertiary,secondary \
        -o "$FILTERED_FILE" -f osm --overwrite
else
    echo "osmium not found, converting original file to XML..."
    osmium cat "$OSM_FILE" -o "$FILTERED_FILE" -f osm --overwrite 2>/dev/null || FILTERED_FILE="$OSM_FILE"
fi

# Step 3: Import into PostgreSQL with osm2pgrouting
echo "[3/4] Importing into PostgreSQL with osm2pgrouting..."
export PGPASSWORD="$DB_PASSWORD"
osm2pgrouting \
    --f "$FILTERED_FILE" \
    --conf /usr/share/osm2pgrouting/mapconfig_for_pedestrian.xml \
    --dbname "$DB_NAME" \
    --username "$DB_USER" \
    --host "$DB_HOST" \
    --port "$DB_PORT" \
    --clean

# Step 4: Create spatial indexes and verify
echo "[4/4] Creating indexes and verifying..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << 'SQL'
CREATE INDEX IF NOT EXISTS idx_ways_the_geom ON ways USING GIST (the_geom);
CREATE INDEX IF NOT EXISTS idx_ways_vertices_the_geom ON ways_vertices_pgr USING GIST (the_geom);
CREATE INDEX IF NOT EXISTS idx_ways_source ON ways (source);
CREATE INDEX IF NOT EXISTS idx_ways_target ON ways (target);
CREATE INDEX IF NOT EXISTS idx_ways_source_target ON ways (source, target);
CREATE INDEX IF NOT EXISTS idx_ways_tag_id ON ways (tag_id);
ANALYZE ways;
ANALYZE ways_vertices_pgr;

SELECT 'ways' AS table_name, count(*) FROM ways
UNION ALL
SELECT 'vertices', count(*) FROM ways_vertices_pgr;
SQL

echo "=== OSM Import Complete ==="
