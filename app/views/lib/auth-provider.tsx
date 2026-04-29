import { CONFIGURED_AUTH_PROVIDERS } from "@lib/config"
import { Provider } from "@lib/proto/settings_connections_pb"
import { t } from "i18next"

export const CONFIGURED_PROVIDERS = CONFIGURED_AUTH_PROVIDERS.map(
  (providerName) => Provider[providerName],
)

export const getAuthProviderName = (provider: Provider) => Provider[provider]

export const getAuthProviderTitle = (provider: Provider) =>
  t(`service.${getAuthProviderName(provider)}.title`)

export const getAuthProviderDescription = (provider: Provider) =>
  t(`service.${getAuthProviderName(provider)}.description`)

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

  return provider === Provider.facebook || provider === Provider.github ? (
    <i
      class={`${className} bi bi-${providerName}`}
      aria-hidden={decorative ? "true" : undefined}
      title={decorative ? undefined : title}
    />
  ) : (
    <img
      class={className}
      src={`/static/img/brand/${providerName}.webp`}
      alt={decorative ? "" : t("alt.logo", { name: title })}
    />
  )
}
