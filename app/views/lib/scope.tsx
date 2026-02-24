import { Scope } from "@lib/proto/shared_pb"
import { t } from "i18next"

export const SCOPE_LABEL: Record<Scope, string> = {
  [Scope.read_prefs]: t("permissions.read_user_preferences"),
  [Scope.write_prefs]: t("permissions.modify_user_preferences"),
  [Scope.write_api]: t("permissions.manage_changesets_and_map_data"),
  [Scope.read_gpx]: t("permissions.read_all_gps_traces"),
  [Scope.write_gpx]: t("permissions.manage_gps_traces"),
  [Scope.write_notes]: t("permissions.manage_notes"),
  [Scope.web_user]: t("permissions.access_the_website"),
}

export const SCOPES_NO_WEB_USER = Object.keys(SCOPE_LABEL)
  .map((scope) => Number(scope) as Scope)
  .filter((scope) => scope !== Scope.web_user)

export const formDataScopes = (formData: FormData) =>
  formData.getAll("scopes").map((value) => Number(value) as Scope)

export const ScopeList = ({
  scopes,
  className = "",
}: {
  scopes: readonly Scope[]
  className?: string
}) => (
  <ul class={`list-unstyled ${className}`}>
    {scopes.length > 0 ? (
      scopes.map((scope) => (
        <li
          key={scope}
          class="d-flex"
        >
          <i class="bi bi-check text-success me-1" />
          <span>
            {SCOPE_LABEL[scope]} <span class="scope">({Scope[scope]})</span>
          </span>
        </li>
      ))
    ) : (
      <li class="d-flex">
        <i class="bi bi-dot text-muted me-1" />
        <span>{t("permissions.no_permissions")}</span>
      </li>
    )}
  </ul>
)
