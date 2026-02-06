import { execFileSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { dirname } from "node:path"
import { escape as escapeRegexp } from "@std/regexp"

const getPackageDist = (pkgName: string) => {
  const pkgPath = `node_modules/${pkgName}/package.json`
  const pkg = JSON.parse(readFileSync(pkgPath, "utf8"))
  const distDir = dirname(pkg.main)
  return `/static-node_modules/${pkgName}/${distDir}/`
}

export const {
  API_URL,
  CHANGESET_COMMENT_BODY_MAX_LENGTH,
  DISPLAY_NAME_MAX_LENGTH,
  ENV,
  MAP_QUERY_AREA_MAX_SIZE,
  MESSAGE_BODY_MAX_LENGTH,
  MESSAGE_RECIPIENTS_LIMIT,
  MESSAGE_SUBJECT_MAX_LENGTH,
  NOTE_COMMENT_BODY_MAX_LENGTH,
  NOTE_QUERY_AREA_MAX_SIZE,
  REPORT_COMMENT_BODY_MAX_LENGTH,
  SEARCH_QUERY_MAX_LENGTH,
  SENTRY_DSN,
  SENTRY_TRACES_SAMPLE_RATE,
  STANDARD_PAGINATION_DISTANCE,
  STANDARD_PAGINATION_MAX_FULL_PAGES,
  URLSAFE_BLACKLIST,
  VERSION,
}: {
  API_URL: string
  CHANGESET_COMMENT_BODY_MAX_LENGTH: number
  DISPLAY_NAME_MAX_LENGTH: number
  ENV: "dev" | "test" | "prod"
  MAP_QUERY_AREA_MAX_SIZE: number
  MESSAGE_BODY_MAX_LENGTH: number
  MESSAGE_RECIPIENTS_LIMIT: number
  MESSAGE_SUBJECT_MAX_LENGTH: number
  NOTE_COMMENT_BODY_MAX_LENGTH: number
  NOTE_QUERY_AREA_MAX_SIZE: number
  REPORT_COMMENT_BODY_MAX_LENGTH: number
  SEARCH_QUERY_MAX_LENGTH: number
  SENTRY_DSN: string
  SENTRY_TRACES_SAMPLE_RATE: number
  STANDARD_PAGINATION_DISTANCE: number
  STANDARD_PAGINATION_MAX_FULL_PAGES: number
  URLSAFE_BLACKLIST: string
  VERSION: string
} = JSON.parse(
  execFileSync(
    "python",
    [
      "-c",
      `
import json
from app.config import *
from app.lib.sentry import *
print(json.dumps({k: globals()[k] for k in ${JSON.stringify([
        "API_URL",
        "CHANGESET_COMMENT_BODY_MAX_LENGTH",
        "DISPLAY_NAME_MAX_LENGTH",
        "ENV",
        "MAP_QUERY_AREA_MAX_SIZE",
        "MESSAGE_BODY_MAX_LENGTH",
        "MESSAGE_RECIPIENTS_LIMIT",
        "MESSAGE_SUBJECT_MAX_LENGTH",
        "NOTE_COMMENT_BODY_MAX_LENGTH",
        "NOTE_QUERY_AREA_MAX_SIZE",
        "REPORT_COMMENT_BODY_MAX_LENGTH",
        "SEARCH_QUERY_MAX_LENGTH",
        "SENTRY_DSN",
        "SENTRY_TRACES_SAMPLE_RATE",
        "STANDARD_PAGINATION_DISTANCE",
        "STANDARD_PAGINATION_MAX_FULL_PAGES",
        "URLSAFE_BLACKLIST",
        "VERSION",
      ])}}))`,
    ],
    { encoding: "utf8" },
  ),
)

export const ID_PATH = getPackageDist("iD")
export const RAPID_PATH = getPackageDist("@rapideditor/rapid")
export const URLSAFE_BLACKLIST_RE = new RegExp(
  `[${escapeRegexp(URLSAFE_BLACKLIST)}]`,
  "u",
)
