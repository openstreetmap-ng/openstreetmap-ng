import "./main.scss"
import { _ENV } from "@lib/config.macro" with { type: "macro" }

if (_ENV !== "prod") {
  import("preact/debug")
}

import "@lib/polyfills"

import "@lib/tracking"

import "@lib/i18n"

import "./navbar/navbar-left"
import "./navbar/navbar-right"

import "./rich-text/_control"
import "@lib/datetime-inputs"
import "@lib/image-proxy"

import "./_unsubscribe-discussion"
import "./admin/applications/index"
import "./admin/tasks"
import "./admin/users/edit"
import "./admin/users/index"
import "./audit/index"
import "./diary/compose"
import "./diary/index"
import "./edit/index"
import "./edit/redirect"
import "./fixthemap"
import "./follows/index"
import "./messages/index"
import "./messages/new"
import "./notes"
import "./oauth2/fragment-callback"
import "./oauth2/response-form-post"
import "./reports/index"
import "./reports/show"
import "./settings/applications/edit"
import "./settings/applications/index"
import "./settings/email"
import "./settings/security"
import "./settings/settings"
import "./traces/_list"
import "./traces/_preview"
import "./traces/edit"
import "./traces/index"
import "./traces/upload"
import "./user/_login-body"
import "./user/account-confirm"
import "./user/profile/profile"
import "./user/reset-password-token"
import "./user/reset-password"
import "./user/signup"
import "./welcome"
import "@lib/timezone-update"

import "@lib/map/main-map"

import "@lib/auth-switcher"
import "@lib/bootstrap"
import "@lib/copy-group"
import "@lib/multi-input"
import "@lib/password-strength"
import "@lib/report"
import "@lib/reset-secret"
