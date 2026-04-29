import {
  AuthProviderIcon,
  CONFIGURED_PROVIDERS,
  getAuthProviderName,
  getAuthProviderTitle,
} from "@lib/auth-provider"
import { Action, Service } from "@lib/proto/auth_provider_pb"
import { Provider } from "@lib/proto/settings_connections_pb"
import { StandardForm } from "@lib/standard-form"
import type { Signal } from "@preact/signals"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { useRef } from "preact/hooks"
import { useDisposeEffect, useDisposeLayoutEffect } from "../lib/dispose-scope"

type AuthAction = Action.login | Action.signup

const ProviderButton = ({
  provider,
  action,
  referer,
}: {
  provider: Provider
  action: AuthAction
  referer: string | undefined
}) => {
  const isLogin = action === Action.login
  const providerName = getAuthProviderName(provider)
  const title = getAuthProviderTitle(provider)

  return (
    <StandardForm
      method={Service.method.startAuthorize}
      buildRequest={() => ({
        provider,
        action,
        referer,
      })}
    >
      <button
        type="submit"
        class={`btn btn-${providerName}`}
      >
        <AuthProviderIcon
          provider={provider}
          decorative
        />
        {isLogin
          ? t("login.sign_in_with_service", { service: title })
          : t("signup.sign_up_with_service", { service: title })}
      </button>
    </StandardForm>
  )
}

const ProvidersPane = ({
  action,
  referer,
}: {
  action: AuthAction
  referer: string | undefined
}) => (
  <div class="auth-providers d-grid gap-2">
    {CONFIGURED_PROVIDERS.map((provider) => (
      <ProviderButton
        provider={provider}
        action={action}
        referer={referer}
      />
    ))}
  </div>
)

export const AuthSwitcher = ({
  action,
  showProviders,
  referer,
  class: className = "",
  ctaClass = "",
  ctaButtonClass = "",
  children,
}: {
  action: AuthAction
  showProviders: Signal<boolean>
  referer?: string
  class?: string
  ctaClass?: string
  ctaButtonClass?: string
  children: ComponentChildren
}) => {
  const isLogin = action === Action.login
  const ref = useRef<HTMLDivElement>(null)

  const scrollToState = () => {
    const element = ref.current
    if (!element) return

    element.scrollTo({
      left: showProviders.value ? 999999 : 0,
    })
  }

  useDisposeLayoutEffect(() => {
    scrollToState()
  }, [showProviders.value])

  useDisposeEffect((scope) => {
    scope.dom(window, "resize", scrollToState)
  }, [])

  return (
    <>
      <div
        class={`auth-switcher ${className}`}
        ref={ref}
      >
        <div class="auth-switcher-pane">{children}</div>
        <div class="auth-switcher-pane">
          <ProvidersPane
            action={action}
            referer={referer}
          />
        </div>
      </div>

      <div class={`auth-switcher-cta ${ctaClass}`}>
        {!showProviders.value ? (
          <button
            type="button"
            class={`btn btn-link ${ctaButtonClass}`}
            onClick={() => (showProviders.value = true)}
          >
            {isLogin ? (
              <>
                <i class="bi bi-list me-1-5" />
                {t("auth_switcher.sign_in_with_a_provider")}
              </>
            ) : (
              t("auth_switcher.sign_up_with_a_provider")
            )}
          </button>
        ) : (
          <button
            type="button"
            class={`btn btn-link ${ctaButtonClass}`}
            onClick={() => (showProviders.value = false)}
          >
            <i class="bi bi-chevron-left small me-1" />
            {t("action.go_back")}
          </button>
        )}
      </div>
    </>
  )
}
