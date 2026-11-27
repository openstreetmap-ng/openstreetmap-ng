CREATE TABLE gps_trace_index (
    trace_id bigint PRIMARY KEY
);

CREATE TABLE gps_trace_pixel (
    trace_id bigint NOT NULL,
    x integer NOT NULL,
    y integer NOT NULL,
    PRIMARY KEY (trace_id, x, y)
);

CREATE TABLE gps_pixel (
    x integer NOT NULL,
    y integer NOT NULL,
    count bigint NOT NULL CHECK (count >= 0),
    PRIMARY KEY (x, y)
);

CREATE TABLE gps_pixel_overview (
    zoom smallint NOT NULL CHECK (zoom >= 0 AND zoom < 16),
    x integer NOT NULL,
    y integer NOT NULL,
    count bigint NOT NULL CHECK (count >= 0),
    PRIMARY KEY (zoom, x, y)
);

CREATE INDEX gps_pixel_overview_nonempty_idx ON gps_pixel_overview (zoom, x, y) WHERE count > 0;
