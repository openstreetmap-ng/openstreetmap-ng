from app.config import DELETED_USER_EMAIL_SUFFIX

_VERSIONS: tuple[str, ...] = (
    f"""
    CREATE EXTENSION hstore;
    CREATE EXTENSION h3;
    CREATE EXTENSION h3_postgis CASCADE;

    CREATE FUNCTION h3_points_to_cells(
        geom geometry,
        resolution integer
    ) RETURNS h3index[]
    LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE
    AS $$
    BEGIN
        RETURN ARRAY(
            SELECT DISTINCT h3_lat_lng_to_cell((dp).geom, resolution)
            FROM ST_DumpPoints(geom) AS dp
        );
    END;
    $$;

    CREATE TABLE "user" (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        email text NOT NULL,
        email_verified boolean NOT NULL,
        display_name text NOT NULL,
        password_pb bytea NOT NULL,
        roles text[] NOT NULL DEFAULT '{{}}',
        language text NOT NULL,
        timezone text,
        home_point geometry(Point, 4326),
        editor text,
        activity_tracking boolean NOT NULL,
        crash_reporting boolean NOT NULL,
        avatar_type text,
        avatar_id text,
        background_id text,
        description text NOT NULL DEFAULT '',
        description_rich_hash bytea,
        created_ip inet NOT NULL,
        created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        password_updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        scheduled_delete_at timestamptz
    );
    CREATE UNIQUE INDEX user_email_idx ON "user" (email);
    CREATE UNIQUE INDEX user_display_name_idx ON "user" (display_name);
    CREATE INDEX user_pending_idx ON "user" (created_at) WHERE email_verified = false;
    CREATE INDEX user_deleted_idx ON "user" (id) WHERE email LIKE '%{DELETED_USER_EMAIL_SUFFIX}';

    CREATE TABLE connected_account (
        user_id bigint NOT NULL REFERENCES "user",
        provider text NOT NULL,
        uid text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        PRIMARY KEY (user_id, provider)
    );
    CREATE UNIQUE INDEX connected_account_provider_uid_idx ON connected_account (provider, uid);

    CREATE TABLE oauth2_application (
        id bigint PRIMARY KEY,
        user_id bigint REFERENCES "user",
        name text NOT NULL,
        avatar_id text,
        client_id text NOT NULL,
        client_secret_hashed bytea,
        client_secret_preview text,
        confidential boolean NOT NULL DEFAULT false,
        redirect_uris text[] NOT NULL DEFAULT '{{}}',
        scopes text[] NOT NULL DEFAULT '{{}}',
        created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    );
    CREATE UNIQUE INDEX oauth2_application_client_id_idx ON oauth2_application (client_id);
    CREATE INDEX oauth2_application_user_idx ON oauth2_application (user_id);

    CREATE TABLE oauth2_token (
        id bigint PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES "user",
        application_id bigint NOT NULL REFERENCES oauth2_application,
        name text,
        token_hashed bytea,
        token_preview text,
        redirect_uri text,
        scopes text[] NOT NULL,
        code_challenge_method text,
        code_challenge text,
        created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        authorized_at timestamptz
    );
    CREATE UNIQUE INDEX oauth2_token_hashed_idx ON oauth2_token (token_hashed) WHERE token_hashed IS NOT NULL;
    CREATE INDEX oauth2_token_user_app_idx ON oauth2_token (user_id, application_id, authorized_at);

    CREATE TABLE user_pref (
        user_id bigint NOT NULL REFERENCES "user",
        app_id bigint REFERENCES oauth2_application,
        key text NOT NULL,
        value text NOT NULL,
        PRIMARY KEY (user_id, app_id, key)
    );

    CREATE TABLE changeset (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id bigint REFERENCES "user",
        tags hstore NOT NULL,
        created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        closed_at timestamptz,
        size integer NOT NULL DEFAULT 0,
        union_bounds geometry(Polygon, 4326)
    );
    CREATE INDEX changeset_user_idx ON changeset (user_id, id) WHERE user_id IS NOT NULL;
    CREATE INDEX changeset_created_at_idx ON changeset (created_at);
    CREATE INDEX changeset_closed_at_idx ON changeset (closed_at) WHERE closed_at IS NOT NULL;
    CREATE INDEX changeset_open_idx ON changeset (updated_at) WHERE closed_at IS NULL;
    CREATE INDEX changeset_empty_idx ON changeset (closed_at) WHERE closed_at IS NOT NULL AND size = 0;
    CREATE INDEX changeset_union_bounds_idx ON changeset USING gist (union_bounds) WHERE union_bounds IS NOT NULL;

    CREATE TABLE changeset_bounds (
        changeset_id bigint NOT NULL REFERENCES changeset ON DELETE CASCADE,
        bounds geometry(Polygon, 4326) NOT NULL
    );
    CREATE INDEX changeset_bounds_id_idx ON changeset_bounds (changeset_id);
    CREATE INDEX changeset_bounds_bounds_idx ON changeset_bounds USING gist (bounds) INCLUDE (changeset_id);

    CREATE TABLE changeset_comment (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES "user",
        changeset_id bigint NOT NULL REFERENCES changeset ON DELETE CASCADE,
        body text NOT NULL,
        body_rich_hash bytea,
        created_at timestamptz NOT NULL DEFAULT statement_timestamp()
    );
    CREATE INDEX changeset_comment_idx ON changeset_comment (changeset_id, id);

    CREATE TABLE diary (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES "user",
        title text NOT NULL,
        body text NOT NULL,
        body_rich_hash bytea,
        language text NOT NULL,
        point geometry(Point, 4326),
        created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
    );
    CREATE INDEX diary_user_id_idx ON diary (user_id, id);
    CREATE INDEX diary_language_idx ON diary (language, id);

    CREATE TABLE diary_comment (
        id bigint PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES "user",
        diary_id bigint NOT NULL REFERENCES diary ON DELETE CASCADE,
        body text NOT NULL,
        body_rich_hash bytea,
        created_at timestamptz NOT NULL DEFAULT statement_timestamp()
    );
    CREATE INDEX diary_comment_idx ON diary_comment (diary_id, id);

    CREATE TABLE mail (
        id bigint PRIMARY KEY,
        source text,
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
    CREATE INDEX mail_scheduled_at_idx ON mail (scheduled_at);

    CREATE TABLE message (
        id bigint PRIMARY KEY,
        from_user_id bigint NOT NULL REFERENCES "user",
        from_user_hidden boolean NOT NULL DEFAULT false,
        to_user_id bigint NOT NULL REFERENCES "user",
        to_user_hidden boolean NOT NULL DEFAULT false,
        read boolean NOT NULL DEFAULT false,
        subject text NOT NULL,
        body text NOT NULL,
        body_rich_hash bytea,
        created_at timestamptz NOT NULL DEFAULT statement_timestamp()
    );
    CREATE INDEX message_from_inbox ON message (from_user_id, id) WHERE from_user_hidden = false;
    CREATE INDEX message_to_inbox ON message (read, to_user_id, id) WHERE to_user_hidden = false;

    CREATE TABLE note (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        point geometry(Point, 4326),
        created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        closed_at timestamptz,
        hidden_at timestamptz
    );
    CREATE INDEX note_point_idx ON note USING gist (point);
    CREATE INDEX note_created_at_idx ON note (created_at);
    CREATE INDEX note_updated_at_idx ON note (updated_at);
    CREATE INDEX note_closed_at_idx ON note (closed_at);
    CREATE INDEX note_hidden_at_idx ON note (hidden_at);

    CREATE TABLE note_comment (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id bigint REFERENCES "user",
        user_ip inet,
        note_id bigint NOT NULL REFERENCES note ON DELETE CASCADE,
        event text NOT NULL,
        body text NOT NULL,
        body_rich_hash bytea,
        created_at timestamptz NOT NULL DEFAULT statement_timestamp()
    );
    CREATE INDEX note_comment_note_created_idx ON note_comment (note_id, created_at);
    CREATE INDEX note_comment_event_user_id_idx ON note_comment (event, user_id, id);
    CREATE INDEX note_comment_body_idx ON note_comment USING gin (to_tsvector('simple', body));

    CREATE TABLE trace (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES "user",
        name text NOT NULL,
        description text NOT NULL,
        tags text[] NOT NULL,
        visibility text NOT NULL,
        file_id text NOT NULL,
        size integer NOT NULL,
        track_sizes integer[] NOT NULL,
        points geometry(MultiPoint, 4326) NOT NULL,
        capture_times timestamptz[],
        elevations double precision[],
        created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT statement_timestamp()
    );
    CREATE INDEX trace_visibility_user_id_idx ON trace (visibility, user_id, id);
    CREATE INDEX trace_tags_idx ON trace USING gin (tags);
    CREATE INDEX trace_points_h3_11_idx ON trace USING gin (h3_points_to_cells(points, 11));
    """,
)
