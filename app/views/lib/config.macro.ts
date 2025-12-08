import { execSync } from "node:child_process"

const pythonConfig: Record<string, any> = JSON.parse(
    execSync(
        `python -c "
import json
from app.config import *
print(json.dumps({
    'API_URL': API_URL,
    'ENV': ENV,
    'MAP_QUERY_AREA_MAX_SIZE': MAP_QUERY_AREA_MAX_SIZE,
    'NOTE_QUERY_AREA_MAX_SIZE': NOTE_QUERY_AREA_MAX_SIZE,
    'VERSION': VERSION,
}))"`,
        { encoding: "utf8" },
    ),
)

export const _API_URL: string = pythonConfig.API_URL
export const _ENV: "dev" | "test" | "prod" = pythonConfig.ENV
export const _MAP_QUERY_AREA_MAX_SIZE: number = pythonConfig.MAP_QUERY_AREA_MAX_SIZE
export const _NOTE_QUERY_AREA_MAX_SIZE: number = pythonConfig.NOTE_QUERY_AREA_MAX_SIZE
export const _VERSION: string = pythonConfig.VERSION
