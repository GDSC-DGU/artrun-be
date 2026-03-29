CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pgrouting;
CREATE EXTENSION IF NOT EXISTS hstore;

-- OSM 임포트 후 수동으로 실행할 인덱스 (osm2pgrouting 이후)
-- CREATE INDEX IF NOT EXISTS idx_ways_source ON ways (source);
-- CREATE INDEX IF NOT EXISTS idx_ways_target ON ways (target);
-- CREATE INDEX IF NOT EXISTS idx_ways_source_target ON ways (source, target);
-- CREATE INDEX IF NOT EXISTS idx_ways_tag_id ON ways (tag_id);
