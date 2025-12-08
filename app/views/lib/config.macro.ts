import { execSync } from "node:child_process"

const pythonConfig: Record<string, any> = JSON.parse(
    execSync(
        `python -c "
import json
from app.config import *
from app.lib.sentry import *
print(json.dumps({
    'API_URL': API_URL,
    'ENV': ENV,
    'MAP_QUERY_AREA_MAX_SIZE': MAP_QUERY_AREA_MAX_SIZE,
    'NOTE_QUERY_AREA_MAX_SIZE': NOTE_QUERY_AREA_MAX_SIZE,
    'SENTRY_DSN': SENTRY_DSN,
    'SENTRY_TRACES_SAMPLE_RATE': SENTRY_TRACES_SAMPLE_RATE,
    'VERSION': VERSION,
}))"`,
        { encoding: "utf8" },
    ),
)

export const _API_URL: string = pythonConfig.API_URL
export const _ENV: "dev" | "test" | "prod" = pythonConfig.ENV
export const _MAP_QUERY_AREA_MAX_SIZE: number = pythonConfig.MAP_QUERY_AREA_MAX_SIZE
export const _NOTE_QUERY_AREA_MAX_SIZE: number = pythonConfig.NOTE_QUERY_AREA_MAX_SIZE
// TODO: revert "UNSET" workaround when fixed https://github.com/unplugin/unplugin-macros/issues/122
export const _SENTRY_DSN: string = pythonConfig.SENTRY_DSN || "UNSET"
export const _SENTRY_TRACES_SAMPLE_RATE: number = pythonConfig.SENTRY_TRACES_SAMPLE_RATE
export const _VERSION: string = pythonConfig.VERSION
