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
  onOpen,
}: {
  message: MessagePage_Summary
  inbox: boolean
  openMessageId: bigint | null
  onOpen: (messageId: bigint) => void
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

  return (
    <li
      class={`social-entry clickable ${isUnread ? "unread" : ""} ${
        isActive ? "active" : ""
      }`}
    >
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

const MessageActionsToolbar = ({
  inbox,
  messageId,
  message,
  onUnread,
  onDelete,
}: {
  inbox: boolean
  messageId: bigint
  message: MessageRead | null
  onUnread: () => void
  onDelete: () => void
}) => {
  const showReplyAll = inbox && (message?.recipients.length ?? 0) > 1
  const disabledGroup = message ? inbox && !message.isRecipient : true

  return (
    <fieldset class={`btn-group border-0 p-0 m-0 ${disabledGroup ? "disabled" : ""}`}>
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

  return (
    <div
      class="message-preview card sticky-top"
      ref={previewRef}
    >
      <div class="py-3 card-header">
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
                      class="d-inline-block"
                      href={`/user/${sender!.displayName}`}
                    >
                      {sender!.displayName}
                    </a>
                    <div>
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
            <MessageActionsToolbar
              inbox={inbox}
              messageId={messageId}
              message={message}
              onUnread={onUnread}
              onDelete={onDelete}
            />
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
        <h5 class="mb-3">{message?.subject}</h5>
        <div
          class="rich-text"
          dangerouslySetInnerHTML={{ __html: message?.bodyRich ?? "" }}
        />
        {state.status === "loading" && (
          <div class="text-center mt-4">
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
      </div>
    </div>
  )
}

const MessagesIndex = ({ inbox, action }: { inbox: boolean; action: string }) => {
  const messages = useSignal<MessagePage_Summary[]>([])
  const openMessageId = useSignal<bigint | null>(null)
  const previewState = useSignal<PreviewState>({ status: "closed" })
  const previewRef = useRef<HTMLDivElement>(null)

  const updateMessageUnread = (messageId: bigint, unread: boolean) => {
    messages.value = messages.value.map((message) => {
      if (message.id !== messageId) return message
      if (message.unread === unread) return message
      return { ...message, unread }
    })
  }

  const removeMessage = (messageId: bigint) => {
    messages.value = messages.value.filter((message) => message.id !== messageId)
  }

  const openMessage = (messageId: bigint) => {
    if (openMessageId.value === messageId) {
      // Reload when clicking the same message
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
    if (!(messageId && confirm(t("messages.delete_confirmation")))) return
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

  // Effect: Fetch open message details
  useSignalEffect(() => {
    const messageId = openMessageId.value
    if (!messageId) {
      previewState.value = { status: "closed" }
      return
    }

    previewState.value = { status: "loading" }
    const abortController = new AbortController()

    const fetchMessage = async () => {
      try {
        const resp = await fetch(`/api/web/messages/${messageId}`, {
          signal: abortController.signal,
          priority: "high",
        })
        assert(resp.ok, `${resp.status} ${resp.statusText}`)

        const buffer = await resp.arrayBuffer()
        abortController.signal.throwIfAborted()
        const message = fromBinary(MessageReadSchema, new Uint8Array(buffer))

        previewState.value = { status: "ready", message }
      } catch (error) {
        if (error.name === "AbortError") return
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
    previewRef.current!.scrollIntoView({ behavior: "smooth", block: "start" })
  })

  return (
    <div class="row flex-wrap-reverse">
      <div class="col-lg">
        <StandardPagination
          action={action}
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
                    onOpen={openMessage}
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

mount("messages-index-body", () => {
  const root = document.getElementById("MessagesIndex")!
  const { inbox, action } = root.dataset
  render(
    <MessagesIndex
      inbox={inbox === "True"}
      action={action!}
    />,
    root,
  )
})
