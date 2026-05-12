import { Action, Category, type CommentBody } from "@lib/proto/report_pb"
import type { JSX } from "preact"

const REPORT_ACTION_ICON: Record<Action, string> = {
  [Action.comment]: "",
  [Action.close]: "bi-check-circle text-success",
  [Action.reopen]: "bi-arrow-counterclockwise text-warning",
  [Action.generic]: "bi-flag text-danger",
  [Action.user_account]: "bi-life-preserver text-info",
  [Action.user_changeset]: "bi-geo-alt text-danger",
  [Action.user_diary]: "bi-journal-x text-danger",
  [Action.user_message]: "bi-envelope-x text-danger",
  [Action.user_note]: "bi-pin-angle text-danger",
  [Action.user_oauth2_application]: "bi-app-indicator text-danger",
  [Action.user_profile]: "bi-person-badge text-danger",
  [Action.user_trace]: "bi-geo text-danger",
}

const ReportCategoryBadge = ({ category }: { category: Category }) => (
  <span
    class="report-category"
    data-category={Category[category]}
  >
    {Category[category]}
  </span>
)

const ObjectLabel = ({ value }: { value: string | null }) =>
  value ? <>&ldquo;{value}&rdquo;</> : <>«Deleted»</>

const ActionExternalLink = ({
  href,
  children,
}: {
  href: string
  children: JSX.Element | string
}) => (
  <a
    href={href}
    target="_blank"
    rel="noopener"
  >
    {children}
  </a>
)

const ReportActionLabel = ({
  body,
  reportedUserId,
}: {
  body: CommentBody
  reportedUserId?: bigint | undefined
}): JSX.Element | null => {
  const { action, actionId, category, object } = body
  const cat =
    category !== undefined ? <ReportCategoryBadge category={category} /> : null

  switch (action) {
    case Action.comment:
      return null
    case Action.close:
      return <>Closed report</>
    case Action.reopen:
      return <>Reopened report</>
    case Action.generic:
      return <>Reported for {cat}</>
    case Action.user_account:
      return <>Reported a problem with {cat}</>
    case Action.user_changeset:
      return (
        <>
          Reported{" "}
          <ActionExternalLink href={`/changeset/${actionId}`}>
            <>changeset {actionId}</>
          </ActionExternalLink>{" "}
          for {cat}
        </>
      )
    case Action.user_diary: {
      const title = object?.kind.case === "diaryTitle" ? object.kind.value : null
      return (
        <>
          Reported{" "}
          <ActionExternalLink href={`/diary/${actionId}`}>
            <>
              diary entry <ObjectLabel value={title} />
            </>
          </ActionExternalLink>{" "}
          for {cat}
        </>
      )
    }
    case Action.user_message: {
      const subject = object?.kind.case === "messageSubject" ? object.kind.value : null
      return (
        <>
          Reported{" "}
          <ActionExternalLink href={`/messages/inbox?show=${actionId}`}>
            <>
              message <ObjectLabel value={subject} />
            </>
          </ActionExternalLink>{" "}
          for {cat}
        </>
      )
    }
    case Action.user_note:
      return (
        <>
          Reported{" "}
          <ActionExternalLink href={`/note/${actionId}`}>
            <>note {actionId}</>
          </ActionExternalLink>{" "}
          for {cat}
        </>
      )
    case Action.user_oauth2_application: {
      const app = object?.kind.case === "oauth2App" ? object.kind.value : null
      return (
        <>
          Reported application{" "}
          {app ? (
            <>
              &ldquo;{app.name}&rdquo; ({actionId})
              {app.redirectUris.map((uri, i) => (
                <sup
                  key={uri}
                  class="text-nowrap"
                >
                  [
                  <a
                    href={uri}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {i + 1}
                  </a>
                  ]
                </sup>
              ))}
            </>
          ) : (
            <>«Deleted» ({actionId})</>
          )}{" "}
          for {cat}
        </>
      )
    }
    case Action.user_profile:
      return (
        <>
          Reported{" "}
          <ActionExternalLink href={`/user-id/${reportedUserId}`}>
            user profile
          </ActionExternalLink>{" "}
          for {cat}
        </>
      )
    case Action.user_trace: {
      const name = object?.kind.case === "traceName" ? object.kind.value : null
      return (
        <>
          Reported{" "}
          <ActionExternalLink href={`/trace/${actionId}`}>
            <>
              GPS trace <ObjectLabel value={name} />
            </>
          </ActionExternalLink>{" "}
          for {cat}
        </>
      )
    }
  }
}

/**
 * Render the action header (icon + label) and rich-text body of a report comment.
 * Used by both list-row previews on IndexPage and the comments list on ShowPage.
 *
 * `reportedUserId` is required only when the comment may carry the `user_profile` action,
 * in which case it links the surrounding report's reported user.
 */
export const ReportCommentBody = ({
  body,
  reportedUserId,
}: {
  body: CommentBody
  reportedUserId?: bigint | undefined
}) => {
  const { action, bodyRich } = body
  // bodyRich presence encodes viewer access: undefined = restricted (server
  // omitted the field), any string (incl. empty) = access granted.
  const hasAccess = bodyRich !== undefined
  // The action span is empty when access is granted, the action has no icon,
  // and the label is null — only the bare comment action falls in that bucket.
  const hasActionContent =
    !hasAccess || Boolean(REPORT_ACTION_ICON[action]) || action !== Action.comment
  // Empty rich-text resolves to "<p></p>"; treat it as no body so we don't
  // render a placeholder paragraph or a divider above empty space.
  const hasBodyContent = bodyRich && bodyRich !== "<p></p>"
  const withBody = hasActionContent && hasBodyContent ? "report-action-with-body" : ""

  return (
    <>
      {hasActionContent && (
        <span class={`report-action ${withBody}`}>
          {!hasAccess ? (
            <>
              <i class="bi bi-lock text-muted me-1-5" />
              <em class="text-muted">Restricted comment</em>
            </>
          ) : (
            <>
              {REPORT_ACTION_ICON[action] && (
                <i class={`bi ${REPORT_ACTION_ICON[action]} me-1-5`} />
              )}
              <ReportActionLabel
                body={body}
                reportedUserId={reportedUserId}
              />
            </>
          )}
        </span>
      )}
      {hasBodyContent && (
        <div
          class="report-body"
          dangerouslySetInnerHTML={{ __html: bodyRich }}
        />
      )}
    </>
  )
}
