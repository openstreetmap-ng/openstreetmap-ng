import { ConnectError } from "@connectrpc/connect"
import { BTooltip } from "@lib/bootstrap"
import {
  config,
  PASSKEY_LIMIT,
  PASSWORD_MIN_LENGTH,
  primaryLanguage,
} from "@lib/config"
import { dateTimeFormat } from "@lib/format"
import { tRich } from "@lib/i18n"
import {
  type Page_SessionValid,
  PageSchema,
  type PasskeyValid,
  Service,
} from "@lib/proto/settings_security_pb"
import { mountProtoPage } from "@lib/proto-page"
import { qsEncode } from "@lib/qs"
import { connectErrorToMessage, rpcUnary } from "@lib/rpc"
import { StandardForm } from "@lib/standard-form"
import { UserAgentIcons } from "@lib/user-agent-icons"
import { formatPackedIp } from "@lib/utils"
import { getPasskeyRegistration } from "@lib/webauthn"
import { useSignal } from "@preact/signals"
import { t } from "i18next"
import { useRef } from "preact/hooks"
import {
  DISABLE_AUTH_METHOD_MODAL_ID,
  type DisableAuthMethodContext,
  DisableAuthMethodModal,
} from "./_disable-auth-method-modal"
import {
  GENERATE_RECOVERY_CODES_MODAL_ID,
  GenerateRecoveryCodesModal,
} from "./_generate-recovery-codes-modal"
import { SettingsNav } from "./_nav"
import { SETUP_TOTP_MODAL_ID, SetupTotpModal } from "./_setup-totp-modal"

const formatTimestamp = (
  unix: bigint,
  dateStyle: Intl.DateTimeFormatOptions["dateStyle"] = "medium",
  timeStyle: Intl.DateTimeFormatOptions["timeStyle"] = "short",
) =>
  dateTimeFormat(primaryLanguage, {
    dateStyle,
    timeStyle,
  }).format(new Date(Number(unix) * 1000))

const PasskeyEntry = ({
  passkey,
  onRename,
  onRequestRemove,
}: {
  passkey: PasskeyValid
  onRename: (passkey: PasskeyValid) => Promise<void>
  onRequestRemove: (passkey: PasskeyValid) => void
}) => {
  const iconLight = passkey.icons[0]
  const iconDark = passkey.icons[1] ?? iconLight

  return (
    <li class="passkey-entry">
      {iconLight ? (
        <>
          <img
            class="passkey-icon-light align-text-top"
            src={iconLight}
            alt=""
            width="16"
            height="16"
          />
          <img
            class="passkey-icon-dark align-text-top"
            src={iconDark}
            alt=""
            width="16"
            height="16"
          />
        </>
      ) : (
        <i class="bi bi-key-fill text-body" />
      )}

      <span class="passkey-name ms-1">{passkey.name}</span>
      <button
        class="btn btn-sm btn-link p-0 ms-1-5"
        type="button"
        onClick={() => void onRename(passkey)}
      >
        <i class="bi bi-pencil-square" />
      </button>
      <span class="text-body-secondary mx-1-5">-</span>
      {t("two_fa.added_on_date", {
        date: formatTimestamp(passkey.createdAt),
      })}
      <button
        class="btn btn-sm btn-link p-0 ms-1-5"
        type="button"
        data-bs-toggle="modal"
        data-bs-target={`#${DISABLE_AUTH_METHOD_MODAL_ID}`}
        onClick={() => onRequestRemove(passkey)}
      >
        {t("action.remove")}
      </button>
    </li>
  )
}

const ActiveSessionEntry = ({
  session,
  onRevoke,
}: {
  session: Page_SessionValid
  onRevoke: (tokenId: bigint) => void
}) => {
  const lastActivity = session.lastActivity
  const sessionId = session.id.toString()
  const sessionIdMarkup = tRich("settings.session_id", {
    id: (
      <span class="session-id">
        {sessionId.slice(0, 5)}
        <i class="bi bi-three-dots" />
        {sessionId.slice(-7)}
      </span>
    ),
  })

  return (
    <li>
      <div class="row g-2 align-items-center">
        <div class="col-sm d-flex gap-2 gap-sm-3 align-items-center">
          {lastActivity?.userAgent && (
            <UserAgentIcons userAgent={lastActivity.userAgent} />
          )}
          <div>
            <h6 class="mb-1">
              {session.current && (
                <BTooltip title={t("settings.this_is_your_current_session")}>
                  <span
                    class="current-session me-1"
                    aria-label={t("settings.this_is_your_current_session")}
                  />
                </BTooltip>
              )}
              {lastActivity
                ? t("settings.last_seen_date_from_ip", {
                    date: formatTimestamp(lastActivity.createdAt, "long"),
                    ip: formatPackedIp(lastActivity.ip),
                  })
                : t("settings.unknown_device")}
            </h6>
            <p class="form-text mb-0">
              {sessionIdMarkup}
              <span class="text-body-secondary mx-1">&middot;</span>
              {t("settings.authorized_at", {
                date: formatTimestamp(session.authorizedAt),
              })}
            </p>
          </div>
        </div>
        <div class="col-sm-auto align-self-center text-end">
          <StandardForm
            method={Service.method.revokeToken}
            buildRequest={() => ({
              tokenId: session.id,
            })}
            onSuccess={(_, ctx) => onRevoke(ctx.request.tokenId)}
            class="d-inline"
          >
            <button
              class="btn btn-sm btn-soft"
              type="submit"
            >
              {t("action.end_session")}
            </button>
          </StandardForm>
        </div>
      </div>
    </li>
  )
}

mountProtoPage(
  PageSchema,
  ({
    email,
    passkeys: initialPasskeys,
    totpCreatedAt: initialTotpCreatedAt,
    recoveryCodesStatus: initialRecoveryCodesStatus,
    activeSessions: initialActiveSessions,
  }) => {
    const passkeys = useSignal(initialPasskeys)
    const totpCreatedAt = useSignal(initialTotpCreatedAt)
    const recoveryCodesStatus = useSignal(initialRecoveryCodesStatus)
    const activeSessions = useSignal(initialActiveSessions)
    const disableCtx = useSignal<DisableAuthMethodContext | undefined>()

    const newPasswordInputRef = useRef<HTMLInputElement>(null)
    const newPasswordConfirmInputRef = useRef<HTMLInputElement>(null)

    const syncPasswordValidity = () => {
      const mismatch =
        newPasswordInputRef.current!.value !== newPasswordConfirmInputRef.current!.value
      const message = mismatch ? t("validation.passwords_missmatch") : ""
      newPasswordInputRef.current!.setCustomValidity(message)
      newPasswordConfirmInputRef.current!.setCustomValidity(message)
    }

    const renamePasskey = async (passkey: PasskeyValid) => {
      const oldName = passkey.name
      let newName = prompt(t("two_fa.enter_new_passkey_name"), oldName)
      if (newName === null) return

      newName = newName.trim()
      if (newName === oldName) return

      try {
        const resp = await rpcUnary(Service.method.renamePasskey)({
          credentialId: passkey.credentialId,
          name: newName,
        })

        passkeys.value = passkeys.value.map((entry) =>
          entry.credentialId === passkey.credentialId
            ? ((entry.name = resp.name), entry)
            : entry,
        )
      } catch (error) {
        alert(connectErrorToMessage(ConnectError.from(error)))
      }
    }

    return (
      <>
        <div class="content-header">
          <h1 class="container">{t("settings.password_and_security")}</h1>
        </div>

        <div class="content-body">
          <div class="container">
            <div class="row">
              <div class="col-lg-auto mb-4">
                <SettingsNav />
              </div>

              <div class="col-lg">
                <h3 class="mb-3">{t("settings.change_password")}</h3>
                <StandardForm
                  method={Service.method.changePassword}
                  buildRequest={({ formData, passwords }) => ({
                    oldPassword: passwords.old_password,
                    newPassword: passwords.new_password,
                    revokeOtherSessions:
                      formData.get("revoke_other_sessions") === "true",
                  })}
                  onSuccess={(_, ctx) => {
                    newPasswordInputRef.current!.setCustomValidity("")
                    newPasswordConfirmInputRef.current!.setCustomValidity("")
                    if (ctx.request.revokeOtherSessions) {
                      activeSessions.value = activeSessions.value.filter(
                        (entry) => entry.current,
                      )
                    }
                  }}
                  resetOnSuccess
                >
                  <input
                    type="text"
                    name="display_name"
                    value={config.userConfig!.user.displayName}
                    autoComplete="username"
                    readOnly
                    hidden
                  />

                  <label class="form-label d-block mb-3">
                    <span class="required">{t("settings.current_password")}</span>
                    <input
                      type="password"
                      class="form-control mt-2"
                      name="old_password"
                      autoComplete="current-password"
                      required
                    />
                  </label>

                  <label class="form-label d-block mb-3">
                    <span class="required">{t("settings.new_password")}</span>
                    <input
                      type="password"
                      class="form-control mt-2"
                      name="new_password"
                      minLength={PASSWORD_MIN_LENGTH}
                      autoComplete="new-password"
                      required
                      ref={newPasswordInputRef}
                      onInput={syncPasswordValidity}
                    />
                  </label>

                  <label class="form-label d-block mb-3">
                    <span class="required">{t("settings.new_password_repeat")}</span>
                    <input
                      type="password"
                      class="form-control mt-2"
                      name="new_password_confirm"
                      minLength={PASSWORD_MIN_LENGTH}
                      autoComplete="new-password"
                      required
                      ref={newPasswordConfirmInputRef}
                      onInput={syncPasswordValidity}
                    />
                  </label>

                  <div class="row g-2 g-md-3 align-items-center">
                    <div class="col-md form-check ms-1">
                      <label class="form-check-label">
                        <input
                          class="form-check-input"
                          type="checkbox"
                          name="revoke_other_sessions"
                          value="true"
                          autoComplete="off"
                        />
                        {t("settings.logout_from_browsers")}
                      </label>
                    </div>
                    <div class="col-md-auto text-end">
                      <a
                        class="link-primary me-3"
                        href="/reset-password"
                      >
                        {t("sessions.new.lost password link")}
                      </a>
                      <button
                        class="btn btn-primary px-3"
                        type="submit"
                      >
                        {t("action.submit")}
                      </button>
                    </div>
                  </div>
                </StandardForm>

                <hr class="my-4" />

                <h3>{t("two_fa.two_factor_methods")}</h3>
                <p>
                  {t(
                    "two_fa.secure_your_account_using_additional_verification_methods",
                  )}
                </p>
                <ul class="two-factor-methods list-unstyled mx-2">
                  <li>
                    <div class="row g-2 align-items-center">
                      <div class="col-sm d-flex gap-2 gap-sm-3">
                        <i class="bi bi-fingerprint two-factor-icon" />
                        <div>
                          <h6 class="d-flex align-items-center mb-0">
                            {t("two_fa.passkeys")}
                            {passkeys.value.length > 0 && (
                              <span class="enabled-badge">{t("state.enabled")}</span>
                            )}
                          </h6>
                          <p class="form-text mb-0">
                            {t(
                              "two_fa.sign_in_securely_with_biometrics_or_security_keys",
                            )}
                          </p>

                          {passkeys.value.length > 0 && (
                            <ul class="metadata list-unstyled mt-0 mb-0">
                              {passkeys.value.map((passkey) => (
                                <PasskeyEntry
                                  key={passkey.credentialId.toString()}
                                  passkey={passkey}
                                  onRename={renamePasskey}
                                  onRequestRemove={(targetPasskey) =>
                                    (disableCtx.value = {
                                      method: "passkey",
                                      credentialId: targetPasskey.credentialId,
                                      title: t("two_fa.remove_passkey"),
                                    })
                                  }
                                />
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                      <div class="col-sm-auto text-end">
                        {passkeys.value.length < PASSKEY_LIMIT && (
                          <StandardForm
                            method={Service.method.registerPasskey}
                            buildRequest={async () => ({
                              registration: await getPasskeyRegistration(),
                            })}
                            onSuccess={(resp) => (passkeys.value = resp.passkeys)}
                            class="add-passkey-form d-inline"
                          >
                            <button
                              class="btn btn-soft"
                              type="submit"
                            >
                              {t("action.configure")}
                            </button>
                          </StandardForm>
                        )}
                      </div>
                    </div>
                  </li>

                  <li>
                    <div class="row g-2 align-items-center">
                      <div class="col-sm d-flex gap-2 gap-sm-3">
                        <i class="bi bi-phone two-factor-icon" />
                        <div>
                          <h6 class="d-flex align-items-center mb-0">
                            {t("two_fa.authenticator_app")}
                            {totpCreatedAt.value && (
                              <span class="enabled-badge">{t("state.enabled")}</span>
                            )}
                          </h6>
                          <p class="form-text mb-0">
                            {t(
                              "two_fa.require_code_from_your_mobile_authenticator_app_when_signing_in",
                            )}
                          </p>
                          {totpCreatedAt.value && (
                            <span class="metadata">
                              <i class="bi bi-clock-history me-1-5" />
                              {t("two_fa.configured_on_date", {
                                date: formatTimestamp(totpCreatedAt.value),
                              })}
                            </span>
                          )}
                        </div>
                      </div>
                      <div class="col-sm-auto text-end">
                        {totpCreatedAt.value ? (
                          <button
                            class="btn btn-soft"
                            type="button"
                            data-bs-toggle="modal"
                            data-bs-target={`#${DISABLE_AUTH_METHOD_MODAL_ID}`}
                            onClick={() =>
                              (disableCtx.value = {
                                method: "totp",
                                title: t("two_fa.disable_authenticator_app"),
                              })
                            }
                          >
                            {t("action.disable")}
                          </button>
                        ) : (
                          <button
                            class="btn btn-soft"
                            type="button"
                            data-bs-toggle="modal"
                            data-bs-target={`#${SETUP_TOTP_MODAL_ID}`}
                          >
                            {t("action.configure")}
                          </button>
                        )}
                      </div>
                    </div>
                  </li>

                  <li>
                    <div class="row g-2 align-items-center">
                      <div class="col-sm d-flex gap-2 gap-sm-3">
                        <i class="bi bi-file-text two-factor-icon" />
                        <div>
                          <h6 class="d-flex align-items-center mb-0">
                            {t("two_fa.recovery_codes")}
                            {recoveryCodesStatus.value.numRemaining > 0 && (
                              <span class="enabled-badge">
                                {t("two_fa.unused_codes_count", {
                                  count: recoveryCodesStatus.value.numRemaining,
                                })}
                              </span>
                            )}
                          </h6>
                          <p class="form-text mb-0">
                            {t(
                              "two_fa.access_your_account_if_you_lose_your_two_factor_authenticator",
                            )}
                          </p>
                          {recoveryCodesStatus.value.numRemaining > 0 && (
                            <span class="metadata">
                              <i class="bi bi-clock-history me-1-5" />
                              {t("two_fa.generated_on_date", {
                                date: formatTimestamp(
                                  recoveryCodesStatus.value.createdAt!,
                                ),
                              })}
                            </span>
                          )}
                        </div>
                      </div>
                      <div class="col-sm-auto text-end">
                        <button
                          class="btn btn-soft"
                          type="button"
                          data-bs-toggle="modal"
                          data-bs-target={`#${GENERATE_RECOVERY_CODES_MODAL_ID}`}
                        >
                          {recoveryCodesStatus.value.numRemaining > 0
                            ? t("action.regenerate")
                            : t("action.configure")}
                        </button>
                      </div>
                    </div>
                  </li>
                </ul>

                <hr class="my-4" />

                <h3>{t("settings.active_sessions")}</h3>
                <p>{t("settings.review_and_manage_your_active_login_sessions")}</p>
                <ul class="active-sessions list-unstyled mx-2">
                  {activeSessions.value.map((session) => (
                    <ActiveSessionEntry
                      key={session.id}
                      session={session}
                      onRevoke={(tokenId) => {
                        const revokedSession = activeSessions.value.find(
                          (entry) => entry.id === tokenId,
                        )

                        if (revokedSession?.current) {
                          window.location.href = `/login${qsEncode({ referer: window.location.pathname + window.location.search })}`
                          return
                        }

                        activeSessions.value = activeSessions.value.filter(
                          (entry) => entry.id !== tokenId,
                        )
                      }}
                    />
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>

        <DisableAuthMethodModal
          ctx={disableCtx}
          passkeys={passkeys}
          totpCreatedAt={totpCreatedAt}
        />
        <SetupTotpModal
          email={email}
          totpCreatedAt={totpCreatedAt}
        />
        <GenerateRecoveryCodesModal recoveryCodesStatus={recoveryCodesStatus} />
      </>
    )
  },
)
