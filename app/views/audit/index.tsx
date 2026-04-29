import { queryParam } from "@lib/codecs"
import { Time } from "@lib/datetime-inputs"
import { unixToLocalDatetime } from "@lib/datetime-local"
import { mountProtoPage } from "@lib/proto-page"
import {
  type EventValid,
  FiltersSchema,
  PageSchema,
  Service,
  Type,
} from "@lib/proto/audit_pb"
import { defineProtoQueryContract } from "@lib/query-contract"
import { StandardPagination } from "@lib/standard-pagination"
import { useUrlQueryState } from "@lib/url-signals"
import { UserAgentIcons } from "@lib/user-agent-icons"
import { formatPackedIp } from "@lib/utils"
import { useComputed, useSignal } from "@preact/signals"
import { t } from "i18next"
import type { SubmitEventHandler } from "preact"
import { useId } from "preact/hooks"

const AUDIT_TYPES = Object.entries(Type)
  .filter(([, value]) => typeof value === "number")
  .map(([name]) => name)

const FILTER_QUERY = defineProtoQueryContract(FiltersSchema, {
  ip: queryParam.text(),
  user: queryParam.text(),
  applicationId: queryParam.positive(),
  type: queryParam.enum(Type),
  createdAfter: queryParam.timestamp(),
  createdBefore: queryParam.timestamp(),
})

const UserCell = ({ event }: { event: EventValid }) => {
  const { user, targetUser } = event

  if (!user) return <span class="text-body-secondary">&mdash;</span>

  return (
    <>
      <a href={`/user-id/${user.id}`}>
        <img
          class="avatar me-1-5"
          src={user.avatarUrl}
          alt={t("alt.profile_picture")}
          loading="lazy"
        />
        <span class="display-name">{user.displayName}</span>
      </a>
      {targetUser && (
        <>
          <i class="bi bi-arrow-right-short me-1" />
          <a href={`/user-id/${targetUser.id}`}>
            <img
              class="avatar me-1-5"
              src={targetUser.avatarUrl}
              alt={t("alt.profile_picture")}
              loading="lazy"
            />
            <span class="display-name">{targetUser.displayName}</span>
          </a>
        </>
      )}
    </>
  )
}

const ClientCell = ({ event }: { event: EventValid }) => (
  <>
    {event.userAgent && (
      <UserAgentIcons
        userAgent={event.userAgent}
        class="me-1"
      />
    )}
    <span class="text-body-secondary">{formatPackedIp(event.ip)}</span>
  </>
)

const ApplicationCell = ({
  event,
  onFilterApplicationId,
}: {
  event: EventValid
  onFilterApplicationId: (applicationId: bigint) => void
}) => {
  const application = event.application
  if (!application) return <span class="text-body-secondary">&mdash;</span>

  return (
    <div class="d-flex align-items-center">
      <img
        class="avatar me-2"
        src={application.avatarUrl}
        alt={t("alt.application_image")}
        loading="lazy"
      />
      <div class="small">
        <div>{application.name}</div>
        <div class="lh-1">
          <button
            type="button"
            class="btn btn-link btn-sm p-0 lh-1"
            onClick={() => onFilterApplicationId(application.id)}
          >
            <code>{application.id}</code>
          </button>
          {application.owner && (
            <>
              <span class="text-body-secondary mx-1">by</span>
              <a href={`/user-id/${application.owner.id}`}>
                {application.owner.displayName}
              </a>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

const Row = ({
  event,
  onFilterApplicationId,
}: {
  event: EventValid
  onFilterApplicationId: (applicationId: bigint) => void
}) => (
  <tr>
    <td>
      <Time
        unix={event.createdAt}
        relativeStyle="short"
      />
    </td>
    <td>
      <code>{Type[event.type]}</code>
    </td>
    <td>
      <UserCell event={event} />
    </td>
    <td>
      <ClientCell event={event} />
    </td>
    <td>
      <ApplicationCell
        event={event}
        onFilterApplicationId={onFilterApplicationId}
      />
    </td>
    <td class="details-col">
      {event.extra ? (
        <div>{event.extra}</div>
      ) : (
        <span class="text-body-secondary">&mdash;</span>
      )}
    </td>
  </tr>
)

mountProtoPage(PageSchema, () => {
  const filters = useUrlQueryState(FILTER_QUERY)
  const filtersKey = useComputed(() => FILTER_QUERY.keyOf(filters.value))
  const totalItems = useSignal<number | undefined>()
  const userId = useId()
  const ipId = useId()
  const typeId = useId()
  const applicationId = useId()
  const createdAfterId = useId()
  const createdBeforeId = useId()

  const onSubmitFilters: SubmitEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault()
    filters.value = FILTER_QUERY.parseFormData(new FormData(e.currentTarget))
  }

  return (
    <>
      <div class="content-header pb-1">
        <div class="container">
          <h1>
            <i class="bi bi-card-checklist me-3" />
            Audit logs
          </h1>
          <p>View and filter system audit events.</p>

          <form
            key={filtersKey.value}
            class="filters-form"
            onSubmit={onSubmitFilters}
          >
            <div class="row g-3 mb-3">
              <div class="col-md-6">
                <label
                  class="form-label"
                  htmlFor={userId}
                >
                  {t("activerecord.models.user")}
                </label>
                <input
                  id={userId}
                  type="text"
                  class="form-control"
                  name="user"
                  defaultValue={filters.value.user}
                  placeholder="Search by name or ID"
                  autoComplete="off"
                  spellcheck={false}
                />
              </div>

              <div class="col-md-6">
                <label
                  class="form-label"
                  htmlFor={ipId}
                >
                  IP Address
                </label>
                <input
                  id={ipId}
                  type="text"
                  class="form-control"
                  name="ip"
                  defaultValue={filters.value.ip}
                  placeholder="e.g., 192.168.1.1 or 10.0.0.0/8"
                  autoComplete="off"
                  spellcheck={false}
                />
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={typeId}
                >
                  Event Type
                </label>
                <select
                  id={typeId}
                  class="form-select form-select-sm"
                  name="type"
                  defaultValue={
                    filters.value.type !== undefined ? Type[filters.value.type] : ""
                  }
                >
                  <option value="">All types</option>
                  {AUDIT_TYPES.map((name) => (
                    <option value={name}>{name}</option>
                  ))}
                </select>
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={applicationId}
                >
                  {t("settings.applications")} ID
                </label>
                <input
                  id={applicationId}
                  type="number"
                  class="form-control form-control-sm"
                  name="application_id"
                  defaultValue={filters.value.applicationId?.toString()}
                  min="1"
                  step="1"
                  placeholder="ID"
                  autoComplete="off"
                />
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={createdAfterId}
                >
                  Events from <small class="text-body-secondary">(local tz)</small>
                </label>
                <input
                  id={createdAfterId}
                  type="datetime-local"
                  class="form-control form-control-sm"
                  name="created_after"
                  defaultValue={unixToLocalDatetime(filters.value.createdAfter)}
                />
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={createdBeforeId}
                >
                  Events to <small class="text-body-secondary">(local tz)</small>
                </label>
                <input
                  id={createdBeforeId}
                  type="datetime-local"
                  class="form-control form-control-sm"
                  name="created_before"
                  defaultValue={unixToLocalDatetime(filters.value.createdBefore)}
                />
              </div>
            </div>

            <div class="text-end">
              <span class="text-muted me-2">{totalItems.value ?? "…"} events</span>
              <div
                class="btn-group"
                role="group"
              >
                <button
                  type="submit"
                  class="btn btn-outline-primary"
                >
                  <i class="bi bi-funnel" /> Apply
                </button>
                <button
                  type="button"
                  class="btn btn-outline-secondary"
                  onClick={() => (filters.value = FILTER_QUERY.parseSearch(""))}
                >
                  <i class="bi bi-arrow-counterclockwise" /> Clear
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>

      <div class="content-body">
        <div class="container">
          <StandardPagination
            method={Service.method.list}
            request={{ filters: filters.value }}
            urlKey="page"
            navTop
            navClassTop="mb-2"
            navClassBottom="mb-0"
            onLoad={(data) => {
              totalItems.value =
                data.state.totalExtent.case === "knownTotal"
                  ? data.state.totalExtent.value.numItems
                  : undefined
            }}
          >
            {(data) => (
              <div class="table-responsive">
                <table class="table table-sm table-hover align-middle">
                  <thead>
                    <tr>
                      <th scope="col">Time</th>
                      <th scope="col">Type</th>
                      <th scope="col">{t("activerecord.models.user")}</th>
                      <th scope="col">Client</th>
                      <th scope="col">{t("settings.applications")}</th>
                      <th scope="col">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.events.length ? (
                      data.events.map((event) => (
                        <Row
                          key={event.id}
                          event={event}
                          onFilterApplicationId={(nextApplicationId) =>
                            (filters.value = {
                              ...filters.value,
                              applicationId: nextApplicationId,
                            })
                          }
                        />
                      ))
                    ) : (
                      <tr>
                        <td
                          colSpan={6}
                          class="text-center text-muted py-4"
                        >
                          No audit events found matching your filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </StandardPagination>
        </div>
      </div>
    </>
  )
})
