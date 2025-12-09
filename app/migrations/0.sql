CREATE EXTENSION IF NOT EXISTS btree_gin;

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE EXTENSION IF NOT EXISTS hstore;

CREATE EXTENSION IF NOT EXISTS h3;

CREATE EXTENSION IF NOT EXISTS h3_postgis CASCADE;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE OR REPLACE FUNCTION h3_points_to_cells_range (geom geometry, resolution integer) RETURNS h3index[] AS $$
WITH RECURSIVE hierarchy(cell, res) AS MATERIALIZED (
    -- Base case: cells at finest resolution
    SELECT h3_latlng_to_cell((dp).geom, resolution), resolution
    FROM ST_DumpPoints(geom) AS dp
    GROUP BY 1
    UNION ALL
    -- Recursive case: parent cells at coarser resolutions
    SELECT h3_cell_to_parent(cell), res - 1
    FROM hierarchy
    WHERE res > 0
    GROUP BY 1, 2)
SELECT array_agg(cell)
FROM hierarchy
$$ LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET
    search_path = public;

CREATE OR REPLACE FUNCTION h3_geometry_to_cells_range (geom geometry, resolution integer) RETURNS h3index[] AS $$
WITH RECURSIVE hierarchy(cell, res) AS MATERIALIZED (
    -- Base case: cells at finest resolution
    SELECT h3_cell, resolution
    FROM h3_polygon_to_cells_experimental(geom, resolution, 'overlapping') AS t(h3_cell)
    UNION ALL
    -- Recursive case: parent cells at coarser resolutions
    SELECT h3_cell_to_parent(cell), res - 1
    FROM hierarchy
    WHERE res > 0
    GROUP BY 1, 2)
SELECT array_agg(cell)
FROM hierarchy
$$ LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET
    search_path = public;

CREATE OR REPLACE FUNCTION h3_geometry_to_compact_cells (geom geometry, resolution integer) RETURNS h3index[] AS $$
WITH extent AS (
    SELECT
        ST_NumGeometries(geom) > 1 AS is_multi,
        GREATEST(
            ST_XMax(geom) - ST_XMin(geom),
            ST_YMax(geom) - ST_YMin(geom)
        ) AS size
),
parts AS (
    SELECT
        (d).geom AS g,
        ST_Dimension((d).geom) AS dim,
        GREATEST(
            3,
            LEAST(
                resolution,
                9 - FLOOR(LN(GREATEST(
                    CASE WHEN (SELECT is_multi FROM extent)
                        THEN (SELECT size FROM extent)
                        ELSE GREATEST(
                            ST_XMax((d).geom) - ST_XMin((d).geom),
                            ST_YMax((d).geom) - ST_YMin((d).geom)
                        )
                    END,
                    0.18
                )) / LN(2))::int
            )
        ) AS res
    FROM extent, ST_Dump(geom) d
)
SELECT array_agg(cell)
FROM h3_compact_cells(ARRAY(
    SELECT DISTINCT h3_cell
    FROM (
        SELECT h3_polygon_to_cells_experimental(g, res, 'overlapping') AS h3_cell
        FROM parts
        WHERE dim = 2

        UNION ALL

        SELECT h3_grid_path_cells(
            h3_latlng_to_cell(ST_PointN(g, i), res),
            h3_latlng_to_cell(ST_PointN(g, i + 1), res)
        ) AS h3_cell
        FROM parts,
             generate_series(1, ST_NPoints(g) - 1) i
        WHERE dim = 1

        UNION ALL

        SELECT h3_latlng_to_cell(g, res) AS h3_cell
        FROM parts
        WHERE dim = 0
    ) cells
)) AS cell
$$ LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET
    search_path = public;

CREATE TYPE avatar_type AS enum('gravatar', 'custom');

CREATE TYPE editor AS enum('id', 'rapid', 'remote');

CREATE TYPE user_role AS enum('moderator', 'administrator');

CREATE TABLE "user" (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL,
    email_verified boolean NOT NULL,
    display_name text NOT NULL,
    roles user_role[] NOT NULL DEFAULT '{}',
    language text NOT NULL,
    timezone text,
    home_point geometry (Point, 4326),
    editor editor,
    activity_tracking boolean NOT NULL,
    crash_reporting boolean NOT NULL,
    avatar_type avatar_type,
    avatar_id text,
    background_id text,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    scheduled_delete_at timestamptz
);

CREATE UNIQUE INDEX user_email_idx ON "user" (email);

CREATE INDEX user_email_pattern_idx ON "user" USING gin (email gin_trgm_ops);

CREATE UNIQUE INDEX user_display_name_idx ON "user" (display_name);

CREATE INDEX user_display_name_pattern_idx ON "user" USING gin (display_name gin_trgm_ops);

CREATE INDEX user_pending_idx ON "user" (created_at)
WITH
    (fillfactor = 100)
WHERE
    NOT email_verified;

CREATE INDEX user_deleted_idx ON "user" (id)
WHERE
    -- DELETED_USER_EMAIL_SUFFIX
    email LIKE '%@deleted.invalid';

CREATE INDEX user_roles_idx ON "user" USING gin (roles);

CREATE TABLE user_password (
    user_id bigint PRIMARY KEY REFERENCES "user" ON DELETE CASCADE,
    password_pb bytea NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE user_passkey (
    credential_id bytea NOT NULL PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES "user" ON DELETE CASCADE,
    aaguid uuid NOT NULL,
    name text,
    algorithm smallint NOT NULL,
    public_key bytea NOT NULL,
    sign_count bigint NOT NULL DEFAULT 0,
    transports TEXT[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    last_used_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX user_passkey_user_id_idx ON user_passkey (user_id, created_at);

CREATE UNLOGGED TABLE user_passkey_challenge (
    challenge bytea PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE user_totp (
    user_id bigint PRIMARY KEY REFERENCES "user" ON DELETE CASCADE,
    secret_encrypted bytea NOT NULL,
    digits smallint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE user_totp_used_code (
    user_id bigint NOT NULL REFERENCES "user" ON DELETE CASCADE,
    code integer NOT NULL,
    time_window bigint NOT NULL,
    PRIMARY KEY (user_id, time_window, code)
);

CREATE TABLE user_recovery_code (
    user_id bigint PRIMARY KEY REFERENCES "user" ON DELETE CASCADE,
    codes_hashed bytea[] NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TYPE auth_provider AS enum(
    'google',
    'facebook',
    'microsoft',
    'github',
    'wikimedia'
);

CREATE TABLE connected_account (
    user_id bigint NOT NULL REFERENCES "user",
    provider auth_provider NOT NULL,
    uid text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY (user_id, provider)
);

CREATE UNIQUE INDEX connected_account_provider_uid_idx ON connected_account (provider, uid);

CREATE TYPE scope AS enum(
    'web_user',
    'read_prefs',
    'write_prefs',
    'write_api',
    'read_gpx',
    'write_gpx',
    'write_notes'
);

CREATE TABLE oauth2_application (
    id bigint PRIMARY KEY,
    user_id bigint REFERENCES "user",
    name text NOT NULL,
    avatar_id text,
    client_id text NOT NULL,
    client_secret_hashed bytea,
    client_secret_preview text,
    confidential boolean NOT NULL DEFAULT FALSE,
    redirect_uris TEXT[] NOT NULL DEFAULT '{}',
    scopes scope[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE UNIQUE INDEX oauth2_application_client_id_idx ON oauth2_application (client_id);

CREATE INDEX oauth2_application_created_at_idx ON oauth2_application (created_at)
WITH
    (fillfactor = 100);

CREATE INDEX oauth2_application_user_created_at_idx ON oauth2_application (user_id, created_at)
WHERE
    user_id IS NOT NULL;

CREATE INDEX oauth2_application_name_pattern_idx ON oauth2_application USING gin (name gin_trgm_ops);

CREATE TYPE oauth2_code_challenge_method AS enum('plain', 'S256');

CREATE TABLE oauth2_token (
    id bigint PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES "user",
    application_id bigint NOT NULL REFERENCES oauth2_application,
    unlisted boolean NOT NULL DEFAULT FALSE,
    name text,
    token_hashed bytea,
    token_preview text,
    redirect_uri text,
    scopes scope[] NOT NULL,
    code_challenge_method oauth2_code_challenge_method,
    code_challenge text,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    authorized_at timestamptz
);

CREATE UNIQUE INDEX oauth2_token_hashed_idx ON oauth2_token (token_hashed)
WHERE
    token_hashed IS NOT NULL;

CREATE INDEX oauth2_token_app_user_idx ON oauth2_token (application_id, user_id) INCLUDE (authorized_at);

CREATE INDEX oauth2_token_user_app_idx ON oauth2_token (user_id, application_id, id) INCLUDE (authorized_at);

CREATE INDEX oauth2_token_stale_unauthorized_idx ON oauth2_token (created_at) INCLUDE (application_id)
WITH
    (fillfactor = 100)
WHERE
    authorized_at IS NULL;

CREATE TYPE audit_type AS enum(
    'add_connected_account',
    'add_passkey',
    'add_totp',
    'admin_task',
    'auth_api',
    'auth_fail',
    'auth_web',
    'authorize_app',
    'change_app_settings',
    'change_display_name',
    'change_email',
    'change_password',
    'change_roles',
    'close_changeset',
    'create_app',
    'create_changeset_comment',
    'create_changeset',
    'create_diary_comment',
    'create_diary',
    'create_note_comment',
    'create_note',
    'create_pat',
    'create_trace',
    'delete_diary',
    'delete_prefs',
    'delete_trace',
    'edit_map',
    'generate_recovery_codes',
    'impersonate',
    'nsfw_image',
    'rate_limit',
    'remove_connected_account',
    'remove_passkey',
    'remove_totp',
    'request_change_email',
    'request_reset_password',
    'revoke_app_all_users',
    'revoke_app',
    'send_message',
    'update_changeset',
    'update_diary',
    'update_note_status',
    'update_prefs',
    'update_trace',
    'use_recovery_code',
    'view_admin_applications',
    'view_admin_users',
    'view_audit'
);

CREATE TABLE audit (
    type audit_type NOT NULL,
    ip inet NOT NULL,
    user_agent text,
    user_id bigint,
    target_user_id bigint,
    application_id bigint,
    token_id bigint,
    extra jsonb,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX audit_created_at_idx ON audit (created_at) INCLUDE (type)
WITH
    (fillfactor = 100);

CREATE INDEX audit_ip_created_at_idx ON audit (ip, created_at) INCLUDE (type, user_id, application_id);

CREATE INDEX audit_user_created_at_idx ON audit (user_id, created_at) INCLUDE (type, ip, application_id)
WHERE
    user_id IS NOT NULL;

CREATE INDEX audit_target_user_created_at_idx ON audit (target_user_id, created_at) INCLUDE (type)
WHERE
    target_user_id IS NOT NULL;

CREATE INDEX audit_application_created_at_idx ON audit (application_id, created_at) INCLUDE (type, ip)
WHERE
    application_id IS NOT NULL;

CREATE INDEX audit_token_created_at_idx ON audit (token_id, created_at)
WHERE
    token_id IS NOT NULL;

CREATE INDEX audit_discard_repeated_idx ON audit (
    type,
    ip,
    user_id,
    target_user_id,
    application_id,
    hashtext (extra::text),
    created_at
);

CREATE TABLE changeset (
    id bigint GENERATED ALWAYS AS IDENTITY,
    user_id bigint,
    tags hstore NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    closed_at timestamptz,
    size integer NOT NULL DEFAULT 0,
    num_create integer NOT NULL DEFAULT 0,
    num_modify integer NOT NULL DEFAULT 0,
    num_delete integer NOT NULL DEFAULT 0,
    union_bounds geometry (Polygon, 4326)
)
WITH
    (
        tsdb.hypertable,
        tsdb.partition_column = 'id',
        tsdb.chunk_interval = '5000000'
    );

CREATE INDEX changeset_user_idx ON changeset (user_id, id)
WHERE
    user_id IS NOT NULL;

CREATE INDEX changeset_user_created_at_idx ON changeset (user_id, created_at)
WHERE
    user_id IS NOT NULL;

CREATE INDEX changeset_created_at_idx ON changeset (created_at)
WITH
    (fillfactor = 100);

CREATE INDEX changeset_closed_at_idx ON changeset (closed_at)
WITH
    (fillfactor = 100)
WHERE
    closed_at IS NOT NULL;

CREATE INDEX changeset_closed_at_empty_idx ON changeset (closed_at)
WITH
    (fillfactor = 100)
WHERE
    closed_at IS NOT NULL
    AND size = 0;

CREATE INDEX changeset_open_idx ON changeset (updated_at) INCLUDE (created_at)
WHERE
    closed_at IS NULL;

CREATE INDEX changeset_union_bounds_idx ON changeset USING gist (union_bounds)
WHERE
    union_bounds IS NOT NULL;

CREATE TABLE changeset_bounds (
    changeset_id bigint NOT NULL,
    bounds geometry (Polygon, 4326) NOT NULL
)
WITH
    (
        tsdb.hypertable,
        tsdb.partition_column = 'changeset_id',
        tsdb.chunk_interval = '5000000'
    );

CREATE INDEX changeset_bounds_bounds_idx ON changeset_bounds USING gist (bounds) INCLUDE (changeset_id);

CREATE TABLE changeset_comment (
    id bigint GENERATED ALWAYS AS IDENTITY,
    user_id bigint NOT NULL,
    changeset_id bigint NOT NULL,
    body text NOT NULL,
    body_rich_hash bytea,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX changeset_comment_changeset_id_idx ON changeset_comment (changeset_id, id);

CREATE INDEX changeset_comment_user_id_idx ON changeset_comment (user_id, id);

CREATE TABLE element (
    sequence_id bigint,
    changeset_id bigint NOT NULL,
    typed_id bigint NOT NULL,
    version bigint NOT NULL,
    latest boolean NOT NULL,
    visible boolean NOT NULL,
    tags hstore,
    point geometry (Point, 4326),
    members BIGINT[],
    members_roles TEXT[],
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
)
WITH
    (
        tsdb.hypertable,
        tsdb.partition_column = 'typed_id',
        tsdb.chunk_interval = '1152921504606846976',
        tsdb.create_default_indexes = FALSE
    );

CREATE INDEX element_sequence_idx ON element (sequence_id)
WITH
    (fillfactor = 100);

CREATE INDEX element_changeset_idx ON element (changeset_id);

CREATE INDEX element_id_version_idx ON element (typed_id, version);

CREATE INDEX element_id_sequence_idx ON element (typed_id, sequence_id);

CREATE INDEX element_point_idx ON element USING gist (point)
WHERE
    typed_id <= 1152921504606846975
    AND point IS NOT NULL
    AND latest;

CREATE INDEX element_members_idx ON element USING gin (members)
WITH
    (fastupdate = FALSE)
WHERE
    typed_id >= 1152921504606846976
    AND latest;

CREATE INDEX element_members_history_idx ON element USING gin (members)
WITH
    (fastupdate = FALSE)
WHERE
    typed_id >= 1152921504606846976
    AND NOT latest;

CREATE UNLOGGED TABLE element_spatial_staging (
    typed_id bigint NOT NULL,
    sequence_id bigint NOT NULL,
    updated_sequence_id bigint NOT NULL,
    depth smallint NOT NULL,
    geom geometry (Geometry, 4326)
);

CREATE INDEX element_spatial_staging_id_updated_idx ON element_spatial_staging (typed_id, updated_sequence_id DESC) INCLUDE (depth);

CREATE INDEX element_spatial_staging_depth_id_idx ON element_spatial_staging (depth, typed_id)
WHERE
    depth > 0;

CREATE UNLOGGED TABLE element_spatial_staging_batch (batch_id integer PRIMARY KEY, typed_ids BIGINT[]);

CREATE UNLOGGED TABLE element_spatial_pending_rels (typed_id bigint PRIMARY KEY);

CREATE TABLE element_spatial (
    typed_id bigint PRIMARY KEY,
    sequence_id bigint NOT NULL,
    geom geometry (Geometry, 4326) NOT NULL,
    bounds_area real GENERATED ALWAYS AS (ST_Area (ST_Envelope (geom))) STORED
);

CREATE INDEX element_spatial_geom_h3_idx ON element_spatial USING gin (h3_geometry_to_compact_cells (geom, 11))
WITH
    (fastupdate = FALSE);

CREATE TABLE element_spatial_watermark (
    id smallint PRIMARY KEY CHECK (id = 1),
    sequence_id bigint NOT NULL
);

CREATE TABLE user_follow (
    follower_id bigint NOT NULL REFERENCES "user",
    followee_id bigint NOT NULL REFERENCES "user",
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY (follower_id, followee_id)
);

CREATE INDEX user_follow_follower_id_created_at_idx ON user_follow (follower_id, created_at);

CREATE INDEX user_follow_followee_id_created_at_idx ON user_follow (followee_id, created_at);

CREATE TABLE diary (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES "user",
    title text NOT NULL,
    body text NOT NULL,
    body_rich_hash bytea,
    body_image_proxy_ids BIGINT[],
    language text NOT NULL,
    point geometry (Point, 4326),
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX diary_user_id_idx ON diary (user_id, id);

CREATE INDEX diary_language_idx ON diary (language, id);

CREATE INDEX diary_body_image_proxy_ids_idx ON diary USING gin (body_image_proxy_ids)
WITH
    (fastupdate = FALSE);

CREATE TABLE diary_comment (
    id bigint PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES "user",
    diary_id bigint NOT NULL REFERENCES diary ON DELETE CASCADE,
    body text NOT NULL,
    body_rich_hash bytea,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX diary_comment_idx ON diary_comment (diary_id, id);

CREATE TABLE image_proxy (
    id bigint PRIMARY KEY,
    url text NOT NULL,
    width smallint,
    height smallint,
    thumbnail text,
    thumbnail_updated_at timestamptz
);

CREATE UNIQUE INDEX image_proxy_url_idx ON image_proxy (url);

CREATE TYPE mail_source AS enum('message', 'diary_comment');

CREATE TABLE mail (
    id bigint PRIMARY KEY,
    source mail_source,
    from_user_id bigint REFERENCES "user",
    to_user_id bigint NOT NULL REFERENCES "user",
    subject text NOT NULL,
    body text NOT NULL,
    ref text,
    priority smallint NOT NULL,
    processing_counter smallint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    scheduled_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX mail_scheduled_at_idx ON mail (scheduled_at)
WITH
    (fillfactor = 100);

CREATE TABLE message (
    id bigint PRIMARY KEY,
    from_user_id bigint NOT NULL REFERENCES "user",
    from_user_hidden boolean NOT NULL DEFAULT FALSE,
    subject text NOT NULL,
    body text NOT NULL,
    body_rich_hash bytea,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX message_from_inbox ON message (from_user_id, id)
WHERE
    NOT from_user_hidden;

CREATE TABLE message_recipient (
    message_id bigint NOT NULL REFERENCES message ON DELETE CASCADE,
    user_id bigint NOT NULL REFERENCES "user",
    hidden boolean NOT NULL DEFAULT FALSE,
    read boolean NOT NULL DEFAULT FALSE,
    PRIMARY KEY (message_id, user_id)
);

CREATE INDEX message_recipient_inbox ON message_recipient (read, user_id, message_id)
WHERE
    NOT hidden;

CREATE TABLE note (
    id bigint GENERATED ALWAYS AS IDENTITY,
    point geometry (Point, 4326) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    closed_at timestamptz,
    hidden_at timestamptz
)
WITH
    (
        tsdb.hypertable,
        tsdb.partition_column = 'id',
        tsdb.chunk_interval = '1000000'
    );

CREATE INDEX note_point_idx ON note USING gist (point, created_at, updated_at, closed_at);

CREATE INDEX note_created_at_idx ON note (created_at)
WITH
    (fillfactor = 100);

CREATE INDEX note_updated_at_idx ON note (updated_at);

CREATE INDEX note_closed_at_idx ON note (closed_at)
WITH
    (fillfactor = 100);

CREATE INDEX note_hidden_idx ON note (hidden_at)
WITH
    (fillfactor = 100)
WHERE
    hidden_at IS NOT NULL;

CREATE TYPE note_event AS enum(
    'opened',
    'closed',
    'reopened',
    'commented',
    'hidden'
);

CREATE TABLE note_comment (
    id bigint GENERATED ALWAYS AS IDENTITY,
    user_id bigint,
    user_ip inet,
    note_id bigint NOT NULL,
    event note_event NOT NULL,
    body text NOT NULL,
    body_rich_hash bytea,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX note_comment_id_idx ON note_comment (id)
WITH
    (fillfactor = 100);

CREATE INDEX note_comment_note_id_idx ON note_comment (note_id, id);

CREATE INDEX note_comment_event_user_id_idx ON note_comment (event, user_id, note_id);

CREATE INDEX note_comment_body_idx ON note_comment USING gin (to_tsvector('simple', body))
WITH
    (fastupdate = FALSE);

CREATE TYPE report_type AS enum('anonymous_note', 'user');

CREATE TABLE report (
    id bigint PRIMARY KEY,
    type report_type NOT NULL,
    type_id bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    closed_at timestamptz
);

CREATE UNIQUE INDEX idx_report_type_id ON report (type, type_id);

CREATE INDEX idx_report_open_updated_at ON report (updated_at) INCLUDE (id)
WITH
    (fillfactor = 100)
WHERE
    closed_at IS NULL;

CREATE INDEX idx_report_closed_updated_at ON report (updated_at)
WITH
    (fillfactor = 100)
WHERE
    closed_at IS NOT NULL;

CREATE TYPE report_action AS enum(
    'comment',
    'close',
    'reopen',
    'generic',
    'user_account',
    'user_changeset',
    'user_diary',
    'user_message',
    'user_note',
    'user_oauth2_application',
    'user_profile',
    'user_trace'
);

CREATE TYPE report_category AS enum(
    'spam',
    'vandalism',
    'harassment',
    'privacy',
    'other'
);

CREATE TABLE report_comment (
    id bigint PRIMARY KEY,
    report_id bigint NOT NULL REFERENCES report,
    user_id bigint NOT NULL REFERENCES "user" ON DELETE CASCADE,
    action report_action NOT NULL,
    action_id bigint,
    body text NOT NULL,
    body_rich_hash bytea,
    category report_category,
    visible_to user_role NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX idx_report_comment_report_id_created_at ON report_comment (report_id, created_at) INCLUDE (action, visible_to);

CREATE INDEX idx_report_comment_action_id ON report_comment (action, action_id);

CREATE TYPE trace_visibility AS enum('identifiable', 'public', 'trackable', 'private');

CREATE TABLE trace (
    id bigint GENERATED ALWAYS AS IDENTITY,
    user_id bigint NOT NULL,
    name text NOT NULL,
    description text NOT NULL,
    tags TEXT[] NOT NULL,
    visibility trace_visibility NOT NULL,
    file_id text NOT NULL,
    size integer NOT NULL,
    -- TODO: MultiLineStringZM when shapely supports it
    -- https://github.com/shapely/shapely/issues/1648
    segments geometry (MultiLineString, 4326) NOT NULL,
    elevations REAL[],
    capture_times TIMESTAMPTZ[],
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
)
WITH
    (
        tsdb.hypertable,
        tsdb.partition_column = 'id',
        tsdb.chunk_interval = '1000000'
    );

CREATE INDEX trace_visibility_user_id_idx ON trace (visibility, user_id, id);

CREATE INDEX trace_tags_idx ON trace USING gin (tags)
WITH
    (fastupdate = FALSE);

CREATE INDEX trace_segments_idx ON trace USING gin (h3_points_to_cells_range (segments, 11))
WITH
    (fastupdate = FALSE);

CREATE TABLE user_pref (
    user_id bigint NOT NULL REFERENCES "user",
    app_id bigint REFERENCES oauth2_application,
    key text NOT NULL,
    value text NOT NULL,
    PRIMARY KEY (user_id, app_id, key)
);

CREATE TYPE user_social_type AS enum(
    'bluesky',
    'discord',
    'facebook',
    'github',
    'instagram',
    'line',
    'linkedin',
    'mastodon',
    'medium',
    'pinterest',
    'reddit',
    'signal',
    'sina-weibo',
    'snapchat',
    'spotify',
    'steam',
    'telegram',
    'threads',
    'tiktok',
    'twitch',
    'wechat',
    'whatsapp',
    'wordpress',
    'x',
    'youtube',
    'other'
);

CREATE TYPE user_social AS (service user_social_type, value text);

CREATE TABLE user_profile (
    user_id bigint PRIMARY KEY REFERENCES "user" ON DELETE CASCADE,
    description text,
    description_rich_hash bytea,
    socials user_social[] NOT NULL DEFAULT '{}'
);

CREATE TYPE user_subscription_target AS enum('changeset', 'diary', 'note', 'user');

CREATE TABLE user_subscription (
    user_id bigint NOT NULL REFERENCES "user",
    target user_subscription_target NOT NULL,
    target_id bigint NOT NULL,
    PRIMARY KEY (target, target_id, user_id)
);

CREATE TYPE user_token_type AS enum(
    'account_confirm',
    'email_change',
    'email_reply',
    'reset_password'
);

CREATE TABLE user_token (
    id bigint PRIMARY KEY,
    type user_token_type NOT NULL,
    user_id bigint NOT NULL REFERENCES "user",
    user_email_hashed bytea NOT NULL,
    token_hashed bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    email_change_new text,
    email_reply_source mail_source,
    email_reply_to_user_id bigint REFERENCES "user",
    email_reply_usage_count smallint
);

CREATE INDEX user_token_user_idx ON user_token (user_id);

CREATE INDEX user_token_type_created_at_idx ON user_token (type, created_at);

CREATE TABLE file (
    context text NOT NULL,
    key text NOT NULL,
    data bytea NOT NULL,
    metadata hstore,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY (context, key)
);

CREATE TABLE admin_task (
    id text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    heartbeat_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX admin_task_heartbeat_at_idx ON admin_task (heartbeat_at);

CREATE UNLOGGED TABLE rate_limit (
    key text PRIMARY KEY,
    usage real NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
)
WITH
    (fillfactor = 90);

CREATE INDEX rate_limit_updated_at_idx ON rate_limit (updated_at)
WITH
    (fillfactor = 100);
