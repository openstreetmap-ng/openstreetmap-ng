import { Time } from "@components/datetime-inputs"
import { ReportButton } from "@components/report"
import { StandardPagination } from "@components/standard-pagination"
import { UserLink } from "@components/user-link"
import { ConnectError } from "@connectrpc/connect"
import { batch, type ReadonlySignal, useSignal } from "@preact/signals"
import {
  type GetPageResponse_SummaryValid,
  type GetResponseValid,
  IndexPageSchema,
  Service,
} from "@proto/message_pb"
import { useDisposeSignalEffect } from "@utils/dispose-scope"
import { isUnmodifiedLeftClick } from "@utils/dom-helpers"
import { unixToLocalDatetime } from "@utils/format"
import { queryParam } from "@utils/path-codecs"
import { mountProtoPage } from "@utils/proto-page"
import { defineQueryContract } from "@utils/query-contract"
import { type QueryContractSignal, usePathSuffixQueryState } from "@utils/query-signals"
import { connectErrorToMessage, rpcUnary } from "@utils/rpc"
import { t } from "i18next"
import { useEffect, useRef } from "preact/hooks"
import { changeUnreadMessagesBadge } from "../navbar/navbar"

import { AgeFilter } from "./_age-filter"
import { processSelection } from "./_selection"

type PreviewState =
  | { status: "loading" }
  | { status: "ready"; message: GetResponseValid }
  | { status: "error"; error: string }

const MESSAGE_QUERY = defineQueryContract({
  show: queryParam.positive(),
  page: queryParam.positiveInt(),
  search_user: queryParam.text(),
  search_subject: queryParam.text(),
  created_after: queryParam.timestamp(),
  created_before: queryParam.timestamp(),
})
type MessageQuery = QueryContractSignal<typeof MESSAGE_QUERY>

const getQueryWithoutShow = (query: MessageQuery) => {
  const next = { ...query.peek() }
  delete next.show
  return next
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

const MessagesListItem = ({
  message,
  inbox,
  query,
  selected,
  busy,
  onSelect,
}: {
  selected: boolean
  busy: boolean
  onSelect: (checked: boolean) => void
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
      {inbox && (
        <label class="position-relative z-1 d-inline-flex align-items-center gap-2 mb-2">
          <input
            class="form-check-input m-0"
            type="checkbox"
            checked={selected}
            disabled={busy}
            onChange={(event) => onSelect(event.currentTarget.checked)}
          />
          <span class="small">
            {t("mailbox_tools.select_message", { subject: message.subject })}
          </span>
        </label>
      )}
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
  const filters = { ...query.value }
  delete filters.show
  delete filters.page
  const {
    search_user: searchUser,
    search_subject: searchSubject,
    created_after: createdAfter,
    created_before: createdBefore,
  } = filters
  const filtersKey = MESSAGE_QUERY.keyOf(filters)
  const messages = useSignal<GetPageResponse_SummaryValid[]>([])
  const previewState = useSignal<PreviewState>({ status: "loading" })
  const selected = useSignal(new Set<bigint>())
  const bulkBusy = useSignal(false)
  const bulkError = useSignal("")
  const mailboxGeneration = useRef(0)
  useEffect(() => {
    mailboxGeneration.current++
    selected.value = new Set()
    bulkError.value = ""
    return () => {
      mailboxGeneration.current++
    }
  }, [inbox, filtersKey])

  const selectMessage = (id: bigint, checked: boolean) => {
    const next = new Set(selected.peek())
    if (checked) next.add(id)
    else next.delete(id)
    selected.value = next
  }

  const markSelected = async (read: boolean) => {
    if (bulkBusy.peek()) return
    const generation = mailboxGeneration.current
    const ids = [...selected.peek()]
    bulkBusy.value = true
    bulkError.value = ""
    try {
      await processSelection(
        ids,
        () => generation === mailboxGeneration.current,
        async (id) => {
          const response = await rpcUnary(Service.method.updateReadState)({ id, read })
          // The badge is global even when the user navigates away while awaiting.
          if (response.updated) {
            changeUnreadMessagesBadge(read ? -1 : 1)
            if (generation === mailboxGeneration.current) updateMessageUnread(id, !read)
          }
        },
        (id) => selectMessage(id, false),
      )
    } catch (error) {
      if (generation === mailboxGeneration.current)
        bulkError.value = connectErrorToMessage(ConnectError.from(error))
    } finally {
      bulkBusy.value = false
    }
  }

  const updateMessageUnread = (messageId: bigint, unread: boolean) =>
    (messages.value = messages.value.map((message) =>
      message.id === messageId && message.unread !== unread
        ? ((message.unread = unread), message)
        : message,
    ))

  const removeMessage = (messageId: bigint) =>
    (messages.value = messages.value.filter((message) => message.id !== messageId))

  const deleteSelected = async () => {
    if (bulkBusy.peek() || !selected.peek().size) return
    const ids = [...selected.peek()]
    if (!confirm(t("mailbox_tools.delete_confirmation", { count: ids.length }))) return
    const generation = mailboxGeneration.current
    bulkBusy.value = true
    bulkError.value = ""
    try {
      await processSelection(
        ids,
        () => generation === mailboxGeneration.current,
        async (id) => {
          const response = await rpcUnary(Service.method.delete)({ id })
          if (response.removedUnread) changeUnreadMessagesBadge(-1)
        },
        (id) =>
          batch(() => {
            removeMessage(id)
            selectMessage(id, false)
            if (query.peek().show === id) query.value = getQueryWithoutShow(query)
          }),
      )
    } catch (error) {
      if (generation === mailboxGeneration.current)
        bulkError.value = connectErrorToMessage(ConnectError.from(error))
    } finally {
      bulkBusy.value = false
    }
  }

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
      const response = await rpcUnary(Service.method.delete)({ id: messageId })

      batch(() => {
        if (response.removedUnread) changeUnreadMessagesBadge(-1)
        removeMessage(messageId)
        selectMessage(messageId, false)
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
              <form
                key={filtersKey}
                class="row g-2 mb-3"
                onSubmit={(event) => {
                  event.preventDefault()
                  query.value = MESSAGE_QUERY.parseFormData(
                    new FormData(event.currentTarget),
                  )
                }}
              >
                <label class="col-sm-6">
                  <span class="form-label">
                    {inbox ? t("mailbox_tools.sender") : t("mailbox_tools.recipient")}
                  </span>
                  <input
                    class="form-control"
                    name="search_user"
                    type="search"
                    maxLength={255}
                    defaultValue={searchUser ?? ""}
                  />
                </label>
                <label class="col-sm-6">
                  <span class="form-label">{t("mailbox_tools.subject")}</span>
                  <input
                    class="form-control"
                    name="search_subject"
                    type="search"
                    maxLength={100}
                    defaultValue={searchSubject ?? ""}
                  />
                </label>
                <label class="col-sm-6">
                  <span class="form-label">{t("mailbox_tools.from_date")}</span>
                  <input
                    class="form-control"
                    name="created_after"
                    type="datetime-local"
                    step="1"
                    min="1970-01-01T00:00"
                    defaultValue={unixToLocalDatetime(createdAfter)}
                  />
                </label>
                <label class="col-sm-6">
                  <span class="form-label">{t("mailbox_tools.to_date")}</span>
                  <input
                    class="form-control"
                    name="created_before"
                    type="datetime-local"
                    step="1"
                    min="1970-01-01T00:00"
                    defaultValue={unixToLocalDatetime(createdBefore)}
                  />
                </label>
                <div class="col-12 d-flex gap-2">
                  <button
                    class="btn btn-primary"
                    type="submit"
                    disabled={bulkBusy.value}
                  >
                    {t("mailbox_tools.apply_filters")}
                  </button>
                  <button
                    class="btn btn-secondary"
                    type="button"
                    disabled={bulkBusy.value}
                    onClick={() => (query.value = {})}
                  >
                    {t("mailbox_tools.reset_filters")}
                  </button>
                </div>
              </form>
              {inbox && (
                <AgeFilter
                  busy={bulkBusy.value}
                  onApply={(cutoff) => (query.value = { created_before: cutoff })}
                />
              )}
              {inbox && (
                <div
                  class="mb-3"
                  aria-busy={bulkBusy.value}
                >
                  <label class="d-flex align-items-center gap-2 mb-2">
                    <input
                      type="checkbox"
                      class="form-check-input m-0"
                      disabled={bulkBusy.value || !messages.value.length}
                      checked={
                        !!messages.value.length &&
                        messages.value.every((message) =>
                          selected.value.has(message.id),
                        )
                      }
                      onChange={(event) => {
                        const checked = event.currentTarget.checked
                        const next = new Set(selected.peek())
                        for (const message of messages.peek()) {
                          if (checked) next.add(message.id)
                          else next.delete(message.id)
                        }
                        selected.value = next
                      }}
                    />
                    {t("mailbox_tools.select_visible")}
                  </label>
                  <p
                    role="status"
                    class="small mb-2"
                  >
                    {t("mailbox_tools.selected", { count: selected.value.size })}
                  </p>
                  <div class="d-flex flex-wrap gap-2">
                    <button
                      type="button"
                      class="btn btn-sm btn-secondary"
                      disabled={bulkBusy.value || !selected.value.size}
                      onClick={() => void markSelected(true)}
                    >
                      {t("mailbox_tools.mark_read")}
                    </button>
                    <button
                      type="button"
                      class="btn btn-sm btn-secondary"
                      disabled={bulkBusy.value || !selected.value.size}
                      onClick={() => void markSelected(false)}
                    >
                      {t("mailbox_tools.mark_unread")}
                    </button>
                    <button
                      type="button"
                      class="btn btn-sm btn-danger"
                      disabled={bulkBusy.value || !selected.value.size}
                      onClick={() => void deleteSelected()}
                    >
                      {t("mailbox_tools.delete_selected")}
                    </button>
                    <button
                      type="button"
                      class="btn btn-sm btn-link"
                      disabled={bulkBusy.value || !selected.value.size}
                      onClick={() => (selected.value = new Set())}
                    >
                      {t("mailbox_tools.clear")}
                    </button>
                  </div>
                  {bulkError.value && (
                    <p
                      role="alert"
                      class="text-danger mt-2"
                    >
                      {bulkError.value}
                    </p>
                  )}
                </div>
              )}
              <StandardPagination
                method={Service.method.getPage}
                request={{
                  inbox,
                  searchUser,
                  searchSubject,
                  createdAfter,
                  createdBefore,
                }}
                urlKey="page"
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
                          selected={selected.value.has(message.id)}
                          busy={bulkBusy.value}
                          onSelect={(checked) => selectMessage(message.id, checked)}
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
