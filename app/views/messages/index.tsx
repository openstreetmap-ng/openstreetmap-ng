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
import { queryParam } from "@utils/path-codecs"
import { mountProtoPage } from "@utils/proto-page"
import { defineQueryContract } from "@utils/query-contract"
import { type QueryContractSignal, usePathSuffixQueryState } from "@utils/query-signals"
import { connectErrorToMessage, rpcUnary } from "@utils/rpc"
import { t } from "i18next"
import { useEffect, useRef } from "preact/hooks"
import { changeUnreadMessagesBadge } from "../navbar/navbar"
import { type BulkAction, runMessageBatch } from "./bulk"

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

const MessagesListItem = ({
  message,
  inbox,
  query,
  selected,
  disabled,
  onSelect,
}: {
  message: GetPageResponse_SummaryValid
  inbox: boolean
  query: MessageQuery
  selected: boolean
  disabled: boolean
  onSelect: () => void
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
      <label class="d-flex align-items-center gap-2 position-relative z-3 mb-2">
        <input
          type="checkbox"
          class="form-check-input m-0"
          checked={selected}
          disabled={disabled}
          onChange={onSelect}
          aria-label={t("mailbox_selection.select_message", {
            subject: message.subject,
          })}
        />
        <span class="small">{t("mailbox_selection.select")}</span>
      </label>
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
  const previewState = useSignal<PreviewState>({ status: "loading" })
  const selected = useSignal(new Set<bigint>())
  const bulkBusy = useSignal(false)
  const bulkError = useSignal("")
  const currentInbox = useRef(inbox)
  const mailboxVersion = useRef(0)
  if (currentInbox.current !== inbox) {
    currentInbox.current = inbox
    mailboxVersion.current++
  }

  useEffect(() => {
    selected.value = new Set()
    bulkError.value = ""
  }, [inbox])

  const toggleSelection = (message: GetPageResponse_SummaryValid) => {
    if (bulkBusy.peek()) return
    const next = new Set(selected.peek())
    if (!next.delete(message.id)) next.add(message.id)
    selected.value = next
  }

  const selectVisible = () => {
    const next = new Set(selected.peek())
    const visible = messages.peek()
    const all = visible.length > 0 && visible.every(({ id }) => next.has(id))
    for (const message of visible) {
      if (all) next.delete(message.id)
      else next.add(message.id)
    }
    selected.value = next
  }

  const updateMessageUnread = (messageId: bigint, unread: boolean) => {
    messages.value = messages.value.map((message) =>
      message.id === messageId && message.unread !== unread
        ? ((message.unread = unread), message)
        : message,
    )
  }

  const removeMessage = (messageId: bigint) => {
    messages.value = messages.value.filter((message) => message.id !== messageId)
    const next = new Set(selected.peek())
    next.delete(messageId)
    selected.value = next
  }

  const applyBulk = async (action: BulkAction) => {
    if (bulkBusy.peek() || !selected.peek().size || (!inbox && action !== "delete"))
      return
    if (action === "delete" && !confirm(t("messages.delete_confirmation"))) return
    const ids = [...selected.peek().keys()]
    const version = mailboxVersion.current
    query.value = getQueryWithoutShow(query)
    bulkBusy.value = true
    bulkError.value = ""
    try {
      const failures = await runMessageBatch(ids, async (id) => {
        if (mailboxVersion.current !== version) return
        if (action === "delete") {
          await rpcUnary(Service.method.delete)({ id })
          if (mailboxVersion.current !== version) return
          batch(() => {
            removeMessage(id)
            if (query.peek().show === id) query.value = getQueryWithoutShow(query)
          })
        } else {
          const read = action === "read"
          const response = await rpcUnary(Service.method.updateReadState)({ id, read })
          if (mailboxVersion.current !== version) return
          batch(() => {
            updateMessageUnread(id, !read)
            if (response.updated) changeUnreadMessagesBadge(read ? -1 : 1)
            if (query.peek().show === id) query.value = getQueryWithoutShow(query)
          })
        }
        const next = new Set(selected.peek())
        next.delete(id)
        selected.value = next
      })
      if (failures.length && mailboxVersion.current === version) {
        bulkError.value = t("mailbox_selection.failed", { count: failures.length })
      }
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
              <fieldset
                class="border-0 p-0 mb-3"
                disabled={bulkBusy.value}
                aria-busy={bulkBusy.value}
              >
                <div class="d-flex flex-wrap align-items-center gap-2">
                  <label class="d-flex align-items-center gap-2 me-2">
                    <input
                      type="checkbox"
                      class="form-check-input m-0"
                      checked={
                        messages.value.length > 0 &&
                        messages.value.every(({ id }) => selected.value.has(id))
                      }
                      disabled={!messages.value.length}
                      onChange={selectVisible}
                    />
                    {t("mailbox_selection.select_visible")}
                  </label>
                  <span
                    role="status"
                    class="small text-muted me-2"
                  >
                    {t("mailbox_selection.count", { count: selected.value.size })}
                  </span>
                  <div
                    class="btn-group"
                    role="group"
                    aria-label={t("mailbox_selection.actions")}
                  >
                    {inbox &&
                      (["read", "unread"] as const).map((action) => (
                        <button
                          type="button"
                          class="btn btn-sm btn-soft"
                          disabled={!selected.value.size}
                          title={t(`mailbox_selection.${action}`)}
                          aria-label={t(`mailbox_selection.${action}`)}
                          onClick={() => void applyBulk(action)}
                        >
                          <i
                            class={`bi bi-envelope${action === "read" ? "-open" : ""}`}
                          />
                        </button>
                      ))}
                    <button
                      type="button"
                      class="btn btn-sm btn-soft"
                      disabled={!selected.value.size}
                      title={t("mailbox_selection.delete")}
                      aria-label={t("mailbox_selection.delete")}
                      onClick={() => void applyBulk("delete")}
                    >
                      <i class="bi bi-trash" />
                    </button>
                    <button
                      type="button"
                      class="btn btn-sm btn-soft"
                      disabled={!selected.value.size}
                      title={t("mailbox_selection.clear")}
                      aria-label={t("mailbox_selection.clear")}
                      onClick={() => {
                        selected.value = new Set()
                        bulkError.value = ""
                      }}
                    >
                      <i class="bi bi-x-lg" />
                    </button>
                  </div>
                </div>
              </fieldset>
              {bulkError.value && (
                <div
                  role="alert"
                  class="alert alert-danger"
                >
                  {bulkError.value}
                </div>
              )}
              <StandardPagination
                method={Service.method.getPage}
                request={{ inbox }}
                urlKey="page"
                onLoad={(data) => {
                  messages.value = data.messages
                }}
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
                          disabled={bulkBusy.value}
                          onSelect={() => toggleSelection(message)}
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
