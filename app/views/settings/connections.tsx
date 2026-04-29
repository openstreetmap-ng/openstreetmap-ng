import {
  AuthProviderIcon,
  CONFIGURED_PROVIDERS,
  getAuthProviderDescription,
  getAuthProviderTitle,
} from "@lib/auth-provider"
import { mountProtoPage } from "@lib/proto-page"
import { Action, Service as AuthProviderService } from "@lib/proto/auth_provider_pb"
import {
  Service as ConnectionsService,
  PageSchema,
  Provider,
} from "@lib/proto/settings_connections_pb"
import { StandardForm } from "@lib/standard-form"
import { useSignal } from "@preact/signals"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { Nav } from "./_nav"

export const ProviderIdentity = ({
  provider,
  children,
}: {
  provider: Provider
  children: ComponentChildren
}) => (
  <>
    <AuthProviderIcon
      provider={provider}
      class="me-3 me-lg-4"
      decorative
    />
    <div>
      <h6 class="mb-0">{getAuthProviderTitle(provider)}</h6>
      {children}
    </div>
  </>
)

const ProviderCell = ({ provider }: { provider: Provider }) => (
  <ProviderIdentity provider={provider}>
    <p class="form-text mb-0">{getAuthProviderDescription(provider)}</p>
  </ProviderIdentity>
)

const ActionCell = ({
  provider,
  connected,
  onDisconnected,
}: {
  provider: Provider
  connected: boolean
  onDisconnected: (provider: Provider) => void
}) =>
  connected ? (
    <StandardForm
      class="d-flex justify-content-end align-items-center"
      method={ConnectionsService.method.remove}
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
    <StandardForm
      class="d-flex justify-content-end align-items-center"
      method={AuthProviderService.method.startAuthorize}
      buildRequest={() => ({
        provider,
        action: Action.settings,
      })}
    >
      <button
        type="submit"
        class="btn btn-soft"
      >
        {t("action.connect")}
      </button>
    </StandardForm>
  )

const Row = ({
  provider,
  connected,
  onDisconnected,
}: {
  provider: Provider
  connected: boolean
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

mountProtoPage(PageSchema, ({ connectedProviders: initialConnectedProviders }) => {
  const connectedProviders = useSignal(initialConnectedProviders)
  const onDisconnected = (provider: Provider) => {
    connectedProviders.value = connectedProviders.value.filter(
      (entry) => entry !== provider,
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
              <Nav />
            </div>

            <div class="col-lg">
              <h3>{t("settings.connections.external_services")}</h3>
              <p>{t("settings.connections.description")}</p>

              <div class="table-responsive">
                <table class="table align-middle">
                  <tbody>
                    {CONFIGURED_PROVIDERS.map((provider) => (
                      <Row
                        provider={provider}
                        connected={connectedProviders.value.includes(provider)}
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
