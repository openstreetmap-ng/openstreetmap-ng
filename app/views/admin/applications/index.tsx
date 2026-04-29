import { BPopover } from "@lib/bootstrap"
import { queryParam } from "@lib/codecs"
import { Time } from "@lib/datetime-inputs"
import { unixToLocalDatetime } from "@lib/datetime-local"
import { mountProtoPage } from "@lib/proto-page"
import type { ListResponse_EntryValid } from "@lib/proto/admin_applications_pb"
import {
  Filters_Sort,
  FiltersSchema,
  PageSchema,
  Service,
} from "@lib/proto/admin_applications_pb"
import { Scope } from "@lib/proto/shared_pb"
import { defineProtoQueryContract } from "@lib/query-contract"
import { rpcUnary } from "@lib/rpc"
import { SCOPE_LABEL } from "@lib/scope"
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
  owner: queryParam.text(),
  interactedUser: queryParam.text(),
  createdAfter: queryParam.timestamp(),
  createdBefore: queryParam.timestamp(),
  sort: queryParam.enum(Filters_Sort, {
    default: Filters_Sort.created_desc,
  }),
})

const InfoCell = ({ entry }: { entry: ListResponse_EntryValid }) => (
  <div class="d-flex align-items-center">
    <img
      class="avatar me-2"
      src={entry.avatarUrl}
      alt={t("alt.application_image")}
      loading="lazy"
    />
    <div class="small">
      <abbr
        class="text-decoration-none"
        title={entry.clientId}
      >
        {entry.name}
      </abbr>
      <div class="lh-1">
        <code>{entry.id}</code>
        <small class="text-body-secondary">
          <span
            class="mx-1"
            aria-hidden="true"
          >
            ·
          </span>
          {entry.confidential
            ? t("settings.confidential_client")
            : t("settings.public_client")}
        </small>
      </div>
    </div>
  </div>
)

const AuthCell = ({
  entry: { scopes, redirectUris },
}: {
  entry: ListResponse_EntryValid
}) => (
  <>
    <div>
      <i class="bi bi-link-45deg me-1" />
      {redirectUris.length > 0 ? (
        <BPopover
          content={() =>
            redirectUris.map((uri) => (
              <a
                key={uri}
                class="d-block"
                href={uri}
                target="_blank"
                rel="noopener noreferrer"
              >
                {uri}
              </a>
            ))
          }
        >
          <button
            type="button"
            class="btn btn-link btn-sm p-0 align-baseline"
          >
            {redirectUris.length} redirect URIs
          </button>
        </BPopover>
      ) : (
        "0 redirect URIs"
      )}
    </div>
    <div class="mt-1">
      <i class="bi bi-key me-1" />
      {scopes.length > 0 ? (
        <BPopover
          content={() => (
            <ul class="mb-0 ps-3">
              {scopes.map((scope) => (
                <li key={scope}>
                  {SCOPE_LABEL[scope]} <span class="scope">({Scope[scope]})</span>
                </li>
              ))}
            </ul>
          )}
        >
          <button
            type="button"
            class="btn btn-link btn-sm p-0 align-baseline"
          >
            {scopes.length} scopes
          </button>
        </BPopover>
      ) : (
        "0 scopes"
      )}
    </div>
  </>
)

const OwnerCell = ({ entry: { owner } }: { entry: ListResponse_EntryValid }) =>
  owner ? (
    <a href={`/user-id/${owner.id}`}>
      <img
        class="avatar me-1-5"
        src={owner.avatarUrl}
        alt={t("alt.profile_picture")}
        loading="lazy"
      />
      <span class="display-name">{owner.displayName}</span>
    </a>
  ) : (
    <span class="text-body-secondary">
      <i class="bi bi-shield-fill-check text-success me-2" />
      System
    </span>
  )

const Row = ({ entry }: { entry: ListResponse_EntryValid }) => (
  <tr>
    <td>
      <InfoCell entry={entry} />
    </td>
    <td class="text-body-secondary lh-sm small">
      <AuthCell entry={entry} />
    </td>
    <td>
      <OwnerCell entry={entry} />
    </td>
    <td>
      <span class="text-body-secondary">{entry.userCount}</span>
    </td>
    <td>
      <Time
        unix={entry.createdAt}
        relativeStyle="short"
      />
    </td>
    <td>
      <IpSummary ipCounts={entry.ipCounts} />
    </td>
    <td>
      <a href={`/audit?application_id=${entry.id}`}>Audit</a>
    </td>
  </tr>
)

mountProtoPage(PageSchema, () => {
  const filters = useUrlQueryState(FILTER_QUERY)
  const filtersKey = useComputed(() => FILTER_QUERY.keyOf(filters.value))
  const entries = useSignal<ListResponse_EntryValid[]>([])
  const totalItems = useSignal<string | null>(null)
  const searchId = useId()
  const sortId = useId()
  const ownerId = useId()
  const interactedUserId = useId()
  const createdAfterId = useId()
  const createdBeforeId = useId()

  const onSubmitFilters: SubmitEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)

    filters.value = FILTER_QUERY.parseFormData(formData)
  }

  const copyPage = () =>
    copyArrayToClipboard(entries.value.map((entry) => entry.id.toString()))

  const exportAll = async () => {
    const response = await rpcUnary(Service.method.exportIds)({
      filters: filters.value,
    })
    exportJsonFile("app-ids.json", response.ids)
  }

  return (
    <>
      <div class="content-header pb-1">
        <div class="container">
          <h1>
            <i class="bi bi-database-gear me-3" />
            Applications
          </h1>
          <p>Filter and inspect created applications.</p>

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
                  placeholder="Search by name or ID"
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
                </select>
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={ownerId}
                >
                  Owner
                </label>
                <input
                  id={ownerId}
                  type="text"
                  class="form-control form-control-sm"
                  name="owner"
                  defaultValue={filters.value.owner}
                  placeholder="User name or ID"
                  autoComplete="off"
                  spellcheck={false}
                />
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={interactedUserId}
                >
                  Interacted user
                </label>
                <input
                  id={interactedUserId}
                  type="text"
                  class="form-control form-control-sm"
                  name="interacted_user"
                  defaultValue={filters.value.interactedUser}
                  placeholder="User name or ID"
                  autoComplete="off"
                  spellcheck={false}
                />
              </div>

              <div class="col-6 col-md-2">
                <label
                  class="form-label"
                  htmlFor={createdAfterId}
                >
                  Created from <small class="text-body-secondary">(local tz)</small>
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
                  Created to <small class="text-body-secondary">(local tz)</small>
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

            <FilterActions
              totalItems={totalItems.value}
              totalLabel="applications"
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
                <table class="table table-sm table-hover align-middle">
                  <thead>
                    <tr>
                      <th scope="col">Application</th>
                      <th scope="col">Auth</th>
                      <th scope="col">Owner</th>
                      <th scope="col">Users</th>
                      <th scope="col">Created</th>
                      <th scope="col">Client</th>
                      <th scope="col">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.entries.length ? (
                      data.entries.map((entry) => (
                        <Row
                          key={entry.id}
                          entry={entry}
                        />
                      ))
                    ) : (
                      <tr>
                        <td
                          colSpan={7}
                          class="text-center text-muted py-4"
                        >
                          No applications found matching your filters.
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
