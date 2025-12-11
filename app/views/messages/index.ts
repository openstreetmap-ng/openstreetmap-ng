import { fromBinary } from "@bufbuild/protobuf"
import { resolveDatetimeLazy } from "@lib/datetime-inputs"
import { mount } from "@lib/mount"
import { MessageReadSchema } from "@lib/proto/shared_pb"
import { configureReportButton } from "@lib/report-modal"
import { configureStandardForm } from "@lib/standard-form"
import { assert, assertExists } from "@std/assert"
import { t } from "i18next"
import { changeUnreadMessagesBadge } from "../navbar/navbar"

mount("messages-index-body", (body) => {
    const messages = body.querySelectorAll(".messages-list li.social-entry.clickable")
    const messagePreview = body.querySelector<HTMLElement>(".message-preview")!
    const messagePreviewContainer = messagePreview.parentElement!
    const messageSender = messagePreview.querySelector(".message-sender")!
    const senderAvatar = messageSender.querySelector("img.avatar")!
    const senderLink = messageSender.querySelector("a.sender-link")!
    const messageTime = messagePreview.querySelector(".message-time")!
    const messageRecipients = messagePreview.querySelector(".message-recipients")!
    const buttonGroup = messagePreview.querySelector(".btn-group")!
    const replyLink = buttonGroup.querySelector("a.reply-link")!
    const replyAllLink = buttonGroup.querySelector("a.reply-all-link")
    const messageTitle = messagePreview.querySelector(".message-title")!
    const messageBody = messagePreview.querySelector(".message-body")!
    const loadingSpinner = messagePreview.querySelector(".loading")!
    const recipientTemplate = body.querySelector("template.message-recipient-template")!
    const reportButton = messagePreview.querySelector("button.report-btn")

    let abortController: AbortController | undefined
    let openTarget: HTMLElement | null = null
    let openMessageId: string | null = null

    const openMessagePreview = async (target: HTMLElement) => {
        const newMessageId = target.dataset.id!
        if (openMessageId === newMessageId) return
        closeMessagePreview()

        openTarget = target
        openMessageId = newMessageId
        console.debug("Messages: Opening preview", openMessageId)
        if (openTarget.classList.contains("unread")) {
            openTarget.classList.remove("unread")
            changeUnreadMessagesBadge(-1)
        }
        openTarget.classList.add("active")
        senderAvatar.removeAttribute("src")
        senderLink.innerHTML = ""
        messageTime.innerHTML = ""
        messageTitle.innerHTML = ""
        messageBody.innerHTML = ""
        messagePreviewContainer.classList.remove("d-none")
        loadingSpinner.classList.remove("d-none")

        // Set show parameter in URL
        updatePageUrl(openTarget)

        // Update reply link
        replyLink.href = `/message/new?reply=${openMessageId}`
        if (replyAllLink) {
            replyAllLink.classList.add("d-none")
            replyAllLink.href = `/message/new?reply_all=${openMessageId}`
        }

        // Abort any pending request
        abortController?.abort()
        abortController = new AbortController()

        // Scroll to the message container
        messagePreviewContainer.scrollIntoView({
            behavior: "smooth",
            block: "start",
        })

        try {
            const resp = await fetch(`/api/web/messages/${openMessageId}`, {
                signal: abortController.signal,
                priority: "high",
            })
            assert(resp.ok, `${resp.status} ${resp.statusText}`)

            const buffer = await resp.arrayBuffer()
            const message = fromBinary(MessageReadSchema, new Uint8Array(buffer))
            console.debug("Messages: Loaded", openMessageId, {
                sender: message.sender?.displayName,
                recipients: message.recipients.length,
            })

            const sender = message.sender!
            senderAvatar.src = sender.avatarUrl
            senderLink.href = `/user/${sender.displayName}`
            senderLink.textContent = sender.displayName
            messageTime.innerHTML = message.time

            // Add each recipient
            const messageRecipientsFragment = document.createDocumentFragment()
            for (const user of message.recipients) {
                const userElement = recipientTemplate.content.cloneNode(
                    true,
                ) as HTMLElement
                const avatar = userElement.querySelector("img.avatar")!
                const link = userElement.querySelector("a.user-link")!

                avatar.src = user.avatarUrl
                link.href = `/user/${user.displayName}`
                link.textContent = user.displayName

                messageRecipientsFragment.appendChild(userElement)
            }
            messageRecipients.innerHTML = ""
            messageRecipients.appendChild(messageRecipientsFragment)
            if (replyAllLink && message.recipients.length > 1) {
                replyAllLink.classList.remove("d-none")
            }

            // Hide button group when moderator viewing reported message
            buttonGroup.classList.toggle("disabled", !message.isRecipient)

            messageTitle.textContent = message.subject
            messageBody.innerHTML = message.bodyRich
            resolveDatetimeLazy(messageTime)

            // Configure report button
            configureReportButton(reportButton, {
                type: "user",
                typeId: sender.id,
                action: "user_message",
                actionId: openMessageId,
            })
        } catch (error) {
            if (error.name === "AbortError") return
            console.error("Messages: Failed to fetch", openMessageId, error)
            messageBody.textContent = error.message
            alert(error.message)
        } finally {
            loadingSpinner.classList.add("d-none")
        }
    }

    const closeMessagePreview = () => {
        if (!openTarget) return
        assertExists(openMessageId)

        console.debug("Messages: Closing preview", openMessageId)
        messagePreviewContainer.classList.add("d-none")
        abortController?.abort()
        openTarget.classList.remove("active")
        openTarget = null
        openMessageId = null

        // Remove show parameter from URL
        updatePageUrl(undefined)
    }

    const updatePageUrl = (message: HTMLElement | undefined) => {
        if (message) {
            const messageLink = message.querySelector("a.stretched-link")!
            window.history.replaceState(null, "", messageLink.href)
        } else {
            const url = new URL(window.location.href)
            url.searchParams.delete("show")
            window.history.replaceState(null, "", url)
        }
    }

    // Configure message header buttons
    const closePreviewButton = messagePreview.querySelector(".btn-close")!
    closePreviewButton.addEventListener("click", closeMessagePreview)

    const unreadButton = messagePreview.querySelector("button.unread-btn")
    if (unreadButton) {
        const unreadForm = messagePreview.querySelector("form.unread-form")!
        configureStandardForm(unreadForm, () => {
            // On success callback, mark the message as unread and update the badge
            const targetId = unreadForm.dataset.targetId!
            console.debug("Messages: Marked as unread", targetId)
            changeUnreadMessagesBadge(1)
            const target = body.querySelector(
                `.messages-list li[data-id="${targetId}"]`,
            )
            if (!target) return
            target.classList.add("unread")
            if (target === openTarget) closeMessagePreview()
        })

        // On unread button click, submit the form
        unreadButton.addEventListener("click", () => {
            console.debug("Messages: Mark as unread clicked", openMessageId)
            unreadForm.dataset.targetId = openMessageId!
            unreadForm.action = `/api/web/messages/${openMessageId}/unread`
            unreadForm.requestSubmit()
        })
    }

    const deleteForm = messagePreview.querySelector("form.delete-form")!
    configureStandardForm(deleteForm, () => {
        const targetId = deleteForm.dataset.targetId!
        console.debug("Messages: Deleted", targetId)
        const target = body.querySelector(`.messages-list li[data-id="${targetId}"]`)
        if (!target) return
        target.remove()
        if (target === openTarget) closeMessagePreview()
    })

    const deleteButton = messagePreview.querySelector("button.delete-btn")!
    deleteButton.addEventListener("click", () => {
        if (!confirm(t("messages.delete_confirmation"))) return
        deleteForm.dataset.targetId = openMessageId!
        deleteForm.action = `/api/web/messages/${openMessageId}/delete`
        deleteForm.requestSubmit()
    })

    // Configure message selection
    for (const message of messages) {
        const messageLink = message.querySelector("a.stretched-link")!

        // On message click, open preview if target is not a link
        messageLink.addEventListener("click", (e) => {
            if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
                return
            e.preventDefault()
            messageLink.blur()
            openMessagePreview(message)
        })
        messageLink.addEventListener("keydown", (e: KeyboardEvent) => {
            if (e.key !== "Enter") return
            e.preventDefault()
            messageLink.blur()
            openMessagePreview(message)
        })

        // Auto-open the message if it's marked as active
        if (message.classList.contains("active")) {
            openMessagePreview(message)
        }
    }
})
