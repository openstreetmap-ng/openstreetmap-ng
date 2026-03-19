import { fromBinary } from "@bufbuild/protobuf"
import { Time } from "@lib/datetime-inputs"
import { mount } from "@lib/mount"
import {
  type MessagePage_Summary,
  type MessagePage_Summary_User,
  MessagePageSchema,
  type MessageRead,
  MessageReadSchema,
} from "@lib/proto/shared_pb"
import { ReportButton } from "@lib/report"
import { StandardPagination } from "@lib/standard-pagination"
import { useSignal, useSignalEffect } from "@preact/signals"
import { assert } from "@std/assert"
import { t } from "i18next"
import { render } from "preact"
import { memo } from "preact/compat"
import { useRef } from "preact/hooks"
import { changeUnreadMessagesBadge } from "../navbar/navbar"

type PreviewState =
  | { status: "closed" }
  | { status: "loading" }
  | { status: "ready"; message: MessageRead }
  | { status: "error"; error: string }

const updatePageUrl = (messageId: bigint | null) => {
  const url = new URL(window.location.href)
  if (messageId) url.searchParams.set("show", messageId.toString())
  else url.searchParams.delete("show")
  window.history.replaceState(null, "", url)
}

const getMessageFromPageUrl = () => {
  const value = new URL(window.location.href).searchParams.get("show")
  if (!value) return null
  try {
    return BigInt(value)
  } catch {
    return null
  }
}

const buildActionUrl = (
  baseAction: string,
  query: string,
  dateAfter: string,
  dateBefore: string,
) => {
  const params = new URLSearchParams()
  if (query) params.set("q", query)
  if (dateAfter) params.set("after", dateAfter)
  if (dateBefore) params.set("before", dateBefore)
  const qs = params.toString()
  return qs ? `${baseAction}?${qs}` : baseAction
}

const summaryUserLink = (user: MessagePage_Summary_User) => (
  <a href={`/user/${user.displayName}`}>
    <img
      class="avatar"
      src={user.avatarUrl}
      alt={t("alt.profile_picture")}
      loading="lazy"
    />
    {user.displayName}
  </a>
)

const summaryRecipients = (message: MessagePage_Summary) => {
  if (message.recipientsCount <= 1) {
    return summaryUserLink(message.recipients[0])
  }

  return (
    <span class="recipients-group">
      {message.recipients.map((recipient) => (
        <img
          class="avatar"
          src={recipient.avatarUrl}
          alt={t("alt.profile_picture")}
          loading="lazy"
          title={recipient.displayName}
          key={recipient.displayName}
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

const MessagesEmpty = memo(() => (
  <li class="text-center text-muted py-5">
    <h3>{t("traces.index.empty_title")}</h3>
  </li>
))

const MessagesListItem = ({
  message,
  inbox,
  openMessageId,
  selected,
  onOpen,
  onToggleSelect,
}: {
  message: MessagePage_Summary
  inbox: boolean
  openMessageId: bigint | null
  selected: boolean
  onOpen: (messageId: bigint) => void
  onToggleSelect: (messageId: bigint) => void
}) => {
  const messageId = message.id
  const isUnread = inbox && message.unread
  const isActive = openMessageId === messageId

  const handleOpen = (event: MouseEvent | KeyboardEvent) => {
    if (event instanceof MouseEvent) {
      if (
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return
    }
    if (event instanceof KeyboardEvent && event.key !== "Enter") return

    event.preventDefault()
    if (event.currentTarget instanceof HTMLElement) event.currentTarget.blur()
    onOpen(messageId)
  }

  const handleCheckbox = (event: Event) => {
    event.stopPropagation()
    onToggleSelect(messageId)
  }

  return (
    <li
      class={`social-entry clickable ${isUnread ? "unread" : ""} ${isActive ? "active" : ""} ${selected ? "selected" : ""}`}
    >
      <div class="d-flex align-items-start">
        <div class="message-checkbox me-2 mt-1">
          <input
            type="checkbox"
            class="form-check-input"
            checked={selected}
            onChange={handleCheckbox}
            onClick={(e) => e.stopPropagation()}
            aria-label={message.subject}
          />
        </div>
        <div class="flex-grow-1 min-w-0">
          <p class="header text-muted d-flex justify-content-between">
            {inbox ? (
              <span>
                {summaryUserLink(message.sender!)} {t("messages.action_sent")}{" "}
                <Time
                  unix={message.time}
                  relativeStyle="long"
                />
              </span>
            ) : (
              <span>
                {summaryRecipients(message)} {t("messages.action_delivered")}{" "}
                <Time
                  unix={message.time}
                  relativeStyle="long"
                />
              </span>
            )}
            <span>
              <a
                class="stretched-link"
                href={`?show=${messageId}`}
                onClick={handleOpen}
                onKeyDown={handleOpen}
              >
                <span class="visually-hidden">{message.subject}</span>
              </a>
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
        </div>
      </div>
    </li>
  )
}

const MessageRecipients = ({
  recipients,
}: {
  recipients: MessageRead["recipients"]
}) => (
  <>
    {recipients.map((recipient) => (
      <span key={recipient.displayName}>
        <img
          class="avatar"
          alt={t("alt.profile_picture")}
          src={recipient.avatarUrl}
          loading="lazy"
        />
        <a href={`/user/${recipient.displayName}`}>{recipient.displayName}</a>
      </span>
    ))}
  </>
)

const MessagePreview = ({
  inbox,
  messageId,
  state,
  onClose,
  onUnread,
  onDelete,
  previewRef,
}: {
  inbox: boolean
  messageId: bigint
  state: PreviewState
  onClose: () => void
  onUnread: () => void
  onDelete: () => void
  previewRef: { current: HTMLDivElement | null }
}) => {
  const message = state.status === "ready" ? state.message : null
  const sender = message?.sender
  const showReplyAll = inbox && (message?.recipients.length ?? 0) > 1
  const disabledGroup = message ? inbox && !message.isRecipient : true

  return (
    <div
      class="message-preview card sticky-top"
      ref={previewRef}
    >
      <div class="message-header py-3 card-header">
        <div class="row g-1">
          <div class="col">
            <div class="message-sender d-flex">
              {message && (
                <>
                  <img
                    class="avatar"
                    alt={t("alt.profile_picture")}
                    src={sender!.avatarUrl}
                    loading="lazy"
                  />
                  <div>
                    <a
                      class="sender-link d-inline-block"
                      href={`/user/${sender!.displayName}`}
                    >
                      {sender!.displayName}
                    </a>
                    <div class="message-time">
                      <Time
                        unix={message.time}
                        dateStyle="long"
                        timeStyle="short"
                      />
                    </div>
                  </div>
                </>
              )}
            </div>
            <div>
              <span class="small text-muted me-2">{t("messages.to_prefix")}:</span>
              <div class="message-recipients">
                {message && <MessageRecipients recipients={message.recipients} />}
              </div>
            </div>
            <fieldset
              class={`btn-group border-0 p-0 m-0 ${disabledGroup ? "disabled" : ""}`}
            >
              <a
                class="reply-link btn btn-sm btn-soft"
                href={`/message/new?reply=${messageId}`}
              >
                <i class="bi bi-reply me-2" />
                {t("messages.message_summary.reply_button")}
              </a>
              {inbox && (
                <>
                  {showReplyAll && (
                    <a
                      class="reply-all-link btn btn-sm btn-soft"
                      href={`/message/new?reply_all=${messageId}`}
                    >
                      <i class="bi bi-reply-all me-2" />
                      {t("messages.reply_all")}
                    </a>
                  )}
                  <button
                    class="unread-btn btn btn-sm btn-soft"
                    type="button"
                    onClick={onUnread}
                  >
                    <i class="bi bi-envelope me-2" />
                    {t("messages.message_summary.unread_button")}
                  </button>
                </>
              )}
              <button
                class="delete-btn btn btn-sm btn-soft"
                type="button"
                onClick={onDelete}
              >
                <i class="bi bi-trash me-2" />
                {t("messages.message_summary.destroy_button")}
              </button>
            </fieldset>
          </div>
          <div class="col-auto">
            <button
              class="btn-close"
              aria-label={t("javascripts.close")}
              type="button"
              onClick={onClose}
            />
          </div>
        </div>
      </div>
      <div class="card-body">
        <h5 class="message-title mb-3">{message?.subject}</h5>
        <div
          class="message-body rich-text"
          dangerouslySetInnerHTML={{ __html: message?.bodyRich ?? "" }}
        />
        {state.status === "loading" && (
          <div class="loading text-center mt-4">
            <output
              class="spinner-border text-body-secondary"
              aria-live="polite"
            >
              <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
            </output>
          </div>
        )}
        {state.status === "error" && (
          <div
            class="alert alert-danger mt-4"
            role="alert"
          >
            {state.error}
          </div>
        )}
        {inbox && message && (
          <div class="text-end mt-3">
            <ReportButton
              class="report-btn btn btn-link btn-sm text-muted p-0"
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
      </div>
    </div>
  )
}

const SearchBar = ({
  onSearch,
}: {
  onSearch: (query: string, dateAfter: string, dateBefore: string) => void
}) => {
  const queryRef = useRef<HTMLInputElement>(null)
  const dateAfterRef = useRef<HTMLInputElement>(null)
  const dateBeforeRef = useRef<HTMLInputElement>(null)
  const expanded = useSignal(false)

  const handleSubmit = (event: Event) => {
    event.preventDefault()
    onSearch(
      queryRef.current?.value ?? "",
      dateAfterRef.current?.value ?? "",
      dateBeforeRef.current?.value ?? "",
    )
  }

  const handleClear = () => {
    if (queryRef.current) queryRef.current.value = ""
    if (dateAfterRef.current) dateAfterRef.current.value = ""
    if (dateBeforeRef.current) dateBeforeRef.current.value = ""
    expanded.value = false
    onSearch("", "", "")
  }

  return (
    <form
      class="messages-search mb-3"
      onSubmit={handleSubmit}
    >
      <div class="input-group">
        <input
          type="text"
          class="form-control"
          placeholder={t("messages.search_placeholder")}
          ref={queryRef}
          aria-label={t("messages.search_placeholder")}
        />
        <button
          class="btn btn-outline-secondary"
          type="button"
          onClick={() => {
            expanded.value = !expanded.value
          }}
          title={t("messages.date_after")}
        >
          <i class="bi bi-calendar-range" />
        </button>
        <button
          class="btn btn-outline-secondary"
          type="submit"
        >
          <i class="bi bi-search" />
        </button>
      </div>
      {expanded.value && (
        <div class="row g-2 mt-2">
          <div class="col-sm-6">
            <label class="form-label small text-muted mb-1">
              {t("messages.date_after")}
            </label>
            <input
              type="date"
              class="form-control form-control-sm"
              ref={dateAfterRef}
            />
          </div>
          <div class="col-sm-6">
            <label class="form-label small text-muted mb-1">
              {t("messages.date_before")}
            </label>
            <input
              type="date"
              class="form-control form-control-sm"
              ref={dateBeforeRef}
            />
          </div>
        </div>
      )}
      <div class="mt-2 d-flex gap-2">
        <button
          class="btn btn-sm btn-link text-muted p-0"
          type="button"
          onClick={handleClear}
        >
          {t("action.reset_filters")}
        </button>
      </div>
    </form>
  )
}

const BulkActionBar = ({
  selectedCount,
  inbox,
  totalVisible,
  onSelectAll,
  onDeselectAll,
  onBulkRead,
  onBulkUnread,
  onBulkDelete,
}: {
  selectedCount: number
  inbox: boolean
  totalVisible: number
  onSelectAll: () => void
  onDeselectAll: () => void
  onBulkRead: () => void
  onBulkUnread: () => void
  onBulkDelete: () => void
}) => {
  if (selectedCount === 0) return null

  const allSelected = selectedCount === totalVisible && totalVisible > 0

  return (
    <div class="bulk-action-bar d-flex align-items-center gap-2 mb-2 p-2 bg-body-secondary rounded">
      <span class="fw-medium small">
        {t("messages.selected_count", { count: selectedCount })}
      </span>
      <button
        class="btn btn-sm btn-outline-secondary"
        type="button"
        onClick={allSelected ? onDeselectAll : onSelectAll}
      >
        {allSelected ? t("messages.deselect_all") : t("messages.select_all")}
      </button>
      <div class="vr" />
      {inbox && (
        <>
          <button
            class="btn btn-sm btn-soft"
            type="button"
            onClick={onBulkRead}
          >
            <i class="bi bi-envelope-open me-1" />
            {t("messages.mark_read")}
          </button>
          <button
            class="btn btn-sm btn-soft"
            type="button"
            onClick={onBulkUnread}
          >
            <i class="bi bi-envelope me-1" />
            {t("messages.mark_unread")}
          </button>
        </>
      )}
      <button
        class="btn btn-sm btn-soft text-danger"
        type="button"
        onClick={onBulkDelete}
      >
        <i class="bi bi-trash me-1" />
        {t("messages.message_summary.destroy_button")}
      </button>
    </div>
  )
}

const MessagesIndex = ({ inbox, action }: { inbox: boolean; action: string }) => {
  const messages = useSignal<MessagePage_Summary[]>([])
  const openMessageId = useSignal<bigint | null>(null)
  const previewState = useSignal<PreviewState>({ status: "closed" })
  const previewRef = useRef<HTMLDivElement>(null)

  // Search state
  const searchQuery = useSignal("")
  const searchDateAfter = useSignal("")
  const searchDateBefore = useSignal("")
  const searchKey = useSignal(0)

  // Selection state: persists across page navigations
  const selectedIds = useSignal<Set<bigint>>(new Set())

  const currentAction = buildActionUrl(
    action,
    searchQuery.value,
    searchDateAfter.value,
    searchDateBefore.value,
  )

  const updateMessageUnread = (messageId: bigint, unread: boolean) => {
    messages.value = messages.value.map((message) => {
      if (message.id !== messageId) return message
      if (message.unread === unread) return message
      return { ...message, unread }
    })
  }

  const removeMessage = (messageId: bigint) => {
    messages.value = messages.value.filter((message) => message.id !== messageId)
    const next = new Set(selectedIds.value)
    next.delete(messageId)
    selectedIds.value = next
  }

  const removeMessages = (ids: Set<bigint>) => {
    messages.value = messages.value.filter((message) => !ids.has(message.id))
    const next = new Set(selectedIds.value)
    for (const id of ids) next.delete(id)
    selectedIds.value = next
  }

  const openMessage = (messageId: bigint) => {
    if (openMessageId.value === messageId) {
      openMessageId.value = null
      openMessageId.value = messageId
      return
    }

    const summary = messages.value.find((message) => message.id === messageId)
    if (summary && inbox && summary.unread) {
      updateMessageUnread(messageId, false)
      changeUnreadMessagesBadge(-1)
    }

    openMessageId.value = messageId
    updatePageUrl(messageId)
  }

  const closeMessage = () => {
    openMessageId.value = null
    updatePageUrl(null)
  }

  const toggleSelect = (messageId: bigint) => {
    const next = new Set(selectedIds.value)
    if (next.has(messageId)) next.delete(messageId)
    else next.add(messageId)
    selectedIds.value = next
  }

  const selectAllVisible = () => {
    const next = new Set(selectedIds.value)
    for (const msg of messages.value) next.add(msg.id)
    selectedIds.value = next
  }

  const deselectAll = () => {
    selectedIds.value = new Set()
  }

  const handleSearch = (query: string, dateAfter: string, dateBefore: string) => {
    searchQuery.value = query
    searchDateAfter.value = dateAfter
    searchDateBefore.value = dateBefore
    searchKey.value += 1
    selectedIds.value = new Set()
    closeMessage()
  }

  const markMessageUnread = async () => {
    const messageId = openMessageId.value
    if (!messageId) return
    try {
      const resp = await fetch(`/api/web/messages/${messageId}/unread`, {
        method: "POST",
        priority: "high",
      })
      assert(resp.ok, `${resp.status} ${resp.statusText}`)
      changeUnreadMessagesBadge(1)
      updateMessageUnread(messageId, true)
      closeMessage()
    } catch (error) {
      console.error("Messages: Failed to mark unread", messageId, error)
      alert(error.message)
    }
  }

  const deleteMessage = async () => {
    const messageId = openMessageId.value
    if (!messageId) return
    if (!confirm(t("messages.delete_confirmation"))) return
    try {
      const resp = await fetch(`/api/web/messages/${messageId}/delete`, {
        method: "POST",
        priority: "high",
      })
      assert(resp.ok, `${resp.status} ${resp.statusText}`)
      removeMessage(messageId)
      closeMessage()
    } catch (error) {
      console.error("Messages: Failed to delete", messageId, error)
      alert(error.message)
    }
  }

  // Bulk actions
  const bulkMarkRead = async () => {
    const ids = [...selectedIds.value]
    if (!ids.length) return
    try {
      const body = new URLSearchParams()
      for (const id of ids) body.append("message_id", id.toString())
      const resp = await fetch("/api/web/messages/bulk/read", {
        method: "POST",
        body,
        priority: "high",
      })
      assert(resp.ok, `${resp.status} ${resp.statusText}`)

      // Count how many were actually unread before marking
      let unreadCount = 0
      messages.value = messages.value.map((msg) => {
        if (!selectedIds.value.has(msg.id)) return msg
        if (msg.unread) unreadCount++
        return msg.unread ? { ...msg, unread: false } : msg
      })
      if (unreadCount) changeUnreadMessagesBadge(-unreadCount)
      selectedIds.value = new Set()
    } catch (error) {
      console.error("Messages: Failed to bulk mark read", error)
      alert(error.message)
    }
  }

  const bulkMarkUnread = async () => {
    const ids = [...selectedIds.value]
    if (!ids.length) return
    try {
      const body = new URLSearchParams()
      for (const id of ids) body.append("message_id", id.toString())
      const resp = await fetch("/api/web/messages/bulk/unread", {
        method: "POST",
        body,
        priority: "high",
      })
      assert(resp.ok, `${resp.status} ${resp.statusText}`)

      let readCount = 0
      messages.value = messages.value.map((msg) => {
        if (!selectedIds.value.has(msg.id)) return msg
        if (!msg.unread) readCount++
        return !msg.unread ? { ...msg, unread: true } : msg
      })
      if (readCount) changeUnreadMessagesBadge(readCount)
      selectedIds.value = new Set()
    } catch (error) {
      console.error("Messages: Failed to bulk mark unread", error)
      alert(error.message)
    }
  }

  const bulkDelete = async () => {
    const ids = [...selectedIds.value]
    if (!ids.length) return
    if (
      !confirm(t("messages.bulk_delete_confirmation", { count: ids.length }))
    )
      return
    try {
      const body = new URLSearchParams()
      for (const id of ids) body.append("message_id", id.toString())
      const resp = await fetch("/api/web/messages/bulk/delete", {
        method: "POST",
        body,
        priority: "high",
      })
      assert(resp.ok, `${resp.status} ${resp.statusText}`)
      const removed = new Set(ids.map((id) => BigInt(id)))
      removeMessages(removed)
      closeMessage()
    } catch (error) {
      console.error("Messages: Failed to bulk delete", error)
      alert(error.message)
    }
  }

  // Effect: Fetch open message details
  useSignalEffect(() => {
    const messageId = openMessageId.value
    if (!messageId) {
      previewState.value = { status: "closed" }
      return
    }

    previewState.value = { status: "loading" }
    const abortController = new AbortController()
    const isStale = () =>
      abortController.signal.aborted || openMessageId.value !== messageId

    const fetchMessage = async () => {
      try {
        const resp = await fetch(`/api/web/messages/${messageId}`, {
          signal: abortController.signal,
          priority: "high",
        })
        assert(resp.ok, `${resp.status} ${resp.statusText}`)

        const buffer = await resp.arrayBuffer()
        const message = fromBinary(MessageReadSchema, new Uint8Array(buffer))
        assert(message.sender, "Messages: Missing sender in read response")
        if (isStale()) return

        previewState.value = { status: "ready", message }
      } catch (error) {
        if (error.name === "AbortError" || isStale()) return
        console.error("Messages: Failed to fetch", messageId, error)
        previewState.value = {
          status: "error",
          error: error.message,
        }
      }
    }

    fetchMessage()
    return () => abortController.abort()
  })

  // Effect: Scroll preview into view when opened
  useSignalEffect(() => {
    if (!openMessageId.value) return
    previewRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
  })

  const selectedCount = selectedIds.value.size

  return (
    <div class="row flex-wrap-reverse">
      <div class="col-lg">
        <SearchBar onSearch={handleSearch} />
        <BulkActionBar
          selectedCount={selectedCount}
          inbox={inbox}
          totalVisible={messages.value.length}
          onSelectAll={selectAllVisible}
          onDeselectAll={deselectAll}
          onBulkRead={bulkMarkRead}
          onBulkUnread={bulkMarkUnread}
          onBulkDelete={bulkDelete}
        />
        <div>
          <StandardPagination
            key={searchKey.value}
            action={currentAction}
            protobuf={MessagePageSchema}
            onLoad={(data) => {
              messages.value = data.messages

              const messageId = openMessageId.peek() ?? getMessageFromPageUrl()
              if (messageId) {
                if (data.messages.some((message) => message.id === messageId)) {
                  openMessage(messageId)
                } else {
                  closeMessage()
                }
              }
            }}
          >
            {() => (
              <ul class="messages-list social-list list-unstyled mb-2">
                {messages.value.length ? (
                  messages.value.map((message) => (
                    <MessagesListItem
                      message={message}
                      inbox={inbox}
                      openMessageId={openMessageId.value}
                      selected={selectedIds.value.has(message.id)}
                      onOpen={openMessage}
                      onToggleSelect={toggleSelect}
                      key={message.id}
                    />
                  ))
                ) : (
                  <MessagesEmpty />
                )}
              </ul>
            )}
          </StandardPagination>
        </div>
      </div>
      {openMessageId.value && (
        <div class="col-lg mb-3">
          <MessagePreview
            inbox={inbox}
            messageId={openMessageId.value}
            state={previewState.value}
            onClose={closeMessage}
            onUnread={markMessageUnread}
            onDelete={deleteMessage}
            previewRef={previewRef}
          />
        </div>
      )}
    </div>
  )
}

mount("messages-index-body", (body) => {
  const root = body.querySelector<HTMLElement>(".messages-index-root")!
  const { inbox, action } = root.dataset
  render(
    <MessagesIndex
      inbox={inbox === "True"}
      action={action!}
    />,
    root,
  )
})
