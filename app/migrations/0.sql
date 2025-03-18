CREATE
    EXTENSION hstore;
CREATE
    EXTENSION h3;
CREATE
    EXTENSION h3_postgis CASCADE; -- Also creates postgis extension

CREATE FUNCTION h3_points_to_cells_range(
    geom geometry,
    resolution integer
) RETURNS h3index[] AS
$$
WITH RECURSIVE hierarchy(cell, res) AS (
    -- Base case: cells at finest resolution
    SELECT public.h3_lat_lng_to_cell((dp).geom, resolution), resolution
    FROM public.ST_DumpPoints(geom) AS dp
    GROUP BY 1
    UNION ALL
    -- Recursive case: parent cells at coarser resolutions
    SELECT public.h3_cell_to_parent(cell), res - 1
    FROM hierarchy
    WHERE res > 0
    GROUP BY 1, 2)
SELECT array_agg(cell)
FROM hierarchy
$$ LANGUAGE sql IMMUTABLE
                STRICT
                PARALLEL SAFE;

CREATE TYPE avatar_type AS ENUM ('gravatar', 'custom');
CREATE TYPE editor AS ENUM ('id', 'rapid', 'remote');
CREATE TYPE user_role AS ENUM ('moderator', 'administrator');
CREATE TABLE "user"
(
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email                 text        NOT NULL,
    email_verified        boolean     NOT NULL,
    display_name          text        NOT NULL,
    password_pb           bytea       NOT NULL,
    password_updated_at   timestamptz NOT NULL DEFAULT statement_timestamp(),
    roles                 user_role[] NOT NULL DEFAULT '{}',
    language              text        NOT NULL,
    timezone              text,
    home_point            geometry(Point, 4326),
    editor                editor,
    activity_tracking     boolean     NOT NULL,
    crash_reporting       boolean     NOT NULL,
    avatar_type           avatar_type,
    avatar_id             text,
    background_id         text,
    description           text        NOT NULL DEFAULT '',
    description_rich_hash bytea,
    created_ip            inet        NOT NULL,
    created_at            timestamptz NOT NULL DEFAULT statement_timestamp(),
    scheduled_delete_at   timestamptz
);
CREATE UNIQUE INDEX user_email_idx ON "user" (email);
CREATE UNIQUE INDEX user_display_name_idx ON "user" (display_name);
CREATE INDEX user_pending_idx ON "user" (created_at) WHERE NOT email_verified;
CREATE INDEX user_deleted_idx ON "user" (id) WHERE email LIKE '%@deleted.invalid'; -- DELETED_USER_EMAIL_SUFFIX

CREATE TYPE auth_provider AS ENUM ('google', 'facebook', 'microsoft', 'github', 'wikimedia');
CREATE TABLE connected_account
(
    user_id    bigint        NOT NULL REFERENCES "user",
    provider   auth_provider NOT NULL,
    uid        text          NOT NULL,
    created_at timestamptz   NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY (user_id, provider)
);
CREATE UNIQUE INDEX connected_account_provider_uid_idx ON connected_account (provider, uid);

CREATE TYPE scope AS ENUM ('web_user', 'read_prefs', 'write_prefs', 'write_api', 'read_gpx', 'write_gpx', 'write_notes');
CREATE TABLE oauth2_application
(
    id                    bigint PRIMARY KEY,
    user_id               bigint REFERENCES "user",
    name                  text        NOT NULL,
    avatar_id             text,
    client_id             text        NOT NULL,
    client_secret_hashed  bytea,
    client_secret_preview text,
    confidential          boolean     NOT NULL DEFAULT false,
    redirect_uris         text[]      NOT NULL DEFAULT '{}',
    scopes                scope[]     NOT NULL DEFAULT '{}',
    created_at            timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at            timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE UNIQUE INDEX oauth2_application_client_id_idx ON oauth2_application (client_id);
CREATE INDEX oauth2_application_user_idx ON oauth2_application (user_id);

CREATE TYPE oauth2_code_challenge_method AS ENUM ('plain', 'S256');
CREATE TABLE oauth2_token
(
    id                    bigint PRIMARY KEY,
    user_id               bigint      NOT NULL REFERENCES "user",
    application_id        bigint      NOT NULL REFERENCES oauth2_application,
    name                  text,
    token_hashed          bytea,
    token_preview         text,
    redirect_uri          text,
    scopes                scope[]     NOT NULL,
    code_challenge_method oauth2_code_challenge_method,
    code_challenge        text,
    created_at            timestamptz NOT NULL DEFAULT statement_timestamp(),
    authorized_at         timestamptz
);
CREATE UNIQUE INDEX oauth2_token_hashed_idx ON oauth2_token (token_hashed) WHERE token_hashed IS NOT NULL;
CREATE INDEX oauth2_token_user_app_authorized_idx ON oauth2_token (user_id, application_id, id, (authorized_at IS NOT NULL));

CREATE TABLE changeset
(
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      bigint REFERENCES "user",
    tags         hstore      NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at   timestamptz NOT NULL DEFAULT statement_timestamp(),
    closed_at    timestamptz,
    size         integer     NOT NULL DEFAULT 0,
    union_bounds geometry(Polygon, 4326)
);
CREATE INDEX changeset_user_idx ON changeset (user_id, id) WHERE user_id IS NOT NULL;
CREATE INDEX changeset_user_created_at_idx ON changeset (user_id, created_at) WHERE user_id IS NOT NULL;
CREATE INDEX changeset_created_at_idx ON changeset (created_at);
CREATE INDEX changeset_closed_at_idx ON changeset (closed_at, (size = 0)) WHERE closed_at IS NOT NULL;
CREATE INDEX changeset_open_idx ON changeset (updated_at) WHERE closed_at IS NULL;
CREATE INDEX changeset_union_bounds_idx ON changeset USING gist (union_bounds) WHERE union_bounds IS NOT NULL;

CREATE TABLE changeset_bounds
(
    changeset_id bigint                  NOT NULL REFERENCES changeset ON DELETE CASCADE,
    bounds       geometry(Polygon, 4326) NOT NULL
);
CREATE INDEX changeset_bounds_id_idx ON changeset_bounds (changeset_id);
CREATE INDEX changeset_bounds_bounds_idx ON changeset_bounds USING gist (bounds) INCLUDE (changeset_id);

CREATE TABLE changeset_comment
(
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        bigint      NOT NULL REFERENCES "user",
    changeset_id   bigint      NOT NULL REFERENCES changeset ON DELETE CASCADE,
    body           text        NOT NULL,
    body_rich_hash bytea,
    created_at     timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX changeset_comment_changeset_id_idx ON changeset_comment (changeset_id, id);

CREATE TABLE element
(
    sequence_id      bigint PRIMARY KEY,
    next_sequence_id bigint REFERENCES element,
    changeset_id     bigint      NOT NULL REFERENCES changeset,
    typed_id         bigint      NOT NULL,
    version          bigint      NOT NULL,
    visible          boolean     NOT NULL,
    tags             hstore,
    point            geometry(Point, 4326),
    members          bigint[],
    members_roles    text[],
    created_at       timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX element_changeset_idx ON element (changeset_id);
CREATE UNIQUE INDEX element_version_idx ON element (typed_id, version);
CREATE INDEX element_current_idx ON element (typed_id, next_sequence_id, sequence_id);
CREATE INDEX element_node_point_idx ON element (point) WHERE point IS NOT NULL AND next_sequence_id IS NULL;
CREATE INDEX element_members_idx ON element USING gin (members) WHERE cardinality(members) > 0;

CREATE TABLE diary
(
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        bigint      NOT NULL REFERENCES "user",
    title          text        NOT NULL,
    body           text        NOT NULL,
    body_rich_hash bytea,
    language       text        NOT NULL,
    point          geometry(Point, 4326),
    created_at     timestamptz NOT NULL DEFAULT statement_timestamp(),
    updated_at     timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX diary_user_id_idx ON diary (user_id, id);
CREATE INDEX diary_language_idx ON diary (language, id);

CREATE TABLE diary_comment
(
    id             bigint PRIMARY KEY,
    user_id        bigint      NOT NULL REFERENCES "user",
    diary_id       bigint      NOT NULL REFERENCES diary ON DELETE CASCADE,
    body           text        NOT NULL,
    body_rich_hash bytea,
    created_at     timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX diary_comment_idx ON diary_comment (diary_id, id);

CREATE TYPE mail_source AS ENUM ('message', 'diary_comment');
CREATE TABLE mail
(
    id                 bigint PRIMARY KEY,
    source             mail_source,
    from_user_id       bigint REFERENCES "user",
    to_user_id         bigint      NOT NULL REFERENCES "user",
    subject            text        NOT NULL,
    body               text        NOT NULL,
    ref                text,
    priority           smallint    NOT NULL,
    processing_counter smallint    NOT NULL DEFAULT 0,
    created_at         timestamptz NOT NULL DEFAULT statement_timestamp(),
    scheduled_at       timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX mail_scheduled_at_idx ON mail (scheduled_at);

CREATE TABLE message
(
    id               bigint PRIMARY KEY,
    from_user_id     bigint      NOT NULL REFERENCES "user",
    from_user_hidden boolean     NOT NULL DEFAULT false,
    to_user_id       bigint      NOT NULL REFERENCES "user",
    to_user_hidden   boolean     NOT NULL DEFAULT false,
    read             boolean     NOT NULL DEFAULT false,
    subject          text        NOT NULL,
    body             text        NOT NULL,
    body_rich_hash   bytea,
    created_at       timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX message_from_inbox ON message (from_user_id, id) WHERE NOT from_user_hidden;
CREATE INDEX message_to_inbox ON message (read, to_user_id, id) WHERE NOT to_user_hidden;

CREATE TABLE note
(
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    point      geometry(Point, 4326) NOT NULL,
    created_at timestamptz           NOT NULL DEFAULT statement_timestamp(),
    updated_at timestamptz           NOT NULL DEFAULT statement_timestamp(),
    closed_at  timestamptz,
    hidden_at  timestamptz
);
CREATE INDEX note_point_idx ON note USING gist (point);
CREATE INDEX note_created_at_idx ON note (created_at);
CREATE INDEX note_updated_at_idx ON note (updated_at);
CREATE INDEX note_closed_at_idx ON note (closed_at);
CREATE INDEX note_hidden_at_idx ON note (hidden_at);

CREATE TYPE note_event AS ENUM ('opened', 'closed', 'reopened', 'commented', 'hidden');
CREATE TABLE note_comment
(
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        bigint REFERENCES "user",
    user_ip        inet,
    note_id        bigint      NOT NULL REFERENCES note ON DELETE CASCADE,
    event          note_event  NOT NULL,
    body           text        NOT NULL,
    body_rich_hash bytea,
    created_at     timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX note_comment_note_id_idx ON note_comment (note_id, id);
CREATE INDEX note_comment_event_user_id_idx ON note_comment (event, user_id, id);
CREATE INDEX note_comment_body_idx ON note_comment USING gin (to_tsvector('simple', body));

CREATE TYPE trace_visibility AS ENUM ('identifiable', 'public', 'trackable', 'private');
CREATE TABLE trace
(
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       bigint                          NOT NULL REFERENCES "user",
    name          text                            NOT NULL,
    description   text                            NOT NULL,
    tags          text[]                          NOT NULL,
    visibility    trace_visibility                NOT NULL,
    file_id       text                            NOT NULL,
    size          integer                         NOT NULL,
    segments      geometry(MultiLineString, 4326) NOT NULL,
    capture_times timestamptz[],
    created_at    timestamptz                     NOT NULL DEFAULT statement_timestamp(),
    updated_at    timestamptz                     NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX trace_visibility_user_id_idx ON trace (visibility, user_id, id);
CREATE INDEX trace_tags_idx ON trace USING gin (tags);
CREATE INDEX trace_segments_idx ON trace USING gin (h3_points_to_cells_range(segments, 11));

CREATE TABLE user_pref
(
    user_id bigint NOT NULL REFERENCES "user",
    app_id  bigint REFERENCES oauth2_application,
    key     text   NOT NULL,
    value   text   NOT NULL,
    PRIMARY KEY (user_id, app_id, key)
);

CREATE TYPE user_subscription_target AS ENUM ('changeset', 'diary', 'note', 'user');
CREATE TABLE user_subscription
(
    user_id   bigint                   NOT NULL REFERENCES "user",
    target    user_subscription_target NOT NULL,
    target_id bigint                   NOT NULL,
    PRIMARY KEY (target, target_id, user_id)
);

CREATE TYPE user_token_type AS ENUM ('account_confirm', 'email_change', 'email_reply', 'reset_password');
CREATE TABLE user_token
(
    id                      bigint PRIMARY KEY,
    type                    user_token_type NOT NULL,
    user_id                 bigint          NOT NULL REFERENCES "user",
    user_email_hashed       bytea           NOT NULL,
    token_hashed            bytea           NOT NULL,
    created_at              timestamptz     NOT NULL DEFAULT statement_timestamp(),
    email_change_new        text,
    email_reply_source      mail_source,
    email_reply_to_user_id  bigint REFERENCES "user",
    email_reply_usage_count smallint
);

CREATE TABLE files
(
    context    text        NOT NULL,
    key        text        NOT NULL,
    data       bytea       NOT NULL,
    metadata   hstore,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY (context, key)
);

CREATE UNLOGGED TABLE rate_limit
(
    key        text PRIMARY KEY,
    usage      real        NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
);
CREATE INDEX rate_limit_updated_at_idx ON rate_limit (updated_at);
