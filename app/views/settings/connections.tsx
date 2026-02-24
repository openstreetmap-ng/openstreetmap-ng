import type { Page_EntryValid } from "@lib/proto/settings_connections_pb"
import { PageSchema, Provider, Service } from "@lib/proto/settings_connections_pb"
import { mountProtoPage } from "@lib/proto-page"
import { StandardForm } from "@lib/standard-form"
import { useSignal } from "@preact/signals"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { SettingsNav } from "./_nav"

export const ProviderIdentity = ({
  provider,
  children,
}: {
  provider: Provider
  children: ComponentChildren
}) => {
  const providerName = Provider[provider]
  return (
    <>
      {provider === Provider.facebook || provider === Provider.github ? (
        <i class={`auth-provider-icon me-3 me-lg-4 bi bi-${providerName}`} />
      ) : (
        <img
          class="auth-provider-icon me-3 me-lg-4"
          src={`/static/img/brand/${providerName}.webp`}
          alt={t("alt.service_image")}
        />
      )}
      <div>
        <h6 class="mb-0">{t(`service.${providerName}.title`)}</h6>
        {children}
      </div>
    </>
  )
}

const ProviderCell = ({ provider }: { provider: Provider }) => {
  const providerName = Provider[provider]

  return (
    <ProviderIdentity provider={provider}>
      <p class="form-text mb-0">{t(`service.${providerName}.description`)}</p>
    </ProviderIdentity>
  )
}

const ActionCell = ({
  provider,
  connected,
  onDisconnected,
}: {
  provider: Provider
  connected: boolean
  onDisconnected: (provider: Provider) => void
}) => {
  const providerName = Provider[provider]

  return connected ? (
    <StandardForm
      class="d-flex justify-content-end align-items-center"
      method={Service.method.remove}
      buildRequest={() => ({ provider })}
      onSuccess={(_, ctx) => onDisconnected(ctx.request.provider)}
    >
      <i
        class="bi bi-link-45deg me-2"
        title={t("state.connected")}
      />
      <button
        type="submit"
        class="btn btn-soft"
      >
        {t("action.disconnect")}
      </button>
    </StandardForm>
  ) : (
    <form
      class="d-flex justify-content-end align-items-center"
      method="POST"
      action={`/oauth2/${providerName}/authorize`}
    >
      <button
        type="submit"
        class="btn btn-soft"
        name="action"
        value="settings"
      >
        {t("action.connect")}
      </button>
    </form>
  )
}

const Row = ({
  entry: { provider, connected },
  onDisconnected,
}: {
  entry: Page_EntryValid
  onDisconnected: (provider: Provider) => void
}) => (
  <tr>
    <td class="d-flex align-items-center">
      <ProviderCell provider={provider} />
    </td>
    <td>
      <ActionCell
        provider={provider}
        connected={connected}
        onDisconnected={onDisconnected}
      />
    </td>
  </tr>
)

mountProtoPage(PageSchema, ({ providers: initialProviders }) => {
  const providers = useSignal(initialProviders)
  const onDisconnected = (provider: Provider) => {
    providers.value = providers.value.map((entry) =>
      entry.provider === provider ? ((entry.connected = false), entry) : entry,
    )
  }

  return (
    <>
      <div class="content-header">
        <h1 class="container">{t("settings.connected_accounts")}</h1>
      </div>

      <div class="content-body">
        <div class="container">
          <div class="row">
            <div class="col-lg-auto mb-4">
              <SettingsNav />
            </div>

            <div class="col-lg">
              <h3>{t("settings.connections.external_services")}</h3>
              <p>{t("settings.connections.description")}</p>

              <div class="table-responsive">
                <table class="table align-middle">
                  <tbody>
                    {providers.value.map((entry) => (
                      <Row
                        key={entry.provider}
                        entry={entry}
                        onDisconnected={onDisconnected}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
})
