import { CONFIGURED_AUTH_PROVIDERS } from "@lib/config"
import { Provider } from "@lib/proto/settings_connections_pb"
import { t } from "i18next"
import type { CSSProperties } from "preact"

export const CONFIGURED_PROVIDERS = CONFIGURED_AUTH_PROVIDERS.map(
  (providerName) => Provider[providerName],
)

export const getAuthProviderName = (provider: Provider) => Provider[provider]

export const getAuthProviderTitle = (provider: Provider) =>
  t(`service.${getAuthProviderName(provider)}.title`)

export const getAuthProviderDescription = (provider: Provider) =>
  t(`service.${getAuthProviderName(provider)}.description`)

type AuthProviderIconStyle = {
  color: string
  darkColor?: string
  backed?: true
}

type AuthProviderIconCssProperties = CSSProperties & {
  "--auth-provider-icon-color": string
  "--auth-provider-icon-dark-color": string
}

const AUTH_PROVIDER_ICON_STYLE: Partial<Record<Provider, AuthProviderIconStyle>> = {
  [Provider.facebook]: {
    color: "#1877f2",
    backed: true,
  },
  [Provider.github]: {
    color: "#24292e",
    darkColor: "#f6f8fa",
  },
}

export const AuthProviderIcon = ({
  provider,
  class: className = "",
  decorative = false,
}: {
  provider: Provider
  class?: string
  decorative?: boolean
}) => {
  const providerName = getAuthProviderName(provider)
  const title = decorative ? "" : getAuthProviderTitle(provider)
  const baseClass = className ? `auth-provider-icon ${className}` : "auth-provider-icon"
  const iconStyle = AUTH_PROVIDER_ICON_STYLE[provider]

  return iconStyle ? (
    <i
      class={`${baseClass} auth-provider-icon-bi${iconStyle.backed ? " auth-provider-icon-backed" : ""} bi bi-${providerName}`}
      style={
        {
          "--auth-provider-icon-color": iconStyle.color,
          "--auth-provider-icon-dark-color": iconStyle.darkColor ?? iconStyle.color,
        } satisfies AuthProviderIconCssProperties
      }
      aria-hidden={decorative ? "true" : undefined}
      title={decorative ? undefined : title}
    />
  ) : (
    <img
      class={`${baseClass} auth-provider-icon-img`}
      src={`/static/img/brand/${providerName}.webp`}
      alt={decorative ? "" : t("alt.logo", { name: title })}
    />
  )
}
