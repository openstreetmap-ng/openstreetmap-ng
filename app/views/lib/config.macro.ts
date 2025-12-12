import { execSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { dirname } from "node:path"
import { escape as escapeRegexp } from "@std/regexp"

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
    'URLSAFE_BLACKLIST': URLSAFE_BLACKLIST,
    'VERSION': VERSION,
}))"`,
        { encoding: "utf8" },
    ),
)

export const _API_URL: string = pythonConfig.API_URL
export const _ENV: "dev" | "test" | "prod" = pythonConfig.ENV
export const _MAP_QUERY_AREA_MAX_SIZE: number = pythonConfig.MAP_QUERY_AREA_MAX_SIZE
export const _NOTE_QUERY_AREA_MAX_SIZE: number = pythonConfig.NOTE_QUERY_AREA_MAX_SIZE
export const _SENTRY_DSN: string = pythonConfig.SENTRY_DSN
export const _SENTRY_TRACES_SAMPLE_RATE: number = pythonConfig.SENTRY_TRACES_SAMPLE_RATE
export const _URLSAFE_BLACKLIST: string = pythonConfig.URLSAFE_BLACKLIST
export const _URLSAFE_BLACKLIST_RE = new RegExp(
    `[${escapeRegexp(_URLSAFE_BLACKLIST)}]`,
    "u",
)
export const _VERSION: string = pythonConfig.VERSION

const getPackageDist = (pkgName: string) => {
    const pkgPath = `node_modules/${pkgName}/package.json`
    const pkg = JSON.parse(readFileSync(pkgPath, "utf-8"))
    const distDir = dirname(pkg.main)
    return `/static-node_modules/${pkgName}/${distDir}/`
}

export const _ID_PATH = getPackageDist("iD")
export const _RAPID_PATH = getPackageDist("@rapideditor/rapid")
