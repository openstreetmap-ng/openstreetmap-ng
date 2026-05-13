import { ConnectError } from "@connectrpc/connect"
import { queryParam } from "@lib/codecs"
import { Time } from "@lib/datetime-inputs"
import { useDisposeSignalEffect } from "@lib/dispose-scope"
import { mountProtoPage } from "@lib/proto-page"
import {
  DeleteOlderThanRequest_TimeUnit,
  type GetPageResponse_SummaryValid,
  type GetPageResponseValid,
  type GetResponseValid,
  IndexPageSchema,
  Service,
} from "@lib/proto/message_pb"
import { defineQueryContract } from "@lib/query-contract"
import { ReportButton } from "@lib/report"
import { connectErrorToMessage, rpcUnary } from "@lib/rpc"
import { UserLink } from "@lib/user-link"
import { StandardPagination } from "@lib/standard-pagination"
import { type QueryContractSignal, usePathSuffixQueryState } from "@lib/url-signals"
import { isUnmodifiedLeftClick } from "@lib/utils"
import { batch, type ReadonlySignal, useSignal } from "@preact/signals"
import { t } from "i18next"
import { useEffect, useRef } from "preact/hooks"
import { changeUnreadMessagesBadge } from "../navbar/navbar"

type PreviewState =
  | { status: "loading" }
  | { status: "ready"; message: GetResponseValid }
  | { status: "error"; error: string }

const MESSAGE_QUERY = defineQueryContract({
  show: queryParam.positive(),
  page: queryParam.positiveInt(),
})
type MessageQuery = QueryContractSignal<typeof MESSAGE_QUERY>

const getQueryWithoutShow = (query: MessageQuery) => {
  const page = query.peek().page
  return page === undefined ? {} : { page }
}

const SummaryRecipients = ({ message }: { message: GetPageResponse_SummaryValid }) => {
  if (message.recipientsCount <= 1) {
    return <UserLink user={message.recipients[0]!} />
  }

  return (
    <span class="recipients-group">
      {message.recipients.map((recipient) => (
        <UserLink
          key={recipient.id}
          user={recipient}
          showName={false}
          title={recipient.displayName}
        />
      ))}
      {message.recipientsCount > message.recipients.length && (
        <span class="fw-medium">
          +{message.recipientsCount - message.recipients.length}
        </span>
      )}
    </span>
  )
}

const MessagesEmpty = () => (
  <li class="text-center text-muted py-5">
    <h3>{t("traces.index.empty_title")}</h3>
  </li>
)

const retentionUnitLabel = (unit: DeleteOlderThanRequest_TimeUnit, count: number) => {
  switch (unit) {
    case DeleteOlderThanRequest_TimeUnit.days:
      return t("messages.retention.unit_days", { count })
    case DeleteOlderThanRequest_TimeUnit.weeks:
      return t("messages.retention.unit_weeks", { count })
    case DeleteOlderThanRequest_TimeUnit.months:
      return t("messages.retention.unit_months", { count })
    case DeleteOlderThanRequest_TimeUnit.years:
      return t("messages.retention.unit_years", { count })
  }
}

const DeleteOlderMessagesForm = ({
  inbox,
  onDeleted,
}: {
  inbox: boolean
  onDeleted: (page: GetPageResponseValid) => void
}) => {
  const count = useSignal(3)
  const unit = useSignal(DeleteOlderThanRequest_TimeUnit.weeks)
  const deleting = useSignal(false)

  const submitDelete = async (event: SubmitEvent) => {
    event.preventDefault()

    const nextCount = Number.isFinite(count.value)
      ? Math.min(999, Math.max(1, Math.trunc(count.value)))
      : 3
    count.value = nextCount

    const mailbox = t(
      inbox ? "messages.retention.mailbox_inbox" : "messages.retention.mailbox_outbox",
    )
    if (
      !confirm(
        t("messages.retention.confirmation", {
          count: nextCount,
          unit: retentionUnitLabel(unit.value, nextCount),
          mailbox,
        }),
      )
    ) {
      return
    }

    deleting.value = true
    try {
      const response = await rpcUnary(Service.method.deleteOlderThan)({
        inbox,
        count: nextCount,
        unit: unit.value,
      })
      const page = await rpcUnary(Service.method.getPage)({ inbox })
      onDeleted(page)
      alert(t("messages.retention.deleted_count", { count: response.deletedCount }))
    } catch (error) {
      console.error("Messages: Failed to delete old messages", error)
      alert(connectErrorToMessage(ConnectError.from(error)))
    } finally {
      deleting.value = false
    }
  }

  return (
    <form
      class="input-group input-group-sm mb-3"
      onSubmit={submitDelete}
    >
      <span class="input-group-text">
        <i class="bi bi-trash" />
      </span>
      <label
        class="visually-hidden"
        for="message-retention-count"
      >
        {t("messages.retention.count_label")}
      </label>
      <input
        id="message-retention-count"
        class="form-control"
        type="number"
        min="1"
        max="999"
        step="1"
        value={count.value}
        disabled={deleting.value}
        onInput={(event) => (count.value = event.currentTarget.valueAsNumber)}
      />
      <label
        class="visually-hidden"
        for="message-retention-unit"
      >
        {t("messages.retention.unit_label")}
      </label>
      <select
        id="message-retention-unit"
        class="form-select"
        value={unit.value}
        disabled={deleting.value}
        onChange={(event) =>
          (unit.value = Number(
            event.currentTarget.value,
          ) as DeleteOlderThanRequest_TimeUnit)
        }
      >
        <option value={DeleteOlderThanRequest_TimeUnit.days}>
          {retentionUnitLabel(DeleteOlderThanRequest_TimeUnit.days, count.value)}
        </option>
        <option value={DeleteOlderThanRequest_TimeUnit.weeks}>
          {retentionUnitLabel(DeleteOlderThanRequest_TimeUnit.weeks, count.value)}
        </option>
        <option value={DeleteOlderThanRequest_TimeUnit.months}>
          {retentionUnitLabel(DeleteOlderThanRequest_TimeUnit.months, count.value)}
        </option>
        <option value={DeleteOlderThanRequest_TimeUnit.years}>
          {retentionUnitLabel(DeleteOlderThanRequest_TimeUnit.years, count.value)}
        </option>
      </select>
      <button
        class="btn btn-outline-danger"
        type="submit"
        disabled={deleting.value}
      >
        {deleting.value ? (
          <span
            class="spinner-border spinner-border-sm"
            aria-hidden="true"
          />
        ) : (
          <>
            <i class="bi bi-trash me-2" />
            {t("messages.retention.submit")}
          </>
        )}
      </button>
    </form>
  )
}

const MessagesListItem = ({
  message,
  inbox,
  query,
}: {
  message: GetPageResponse_SummaryValid
  inbox: boolean
  query: MessageQuery
}) => {
  const messageId = message.id
  const isUnread = inbox && message.unread
  const isActive = query.value.show === messageId

  const handleOpen = (event: MouseEvent & { currentTarget: HTMLAnchorElement }) => {
    if (!isUnmodifiedLeftClick(event)) return
    event.preventDefault()
    event.currentTarget.blur()
    query.value = { ...query.peek(), show: messageId }
  }

  return (
    <li
      class={`social-entry clickable ${isUnread ? "unread" : ""} ${
        isActive ? "active" : ""
      }`}
    >
      <p class="header text-muted d-flex justify-content-between">
        {inbox ? (
          <span>
            <UserLink user={message.sender!} /> {t("messages.action_sent")}{" "}
            <Time
              unix={message.createdAt}
              relativeStyle="long"
            />
          </span>
        ) : (
          <span>
            <SummaryRecipients message={message} /> {t("messages.action_delivered")}{" "}
            <Time
              unix={message.createdAt}
              relativeStyle="long"
            />
          </span>
        )}
        <span>
          <a
            class="stretched-link"
            href={MESSAGE_QUERY.encode({ ...query.value, show: messageId })}
            onClick={handleOpen}
            aria-label={message.subject}
          />
          <span class="unread-badge badge text-bg-primary">
            <i class="bi bi-bell-fill me-1" />
            {t("state.unread")}
          </span>
        </span>
      </p>
      <div class="body">
        <h6 class="title">{message.subject}</h6>
        <p class="description">{message.bodyPreview}</p>
      </div>
    </li>
  )
}

const MessageActionsToolbar = ({
  inbox,
  messageId,
  message,
  onUnread,
  onDelete,
}: {
  inbox: boolean
  messageId: bigint
  message: GetResponseValid
  onUnread: () => void
  onDelete: () => void
}) => {
  const disabledGroup = inbox && !message.isRecipient
  const showReplyAll = inbox && message.recipients.length > 1

  return (
    <fieldset
      class="btn-group border-0 p-0 m-0"
      disabled={disabledGroup}
    >
      <a
        class="btn btn-sm btn-soft"
        href={`/message/new?reply=${messageId}`}
      >
        <i class="bi bi-reply me-2" />
        {t("messages.message_summary.reply_button")}
      </a>
      {inbox && (
        <>
          {showReplyAll && (
            <a
              class="btn btn-sm btn-soft"
              href={`/message/new?reply_all=${messageId}`}
            >
              <i class="bi bi-reply-all me-2" />
              {t("messages.reply_all")}
            </a>
          )}
          <button
            class="btn btn-sm btn-soft"
            type="button"
            onClick={onUnread}
          >
            <i class="bi bi-envelope me-2" />
            {t("messages.message_summary.unread_button")}
          </button>
        </>
      )}
      <button
        class="btn btn-sm btn-soft"
        type="button"
        onClick={onDelete}
      >
        <i class="bi bi-trash me-2" />
        {t("messages.message_summary.destroy_button")}
      </button>
    </fieldset>
  )
}

const MessagePreview = ({
  inbox,
  previewState,
  query,
  onUnread,
  onDelete,
}: {
  inbox: boolean
  previewState: ReadonlySignal<PreviewState>
  query: MessageQuery
  onUnread: () => void
  onDelete: () => void
}) => {
  const messageId = query.value.show!
  const preview = previewState.value
  const message = preview.status === "ready" ? preview.message : null
  const sender = message?.sender
  const previewRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const preview = previewRef.current!

    const previewTop = preview.getBoundingClientRect().top + window.scrollY
    const viewportTop = window.scrollY
    if (previewTop >= viewportTop) return

    preview.scrollIntoView({ block: "start" })
  }, [])

  return (
    <div
      class="message-preview card sticky-top"
      ref={previewRef}
    >
      <div class="py-3 card-header">
        <div class="row g-1">
          <div class="col">
            {message && (
              <>
                <div class="message-sender d-flex">
                  <UserLink
                    user={sender!}
                    showName={false}
                  />
                  <div>
                    <UserLink
                      class="d-inline-block"
                      user={sender!}
                      showAvatar={false}
                    />
                    <div>
                      <Time
                        unix={message.createdAt}
                        dateStyle="long"
                        timeStyle="short"
                      />
                    </div>
                  </div>
                </div>
                <div>
                  <span class="small text-muted me-2">{t("messages.to_prefix")}:</span>
                  <div class="message-recipients">
                    {message.recipients.map((recipient) => (
                      <UserLink
                        key={recipient.id}
                        user={recipient}
                      />
                    ))}
                  </div>
                </div>
                <MessageActionsToolbar
                  inbox={inbox}
                  messageId={messageId}
                  message={message}
                  onUnread={onUnread}
                  onDelete={onDelete}
                />
              </>
            )}
          </div>
          <div class="col-auto">
            <button
              class="btn-close"
              aria-label={t("javascripts.close")}
              type="button"
              onClick={() => (query.value = getQueryWithoutShow(query))}
            />
          </div>
        </div>
      </div>
      <div class="card-body">
        {preview.status === "loading" && (
          <div class="text-center mt-4">
            <output
              class="spinner-border text-body-secondary"
              aria-live="polite"
            >
              <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
            </output>
          </div>
        )}
        {preview.status === "error" && (
          <div
            class="alert alert-danger mt-4"
            role="alert"
          >
            {preview.error}
          </div>
        )}
        {message && (
          <>
            <h5 class="title">{message.subject}</h5>
            <div
              class="rich-text"
              dangerouslySetInnerHTML={{ __html: message.bodyRich }}
            />
            {inbox && (
              <div class="text-end mt-3">
                <ReportButton
                  class="btn btn-link btn-sm text-muted p-0"
                  reportType="user"
                  reportTypeId={sender!.id}
                  reportAction="user_message"
                  reportActionId={messageId}
                >
                  <i class="bi bi-flag small me-1-5" />
                  {t("report.report_object", {
                    object: t("activerecord.models.message"),
                  })}
                </ReportButton>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

mountProtoPage(IndexPageSchema, () => {
  const route = usePathSuffixQueryState(
    { inbox: "/inbox", outbox: "/outbox" },
    MESSAGE_QUERY,
    { defaultKey: "inbox" },
  )
  const inbox = route.value === "inbox"
  const query = route.query
  const messages = useSignal<GetPageResponse_SummaryValid[]>([])
  const pageResponse = useSignal<GetPageResponseValid | null>(null)
  const previewState = useSignal<PreviewState>({ status: "loading" })

  const handleOlderMessagesDeleted = (page: GetPageResponseValid) => {
    batch(() => {
      query.value = getQueryWithoutShow(query)
      pageResponse.value = page
    })
  }

  const updateMessageUnread = (messageId: bigint, unread: boolean) =>
    (messages.value = messages.value.map((message) =>
      message.id === messageId && message.unread !== unread
        ? ((message.unread = unread), message)
        : message,
    ))

  const removeMessage = (messageId: bigint) =>
    (messages.value = messages.value.filter((message) => message.id !== messageId))

  const markMessageUnread = async () => {
    const messageId = query.value.show
    if (!messageId) return

    const preview = previewState.peek()
    if (!(inbox && preview.status === "ready" && preview.message.isRecipient)) return

    try {
      const response = await rpcUnary(Service.method.updateReadState)({
        id: messageId,
        read: false,
      })

      batch(() => {
        if (response.updated) {
          updateMessageUnread(messageId, true)
          changeUnreadMessagesBadge(1)
        }
        query.value = getQueryWithoutShow(query)
      })
    } catch (error) {
      console.error("Messages: Failed to mark unread", messageId, error)
      alert(connectErrorToMessage(ConnectError.from(error)))
    }
  }

  const deleteMessage = async () => {
    const messageId = query.value.show
    if (!(messageId && confirm(t("messages.delete_confirmation")))) return
    try {
      await rpcUnary(Service.method.delete)({ id: messageId })

      batch(() => {
        removeMessage(messageId)
        query.value = getQueryWithoutShow(query)
      })
    } catch (error) {
      console.error("Messages: Failed to delete", messageId, error)
      alert(connectErrorToMessage(ConnectError.from(error)))
    }
  }

  // Effect: Fetch open message details
  useDisposeSignalEffect((scope) => {
    const messageId = query.value.show
    previewState.value = { status: "loading" }
    if (!messageId) return

    const fetchMessage = async () => {
      try {
        const message = await rpcUnary(Service.method.get)(
          { id: messageId },
          { signal: scope.signal },
        )

        batch(() => {
          if (inbox && message.isRecipient && message.wasUnread) {
            changeUnreadMessagesBadge(-1)
            updateMessageUnread(messageId, false)
          }
          previewState.value = { status: "ready", message }
        })
      } catch (error) {
        if (error.name === "AbortError") return
        console.error("Messages: Failed to fetch", messageId, error)

        previewState.value = {
          status: "error",
          error: connectErrorToMessage(ConnectError.from(error)),
        }
      }
    }
    void fetchMessage()
  })

  return (
    <>
      <div class="content-header pb-0">
        <div class="container">
          <h1>{t("users.show.my messages")}</h1>
          <p>{t("messages.description")}</p>

          <nav>
            <ul class="nav nav-tabs nav-tabs-md flex-column flex-md-row">
              <li class="nav-item">
                <a
                  href="/messages/inbox"
                  class={`nav-link ${inbox ? "active" : ""}`}
                  aria-current={inbox ? "page" : undefined}
                >
                  {t("messages.heading.my_inbox")}
                </a>
              </li>
              <li class="nav-item">
                <a
                  href="/messages/outbox"
                  class={`nav-link ${inbox ? "" : "active"}`}
                  aria-current={inbox ? undefined : "page"}
                >
                  {t("messages.heading.my_outbox")}
                </a>
              </li>
              <li class="nav-item ms-auto">
                <a
                  class="btn btn-soft"
                  href="/message/new"
                >
                  <i class="bi bi-envelope-plus me-2" />
                  {t("action.send_a_message")}
                </a>
              </li>
            </ul>
          </nav>
        </div>
      </div>

      <div class="content-body">
        <div class="container">
          <div class="row flex-wrap-reverse">
            <div class="col-lg">
              <DeleteOlderMessagesForm
                inbox={inbox}
                onDeleted={handleOlderMessagesDeleted}
              />
              <StandardPagination
                method={Service.method.getPage}
                request={{ inbox }}
                urlKey="page"
                responseSignal={pageResponse}
                onLoad={(data) => (messages.value = data.messages)}
              >
                {() => (
                  <ul class="messages-list social-list list-unstyled mb-2">
                    {messages.value.length ? (
                      messages.value.map((message) => (
                        <MessagesListItem
                          key={message.id}
                          message={message}
                          inbox={inbox}
                          query={query}
                        />
                      ))
                    ) : (
                      <MessagesEmpty />
                    )}
                  </ul>
                )}
              </StandardPagination>
            </div>
            {query.value.show && (
              <div class="col-lg mb-3">
                <MessagePreview
                  key={query.value.show}
                  inbox={inbox}
                  previewState={previewState}
                  query={query}
                  onUnread={markMessageUnread}
                  onDelete={deleteMessage}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
})
