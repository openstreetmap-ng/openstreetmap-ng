# Overpass to SQL Transpiler - Implementation Guide

This document provides comprehensive guidance for implementing a transpiler that converts Overpass QL queries into PostgreSQL/PostGIS queries against the OpenStreetMap-NG database schema.

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Overpass QL Syntax Reference](#overpass-ql-syntax-reference)
3. [Database Schema Overview](#database-schema-overview)
4. [TypedElementId Encoding](#typedelementid-encoding)
5. [Index Strategy & Optimization](#index-strategy--optimization)
6. [Tag Filtering in SQL](#tag-filtering-in-sql)
7. [Spatial Query Patterns](#spatial-query-patterns)
8. [Materialization & Consistency](#materialization--consistency)
9. [Comprehensive Examples](#comprehensive-examples)
10. [Edge Cases & Special Handling](#edge-cases--special-handling)
11. [Architecture Recommendations](#architecture-recommendations)
12. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

### Goal

Transpile Overpass QL queries into PostgreSQL queries that execute against our database, providing similar functionality to the official Overpass API while leveraging our existing infrastructure.

### Scope

Target the **99% use case** - the most common query patterns:
- Tag queries with bounding box filters
- Recursive queries for complete geometry (way nodes, relation members)
- Multi-type queries (`nwr`)
- Around/radius queries
- Area queries (named administrative boundaries)

### Key Findings

| Aspect | Current State | Recommendation |
|--------|---------------|----------------|
| **Tag Indexing** | No GIN index on `element.tags` | **Add GIN index** - critical for performance |
| **Spatial Indexing** | H3 grid + GiST on points | Excellent - use existing patterns |
| **Materialization** | ~5 minute delay on `element_spatial` | Design for freshness vs consistency trade-offs |
| **Member Queries** | GIN index on `members` array | Well-optimized, use `&&` operator |

---

## Overpass QL Syntax Reference

### Query Structure

```
[settings];
query_statement(s);
output_statement;
```

### Element Types

| Overpass | Description | TypedElementId Range |
|----------|-------------|----------------------|
| `node` | Individual points | `0` to `1152921504606846975` |
| `way` | Ordered sequences of nodes | `1152921504606846976` to `2305843009213693951` |
| `relation` | Collections of elements | `2305843009213693952` to `3458764513820540927` |
| `nwr` | All three types | Union of above ranges |
| `area` | Derived closed polygons | Synthetic (not stored) |

### Filter Types

#### Tag Filters (Square Brackets)

| Syntax | Description | SQL Equivalent |
|--------|-------------|----------------|
| `[key]` | Key exists | `tags ? 'key'` |
| `[!key]` | Key doesn't exist | `NOT (tags ? 'key')` |
| `[key=value]` | Exact match | `tags @> 'key=>value'::hstore` |
| `[key!=value]` | Not equal | `NOT (tags @> 'key=>value'::hstore)` |
| `[key~pattern]` | Regex on value | `tags -> 'key' ~ 'pattern'` |
| `[key~pattern,i]` | Case-insensitive regex | `tags -> 'key' ~* 'pattern'` |
| `[~keypattern~valuepattern]` | Regex on both | See [Complex Tag Patterns](#complex-tag-patterns) |

#### Spatial Filters (Round Brackets)

| Syntax | Description | SQL Equivalent |
|--------|-------------|----------------|
| `(south,west,north,east)` | Bounding box | `geom && ST_MakeEnvelope(west, south, east, north, 4326)` |
| `(around:radius,lat,lon)` | Radius from point | `ST_DWithin(geom, ST_Point(lon, lat), radius_degrees)` |
| `(area.name)` | Within named area | `ST_Intersects(geom, area_geom)` |

### Recursion Operators

| Operator | Description | SQL Implementation |
|----------|-------------|-------------------|
| `>` | Recurse down (nodes of ways, members of relations) | Join on `members` array |
| `>>` | Recursive down (all descendants) | Recursive CTE |
| `<` | Recurse up (parent ways/relations) | `members && ARRAY[...]` |
| `<<` | Recursive up (all ancestors) | Recursive CTE |

### Set Operations

| Syntax | Description | SQL Equivalent |
|--------|-------------|----------------|
| `(stmt1; stmt2;)` | Union | `UNION ALL` |
| `.set1.set2` | Intersection | `INTERSECT` |
| `(stmt1; - stmt2;)` | Difference | `EXCEPT` |
| `-> .name` | Store in named set | Temp table or CTE |

### Output Modifiers

| Modifier | Description | Data Returned |
|----------|-------------|---------------|
| `out` | Basic output | IDs, tags |
| `out geom` | Full geometry | + node coordinates |
| `out center` | Center point | `ST_Centroid(ST_Envelope(geom))` |
| `out bb` | Bounding box | `ST_Envelope(geom)` |
| `out meta` | Metadata | + version, changeset, timestamp, user |
| `out skel` | Skeleton | IDs only, no tags |

---

## Database Schema Overview

### Core Tables

#### `element` (TimescaleDB Hypertable)

```sql
CREATE TABLE element (
    sequence_id bigint,              -- Global monotonic sequence
    changeset_id bigint NOT NULL,    -- Reference to changeset
    typed_id bigint NOT NULL,        -- Type (4 bits) + ID (60 bits)
    version bigint NOT NULL,         -- Per-element version counter
    latest boolean NOT NULL,         -- TRUE for current version
    visible boolean NOT NULL,        -- FALSE for deleted elements
    tags hstore,                     -- Key-value tags
    point geometry(Point, 4326),     -- Node location (nodes only)
    members BIGINT[],                -- Member typed_ids (ways/relations)
    members_roles TEXT[],            -- Member roles (relations only)
    created_at timestamptz NOT NULL
);
```

**Partitioning**: Hypertable partitioned by `typed_id` with chunk interval `1152921504606846976` (naturally separates nodes/ways/relations).

#### `element_spatial` (Materialized Geometries)

```sql
CREATE TABLE element_spatial (
    typed_id bigint PRIMARY KEY,     -- Reference to element
    sequence_id bigint NOT NULL,     -- Version reference
    geom geometry(Geometry, 4326),   -- Pre-computed geometry
    bounds_area real GENERATED       -- ST_Area(ST_Envelope(geom))
);
```

**Purpose**: Pre-computed geometries for ways (linestrings/polygons) and relations (multi-geometries). Updated every ~5 minutes.

#### `element_spatial_watermark`

```sql
CREATE TABLE element_spatial_watermark (
    id smallint PRIMARY KEY CHECK (id = 1),
    sequence_id bigint NOT NULL      -- Last processed sequence_id
);
```

**Purpose**: Tracks materialization progress for crash recovery and staleness detection.

### Versioning Model

- **`sequence_id`**: Global ordering across all element modifications (for replication/API)
- **`version`**: Per-element version counter (incremented on each modification)
- **`latest`**: Boolean flag for current version (indexed, enables fast lookups)
- **`visible`**: FALSE for deleted elements (deletions are versioned, not physical)

**Getting Latest Version**:
```sql
SELECT DISTINCT ON (typed_id) *
FROM element
WHERE typed_id = ANY($1)
ORDER BY typed_id, sequence_id DESC
```

---

## TypedElementId Encoding

The `typed_id` field encodes both element type and ID in a single 64-bit integer:

```
┌───────────────────────────────────────────────────────────────────┐
│  4 bits (type)  │           60 bits (element ID)                  │
└───────────────────────────────────────────────────────────────────┘
```

### Type Ranges

| Type | Range Min | Range Max | Constant |
|------|-----------|-----------|----------|
| Node | `0` | `1152921504606846975` | `TYPED_ELEMENT_ID_NODE_MAX` |
| Way | `1152921504606846976` | `2305843009213693951` | `TYPED_ELEMENT_ID_WAY_MIN/MAX` |
| Relation | `2305843009213693952` | `3458764513820540927` | `TYPED_ELEMENT_ID_RELATION_MIN/MAX` |

### Encoding Functions

```python
# In app/models/element.py
TYPED_ELEMENT_ID_RELATION_MIN = typed_element_id('relation', ElementId(0))  # 2 << 60
TYPED_ELEMENT_ID_WAY_MIN = typed_element_id('way', ElementId(0))            # 1 << 60
TYPED_ELEMENT_ID_NODE_MAX = TYPED_ELEMENT_ID_WAY_MIN - 1                    # (1 << 60) - 1

# Encoding: typed_id = (type_bits << 60) | element_id
# Decoding: type = typed_id >> 60, element_id = typed_id & ((1 << 60) - 1)
```

### SQL Type Filtering

```sql
-- Nodes only
WHERE typed_id <= 1152921504606846975

-- Ways only
WHERE typed_id BETWEEN 1152921504606846976 AND 2305843009213693951

-- Relations only
WHERE typed_id >= 2305843009213693952

-- Ways and relations (has members)
WHERE typed_id >= 1152921504606846976
```

---

## Index Strategy & Optimization

### Current Indexes on `element`

| Index | Columns | Type | Condition | Purpose |
|-------|---------|------|-----------|---------|
| `element_sequence_idx` | `(sequence_id)` | btree | - | Timeline queries |
| `element_changeset_idx` | `(changeset_id)` | btree | - | Changeset lookups |
| `element_id_version_idx` | `(typed_id, version)` | btree | - | Version history |
| `element_id_sequence_idx` | `(typed_id, sequence_id)` | btree | - | Sequence lookups |
| `element_point_idx` | `(point)` | gist | `typed_id <= NODE_MAX AND point IS NOT NULL AND latest` | Node spatial queries |
| `element_members_idx` | `(members)` | gin | `typed_id >= WAY_MIN AND latest` | Member lookups (current) |
| `element_members_history_idx` | `(members)` | gin | `typed_id >= WAY_MIN AND NOT latest` | Member lookups (history) |

### Index on `element_spatial`

| Index | Columns | Type | Purpose |
|-------|---------|------|---------|
| `element_spatial_geom_h3_idx` | `h3_geometry_to_compact_cells(geom, 11)` | gin | H3 spatial indexing |

### Critical Gap: No Tag Index

**Current state**: The `element.tags` column has **NO INDEX**.

**Impact**: Any tag-based query requires a full table scan.

**Recommended Addition**:
```sql
-- Add GIN index on tags for tag filtering
CREATE INDEX element_tags_gin_idx ON element USING gin (tags)
WITH (fastupdate = FALSE)
WHERE tags IS NOT NULL AND visible AND latest;
```

**Rationale**:
- GIN index supports `?`, `@>`, `?&` operators efficiently
- Partial index (`WHERE latest`) reduces size significantly
- `fastupdate = FALSE` provides consistent query performance

### Query Optimizer Hints

The codebase uses PostgreSQL pg_hint_plan extension for index selection:

```sql
/*+ BitmapScan(element element_members_idx) */
SELECT * FROM element
WHERE members && $1::bigint[]
AND typed_id >= 1152921504606846976
AND latest
```

---

## Tag Filtering in SQL

### hstore Operators

| Operator | SQL | Description |
|----------|-----|-------------|
| Key exists | `tags ? 'key'` | Check if key present |
| Key not exists | `NOT (tags ? 'key')` | Check if key absent |
| Exact match | `tags @> 'key=>value'::hstore` | Contains key-value pair |
| Get value | `tags -> 'key'` | Returns value or NULL |
| Any key exists | `tags ?| ARRAY['k1','k2']` | Any of keys present |
| All keys exist | `tags ?& ARRAY['k1','k2']` | All keys present |

### Overpass to SQL Mapping

#### Simple Filters

```sql
-- [amenity]
WHERE tags ? 'amenity'

-- [!amenity]
WHERE NOT (tags ? 'amenity')

-- [amenity=restaurant]
WHERE tags @> 'amenity=>restaurant'::hstore

-- [amenity!=restaurant]
WHERE NOT (tags @> 'amenity=>restaurant'::hstore)
-- Note: This also matches elements WITHOUT the amenity key!
-- For "has amenity but not restaurant":
WHERE tags ? 'amenity' AND NOT (tags @> 'amenity=>restaurant'::hstore)
```

#### Regex Filters

```sql
-- [name~^Main]
WHERE tags -> 'name' ~ '^Main'

-- [name~^Main,i] (case-insensitive)
WHERE tags -> 'name' ~* '^main'

-- [amenity~cafe|restaurant|bar]
WHERE (tags -> 'amenity') ~ 'cafe|restaurant|bar'
-- Or more efficient:
WHERE (tags -> 'amenity') IN ('cafe', 'restaurant', 'bar')
```

#### Complex Tag Patterns

```sql
-- [~^addr:.*$~.] (any addr:* tag with any value)
WHERE EXISTS (
    SELECT 1 FROM each(tags) AS t(key, value)
    WHERE t.key ~ '^addr:.*$'
)

-- [~name~^Main] (any key containing "name" with value starting with "Main")
WHERE EXISTS (
    SELECT 1 FROM each(tags) AS t(key, value)
    WHERE t.key ~ 'name' AND t.value ~ '^Main'
)
```

### Performance Recommendations

1. **Prefer `@>` for exact matches** - Uses GIN index effectively
2. **Use `?&` for multiple key existence** - Single index lookup
3. **Avoid `each()` on hot paths** - Forces table scan
4. **Combine spatial filter first** - Reduce candidate set before tag filtering

```sql
-- Good: Spatial filter first, then tag filter
SELECT * FROM element
WHERE point && $bbox
  AND typed_id <= 1152921504606846975
  AND latest
  AND tags @> 'amenity=>restaurant'::hstore

-- Bad: Tag filter without spatial restriction
SELECT * FROM element
WHERE tags @> 'amenity=>restaurant'::hstore
  AND latest
-- Will scan entire table!
```

---

## Spatial Query Patterns

### Bounding Box Queries

```sql
-- Overpass: node["amenity"="restaurant"](48.0,16.3,48.1,16.4)
SELECT * FROM element
WHERE typed_id <= 1152921504606846975
  AND point && ST_MakeEnvelope(16.3, 48.0, 16.4, 48.1, 4326)
  AND latest
  AND tags @> 'amenity=>restaurant'::hstore
```

**Note**: Overpass bbox order is `(south,west,north,east)` but PostGIS `ST_MakeEnvelope` expects `(xmin,ymin,xmax,ymax)` = `(west,south,east,north)`.

### Radius/Around Queries

```sql
-- Overpass: node["amenity"="restaurant"](around:1000,52.52,13.40)
-- Option 1: Geography type (accurate, slower)
SELECT * FROM element
WHERE typed_id <= 1152921504606846975
  AND latest
  AND ST_DWithin(
    point::geography,
    ST_Point(13.40, 52.52)::geography,
    1000  -- meters
  )
  AND tags @> 'amenity=>restaurant'::hstore

-- Option 2: Geometry type (approximate, faster)
-- 1000 meters ≈ 0.009 degrees at ~52° latitude
SELECT * FROM element
WHERE typed_id <= 1152921504606846975
  AND latest
  AND ST_DWithin(point, ST_Point(13.40, 52.52), 0.009)
  AND tags @> 'amenity=>restaurant'::hstore
```

**Conversion**: At the equator, 1 degree ≈ 111.32 km. Use:
```python
def meters_to_degrees(meters: float, latitude: float = 0) -> float:
    return meters / (111320 * cos(radians(latitude)))
```

### H3 Spatial Index Usage

For complex geometries (ways, relations), use the H3 index:

```sql
-- Query features intersecting a polygon
WITH search_params AS (
    SELECT
        $polygon AS area,
        polygon_to_h3_search($polygon, 11) AS h3_cells
)
SELECT es.typed_id, es.geom, e.tags
FROM element_spatial es
INNER JOIN element e ON e.typed_id = es.typed_id AND e.latest
CROSS JOIN search_params sp
WHERE h3_geometry_to_compact_cells(es.geom, 11) && sp.h3_cells::h3index[]
  AND ST_Intersects(es.geom, sp.area)
```

**Two-phase filtering**:
1. H3 grid cells for approximate spatial filtering (very fast, uses GIN index)
2. `ST_Intersects` for exact geometry validation (more expensive, smaller dataset)

### Combined Node + Way/Relation Queries

The codebase pattern from `element_spatial_query.py`:

```sql
WITH area_center AS (
    SELECT ST_X(ST_Centroid($area)) AS cx, ST_Y(ST_Centroid($area)) AS cy
)
SELECT typed_id, sequence_id, geom, version, tags
FROM (
    -- Ways/Relations from element_spatial (pre-computed)
    SELECT es.typed_id, es.sequence_id, es.geom, e.version, e.tags, es.bounds_area AS sort_key
    FROM element_spatial es
    INNER JOIN element e ON e.typed_id = es.typed_id AND e.latest
    WHERE h3_geometry_to_compact_cells(es.geom, 11) && $h3_cells::h3index[]
      AND ST_Intersects(es.geom, $area)

    UNION ALL

    -- Nodes directly from element table (always fresh)
    SELECT e.typed_id, e.sequence_id, e.point AS geom, e.version, e.tags,
           (ST_X(e.point) - area_center.cx)^2 + (ST_Y(e.point) - area_center.cy)^2 AS sort_key
    FROM element e, area_center
    WHERE e.typed_id <= 1152921504606846975
      AND e.latest AND e.visible
      AND e.tags IS NOT NULL
      AND ST_Intersects(e.point, $area)
) combined
ORDER BY sort_key
LIMIT $limit
```

---

## Materialization & Consistency

### The Materialization Pipeline

`element_spatial` is populated by `ElementSpatialService._update()`:

1. **Detect Changes**: Query `element` for `sequence_id > watermark`
2. **Process Ways**: Build geometries from member nodes using `ST_MakeLine`
3. **Process Relations**: Recursively build from member ways/relations (up to 15 depths)
4. **Atomic Finalize**: Merge staging tables into `element_spatial`, update watermark

**Typical Latency**: ~5 minutes between updates (290-310 second sleep cycle)

### Staleness Detection

```sql
-- Check if data might be stale
SELECT
    (SELECT MAX(sequence_id) FROM element) AS current_max,
    (SELECT sequence_id FROM element_spatial_watermark LIMIT 1) AS watermark;

-- If current_max > watermark, element_spatial may be stale
```

### Freshness Strategies

| Strategy | Latency | Consistency | Use Case |
|----------|---------|-------------|----------|
| **Best Effort** | Lowest | May return 5-min stale data | Real-time map views |
| **Nodes Fresh** | Low | Nodes fresh, ways/relations ~5min | Feature queries |
| **Force Refresh** | ~5min | Guaranteed fresh | Critical operations |

**Recommendation**: Use the "Nodes Fresh" pattern by default:
- Query `element` directly for nodes (always current)
- Query `element_spatial` for ways/relations (pre-computed)
- Document staleness window in API responses

### Isolation Levels

```python
# For consistent multi-element queries
async with db(isolation_level=IsolationLevel.REPEATABLE_READ) as conn:
    # All queries see same snapshot
    nodes = await fetch_nodes(conn)
    ways = await fetch_ways(conn)
    relations = await fetch_relations(conn)
```

**When to use REPEATABLE_READ**:
- Map tile rendering (prevent tile inconsistencies)
- Historical/snapshot queries
- Multi-element recursive queries

---

## Comprehensive Examples

### Example 1: Simple POI Query

**Overpass**:
```
[out:json];
node["amenity"="cafe"](48.0,16.3,48.1,16.4);
out;
```

**SQL**:
```sql
SELECT
    typed_id,
    version,
    tags,
    point AS geom
FROM element
WHERE typed_id <= 1152921504606846975
  AND point && ST_MakeEnvelope(16.3, 48.0, 16.4, 48.1, 4326)
  AND latest
  AND tags @> 'amenity=>cafe'::hstore
```

### Example 2: Multi-Type Query with Tags

**Overpass**:
```
[out:json];
nwr["building"="yes"]["name"](48.0,16.3,48.1,16.4);
out geom;
```

**SQL**:
```sql
WITH bbox AS (
    SELECT ST_MakeEnvelope(16.3, 48.0, 16.4, 48.1, 4326) AS geom
)
-- Nodes
SELECT e.typed_id, e.version, e.tags, e.point AS geom, 'node' AS type
FROM element e, bbox
WHERE e.typed_id <= 1152921504606846975
  AND e.point && bbox.geom
  AND e.latest
  AND e.tags @> 'building=>yes'::hstore
  AND e.tags ? 'name'

UNION ALL

-- Ways and Relations (from element_spatial)
SELECT e.typed_id, e.version, e.tags, es.geom,
       CASE WHEN e.typed_id <= 2305843009213693951 THEN 'way' ELSE 'relation' END AS type
FROM element_spatial es
INNER JOIN element e ON e.typed_id = es.typed_id AND e.latest
CROSS JOIN bbox
WHERE h3_geometry_to_compact_cells(es.geom, 11) &&
      h3_geometry_to_compact_cells(bbox.geom, 11)
  AND ST_Intersects(es.geom, bbox.geom)
  AND e.tags @> 'building=>yes'::hstore
  AND e.tags ? 'name'
```

### Example 3: Way with Complete Geometry (Recurse Down)

**Overpass**:
```
[out:json];
way["highway"="primary"](48.0,16.3,48.1,16.4);
(
  _;
  >;
);
out geom;
```

**SQL**:
```sql
WITH
-- Step 1: Find matching ways
matching_ways AS (
    SELECT e.typed_id, e.version, e.tags, e.members, es.geom
    FROM element e
    INNER JOIN element_spatial es ON es.typed_id = e.typed_id
    WHERE e.typed_id BETWEEN 1152921504606846976 AND 2305843009213693951
      AND e.latest
      AND e.tags @> 'highway=>primary'::hstore
      AND h3_geometry_to_compact_cells(es.geom, 11) &&
          h3_geometry_to_compact_cells(ST_MakeEnvelope(16.3, 48.0, 16.4, 48.1, 4326), 11)
),
-- Step 2: Get all member node IDs
member_nodes AS (
    SELECT DISTINCT UNNEST(members) AS node_typed_id
    FROM matching_ways
)
-- Return ways
SELECT typed_id, version, tags, geom, 'way' AS type
FROM matching_ways

UNION ALL

-- Return member nodes
SELECT e.typed_id, e.version, e.tags, e.point AS geom, 'node' AS type
FROM element e
INNER JOIN member_nodes mn ON mn.node_typed_id = e.typed_id
WHERE e.latest
```

### Example 4: Radius Query Around a Point

**Overpass**:
```
[out:json];
node["amenity"="restaurant"](around:500,52.52,13.40);
out;
```

**SQL**:
```sql
-- Using geography for accurate distance
SELECT
    typed_id,
    version,
    tags,
    point AS geom,
    ST_Distance(point::geography, ST_Point(13.40, 52.52)::geography) AS distance_meters
FROM element
WHERE typed_id <= 1152921504606846975
  AND latest
  AND ST_DWithin(
    point::geography,
    ST_Point(13.40, 52.52)::geography,
    500  -- meters
  )
  AND tags @> 'amenity=>restaurant'::hstore
ORDER BY distance_meters
```

### Example 5: Find Parent Ways/Relations (Recurse Up)

**Overpass**:
```
[out:json];
node(123456);
<;
out;
```

**SQL**:
```sql
WITH target_node AS (
    SELECT (1 << 60) * 0 + 123456 AS typed_id  -- node type (0) + id
)
-- Find parent ways
SELECT e.typed_id, e.version, e.tags, 'way' AS type
FROM element e, target_node tn
WHERE e.typed_id BETWEEN 1152921504606846976 AND 2305843009213693951
  AND e.latest
  AND e.members && ARRAY[tn.typed_id]

UNION ALL

-- Find parent relations
SELECT e.typed_id, e.version, e.tags, 'relation' AS type
FROM element e, target_node tn
WHERE e.typed_id >= 2305843009213693952
  AND e.latest
  AND e.members && ARRAY[tn.typed_id]
```

**With Index Hint**:
```sql
/*+ BitmapScan(element element_members_idx) */
SELECT DISTINCT ON (typed_id) *
FROM element
WHERE members && ARRAY[$node_typed_id]::bigint[]
  AND typed_id >= 1152921504606846976
  AND latest
```

### Example 6: Area Query (Named Boundary)

**Overpass**:
```
[out:json];
area["name"="Berlin"]["boundary"="administrative"];
node["amenity"="cafe"](area);
out;
```

**SQL** (requires pre-computed area geometry):
```sql
-- Step 1: Get Berlin boundary polygon from element_spatial
WITH berlin_area AS (
    SELECT es.geom
    FROM element e
    INNER JOIN element_spatial es ON es.typed_id = e.typed_id
    WHERE e.typed_id >= 2305843009213693952  -- relations
      AND e.latest
      AND e.tags @> 'name=>Berlin'::hstore
      AND e.tags @> 'boundary=>administrative'::hstore
    LIMIT 1
)
-- Step 2: Find cafes within that polygon
SELECT e.typed_id, e.version, e.tags, e.point AS geom
FROM element e
CROSS JOIN berlin_area ba
WHERE e.typed_id <= 1152921504606846975
  AND e.latest
  AND ST_Intersects(e.point, ba.geom)
  AND e.tags @> 'amenity=>cafe'::hstore
```

### Example 7: Union of Multiple Tag Values

**Overpass**:
```
[out:json];
(
  node["amenity"="cafe"];
  node["amenity"="restaurant"];
  node["amenity"="bar"];
)(48.0,16.3,48.1,16.4);
out;
```

**SQL**:
```sql
SELECT typed_id, version, tags, point AS geom
FROM element
WHERE typed_id <= 1152921504606846975
  AND point && ST_MakeEnvelope(16.3, 48.0, 16.4, 48.1, 4326)
  AND latest
  AND (
    tags @> 'amenity=>cafe'::hstore
    OR tags @> 'amenity=>restaurant'::hstore
    OR tags @> 'amenity=>bar'::hstore
  )

-- Or more efficiently using regex:
SELECT typed_id, version, tags, point AS geom
FROM element
WHERE typed_id <= 1152921504606846975
  AND point && ST_MakeEnvelope(16.3, 48.0, 16.4, 48.1, 4326)
  AND latest
  AND tags ? 'amenity'
  AND (tags -> 'amenity') IN ('cafe', 'restaurant', 'bar')
```

### Example 8: Exclusion/Difference Query

**Overpass**:
```
[out:json];
(
  node["amenity"="restaurant"];
  - node["amenity"="restaurant"]["cuisine"="fast_food"];
)(48.0,16.3,48.1,16.4);
out;
```

**SQL**:
```sql
SELECT typed_id, version, tags, point AS geom
FROM element
WHERE typed_id <= 1152921504606846975
  AND point && ST_MakeEnvelope(16.3, 48.0, 16.4, 48.1, 4326)
  AND latest
  AND tags @> 'amenity=>restaurant'::hstore
  AND NOT (tags @> 'cuisine=>fast_food'::hstore)
```

### Example 9: Recursive Relation Query

**Overpass**:
```
[out:json];
relation["type"="route"]["route"="bus"]["ref"="100"];
>>;
out geom;
```

**SQL**:
```sql
WITH RECURSIVE
-- Step 1: Find the target relation
target_relation AS (
    SELECT typed_id, members
    FROM element
    WHERE typed_id >= 2305843009213693952
      AND latest
      AND tags @> 'type=>route'::hstore
      AND tags @> 'route=>bus'::hstore
      AND tags @> 'ref=>100'::hstore
    LIMIT 1
),
-- Step 2: Recursively get all members
all_members AS (
    -- Base case: direct members
    SELECT UNNEST(members) AS typed_id, 1 AS depth
    FROM target_relation

    UNION ALL

    -- Recursive case: members of member relations
    SELECT UNNEST(e.members) AS typed_id, am.depth + 1
    FROM all_members am
    INNER JOIN element e ON e.typed_id = am.typed_id AND e.latest
    WHERE am.typed_id >= 2305843009213693952  -- only recurse into relations
      AND am.depth < 15  -- prevent infinite loops
),
-- Step 3: Deduplicate
distinct_members AS (
    SELECT DISTINCT typed_id FROM all_members
)
-- Return all elements with geometry
SELECT e.typed_id, e.version, e.tags,
       COALESCE(es.geom, e.point) AS geom,
       CASE
           WHEN e.typed_id <= 1152921504606846975 THEN 'node'
           WHEN e.typed_id <= 2305843009213693951 THEN 'way'
           ELSE 'relation'
       END AS type
FROM distinct_members dm
INNER JOIN element e ON e.typed_id = dm.typed_id AND e.latest
LEFT JOIN element_spatial es ON es.typed_id = e.typed_id
```

---

## Edge Cases & Special Handling

### Tag Filter Edge Cases

#### Empty Tag Values
```sql
-- Overpass: [power~"^$"] (empty value)
WHERE tags -> 'power' = ''
```

#### Negation Semantics
```sql
-- Overpass: [amenity!=restaurant]
-- This matches: items WITHOUT amenity key OR items WITH amenity != restaurant
WHERE NOT (tags @> 'amenity=>restaurant'::hstore)

-- For "has amenity but not restaurant":
WHERE tags ? 'amenity' AND tags -> 'amenity' != 'restaurant'
```

#### Special Characters
```sql
-- Keys with colons (common in OSM)
WHERE tags @> 'addr:housenumber=>42'::hstore

-- Values with special characters
WHERE tags @> 'name=>O''Reilly'::hstore  -- Escape single quote
```

### Unicode & Case Sensitivity

```sql
-- Default: case-sensitive
WHERE tags -> 'name' = 'Berlin'

-- Case-insensitive (Overpass ,i flag)
WHERE LOWER(tags -> 'name') = LOWER('Berlin')
-- Or with regex:
WHERE tags -> 'name' ~* '^berlin$'
```

### Recursion Depth Limits

Always limit recursion to prevent infinite loops:

```sql
WITH RECURSIVE members AS (
    SELECT typed_id, 1 AS depth FROM seed
    UNION ALL
    SELECT UNNEST(e.members), depth + 1
    FROM members m
    JOIN element e ON e.typed_id = m.typed_id
    WHERE depth < 15  -- CRITICAL: prevent infinite loops
)
```

### Empty Result Handling

```sql
-- Return empty array, not NULL
SELECT COALESCE(
    (SELECT array_agg(typed_id) FROM results),
    ARRAY[]::bigint[]
) AS typed_ids
```

### Query Timeout

```sql
-- Set statement timeout for long-running queries
SET statement_timeout = '30s';

-- Or per-query:
SELECT /*+ set(statement_timeout '30s') */ * FROM ...
```

---

## Architecture Recommendations

### Transpiler Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      Overpass QL Parser                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Lexer   │→ │  Parser  │→ │   AST    │→ │  Validator   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      SQL Generator                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Type Router  │→ │ Filter Gen   │→ │ Query Composer       │ │
│  │ (node/way/   │  │ (tag/spatial │  │ (CTEs, JOINs,        │ │
│  │  relation)   │  │  /member)    │  │  UNIONs, recursion)  │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Query Executor                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Freshness    │→ │ Connection   │→ │ Result               │ │
│  │ Strategy     │  │ Manager      │  │ Formatter            │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### AST Node Types

```python
@dataclass
class OverpassQuery:
    settings: QuerySettings
    statements: list[Statement]
    output: OutputSpec

@dataclass
class QuerySettings:
    timeout: int = 180
    maxsize: int = 536870912
    out_format: str = 'xml'
    bbox: tuple[float, float, float, float] | None = None

@dataclass
class ElementQuery:
    element_type: Literal['node', 'way', 'relation', 'nwr', 'area']
    filters: list[Filter]
    spatial: SpatialFilter | None

@dataclass
class TagFilter:
    key: str
    operator: Literal['exists', 'not_exists', 'eq', 'neq', 'regex', 'regex_i']
    value: str | None

@dataclass
class BboxFilter:
    south: float
    west: float
    north: float
    east: float

@dataclass
class AroundFilter:
    radius_meters: float
    center: tuple[float, float] | None  # lat, lon
    reference_set: str | None  # named set to measure from

@dataclass
class RecurseOp:
    direction: Literal['down', 'down_rec', 'up', 'up_rec']
```

### SQL Generation Patterns

```python
class SQLGenerator:
    def generate(self, ast: OverpassQuery) -> ComposedSQL:
        # 1. Analyze query to determine required tables
        sources = self._analyze_sources(ast)

        # 2. Generate CTEs for named sets
        ctes = self._generate_ctes(ast)

        # 3. Generate per-type queries
        type_queries = []
        for elem_type in sources.element_types:
            type_queries.append(self._generate_type_query(elem_type, ast))

        # 4. Combine with UNION ALL
        main_query = SQL(' UNION ALL ').join(type_queries)

        # 5. Apply output limits and ordering
        return self._wrap_with_output(main_query, ast.output)

    def _generate_type_query(self, elem_type: str, ast: OverpassQuery) -> SQL:
        conditions = []
        params = []

        # Type filter
        if elem_type == 'node':
            conditions.append(SQL('typed_id <= 1152921504606846975'))
        elif elem_type == 'way':
            conditions.append(SQL('typed_id BETWEEN 1152921504606846976 AND 2305843009213693951'))
        elif elem_type == 'relation':
            conditions.append(SQL('typed_id >= 2305843009213693952'))

        # Always filter for latest
        conditions.append(SQL('latest'))

        # Tag filters
        for tag_filter in ast.tag_filters:
            cond, param = self._generate_tag_condition(tag_filter)
            conditions.append(cond)
            params.extend(param)

        # Spatial filters
        if ast.spatial:
            cond, param = self._generate_spatial_condition(ast.spatial, elem_type)
            conditions.append(cond)
            params.extend(param)

        return SQL('''
            SELECT typed_id, version, tags, {geom}
            FROM {table}
            WHERE {conditions}
        ''').format(
            geom=SQL('point') if elem_type == 'node' else SQL('geom'),
            table=SQL('element') if elem_type == 'node' else SQL('element_spatial es INNER JOIN element e ON es.typed_id = e.typed_id AND e.latest'),
            conditions=SQL(' AND ').join(conditions),
        ), params
```

### Caching Strategy

```python
@dataclass
class QueryCache:
    """Cache for expensive query components."""

    # Cache area geometries by name (e.g., "Berlin", "London")
    area_cache: dict[str, BaseGeometry] = field(default_factory=dict)

    # Cache H3 cells for frequently queried bboxes
    h3_cache: dict[tuple[float, float, float, float], list[int]] = field(default_factory=dict)

    def get_area_geometry(self, area_name: str, area_tags: dict[str, str]) -> BaseGeometry:
        cache_key = f"{area_name}:{hash(frozenset(area_tags.items()))}"
        if cache_key not in self.area_cache:
            self.area_cache[cache_key] = self._fetch_area_geometry(area_name, area_tags)
        return self.area_cache[cache_key]
```

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1-2)

1. **Add tag index** (CRITICAL):
   ```sql
   CREATE INDEX CONCURRENTLY element_tags_gin_idx ON element
   USING gin (tags)
   WHERE tags IS NOT NULL AND visible AND latest;
   ```

2. **Create parser for Overpass QL subset**:
   - Tag filters: `[key]`, `[key=value]`, `[key~pattern]`
   - Bbox filters: `(s,w,n,e)`
   - Element types: `node`, `way`, `relation`, `nwr`
   - Output: `out`, `out geom`, `out center`

3. **Implement basic SQL generator**:
   - Single element type queries
   - Tag + bbox filtering
   - Output formatting

### Phase 2: Recursion & Members (Week 2-3)

1. **Implement recurse operators**:
   - `>` (down): Get members
   - `<` (up): Get parents using `members &&` operator

2. **Implement way geometry retrieval**:
   - Join with `element_spatial` for pre-computed geometries
   - Fallback to node coordinate assembly

3. **Handle mixed queries**:
   - `nwr` type queries
   - Union of multiple element types

### Phase 3: Advanced Features (Week 3-4)

1. **Area queries**:
   - Pre-compute common area geometries
   - Named area lookup (`area["name"="Berlin"]`)

2. **Around queries**:
   - `ST_DWithin` with geography type
   - Reference set radius queries

3. **Set operations**:
   - Named sets (temp tables or CTEs)
   - Intersection, difference

### Phase 4: Optimization & Testing (Week 4-5)

1. **Query optimization**:
   - EXPLAIN ANALYZE for all query patterns
   - Index hint integration
   - H3 spatial filtering

2. **Performance testing**:
   - Benchmark vs Overpass API
   - Load testing
   - Memory/timeout limits

3. **Documentation & API**:
   - Public API endpoint
   - Rate limiting
   - Error handling

### Success Metrics

| Metric | Target |
|--------|--------|
| Query coverage | 95% of common Overpass patterns |
| Response time (simple) | < 500ms |
| Response time (complex) | < 5s |
| Result accuracy | 99% match with Overpass API |
| Freshness | < 5min for ways/relations, real-time for nodes |

---

## Appendix A: Quick Reference

### Overpass → SQL Cheat Sheet

| Overpass | SQL |
|----------|-----|
| `node` | `WHERE typed_id <= 1152921504606846975` |
| `way` | `WHERE typed_id BETWEEN 1152921504606846976 AND 2305843009213693951` |
| `relation` | `WHERE typed_id >= 2305843009213693952` |
| `nwr` | `UNION ALL` of all three |
| `[key]` | `tags ? 'key'` |
| `[key=val]` | `tags @> 'key=>val'::hstore` |
| `[key~pat]` | `tags -> 'key' ~ 'pat'` |
| `(s,w,n,e)` | `geom && ST_MakeEnvelope(w,s,e,n,4326)` |
| `(around:r,lat,lon)` | `ST_DWithin(geom::geography, ST_Point(lon,lat)::geography, r)` |
| `>` | `WHERE typed_id = ANY(members)` |
| `<` | `WHERE members && ARRAY[...]` |
| `out geom` | Include geometry column |
| `out center` | `ST_Centroid(ST_Envelope(geom))` |

### Key Constants

```python
TYPED_ELEMENT_ID_NODE_MAX = 1152921504606846975      # (1 << 60) - 1
TYPED_ELEMENT_ID_WAY_MIN = 1152921504606846976       # 1 << 60
TYPED_ELEMENT_ID_WAY_MAX = 2305843009213693951       # (2 << 60) - 1
TYPED_ELEMENT_ID_RELATION_MIN = 2305843009213693952  # 2 << 60
```

### Index Hints

```sql
-- Force bitmap scan on members array
/*+ BitmapScan(element element_members_idx) */

-- Force bitmap scan including history
/*+ BitmapScan(element element_members_idx element_members_history_idx) */
```

---

## Appendix B: Files Reference

| File | Purpose |
|------|---------|
| `app/models/element.py` | TypedElementId encoding constants |
| `app/queries/element_query.py` | Core element query patterns |
| `app/queries/element_spatial_query.py` | Spatial query with H3 indexing |
| `app/services/element_spatial_service.py` | Geometry materialization |
| `app/migrations/0.sql` | Schema and index definitions |
| `app/lib/geo_utils.py` | H3 and coordinate utilities |
| `app/db.py` | Connection management, isolation levels |

---

*Document Version: 1.0*
*Last Updated: 2025-12-02*
*Author: Research compilation for Overpass SQL Transpiler implementation*
