import type { MessageInitShape } from "@bufbuild/protobuf"
import { ENV } from "@lib/config"
import {
  CredentialsSchema,
  LoginRequestSchema,
  type LoginResponse,
  type PasskeyAssertion,
  Service,
} from "@lib/proto/auth_pb"
import { Action } from "@lib/proto/auth_provider_pb"
import { PageSchema as LoginPageSchema } from "@lib/proto/login_pb"
import { mountProtoPage } from "@lib/proto-page"
import { StandardForm } from "@lib/standard-form"
import { NON_DIGIT_RE, throwAbortError } from "@lib/utils"
import { getPasskeyAssertion, startConditionalMediation } from "@lib/webauthn"
import { useSignal } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { Modal } from "bootstrap"
import { t } from "i18next"
import type { RefObject } from "preact"
import { render } from "preact"
import type { MutableRef } from "preact/hooks"
import { useEffect, useId, useRef } from "preact/hooks"
import { useDisposeEffect } from "../lib/dispose-scope"
import { getAuthProviderReferer } from "./_auth-provider-referer"
import { AuthSwitcher } from "./_auth-switcher"
import { TestSiteReminder } from "./_test-site-reminder"

enum LoginState {
  credentials,
  passkey,
  totp,
  recovery,
  methodSelect,
}

enum SubmitMode {
  none,
  passkey,
  passwordless,
}

const TEST_LOGINS = ["user1", "user2", "moderator", "admin"] as const

const MethodButton = ({
  icon,
  title,
  description,
  onClick,
}: {
  icon: string
  title: string
  description: string
  onClick: () => void
}) => (
  <button
    type="button"
    class="list-group-item list-group-item-action d-flex align-items-center gap-3 py-3"
    onClick={onClick}
  >
    <i class={`bi ${icon} fs-4 text-secondary`} />
    <span class="flex-grow-1">
      <strong class="d-block">{title}</strong>
      <small class="text-body-secondary">{description}</small>
    </span>
    <i class="bi bi-chevron-right text-body-tertiary" />
  </button>
)

const TotpCodeInputs = ({
  digits,
  inputRefs,
  onComplete,
}: {
  digits: number
  inputRefs: MutableRef<HTMLInputElement[]>
  onComplete: () => void
}) => {
  const refs = inputRefs.current

  return (
    <div class="totp-input-group d-flex justify-content-center gap-1">
      {Array.from({ length: digits }, (_, index) => (
        <input
          key={index}
          ref={(el) => {
            if (el) refs[index] = el
          }}
          type="text"
          class="form-control"
          maxlength={1}
          inputmode="numeric"
          pattern="[0-9]"
          autocomplete="one-time-code"
          onInput={(e) => {
            const input = e.currentTarget
            let value = input.value
            if (value.length !== 1 || value < "0" || value > "9") value = ""
            input.value = value

            if (!value) return
            if (index < digits - 1) {
              const nextInput = refs[index + 1]
              nextInput?.focus()
              nextInput?.select()
            } else {
              onComplete()
            }
          }}
          onKeyDown={(e) => {
            if (e.isComposing) return

            const prevInput = refs[index - 1]
            const nextInput = refs[index + 1]
            const value = e.currentTarget.value
            if (e.key === "Enter") {
              e.preventDefault()
              onComplete()
            } else if (e.key === "Backspace" && !value && prevInput) {
              prevInput.focus()
              prevInput.select()
            } else if (e.key === "ArrowLeft" && prevInput) {
              e.preventDefault()
              prevInput.focus()
              prevInput.select()
            } else if (e.key === "ArrowRight" && nextInput) {
              e.preventDefault()
              nextInput.focus()
              nextInput.select()
            }
          }}
          onFocus={(e) => e.currentTarget.select()}
          onPaste={(e) => {
            e.preventDefault()
            const clipboardData = e.clipboardData
            if (!clipboardData) return

            const digitsOnly = clipboardData.getData("text").replace(NON_DIGIT_RE, "")
            if (!digitsOnly.length) return

            for (let i = 0; i < digitsOnly.length && index + i < digits; i++) {
              const input = refs[index + i]
              if (input) input.value = digitsOnly[i]!
            }

            const focusIndex = Math.min(index + digitsOnly.length, digits - 1)
            refs[focusIndex]?.focus()
            onComplete()
          }}
        />
      ))}
    </div>
  )
}

const FormActionButtons = ({
  onCancel,
  onSubmit,
}: {
  onCancel: () => void
  onSubmit?: () => void
}) => (
  <div class="d-flex gap-2 mt-3">
    <button
      class="btn btn-soft"
      type="button"
      onClick={onCancel}
    >
      {t("action.cancel")}
    </button>
    <button
      class="btn btn-primary fw-medium flex-grow-1"
      type={onSubmit ? "button" : "submit"}
      onClick={onSubmit}
    >
      {t("login.sign_in")}
    </button>
  </div>
)

const CredentialsPane = ({
  displayNameInputRef,
  passwordInputRef,
  rememberInputRef,
}: {
  displayNameInputRef: RefObject<HTMLInputElement>
  passwordInputRef: RefObject<HTMLInputElement>
  rememberInputRef: RefObject<HTMLInputElement>
}) => (
  <>
    <label class="form-label d-block mb-2">
      {t("sessions.new.email or username")}
      <TestSiteReminder>
        <input
          ref={displayNameInputRef}
          type="text"
          class="form-control mt-2"
          name="display_name_or_email"
          // oxlint-disable-next-line jsx_a11y/autocomplete-valid
          autocomplete="username webauthn"
          autocapitalize="none"
          required
        />
      </TestSiteReminder>
    </label>

    <label class="form-label d-block mb-3">
      {t("sessions.new.password")}
      <input
        ref={passwordInputRef}
        type="password"
        class="form-control mt-2"
        name="password"
        autocomplete="current-password"
        required
      />
    </label>

    <div class="d-flex justify-content-between align-items-center mx-1 mb-3">
      <div class="form-check">
        <label class="form-check-label">
          <input
            ref={rememberInputRef}
            class="form-check-input"
            type="checkbox"
            name="remember"
            value="True"
            autocomplete="off"
          />
          {t("sessions.new.remember")}
        </label>
      </div>
      <a
        class="link-primary small"
        href="/reset-password"
      >
        {t("sessions.new.lost password link")}
      </a>
    </div>

    <button
      class="btn btn-primary w-100 fw-medium"
      type="submit"
    >
      {t("login.sign_in")}
    </button>
  </>
)

const PasskeyPane = ({
  onRetry,
  onTryAnotherMethod,
}: {
  onRetry: () => void
  onTryAnotherMethod: () => void
}) => (
  <div>
    <p class="text-center text-body-secondary mb-3">
      {t("two_fa.could_not_complete_passkey_verification")}
    </p>
    <button
      class="btn btn-primary fw-medium w-100 mb-3"
      type="button"
      onClick={onRetry}
    >
      <i class="bi bi-arrow-clockwise me-1-5" />
      {t("two_fa.retry_passkey")}
    </button>
    <div class="text-center">
      <button
        class="btn btn-link btn-sm p-0"
        type="button"
        onClick={onTryAnotherMethod}
      >
        {t("two_fa.try_another_method")}
      </button>
    </div>
  </div>
)

const TotpPane = ({
  digits,
  inputRefs,
  onComplete,
  onTryAnotherMethod,
  onCancel,
}: {
  digits: number
  inputRefs: MutableRef<HTMLInputElement[]>
  onComplete: () => void
  onTryAnotherMethod: () => void
  onCancel: () => void
}) => (
  <div>
    <label class="form-label d-block mb-2">
      {t("two_fa.enter_two_factor_code")}
      <p class="form-text">{t("two_fa.enter_the_one_time_code_from_your_app")}</p>
      <TotpCodeInputs
        digits={digits}
        inputRefs={inputRefs}
        onComplete={onComplete}
      />
    </label>
    <div class="text-center">
      <button
        class="btn btn-link btn-sm p-0"
        type="button"
        onClick={onTryAnotherMethod}
      >
        {t("two_fa.try_another_method")}
      </button>
    </div>
    <FormActionButtons
      onCancel={onCancel}
      onSubmit={onComplete}
    />
  </div>
)

const RecoveryPane = ({
  recoveryCodeInputRef,
  onTryAnotherMethod,
  onCancel,
}: {
  recoveryCodeInputRef: RefObject<HTMLInputElement>
  onTryAnotherMethod: () => void
  onCancel: () => void
}) => (
  <div>
    <label class="form-label d-block mb-2">
      {t("two_fa.enter_recovery_code")}
      <p class="form-text">{t("two_fa.enter_one_of_your_recovery_codes")}</p>
      <input
        ref={recoveryCodeInputRef}
        type="text"
        class="form-control form-control-lg"
        name="recovery_code"
        autocomplete="off"
        autocapitalize="none"
        inputmode="text"
        maxlength={14}
      />
    </label>
    <div class="text-center">
      <button
        class="btn btn-link btn-sm p-0"
        type="button"
        onClick={onTryAnotherMethod}
      >
        {t("two_fa.try_another_method")}
      </button>
    </div>
    <FormActionButtons onCancel={onCancel} />
  </div>
)

const MethodSelectPane = ({
  loginResponse,
  onPasskey,
  onTotp,
  onRecovery,
  onBypass,
  onCancel,
}: {
  loginResponse: LoginResponse | undefined
  onPasskey: () => void
  onTotp: () => void
  onRecovery: () => void
  onBypass: () => void
  onCancel: () => void
}) => (
  <div class="login-methods">
    <p class="text-center text-body-secondary mb-3">
      {t("two_fa.choose_how_to_verify")}
    </p>
    <div class="list-group list-group-flush mb-3">
      {[
        ...(loginResponse?.passkey
          ? [
              {
                icon: "bi-fingerprint",
                title: t("two_fa.passkeys"),
                description: t("two_fa.use_biometrics_or_security_keys"),
                onClick: onPasskey,
              },
            ]
          : []),
        ...(loginResponse?.totp
          ? [
              {
                icon: "bi-phone",
                title: t("two_fa.authenticator_app"),
                description: t("two_fa.enter_the_code_from_your_authenticator_app"),
                onClick: onTotp,
              },
            ]
          : []),
        ...(loginResponse?.recovery
          ? [
              {
                icon: "bi-file-text",
                title: t("two_fa.recovery_codes"),
                description: t("two_fa.use_one_of_your_saved_recovery_codes"),
                onClick: onRecovery,
              },
            ]
          : []),
        ...(ENV !== "prod"
          ? [
              {
                icon: "bi-skip-forward",
                title: "Bypass 2FA",
                description: "This is a testing environment",
                onClick: onBypass,
              },
            ]
          : []),
      ].map(({ icon, title, description, onClick }) => (
        <MethodButton
          icon={icon}
          title={title}
          description={description}
          onClick={onClick}
        />
      ))}
    </div>
    <button
      class="btn btn-soft w-100"
      type="button"
      onClick={onCancel}
    >
      {t("action.cancel")}
    </button>
  </div>
)

const LoginCard = ({
  modalRef,
  titleId,
}: {
  modalRef?: RefObject<HTMLDivElement | null>
  titleId?: string
}) => {
  const isModal = modalRef !== undefined
  const referrer = getAuthProviderReferer()
  const loginState = useSignal(LoginState.credentials)
  const showAuthProviders = useSignal(false)
  const formRef = useRef<HTMLFormElement>(null)
  const displayNameInputRef = useRef<HTMLInputElement>(null)
  const passwordInputRef = useRef<HTMLInputElement>(null)
  const recoveryCodeInputRef = useRef<HTMLInputElement>(null)
  const rememberInputRef = useRef<HTMLInputElement>(null)
  const totpInputRefs = useRef<HTMLInputElement[]>([])
  const credentialsRef = useRef<{
    credentials: MessageInitShape<typeof CredentialsSchema>
    remember: boolean
  }>()
  const submitModeRef = useRef(SubmitMode.none)
  const bypass2faRef = useRef(false)
  const passkeyAssertionRef = useRef<PasskeyAssertion>()
  const pageMediationStartedRef = useRef(false)
  const conditionalMediationAbortRef = useRef<AbortController>()
  const loginResponseRef = useRef<LoginResponse>()

  const getTotpCode = () => {
    const digits = loginResponseRef.current?.totp ?? 0
    if (!digits) return null

    let code = ""
    for (let i = 0; i < digits; i++) {
      const value = totpInputRefs.current[i]?.value ?? ""
      if (value.length !== 1) return null
      code += value
    }
    return Number.parseInt(code, 10)
  }

  const resetLoginState = () => {
    conditionalMediationAbortRef.current?.abort()
    conditionalMediationAbortRef.current = undefined
    loginResponseRef.current = undefined
    loginState.value = LoginState.credentials
    showAuthProviders.value = false
    credentialsRef.current = undefined
    submitModeRef.current = SubmitMode.none
    bypass2faRef.current = false
    passkeyAssertionRef.current = undefined
    if (formRef.current) formRef.current.reset()
  }

  const setLoginState = (state: LoginState) => {
    loginState.value = state
    if (state === LoginState.totp) {
      queueMicrotask(() => {
        const digits = loginResponseRef.current?.totp ?? 0
        for (let i = 0; i < digits; i++) {
          const input = totpInputRefs.current[i]
          if (input) input.value = ""
        }
        totpInputRefs.current[0]?.focus()
      })
    } else if (state === LoginState.recovery) {
      if (recoveryCodeInputRef.current) {
        recoveryCodeInputRef.current.value = ""
      }
      queueMicrotask(() => recoveryCodeInputRef.current?.focus())
    }
  }

  const tryTotpSubmit = () => {
    if (!getTotpCode()) return false
    formRef.current!.requestSubmit()
    return true
  }

  const requestSubmitPasswordless = () => {
    submitModeRef.current = SubmitMode.passwordless
    displayNameInputRef.current!.required = false
    passwordInputRef.current!.required = false
    formRef.current!.requestSubmit()
  }

  const requestSubmitPasskey = () => {
    submitModeRef.current = SubmitMode.passkey
    formRef.current!.requestSubmit()
  }

  const initConditionalMediation = async () => {
    resetLoginState()
    conditionalMediationAbortRef.current = new AbortController()
    const assertion = await startConditionalMediation(
      conditionalMediationAbortRef.current.signal,
    )
    if (!assertion) return
    passkeyAssertionRef.current = assertion
    requestSubmitPasswordless()
  }

  useDisposeEffect(
    (scope) => {
      if (!modalRef?.current) return

      scope.dom(modalRef.current, "show.bs.modal", initConditionalMediation)
      scope.dom(modalRef.current, "hidden.bs.modal", resetLoginState)
    },
    [modalRef],
  )

  useEffect(() => {
    let timeoutId: number | undefined
    if (!isModal && !pageMediationStartedRef.current) {
      pageMediationStartedRef.current = true
      timeoutId = window.setTimeout(() => {
        void initConditionalMediation()
      }, 100)
    }

    return () => {
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
      conditionalMediationAbortRef.current?.abort()
    }
  }, [isModal])

  const form = (
    <StandardForm
      class="login-form"
      formRef={formRef}
      method={Service.method.login}
      buildRequest={async ({ formData, passwords }) => {
        const nextCredentials = (() => {
          const displayNameOrEmail = formData.get("display_name_or_email")
          const password = passwords.password
          if (
            !(typeof displayNameOrEmail === "string" && displayNameOrEmail && password)
          )
            return

          credentialsRef.current = {
            credentials: {
              displayNameOrEmail,
              password,
            },
            remember: formData.has("remember"),
          }
          return credentialsRef.current.credentials
        })()

        const submitMode = submitModeRef.current
        const isPasswordless = submitMode === SubmitMode.passwordless
        submitModeRef.current = SubmitMode.none

        const credentials =
          nextCredentials ??
          (isPasswordless ? undefined : credentialsRef.current?.credentials)

        if (
          !credentials &&
          (loginState.value !== LoginState.credentials ||
            submitMode === SubmitMode.passkey)
        ) {
          throw new Error("Missing login credentials state")
        }

        let passkey = passkeyAssertionRef.current
        if (submitMode !== SubmitMode.none) {
          conditionalMediationAbortRef.current?.abort()

          if (isPasswordless) {
            displayNameInputRef.current!.required = true
            passwordInputRef.current!.required = true
          }

          const result =
            passkey ??
            (await getPasskeyAssertion(
              credentials,
              isPasswordless ? "required" : "discouraged",
            ))
          passkeyAssertionRef.current = undefined

          if (!result) {
            if (!isPasswordless) setLoginState(LoginState.passkey)
            throwAbortError()
          }
          passkey = result
        }

        const request: MessageInitShape<typeof LoginRequestSchema> = {}
        if (credentials) request.credentials = credentials
        if (passkey) request.passkey = passkey

        if (loginState.value === LoginState.totp) {
          request.totpCode = getTotpCode() ?? throwAbortError()
        } else if (loginState.value === LoginState.recovery) {
          const recoveryCode = formData.get("recovery_code")
          if (typeof recoveryCode === "string" && recoveryCode) {
            request.recoveryCode = recoveryCode
          }
        }

        if (bypass2faRef.current) {
          bypass2faRef.current = false
          request.bypass2fa = true
        }

        if (nextCredentials) {
          request.remember = formData.has("remember")
        } else if (credentialsRef.current?.remember) {
          request.remember = true
        }

        return request
      }}
      onSuccess={(resp, ctx) => {
        const needsTwoFactor = Boolean(resp.passkey || resp.totp || resp.recovery)
        loginResponseRef.current = needsTwoFactor ? resp : undefined

        if (resp.passkey) {
          queueMicrotask(requestSubmitPasskey)
          return
        }
        if (resp.totp) {
          setLoginState(LoginState.totp)
          return
        }
        if (resp.recovery) {
          setLoginState(LoginState.methodSelect)
          return
        }
        ctx.redirect(referrer)
      }}
    >
      <div hidden={loginState.value !== LoginState.credentials}>
        <CredentialsPane
          displayNameInputRef={displayNameInputRef}
          passwordInputRef={passwordInputRef}
          rememberInputRef={rememberInputRef}
        />
      </div>
      <div hidden={loginState.value !== LoginState.passkey}>
        <PasskeyPane
          onRetry={requestSubmitPasskey}
          onTryAnotherMethod={() => setLoginState(LoginState.methodSelect)}
        />
      </div>
      <div hidden={loginState.value !== LoginState.totp}>
        <TotpPane
          digits={loginResponseRef.current?.totp ?? 0}
          inputRefs={totpInputRefs}
          onComplete={tryTotpSubmit}
          onTryAnotherMethod={() => setLoginState(LoginState.methodSelect)}
          onCancel={resetLoginState}
        />
      </div>
      <div hidden={loginState.value !== LoginState.recovery}>
        <RecoveryPane
          recoveryCodeInputRef={recoveryCodeInputRef}
          onTryAnotherMethod={() => setLoginState(LoginState.methodSelect)}
          onCancel={resetLoginState}
        />
      </div>
      <div hidden={loginState.value !== LoginState.methodSelect}>
        <MethodSelectPane
          loginResponse={loginResponseRef.current}
          onPasskey={requestSubmitPasskey}
          onTotp={() => setLoginState(LoginState.totp)}
          onRecovery={() => setLoginState(LoginState.recovery)}
          onBypass={() => {
            bypass2faRef.current = true
            formRef.current!.requestSubmit()
          }}
          onCancel={resetLoginState}
        />
      </div>
    </StandardForm>
  )

  return (
    <div class="modal-content">
      <div class={`modal-header border-0 ${isModal ? "pb-0" : ""}`}>
        {isModal && (
          <button
            class="btn-close"
            aria-label={t("javascripts.close")}
            type="button"
            data-bs-dismiss="modal"
          />
        )}
      </div>

      <div class="login-body modal-body px-4 pt-0">
        <div class="text-center mb-4">
          <img
            class="brand-img mb-2"
            src="/static/img/favicon/256.webp"
            alt={t("alt.logo", { name: t("project_name") })}
          />
          <h4
            id={titleId}
            class="modal-title"
          >
            {t("login.welcome_back")}
          </h4>
          <p class="form-text mt-0">
            {t("sessions.new.no account")}{" "}
            <a
              href="/signup"
              class="link-primary"
            >
              {t("sessions.new.register now")}
            </a>
          </p>
        </div>

        <AuthSwitcher
          class="mb-2"
          action={Action.login}
          showProviders={showAuthProviders}
          referer={referrer}
        >
          <>
            {form}

            <div class="divider my-3">
              <span class="divider-text">{t("login.or_continue_with")}</span>
            </div>

            <button
              class="passkey-login btn btn-soft w-100"
              type="button"
              onClick={() => {
                resetLoginState()
                requestSubmitPasswordless()
              }}
            >
              <img
                class="dark-filter-invert"
                src="/static/img/brand/passkeys-black.webp"
                alt={t("alt.passkey_icon")}
                draggable={false}
                loading="lazy"
              />
              {t("login.sign_in_with_a_passkey")}
            </button>
          </>
        </AuthSwitcher>
      </div>

      {ENV !== "prod" && (
        <div class="modal-footer">
          {TEST_LOGINS.map((login) => (
            <button
              class="btn btn-sm btn-secondary"
              type="button"
              onClick={() => {
                resetLoginState()
                displayNameInputRef.current!.value = login
                passwordInputRef.current!.value = "x"
                rememberInputRef.current!.checked = true
                formRef.current!.requestSubmit()
              }}
            >
              {login}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const LoginModal = () => {
  const modalRef = useRef<HTMLDivElement>(null)
  const titleId = useId()

  return (
    <div
      ref={modalRef}
      class="LoginModal modal fade"
      tabIndex={-1}
      aria-labelledby={titleId}
      aria-hidden="true"
    >
      <div class="modal-dialog modal-dialog-centered">
        <LoginCard
          modalRef={modalRef}
          titleId={titleId}
        />
      </div>
    </div>
  )
}

const getLoginModal = memoize(() => {
  const root = document.createElement("div")
  render(<LoginModal />, root)
  document.body.append(root)
  return new Modal(root.firstElementChild!)
})

export const showLoginModal = () => {
  if (document.body.classList.contains(LoginPageSchema.typeName)) {
    const input = document.querySelector(
      '[data-page-root] input[name="display_name_or_email"]',
    )!
    input.focus()
    input.select()
    return
  }

  getLoginModal().show()
}

mountProtoPage(LoginPageSchema, () => (
  <>
    <div class="content-header" />
    <div class="content-body">
      <div class="container">
        <div
          class="LoginModal modal position-static d-block"
          tabIndex={-1}
        >
          <div class="modal-dialog modal-dialog-centered">
            <LoginCard />
          </div>
        </div>
      </div>
    </div>
  </>
))
