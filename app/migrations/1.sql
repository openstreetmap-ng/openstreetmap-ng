CREATE TABLE task (
    id text PRIMARY KEY,
    heartbeat_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX task_heartbeat_at_idx ON task (heartbeat_at);
