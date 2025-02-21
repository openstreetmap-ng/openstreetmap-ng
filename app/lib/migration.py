from app.config import DELETED_USER_EMAIL_SUFFIX

_VERSIONS: tuple[str, ...] = (
    f"""
    CREATE EXTENSION hstore;

    CREATE TABLE "user" (
        id bigint GENERATED ALWAYS AS IDENTITY,
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

    CREATE TABLE changeset (
        id bigint GENERATED ALWAYS AS IDENTITY,
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
        id bigint GENERATED ALWAYS AS IDENTITY,
        user_id bigint NOT NULL REFERENCES "user",
        changeset_id bigint NOT NULL REFERENCES changeset ON DELETE CASCADE,
        body text NOT NULL,
        body_rich_hash bytea,
        created_at timestamptz NOT NULL DEFAULT statement_timestamp()
    );
    CREATE INDEX changeset_comment_idx ON changeset_comment (changeset_id, created_at);

    CREATE TABLE oauth2_application (
        id bigint GENERATED ALWAYS AS IDENTITY,
        user_id bigint REFERENCES "user",
        name text NOT NULL,
        avatar_id text,
        client_id text NOT NULL,
        client_secret_hashed bytea,
        client_secret_preview text,
        is_confidential boolean NOT NULL DEFAULT false,
        redirect_uris text[] NOT NULL DEFAULT '{{}}',
        scopes text[] NOT NULL DEFAULT '{{}}',
        created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    );
    CREATE UNIQUE INDEX oauth2_application_client_id_idx ON oauth2_application (client_id);
    CREATE INDEX oauth2_application_user_idx ON oauth2_application (user_id);

    CREATE TABLE user_pref (
        user_id bigint NOT NULL REFERENCES "user",
        app_id bigint REFERENCES oauth2_application,
        key text NOT NULL,
        value text NOT NULL,
        PRIMARY KEY (user_id, app_id, key)
    );
    """,
)
