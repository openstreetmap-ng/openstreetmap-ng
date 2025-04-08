CREATE TABLE admin_task (
    id text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    heartbeat_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE INDEX admin_task_heartbeat_at_idx ON admin_task (heartbeat_at);
