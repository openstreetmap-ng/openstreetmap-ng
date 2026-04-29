import { BTooltip } from "@lib/bootstrap"
import { queryParam } from "@lib/codecs"
import { Time } from "@lib/datetime-inputs"
import { unixToLocalDatetime } from "@lib/datetime-local"
import { mountProtoPage } from "@lib/proto-page"
import type { ListResponse_EntryValid } from "@lib/proto/admin_users_pb"
import {
  Filters_Sort,
  FiltersSchema,
  PageSchema,
  Role,
  Service,
} from "@lib/proto/admin_users_pb"
import { defineProtoQueryContract } from "@lib/query-contract"
import { rpcUnary } from "@lib/rpc"
import { StandardPagination } from "@lib/standard-pagination"
import { useUrlQueryState } from "@lib/url-signals"
import { useComputed, useSignal } from "@preact/signals"
import { t } from "i18next"
import type { SubmitEventHandler } from "preact"
import { useId } from "preact/hooks"
import {
  copyArrayToClipboard,
  exportJsonFile,
  FilterActions,
  totalItemsFromPaginationState,
} from "../_filter-actions"
import { IpSummary } from "../_ip-summary"

const FILTER_QUERY = defineProtoQueryContract(FiltersSchema, {
  search: queryParam.text(),
  unverified: queryParam.flag(),
  roles: queryParam.enumList(Role),
  createdAfter: queryParam.timestamp(),
  createdBefore: queryParam.timestamp(),
  applicationId: queryParam.positive(),
  sort: queryParam.enum(Filters_Sort, {
    default: Filters_Sort.created_desc,
  }),
})

const IdentityCell = ({ entry: { account } }: { entry: ListResponse_EntryValid }) => (
  <>
    <a href={`/user-id/${account.id}`}>
      <img
        class="avatar me-1-5"
        src={account.avatarUrl}
        alt={t("alt.profile_picture")}
        loading="lazy"
      />
      <span class={`display-name ${account.deleted ? "text-muted" : ""}`}>
        {account.displayName}
      </span>
    </a>
    <span class="roles">
      {account.roles.map((role) => (
        <BTooltip
          key={role}
          title={
            role === Role.administrator
              ? t("users.show.role.administrator")
              : t("users.show.role.moderator")
          }
        >
          <i
            class={`bi bi-star-fill ${
              role === Role.administrator ? "text-danger" : "text-blue"
            } ms-1-5`}
          />
        </BTooltip>
      ))}
    </span>
  </>
)

const StatusCell = ({ entry: { account } }: { entry: ListResponse_EntryValid }) => (
  <>
    {!account.emailVerified && (
      <span class="badge text-bg-danger me-1">Unverified</span>
    )}
    {account.scheduledDeleteAt && (
      <span class="badge text-bg-warning me-1">Pending deletion</span>
    )}
    {account.deleted && <span class="badge text-bg-secondary">Deleted</span>}
    {account.emailVerified && !account.scheduledDeleteAt && !account.deleted && (
      <span class="text-body-secondary">&mdash;</span>
    )}
  </>
)

const TwoFactorCell = ({
  entry: { twoFactorStatus },
}: {
  entry: ListResponse_EntryValid
}) => (
  <div class="d-flex gap-1">
    {[
      { icon: "fingerprint", enabled: twoFactorStatus.hasPasskeys },
      { icon: "phone", enabled: twoFactorStatus.hasTotp },
      { icon: "file-text", enabled: twoFactorStatus.hasRecovery },
    ].map(({ icon, enabled }) => (
      <i class={`bi bi-${icon} ${enabled ? "text-success" : "text-body-tertiary"}`} />
    ))}
  </div>
)

const Row = ({ entry }: { entry: ListResponse_EntryValid }) => {
  const { account } = entry
  return (
    <tr>
      <td>
        <IdentityCell entry={entry} />
      </td>
      <td>
        <span class={account.deleted ? "text-muted" : "text-body-secondary"}>
          {account.email}
        </span>
      </td>
      <td class="status">
        <StatusCell entry={entry} />
      </td>
      <td>
        <TwoFactorCell entry={entry} />
      </td>
      <td>
        <Time
          unix={account.createdAt}
          relativeStyle="short"
        />
      </td>
      <td>
        <IpSummary ipCounts={entry.ipCounts} />
      </td>
      <td>
        <a
          href={`/admin/users/${account.id}`}
          class="link-primary me-2"
        >
          Manage
        </a>
        <a href={`/audit?user=${account.id}`}>Audit</a>
      </td>
    </tr>
  )
}

mountProtoPage(PageSchema, () => {
  const filters = useUrlQueryState(FILTER_QUERY)
  const filtersKey = useComputed(() => FILTER_QUERY.keyOf(filters.value))
  const entries = useSignal<ListResponse_EntryValid[]>([])
  const totalItems = useSignal<string | null>(null)
  const searchId = useId()
  const sortId = useId()
  const applicationIdId = useId()
  const createdAfterId = useId()
  const createdBeforeId = useId()
  const rolesId = useId()
  const unverifiedId = useId()

  const onSubmitFilters: SubmitEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)

    filters.value = FILTER_QUERY.parseFormData(formData)
  }

  const copyPage = () =>
    copyArrayToClipboard(entries.value.map((entry) => entry.account.id.toString()))

  const exportAll = async () => {
    const response = await rpcUnary(Service.method.exportIds)({
      filters: filters.value,
    })
    exportJsonFile("user-ids.json", response.ids)
  }

  return (
    <>
      <div class="content-header pb-1">
        <div class="container">
          <h1>
            <i class="bi bi-database-gear me-3" />
            Users
          </h1>
          <p>Filter and manage registered users.</p>

          <form
            key={filtersKey.value}
            class="filters-form"
            onSubmit={onSubmitFilters}
          >
            <div class="row g-3 mb-3">
              <div class="col-12">
                <label
                  class="form-label"
                  htmlFor={searchId}
                >
                  Search
                </label>
                <input
                  id={searchId}
                  type="text"
                  class="form-control"
                  name="search"
                  defaultValue={filters.value.search}
                  placeholder="Search by name, email, or IP address (e.g., @gmail.com, 192.168.1.1, 10.0.0.0/8)"
                  autoComplete="off"
                  spellcheck={false}
                />
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={sortId}
                >
                  Sort
                </label>
                <select
                  id={sortId}
                  class="form-select form-select-sm"
                  name="sort"
                  defaultValue={Filters_Sort[filters.value.sort]}
                >
                  <option value="created_desc">Newest first</option>
                  <option value="created_asc">Oldest first</option>
                  <option value="name_asc">Name (A-Z)</option>
                  <option value="name_desc">Name (Z-A)</option>
                </select>
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={applicationIdId}
                >
                  Application ID
                </label>
                <input
                  id={applicationIdId}
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
                  Registered from <small class="text-body-secondary">(local tz)</small>
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
                  Registered to <small class="text-body-secondary">(local tz)</small>
                </label>
                <input
                  id={createdBeforeId}
                  type="datetime-local"
                  class="form-control form-control-sm"
                  name="created_before"
                  defaultValue={unixToLocalDatetime(filters.value.createdBefore)}
                />
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={rolesId}
                >
                  Roles
                </label>
                <select
                  id={rolesId}
                  class="form-select form-select-sm"
                  name="roles"
                  multiple
                >
                  <option
                    value="moderator"
                    selected={filters.value.roles.includes(Role.moderator)}
                  >
                    Moderator
                  </option>
                  <option
                    value="administrator"
                    selected={filters.value.roles.includes(Role.administrator)}
                  >
                    Administrator
                  </option>
                </select>
              </div>

              <div class="col-md-1 form-check">
                <input
                  id={unverifiedId}
                  type="checkbox"
                  class="form-check-input"
                  name="unverified"
                  value="true"
                  defaultChecked={filters.value.unverified}
                />
                <label
                  class="form-check-label"
                  htmlFor={unverifiedId}
                >
                  Unverified
                </label>
              </div>
            </div>

            <FilterActions
              totalItems={totalItems.value}
              totalLabel="users"
              onCopyPage={copyPage}
              onExportAll={exportAll}
              onClear={() => (filters.value = FILTER_QUERY.parseSearch(""))}
            />
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
            onLoad={(data) => {
              totalItems.value = totalItemsFromPaginationState(data.state)
              entries.value = data.entries
            }}
          >
            {(data) => (
              <div class="table-responsive">
                <table class="table table-sm table-hover align-middle users-table">
                  <thead>
                    <tr>
                      <th scope="col">User</th>
                      <th scope="col">Email</th>
                      <th scope="col">Status</th>
                      <th scope="col">2FA</th>
                      <th scope="col">Registered</th>
                      <th scope="col">Client</th>
                      <th scope="col">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.entries.length ? (
                      data.entries.map((entry) => (
                        <Row
                          key={entry.account.id}
                          entry={entry}
                        />
                      ))
                    ) : (
                      <tr>
                        <td
                          colSpan={7}
                          class="text-center text-muted py-4"
                        >
                          No users found matching your filters.
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
