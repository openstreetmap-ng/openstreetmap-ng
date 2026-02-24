import { create } from "@bufbuild/protobuf"
import { BAccordion } from "@lib/bootstrap"
import {
  API_URL,
  config,
  OAUTH_APP_NAME_MAX_LENGTH,
  OAUTH_PAT_NAME_MAX_LENGTH,
} from "@lib/config"
import { CopyButton } from "@lib/copy-group"
import { Time } from "@lib/datetime-inputs"
import { tRich } from "@lib/i18n"
import { mountProtoPage } from "@lib/proto-page"
import {
  type AdminPage_EntryValid,
  AdminPageSchema,
  type AuthorizationsPage_EntryValid,
  AuthorizationsPageSchema,
  Service,
  TokensPage_TokenSchema,
  type TokensPage_TokenValid,
  TokensPageSchema,
} from "@lib/proto/settings_applications_pb"
import { Service as SecurityService } from "@lib/proto/settings_security_pb"
import { Scope } from "@lib/proto/shared_pb"
import { ReportButton } from "@lib/report"
import { formDataScopes, SCOPE_LABEL, ScopeList, SCOPES_NO_WEB_USER } from "@lib/scope"
import { StandardForm } from "@lib/standard-form"
import { headersDate, throwAbortError } from "@lib/utils"
import { useSignal, useSignalEffect } from "@preact/signals"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { useRef } from "preact/hooks"
import { SettingsNav } from "../_nav"
import { SettingsApplicationsNav } from "./_nav"

const SYSTEM_APP_WEB_CLIENT_ID = "SystemApp.web"
const API_DOMAIN = new URL(API_URL).host

const ApplicationsLayout = ({
  title,
  children,
}: {
  title: string
  children: ComponentChildren
}) => (
  <>
    <div class="content-header">
      <h1 class="container">{title}</h1>
    </div>

    <div class="content-body">
      <div class="container">
        <div class="row">
          <div class="col-lg-auto mb-4">
            <SettingsNav />
          </div>

          <div class="col-lg">{children}</div>
        </div>
      </div>
    </div>
  </>
)

const PermissionsActions = ({
  scopes,
  actions,
}: {
  scopes: readonly Scope[]
  actions: ComponentChildren
}) => (
  <div class="row g-3 g-md-2">
    <div class="col-md">
      <h6>{t("settings.requested_permissions")}</h6>
      <ScopeList scopes={scopes} />
    </div>
    {actions ? <div class="col-md-auto align-self-end text-end">{actions}</div> : null}
  </div>
)

const TimelineDate = ({ unix }: { unix: bigint }) => (
  <>
    <Time
      class="fw-medium"
      unix={unix}
      dateStyle="long"
      timeStyle="short"
    />{" "}
    (
    <Time
      unix={unix}
      relativeStyle="long"
    />
    )
  </>
)

const TimestampDescription = ({
  timestamp,
}: {
  timestamp: {
    kind: "authorized" | "created" | "updated"
    unix: bigint
  }
}) => {
  const date = <TimelineDate unix={timestamp.unix} />

  switch (timestamp.kind) {
    case "authorized":
      return tRich("settings.authorized_at", {
        date,
      })
    case "created":
      return tRich("settings.created_at", {
        date,
      })
    case "updated":
      return tRich("settings.updated_at", {
        date,
      })
  }
}

export const ApplicationAccordionEntry = ({
  avatarUrl,
  name,
  timestamp,
  descriptionExtra,
  scopes,
  actions,
}: {
  avatarUrl: string
  name: string
  timestamp: {
    kind: "authorized" | "created"
    unix: bigint
  }
  descriptionExtra?: ComponentChildren
  scopes: readonly Scope[]
  actions?: ComponentChildren
}) => (
  <BAccordion
    header={
      <div class="row align-items-center g-3 g-lg-4">
        <div class="col-auto">
          <img
            class="app-avatar avatar"
            src={avatarUrl}
            alt={t("alt.application_image")}
            loading="lazy"
          />
        </div>
        <div class="col">
          <h6 class="mb-1">{name}</h6>
          <p class="form-text mb-0">
            <TimestampDescription timestamp={timestamp} />
            {descriptionExtra ? (
              <>
                <br />
                {descriptionExtra}
              </>
            ) : null}
          </p>
        </div>
      </div>
    }
  >
    <PermissionsActions
      scopes={scopes}
      actions={actions}
    />
  </BAccordion>
)

const AuthorizationsOwnerInfo = ({
  entry,
}: {
  entry: AuthorizationsPage_EntryValid
}) => {
  const owner = entry.application.owner

  if (owner?.id === config.userConfig!.user.id) {
    return (
      <>
        <i class="bi bi-person-fill text-primary" /> {t("settings.owned_by_you")}
      </>
    )
  }

  if (!owner) {
    return (
      <>
        <i class="bi bi-shield-fill-check text-success" />{" "}
        {tRich("settings.owned_by_user", {
          name: <a href="/">{t("project_name")}</a>,
        })}
      </>
    )
  }

  return tRich("settings.owned_by_user", {
    name: (
      <a href={`/user/${owner.displayName}`}>
        <img
          class="avatar me-1"
          src={owner.avatarUrl}
          alt={t("alt.profile_picture")}
          loading="lazy"
        />
        {owner.displayName}
      </a>
    ),
  })
}

const AuthorizationEntry = ({
  entry,
  onRevoke,
}: {
  entry: AuthorizationsPage_EntryValid
  onRevoke: (applicationId: bigint) => void
}) => {
  const { application } = entry
  const canRevoke = application.clientId !== SYSTEM_APP_WEB_CLIENT_ID
  const canReport = Boolean(application.owner)

  return (
    <ApplicationAccordionEntry
      avatarUrl={application.avatarUrl}
      name={application.name}
      timestamp={{
        kind: "authorized",
        unix: entry.authorizedAt,
      }}
      descriptionExtra={<AuthorizationsOwnerInfo entry={entry} />}
      scopes={application.scopes}
      actions={
        canRevoke ? (
          <StandardForm
            class={canReport ? "btn-group" : ""}
            method={Service.method.revokeAuthorization}
            buildRequest={() => ({ id: application.id })}
            onSuccess={() => onRevoke(application.id)}
          >
            <button
              class="btn btn-soft"
              type="submit"
            >
              {t("action.revoke_access")}
            </button>

            {canReport ? (
              <>
                <button
                  class="btn btn-soft dropdown-toggle dropdown-toggle-split"
                  type="button"
                  data-bs-toggle="dropdown"
                  aria-expanded={false}
                  aria-label={t("action.show_more")}
                />
                <ul class="dropdown-menu">
                  <li>
                    <ReportButton
                      class="dropdown-item"
                      reportType="user"
                      reportTypeId={application.owner!.id}
                      reportAction="user_oauth2_application"
                      reportActionId={application.id}
                    >
                      {t("report.report_object", {
                        object: t("oauth2_authorized_applications.index.application"),
                      })}
                    </ReportButton>
                  </li>
                </ul>
              </>
            ) : null}
          </StandardForm>
        ) : null
      }
    />
  )
}

const AdminEntry = ({ entry }: { entry: AdminPage_EntryValid }) => (
  <ApplicationAccordionEntry
    avatarUrl={entry.avatarUrl}
    name={entry.name}
    timestamp={{
      kind: "created",
      unix: entry.createdAt,
    }}
    descriptionExtra={
      <>
        <i class="bi bi-person-fill text-primary" /> {t("settings.owned_by_you")}
      </>
    }
    scopes={entry.scopes}
    actions={
      <a
        class="btn btn-soft"
        href={`/settings/applications/admin/${entry.id}/edit`}
      >
        {t("layouts.edit")}
      </a>
    }
  />
)

export const TokenAccordionEntry = ({
  name,
  timestamp,
  scopes,
  accessToken,
  actions,
  defaultOpen = false,
}: {
  name: string
  timestamp: {
    kind: "updated" | "created"
    unix: bigint
  }
  scopes: readonly Scope[]
  accessToken: {
    value: string
    controls?: ComponentChildren
    form?: (field: ComponentChildren) => ComponentChildren
  }
  actions?: ComponentChildren
  defaultOpen?: boolean
}) => (
  <BAccordion
    defaultOpen={defaultOpen}
    header={
      <div class="row align-items-center g-3 g-lg-4">
        <div class="col-auto">
          <i
            class={`token-icon bi bi-key${timestamp.kind === "updated" ? "-fill" : ""}`}
          />
        </div>
        <div class="col">
          <h6 class="mb-1">{name}</h6>
          <p class="form-text mb-0">
            <TimestampDescription timestamp={timestamp} />
          </p>
        </div>
      </div>
    }
  >
    {accessToken.form ? (
      accessToken.form(
        <label class="w-100 mb-3">
          <span class="h6">{t("settings.access_token")}</span>
          <div class="input-group mt-2">
            <input
              type="text"
              class="form-control font-monospace bg-body-tertiary"
              value={accessToken.value}
              readOnly
            />
            {accessToken.controls}
          </div>
        </label>,
      )
    ) : (
      <label class="w-100 mb-3">
        <span class="h6">{t("settings.access_token")}</span>
        <div class="input-group mt-2">
          <input
            type="text"
            class="form-control font-monospace bg-body-tertiary"
            value={accessToken.value}
            readOnly
          />
          {accessToken.controls}
        </div>
      </label>
    )}

    <PermissionsActions
      scopes={scopes}
      actions={actions}
    />
  </BAccordion>
)

type TokenState = TokensPage_TokenValid & {
  secret?: string
}

const removeAuthorizationByAppId = (
  entries: readonly AuthorizationsPage_EntryValid[],
  applicationId: bigint,
) => entries.filter((entry) => entry.application.id !== applicationId)

const removeTokenById = (tokens: readonly TokenState[], tokenId: bigint) =>
  tokens.filter((token) => token.id !== tokenId)

const updateTokenSecret = (
  tokens: readonly TokenState[],
  tokenId: bigint,
  secret: string,
  authorizedAt: bigint,
) =>
  tokens.map((token) => {
    if (token.id !== tokenId) return token
    token.secret = secret
    token.authorizedAt = authorizedAt
    return token
  })

const TokenEntry = ({
  token,
  onSecret,
  onRevoke,
  defaultOpen,
}: {
  token: TokenState
  onSecret: (tokenId: bigint, secret: string, authorizedAt: bigint) => void
  onRevoke: (tokenId: bigint) => void
  defaultOpen: boolean
}) => {
  const authorizedAt = token.authorizedAt
  const tokenValue = token.secret
  const tokenDisplay =
    tokenValue ?? (token.tokenPreview ? `${token.tokenPreview}...` : "")

  return (
    <TokenAccordionEntry
      name={token.name}
      timestamp={
        authorizedAt
          ? { kind: "updated", unix: authorizedAt }
          : { kind: "created", unix: token.createdAt }
      }
      scopes={token.scopes}
      defaultOpen={defaultOpen}
      accessToken={{
        value: tokenDisplay,
        controls: (
          <>
            <button
              class="btn btn-soft"
              type="submit"
            >
              <i class="bi bi-arrow-clockwise me-1-5" />
              {t("settings.new_access_token")}
            </button>
            {tokenValue && (
              <CopyButton
                class="btn btn-primary"
                title={t("action.copy")}
                getText={() => tokenValue}
              />
            )}
          </>
        ),
        form: (field) => (
          <StandardForm
            method={Service.method.resetAccessToken}
            buildRequest={() => {
              if (!confirm(t("settings.new_secret_question"))) {
                throwAbortError()
              }
              return { tokenId: token.id }
            }}
            onSuccess={(resp, ctx) =>
              onSecret(token.id, resp.secret, headersDate(ctx.headers))
            }
          >
            {field}
          </StandardForm>
        ),
      }}
      actions={
        <StandardForm
          method={SecurityService.method.revokeToken}
          buildRequest={() => ({ tokenId: token.id })}
          onSuccess={() => onRevoke(token.id)}
        >
          <button
            class="btn btn-soft"
            type="submit"
          >
            {t("action.revoke_key")}
          </button>
        </StandardForm>
      }
    />
  )
}

mountProtoPage(AuthorizationsPageSchema, ({ entries: initialEntries }) => {
  const entries = useSignal(initialEntries)

  return (
    <ApplicationsLayout title={t("settings.applications")}>
      <SettingsApplicationsNav />

      <p>{t("settings.authorizations.description")}</p>
      <ul class="applications-list list-unstyled">
        {entries.value.map((entry) => {
          const id = entry.application.id
          return (
            <li key={id}>
              <AuthorizationEntry
                entry={entry}
                onRevoke={(applicationId) =>
                  (entries.value = removeAuthorizationByAppId(
                    entries.value,
                    applicationId,
                  ))
                }
              />
            </li>
          )
        })}
      </ul>
    </ApplicationsLayout>
  )
})

mountProtoPage(AdminPageSchema, ({ entries: initialEntries }) => {
  const entries = useSignal(initialEntries)
  const showCreateForm = useSignal(false)
  const createNameInputRef = useRef<HTMLInputElement>(null)

  useSignalEffect(() => {
    if (showCreateForm.value) {
      createNameInputRef.current!.focus()
    }
  })

  return (
    <ApplicationsLayout title={t("settings.applications")}>
      <SettingsApplicationsNav />

      <p>{t("settings.my_applications.description")}</p>
      <ul class="applications-list list-unstyled">
        {entries.value.map((entry) => (
          <li key={entry.id}>
            <AdminEntry entry={entry} />
          </li>
        ))}
      </ul>
      {entries.value.length === 0 && (
        <p class="form-text">
          <i class="bi bi-info-circle me-2" />
          {t("settings.my_applications.you_have_not_registered_any_applications_yet")}
        </p>
      )}

      <div class="d-flex justify-content-end mb-2">
        {!showCreateForm.value ? (
          <button
            class="btn btn-primary"
            type="button"
            onClick={() => (showCreateForm.value = true)}
          >
            <i class="bi bi-plus-lg" /> {t("settings.my_applications.new_application")}
          </button>
        ) : (
          <StandardForm
            class="d-flex"
            method={Service.method.create}
            buildRequest={({ formData }) => ({
              name: formData.get("name") as string,
            })}
            onSuccess={(resp) => {
              window.location.href = `/settings/applications/admin/${resp.id}/edit`
            }}
          >
            <input
              type="text"
              class="form-control me-2"
              name="name"
              placeholder={t("settings.name")}
              maxLength={OAUTH_APP_NAME_MAX_LENGTH}
              autoComplete="off"
              required
              ref={createNameInputRef}
            />
            <button
              class="btn btn-primary"
              type="submit"
            >
              {t("action.submit")}
            </button>
          </StandardForm>
        )}
      </div>
    </ApplicationsLayout>
  )
})

mountProtoPage(
  TokensPageSchema,
  ({ tokens: initialTokens, expandedTokenId: initialExpandedTokenId }) => {
    const tokens = useSignal<TokenState[]>(initialTokens)
    const expandedTokenId = useSignal(initialExpandedTokenId)
    const showCreateForm = useSignal(false)

    return (
      <ApplicationsLayout title={t("settings.applications")}>
        <SettingsApplicationsNav />

        <p>{t("settings.my_tokens.description")}</p>
        <ul class="applications-list list-unstyled">
          {tokens.value.map((token) => (
            <li key={token.id}>
              <TokenEntry
                token={token}
                defaultOpen={expandedTokenId.value === token.id}
                onSecret={(tokenId, secret, authorizedAt) =>
                  (tokens.value = updateTokenSecret(
                    tokens.value,
                    tokenId,
                    secret,
                    authorizedAt,
                  ))
                }
                onRevoke={(tokenId) =>
                  (tokens.value = removeTokenById(tokens.value, tokenId))
                }
              />
            </li>
          ))}
        </ul>
        {tokens.value.length === 0 && (
          <p class="form-text">
            <i class="bi bi-info-circle me-2" />
            {t("settings.my_tokens.you_have_not_created_any_tokens_yet")}
          </p>
        )}

        <BAccordion
          class="mb-4"
          open={showCreateForm.value}
          onOpenChange={(open) => (showCreateForm.value = open)}
          header={t("settings.my_tokens.create_a_new_token")}
        >
          <StandardForm
            method={Service.method.createToken}
            buildRequest={({ formData }) => ({
              name: formData.get("name") as string,
              scopes: formDataScopes(formData),
            })}
            onSuccess={(resp, ctx) => {
              const token: TokenState = create(TokensPage_TokenSchema, {
                id: resp.id,
                name: ctx.request.name,
                createdAt: headersDate(ctx.headers),
                scopes: ctx.request.scopes,
              })
              tokens.value = [token, ...tokens.value]
              expandedTokenId.value = token.id
              showCreateForm.value = false
            }}
            resetOnSuccess
          >
            <label class="form-label d-block">
              <span class="required">{t("settings.name")}</span>
              <input
                type="text"
                class="form-control mt-2"
                name="name"
                maxLength={OAUTH_PAT_NAME_MAX_LENGTH}
                required
              />
            </label>
            <p class="form-text mb-3">{t("settings.my_tokens.name_hint")}</p>

            <p class="form-label">{t("settings.requested_permissions")}</p>
            <ul class="list-unstyled ms-1">
              {SCOPES_NO_WEB_USER.map((scope) => (
                <li
                  class="form-check"
                  key={scope}
                >
                  <label class="form-check-label d-block">
                    <input
                      class="form-check-input"
                      type="checkbox"
                      name="scopes"
                      value={scope}
                    />
                    {SCOPE_LABEL[scope]} <span class="scope">({Scope[scope]})</span>
                  </label>
                </li>
              ))}
            </ul>

            <div class="text-end">
              <button
                type="submit"
                class="btn btn-primary"
              >
                {t("action.submit")}
              </button>
            </div>
          </StandardForm>
        </BAccordion>

        <hr class="my-4" />

        <h3>{t("settings.my_tokens.how_to_use.title")}</h3>
        <p>{t("settings.my_tokens.how_to_use.description")}</p>
        <div class="card mb-3">
          <div class="card-header">
            <i class="bi bi-globe2 me-2" />
            {t("settings.my_tokens.how_to_use.example_http_request")}
          </div>
          <div class="card-body">
            <pre class="mb-0">
              <code>{`GET /api/0.7/user/details HTTP/1.1\nHost: ${API_DOMAIN}\nAuthorization: Bearer your_access_token_here`}</code>
            </pre>
          </div>
        </div>
        <div class="card">
          <div class="card-header">
            <i class="bi bi-terminal me-2" />
            {t("settings.my_tokens.how_to_use.example_curl_command")}
          </div>
          <div class="card-body">
            <pre class="mb-0">
              <code>{`curl -H "Authorization: Bearer your_access_token_here" \\\n    ${API_URL}/api/0.7/user/details`}</code>
            </pre>
          </div>
        </div>
      </ApplicationsLayout>
    )
  },
)
