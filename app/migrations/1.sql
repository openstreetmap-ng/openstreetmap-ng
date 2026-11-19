-- GPS tiles query line extents, rather than H3 cells containing recorded points.
CREATE INDEX trace_segments_bbox_idx ON trace USING gist (segments);

CREATE INDEX trace_segments_shifted_bbox_idx ON trace USING gist (ST_ShiftLongitude(segments));
