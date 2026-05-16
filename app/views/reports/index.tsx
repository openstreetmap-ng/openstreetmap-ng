import { Time } from "@components/datetime-inputs"
import { StandardPagination } from "@components/standard-pagination"
import { UserLink } from "@components/user-link"
import {
  Action,
  IndexPageSchema,
  type ListResponse_EntryValid,
  Service,
  Status,
  StatusSchema,
} from "@proto/report_pb"
import { queryParam } from "@utils/path-codecs"
import { mountProtoPage } from "@utils/proto-page"
import { defineQueryContract } from "@utils/query-contract"
import { useUrlQueryState } from "@utils/query-signals"
import { t } from "i18next"
import { ReportCommentBody } from "./_comment"

const STATUS_QUERY = defineQueryContract({
  status: queryParam.enum(StatusSchema, { default: Status.any }),
})

const Row = ({ entry }: { entry: ListResponse_EntryValid }) => {
  const { header, numComments, lastComment } = entry
  const reportedUserId =
    header.target.case === "reportedUser" ? header.target.value.id : undefined
  const isOpen = !header.closedAt

  return (
    <li class="social-entry clickable">
      <p class="header text-muted d-flex justify-content-between">
        <span>
          {header.target.case === "reportedUser" ? (
            <>
              <UserLink
                user={header.target.value}
                admin
                showName={false}
              />
              <strong>Reported</strong>{" "}
              <UserLink
                class="ms-1"
                user={header.target.value}
                admin
                showAvatar={false}
              />
            </>
          ) : (
            <>
              <strong>Reported anonymous</strong>{" "}
              <a
                class="ms-1"
                href={`/note/${header.target.value}`}
              >
                note {header.target.value}
              </a>
            </>
          )}{" "}
          • updated <Time unix={header.updatedAt} />
          <a
            class="stretched-link"
            href={`/reports/${header.id}`}
            aria-label={`Open report ${header.id}`}
          />
        </span>
        {isOpen && <span class="badge bg-primary">Open</span>}
      </p>
      <div class="body">
        <div class="d-flex justify-content-between">
          <div class="body-preview">
            {lastComment && (
              <ReportCommentBody
                body={lastComment}
                reportedUserId={reportedUserId}
              />
            )}
          </div>
          <div class="num-comments ms-3">
            <span class={`badge d-flex align-items-center ${attentionBadge(entry)}`}>
              {numComments}
              <i class="bi bi-chat-left-text ms-1" />
            </span>
          </div>
        </div>
      </div>
    </li>
  )
}

// Highlight the comment-count badge when the report is open and the most recent
// activity is something other than a moderator-internal event (comment / close / reopen).
const attentionBadge = (entry: ListResponse_EntryValid) => {
  if (entry.header.closedAt) return "text-body"
  const last = entry.lastComment
  if (last?.bodyRich === undefined) return "text-body"
  if (
    last.action === Action.comment ||
    last.action === Action.close ||
    last.action === Action.reopen
  ) {
    return "text-body"
  }
  return "text-bg-light-green"
}

mountProtoPage(IndexPageSchema, () => {
  const filters = useUrlQueryState(STATUS_QUERY)

  return (
    <>
      <div class="content-header pb-1">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <h1>Content Reports</h1>
          <p>Review and manage user-submitted reports about problematic content.</p>

          <nav class="nav">
            <div class="nav-item ms-auto">
              <div class="input-group">
                <label
                  htmlFor="reportStatusFilter"
                  class="input-group-text"
                >
                  Filter by status
                </label>
                <select
                  id="reportStatusFilter"
                  class="form-select"
                  autocomplete="off"
                  value={Status[filters.value.status]}
                  onChange={(e) =>
                    (filters.value = {
                      status: Status[e.currentTarget.value as keyof typeof Status],
                    })
                  }
                >
                  <option value="any">{t("state.any")}</option>
                  <option value="open">Open</option>
                  <option value="closed">Closed</option>
                </select>
              </div>
            </div>
          </nav>
        </div>
      </div>

      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <StandardPagination
            method={Service.method.list}
            request={{ status: filters.value.status }}
            urlKey="page"
          >
            {(data) => (
              <ul class="social-list list-unstyled mb-2">
                {data.entries.length ? (
                  data.entries.map((entry) => (
                    <Row
                      key={entry.header.id}
                      entry={entry}
                    />
                  ))
                ) : (
                  <li>
                    <h3>{t("traces.index.empty_title")}</h3>
                  </li>
                )}
              </ul>
            )}
          </StandardPagination>
        </div>
      </div>
    </>
  )
})
