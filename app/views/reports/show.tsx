import { isAdministrator, REPORT_COMMENT_BODY_MAX_LENGTH } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { mountProtoPage } from "@lib/proto-page"
import { Role } from "@lib/proto/admin_users_pb"
import {
  Action,
  type CommentValid,
  type HeaderValid,
  type ListCommentsResponseValid,
  Service,
  ShowPageSchema,
} from "@lib/proto/report_pb"
type ReportEvent = "comment" | "close" | "reopen"
import { ReportCommentBody } from "./_comment"
import { StandardForm } from "@lib/standard-form"
import { StandardPagination } from "@lib/standard-pagination"
import { UserLink } from "@lib/user-link"
import { type Signal, useSignal } from "@preact/signals"

const reportedUserIdOf = (header: HeaderValid) =>
  header.target.case === "reportedUser" ? header.target.value.id : undefined

const ReportTitle = ({ header }: { header: HeaderValid }) => {
  switch (header.target.case) {
    case "reportedUser":
      return (
        <>
          Reported{" "}
          <a href={`/user-id/${header.target.value.id}`}>
            {header.target.value.displayName}
          </a>
        </>
      )
    case "anonymousNoteId":
      return (
        <>
          Reported anonymous{" "}
          <a href={`/note/${header.target.value}`}>note {header.target.value}</a>
        </>
      )
  }
}

const ReportHeaderCard = ({ header }: { header: HeaderValid }) => (
  <div class="content-header">
    <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
      <a
        href="/reports"
        class="btn btn-sm btn-soft mb-3"
      >
        <i class="bi bi-arrow-left me-1-5" />
        Back to reports
      </a>
      <div class="row">
        {header.target.case === "reportedUser" && (
          <div class="col-auto">
            <UserLink
              user={header.target.value}
              admin
              showName={false}
            />
          </div>
        )}
        <div class="col">
          <h1 class="d-flex align-items-center gap-3">
            <span>
              <ReportTitle header={header} />
            </span>
            <span class={`badge ${header.closedAt ? "bg-secondary" : "bg-primary"}`}>
              {header.closedAt ? "Closed" : "Open"}
            </span>
          </h1>
          <p class="text-body-secondary mb-0">
            <i class="bi bi-clock-history me-1-5" />
            Last updated at{" "}
            <Time
              unix={header.updatedAt}
              dateStyle="short"
              timeStyle="short"
            />
          </p>
        </div>
      </div>
    </div>
  </div>
)

const VisibilityCell = ({ comment }: { comment: CommentValid }) => {
  const value = useSignal(comment.visibleTo)
  const disabled = useSignal(false)
  return (
    <StandardForm
      class="visibility-form"
      method={Service.method.updateCommentVisibility}
      buildRequest={({ formData }) => ({
        commentId: comment.id,
        visibleTo: Role[formData.get("visible_to") as keyof typeof Role],
      })}
      onSuccess={() => {
        disabled.value = false
      }}
      onError={() => {
        // Roll back to the last successful value.
        value.value = comment.visibleTo
        disabled.value = false
      }}
    >
      <select
        name="visible_to"
        class={`form-select form-select-sm ${disabled.value ? "disabled" : ""}`}
        value={Role[value.value]}
        onChange={(e) => {
          const next = Role[e.currentTarget.value as keyof typeof Role]
          value.value = next
          disabled.value = true
          e.currentTarget.form?.requestSubmit()
        }}
      >
        <option value="moderator">Moderators</option>
        <option value="administrator">❗ Administrators</option>
      </select>
    </StandardForm>
  )
}

const CommentEntry = ({
  comment,
  reportedUserId,
  isAdmin,
}: {
  comment: CommentValid
  reportedUserId?: bigint | undefined
  isAdmin: boolean
}) => {
  const { user } = comment.body
  const action = comment.body.action
  const verb =
    action === Action.comment
      ? "commented"
      : action === Action.close
        ? "closed"
        : action === Action.reopen
          ? "reopened"
          : "reported"
  return (
    <li class="social-entry">
      <div class="header text-muted d-flex justify-content-between align-items-center">
        <span>
          {user && (
            <UserLink
              user={user}
              admin
            />
          )}{" "}
          {verb} <Time unix={comment.createdAt} />
        </span>
        {isAdmin && <VisibilityCell comment={comment} />}
      </div>
      <div class="body">
        <ReportCommentBody
          body={comment.body}
          reportedUserId={reportedUserId}
        />
      </div>
    </li>
  )
}

const ModerationActions = ({
  header,
  commentsResponse,
}: {
  header: Signal<HeaderValid>
  commentsResponse: Signal<ListCommentsResponseValid | null>
}) => {
  const body = useSignal("")
  const reportId = header.value.id
  const isOpen = !header.value.closedAt
  const hasBody = body.value.trim().length > 0

  return (
    <StandardForm
      method={Service.method.addComment}
      buildRequest={({ formData }) => ({
        reportId,
        event: Action[formData.get("event") as ReportEvent],
        body: body.value,
      })}
      // Mutation returns fresh { header, comments } so the page state updates
      // in a single write — no parallel refetch, no batching, no remount.
      onSuccess={(result) => {
        body.value = ""
        header.value = result.header
        commentsResponse.value = result.comments
      }}
    >
      <h3 class="mb-3">Moderation Actions</h3>
      <textarea
        class="form-control mb-3"
        rows={3}
        placeholder="Enter your comment..."
        maxLength={REPORT_COMMENT_BODY_MAX_LENGTH}
        value={body.value}
        onInput={(e) => (body.value = e.currentTarget.value)}
      />
      <div class="text-end">
        <button
          type="submit"
          name="event"
          value={isOpen ? "close" : "reopen"}
          class={`btn ${isOpen ? "btn-success" : "btn-secondary"}`}
        >
          <i
            class={`bi me-1 ${isOpen ? "bi-check-circle" : "bi-arrow-counterclockwise"}`}
          />
          {isOpen
            ? hasBody
              ? "Comment & Close"
              : "Close"
            : hasBody
              ? "Comment & Reopen"
              : "Reopen"}
        </button>
        <button
          type="submit"
          name="event"
          value="comment"
          class="btn btn-primary ms-1"
          disabled={!hasBody}
        >
          <i class="bi bi-chat-left-text me-1" />
          Comment
        </button>
      </div>
    </StandardForm>
  )
}

mountProtoPage(ShowPageSchema, ({ reportId, header: initialHeader }) => {
  const header = useSignal(initialHeader)
  const commentsResponse = useSignal<ListCommentsResponseValid | null>(null)
  const reportedUserId = reportedUserIdOf(header.value)

  return (
    <>
      <ReportHeaderCard header={header.value} />
      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <div class="report-comments-pagination mb-4">
            <StandardPagination
              method={Service.method.listComments}
              request={{ reportId }}
              urlKey="page"
              responseSignal={commentsResponse}
            >
              {(data) => (
                <ul class="social-list list-unstyled mb-2">
                  {data.entries.map((c) => (
                    <CommentEntry
                      key={c.id}
                      comment={c}
                      reportedUserId={reportedUserId}
                      isAdmin={isAdministrator}
                    />
                  ))}
                </ul>
              )}
            </StandardPagination>
          </div>

          <ModerationActions
            header={header}
            commentsResponse={commentsResponse}
          />
        </div>
      </div>
    </>
  )
})
