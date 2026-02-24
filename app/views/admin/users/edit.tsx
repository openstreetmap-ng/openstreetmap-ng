import { Time } from "@lib/datetime-inputs"
import { tRich } from "@lib/i18n"
import type {
  EditPage_Application,
  EditPage_ConnectedAccountValid,
  EditPage_Token,
} from "@lib/proto/admin_users_pb"
import { EditPageSchema, Role, Service } from "@lib/proto/admin_users_pb"
import { mountProtoPage } from "@lib/proto-page"
import { StandardForm } from "@lib/standard-form"
import { throwAbortError } from "@lib/utils"
import { useSignal } from "@preact/signals"
import { t } from "i18next"
import { useEffect, useRef } from "preact/hooks"
import {
  ApplicationAccordionEntry,
  TokenAccordionEntry,
} from "../../settings/applications/index"
import { ProviderIdentity } from "../../settings/connections"

const TABS = [
  ["account", "Account settings"],
  ["connections", t("settings.connected_accounts")],
  ["authorizations", t("settings.authorizations.title")],
  ["applications", t("settings.my_applications.title")],
  ["tokens", t("settings.my_tokens.title")],
] as const

const ApplicationEntry = ({ entry }: { entry: EditPage_Application }) => (
  <ApplicationAccordionEntry
    avatarUrl={entry.avatarUrl}
    name={entry.name}
    timestamp={
      entry.authorizedAt
        ? { kind: "authorized", unix: entry.authorizedAt }
        : { kind: "created", unix: entry.createdAt! }
    }
    descriptionExtra={
      entry.owner ? (
        <>
          <i class="bi bi-person-fill text-primary" />{" "}
          {tRich("settings.owned_by_user", {
            name: (
              <a href={`/user-id/${entry.owner.id.toString()}`}>
                {entry.owner.displayName}
              </a>
            ),
          })}
        </>
      ) : (
        <>
          <i class="bi bi-shield-fill-check text-success" />{" "}
          {tRich("settings.owned_by_user", {
            name: <a href="/">{t("project_name")}</a>,
          })}
        </>
      )
    }
    scopes={entry.scopes}
  />
)

const TokenEntry = ({ token }: { token: EditPage_Token }) => (
  <TokenAccordionEntry
    name={token.name ?? ""}
    timestamp={
      token.authorizedAt
        ? { kind: "updated", unix: token.authorizedAt }
        : { kind: "created", unix: token.createdAt }
    }
    scopes={token.scopes}
    accessToken={{
      value: token.tokenPreview ? `${token.tokenPreview}...` : "",
    }}
  />
)

const ProviderCell = ({
  connection,
}: {
  connection: EditPage_ConnectedAccountValid
}) => (
  <ProviderIdentity provider={connection.provider}>
    <p class="form-text mb-0">
      UID: <code>{connection.uid}</code> ·{" "}
      <Time
        unix={connection.createdAt}
        dateStyle="long"
        timeStyle="short"
      />
    </p>
  </ProviderIdentity>
)

const Row = ({ connection }: { connection: EditPage_ConnectedAccountValid }) => (
  <tr>
    <td class="d-flex align-items-center">
      <ProviderCell connection={connection} />
    </td>
    <td class="text-end text-success">
      <i class="bi bi-link-45deg me-2" />
      {t("state.connected")}
    </td>
  </tr>
)

mountProtoPage(
  EditPageSchema,
  ({
    account: initialAccount,
    twoFactorStatus: initialTwoFactorStatus,
    connectedAccounts,
    authorizations,
    applications,
    tokens,
  }) => {
    const account = useSignal(initialAccount)
    const twoFactorStatus = useSignal(initialTwoFactorStatus)
    const activeTab = useSignal<(typeof TABS)[number][0]>("account")
    const baseRoles = useRef([...initialAccount.roles])
    const newPasswordInputRef = useRef<HTMLInputElement>(null)
    const newPasswordConfirmInputRef = useRef<HTMLInputElement>(null)

    const syncPasswordValidity = () => {
      const password = newPasswordInputRef.current?.value ?? ""
      const confirm = newPasswordConfirmInputRef.current?.value ?? ""
      const message =
        confirm && password !== confirm ? t("validation.passwords_missmatch") : ""
      if (newPasswordConfirmInputRef.current) {
        newPasswordConfirmInputRef.current.setCustomValidity(message)
      }
    }
    useEffect(syncPasswordValidity, [])

    const renderAccountTab = () => (
      <div>
        <h3 class="mb-3">Account information</h3>
        <StandardForm
          method={Service.method.update}
          buildRequest={({ formData, passwords }) => {
            const nextRoles = formData
              .getAll("roles")
              .map((value) => Role[value as keyof typeof Role])
            const oldRoles = new Set(baseRoles.current)
            const currentRoles = new Set(nextRoles)

            for (const role of oldRoles) {
              if (!currentRoles.has(role)) {
                if (!confirm(`Remove ${Role[role]} role from this user?`)) {
                  throwAbortError()
                }
              }
            }

            for (const role of currentRoles) {
              if (!oldRoles.has(role)) {
                if (!confirm(`Grant ${Role[role]} role to this user?`)) {
                  throwAbortError()
                }
              }
            }

            return {
              userId: account.value.id,
              displayName: (formData.get("display_name") as string) || undefined,
              email: (formData.get("email") as string) || undefined,
              emailVerified: formData.get("email_verified") === "true",
              roles: nextRoles,
              newPassword: passwords.new_password,
            }
          }}
          onSuccess={(_, ctx) => {
            account.value = {
              ...account.value,
              displayName: ctx.request.displayName ?? account.value.displayName,
              email: ctx.request.email ?? account.value.email,
              emailVerified: ctx.request.emailVerified,
              roles: [...ctx.request.roles],
            }
            baseRoles.current = [...ctx.request.roles]
            if (newPasswordInputRef.current) newPasswordInputRef.current.value = ""
            if (newPasswordConfirmInputRef.current)
              newPasswordConfirmInputRef.current.value = ""
          }}
          class="account-form mb-4"
        >
          <label class="form-label d-block">
            <span>{t("activerecord.attributes.user.display_name")}</span>
            <input
              type="text"
              class="form-control mt-2"
              name="display_name"
              placeholder={account.value.displayName}
            />
          </label>
          <p class="form-text">Leave blank to keep current value</p>

          <label class="form-label d-block">
            <span>{t("passwords.new.email address")}</span>
            <input
              type="email"
              class="form-control mt-2"
              name="email"
              placeholder={account.value.email}
            />
          </label>
          <p class="form-text">Leave blank to keep current value</p>

          <div class="form-check">
            <label class="form-check-label">
              <input
                class="form-check-input"
                type="checkbox"
                name="email_verified"
                value="true"
                defaultChecked={account.value.emailVerified}
              />
              Email verified
            </label>
          </div>

          <hr class="my-3" />

          <h4 class="mb-3">Roles</h4>
          <div class="mb-3">
            {[Role.moderator, Role.administrator].map((role) => (
              <div
                key={role}
                class="form-check"
              >
                <label class="form-check-label">
                  <input
                    class="form-check-input role-checkbox"
                    type="checkbox"
                    name="roles"
                    value={Role[role]}
                    defaultChecked={account.value.roles.includes(role)}
                  />
                  <i
                    class={`bi bi-star-fill ${
                      role === Role.administrator ? "text-danger" : "text-blue"
                    }`}
                  />
                  <span class="ms-1">{Role[role]}</span>
                </label>
              </div>
            ))}
          </div>

          <hr class="my-3" />

          <h4 class="mb-3">{t("settings.change_password")}</h4>
          <label class="form-label d-block">
            <span>{t("settings.new_password")}</span>
            <input
              type="password"
              class="form-control mt-2"
              name="new_password"
              ref={newPasswordInputRef}
              onInput={syncPasswordValidity}
            />
          </label>
          <p class="form-text">Leave blank to keep current password</p>

          <label class="form-label d-block">
            <span>{t("settings.new_password_repeat")}</span>
            <input
              type="password"
              class="form-control mt-2"
              name="new_password_confirm"
              ref={newPasswordConfirmInputRef}
              onInput={syncPasswordValidity}
            />
          </label>

          <hr class="my-4" />

          <div class="text-end">
            <button
              class="btn btn-primary px-3"
              type="submit"
            >
              {t("action.save_changes")}
            </button>
          </div>
        </StandardForm>

        <h4 class="mb-3">{t("two_fa.two_factor_methods")}</h4>
        <div class="d-flex gap-3">
          <i
            class={`bi bi-fingerprint fs-4 ${
              twoFactorStatus.value.hasPasskeys ? "text-success" : "text-body-tertiary"
            }`}
          />
          <i
            class={`bi bi-phone fs-4 ${
              twoFactorStatus.value.hasTotp ? "text-success" : "text-body-tertiary"
            }`}
          />
          <i
            class={`bi bi-file-text fs-4 ${
              twoFactorStatus.value.hasRecovery ? "text-success" : "text-body-tertiary"
            }`}
          />

          {(twoFactorStatus.value.hasPasskeys || twoFactorStatus.value.hasTotp) && (
            <StandardForm
              method={Service.method.resetTwoFactor}
              buildRequest={() => {
                if (
                  !confirm(
                    "Reset two-factor authentication for this user?\n\nThis will remove:\n• All passkeys\n• Authenticator app",
                  )
                ) {
                  throwAbortError()
                }
                return { userId: account.value.id }
              }}
              onSuccess={() => {
                twoFactorStatus.value = {
                  ...twoFactorStatus.value,
                  hasPasskeys: false,
                  hasTotp: false,
                }
              }}
              class="ms-2"
            >
              <button
                class="btn btn-outline-danger"
                type="submit"
              >
                Reset 2FA
              </button>
            </StandardForm>
          )}
        </div>
      </div>
    )

    return (
      <>
        <div class="content-header pb-0">
          <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
            <a
              href="/admin/users"
              class="btn btn-sm btn-soft mb-3"
            >
              <i class="bi bi-arrow-left me-1-5" />
              Back to users
            </a>

            <div class="row mb-3">
              <div class="col-auto">
                <a href={`/user-id/${account.value.id.toString()}`}>
                  <img
                    class="avatar"
                    src={account.value.avatarUrl}
                    alt={t("alt.profile_picture")}
                  />
                </a>
              </div>
              <div class="col">
                <h1 class="mb-2">
                  <a
                    class="link-body-emphasis text-decoration-none"
                    href={`/user-id/${account.value.id.toString()}`}
                  >
                    {account.value.displayName}
                  </a>
                </h1>
                <div class="d-flex flex-wrap gap-3 text-body-secondary">
                  <span>
                    <i class="bi bi-calendar3 me-1" />
                    Registered{" "}
                    <Time
                      unix={account.value.createdAt}
                      dateStyle="short"
                      timeStyle="short"
                    />
                  </span>
                  <a href={`/audit?user=${account.value.id.toString()}`}>
                    <i class="bi bi-journal-text me-1-5" />
                    Audit logs
                  </a>
                </div>

                {account.value.deleted ? (
                  <div
                    class="alert alert-secondary mt-3 mb-0"
                    role="alert"
                  >
                    <i class="bi bi-info-circle me-2" />
                    This account has been deleted
                  </div>
                ) : account.value.scheduledDeleteAt ? (
                  <div
                    class="alert alert-warning mt-3 mb-0"
                    role="alert"
                  >
                    <i class="bi bi-exclamation-triangle me-2" />
                    Scheduled for deletion on{" "}
                    <Time
                      unix={account.value.scheduledDeleteAt}
                      dateStyle="long"
                      timeStyle="short"
                    />
                  </div>
                ) : null}
              </div>

              {!account.value.deleted && (
                <div class="col-auto">
                  <StandardForm
                    method={Service.method.impersonate}
                    buildRequest={() => {
                      if (
                        !confirm(
                          "Login as this user? You will need to re-authenticate to regain admin access.",
                        )
                      ) {
                        throwAbortError()
                      }
                      return { userId: account.value.id }
                    }}
                    onSuccess={(resp) => {
                      window.location.href = resp.redirectUrl || "/"
                    }}
                    class="impersonate-form"
                  >
                    <button
                      class="btn btn-secondary"
                      type="submit"
                    >
                      Login as user
                      <i class="bi bi-box-arrow-in-right ms-1" />
                    </button>
                  </StandardForm>
                </div>
              )}
            </div>

            {!account.value.deleted && (
              <nav>
                <ul class="nav nav-underline gap-2 gap-sm-3 justify-content-around justify-content-sm-start mb-4">
                  {TABS.map(([tab, label]) => (
                    <li
                      key={tab}
                      class="nav-item"
                    >
                      <button
                        type="button"
                        class={`nav-link ${activeTab.value === tab ? "active" : ""}`}
                        onClick={() => (activeTab.value = tab)}
                      >
                        {label}
                      </button>
                    </li>
                  ))}
                </ul>
              </nav>
            )}
          </div>
        </div>

        <div class="content-body">
          <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
            {!account.value.deleted && (
              <div class="tab-content">
                {activeTab.value === "account" && renderAccountTab()}

                {activeTab.value === "connections" && (
                  <div>
                    <h3 class="mb-3">{t("settings.connected_accounts")}</h3>
                    <p>{t("settings.connections.description")}</p>
                    {connectedAccounts.length ? (
                      <div class="table-responsive">
                        <table class="table align-middle">
                          <tbody>
                            {connectedAccounts.map((connection) => (
                              <Row
                                key={connection.provider}
                                connection={connection}
                              />
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p class="text-body-secondary">No connected accounts</p>
                    )}
                  </div>
                )}

                {activeTab.value === "authorizations" && (
                  <div>
                    <h3 class="mb-3">{t("settings.authorizations.title")}</h3>
                    <p>{t("settings.authorizations.description")}</p>
                    {authorizations.length ? (
                      <ul class="applications-list list-unstyled">
                        {authorizations.map((entry) => (
                          <li key={entry.id}>
                            <ApplicationEntry entry={entry} />
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p class="text-body-secondary">No authorized applications</p>
                    )}
                  </div>
                )}

                {activeTab.value === "applications" && (
                  <div>
                    <h3 class="mb-3">{t("settings.my_applications.title")}</h3>
                    <p>{t("settings.my_applications.description")}</p>
                    {applications.length ? (
                      <ul class="applications-list list-unstyled">
                        {applications.map((entry) => (
                          <li key={entry.id}>
                            <ApplicationEntry entry={entry} />
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p class="text-body-secondary">
                        {t(
                          "settings.my_applications.you_have_not_registered_any_applications_yet",
                        )}
                      </p>
                    )}
                  </div>
                )}

                {activeTab.value === "tokens" && (
                  <div>
                    <h3 class="mb-3">{t("settings.my_tokens.title")}</h3>
                    <p>{t("settings.my_tokens.description")}</p>
                    {tokens.length ? (
                      <ul class="applications-list list-unstyled">
                        {tokens.map((token) => (
                          <li key={token.id}>
                            <TokenEntry token={token} />
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p class="text-body-secondary">
                        {t("settings.my_tokens.you_have_not_created_any_tokens_yet")}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </>
    )
  },
)
