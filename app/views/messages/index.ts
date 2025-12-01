import { t } from "i18next"
import { resolveDatetimeLazy } from "../lib/datetime"
import { mount } from "../lib/mount"
import { configureReportButton } from "../lib/report-modal"
import { configureStandardForm } from "../lib/standard-form"
import { changeUnreadMessagesBadge } from "../navbar/navbar"

mount("messages-index-body", (body) => {
    const messages = body.querySelectorAll(".messages-list li.social-entry.clickable")
    const messagePreview = body.querySelector(".message-preview") as HTMLElement
    const messagePreviewContainer = messagePreview.parentElement
    const messageSender = messagePreview.querySelector(".message-sender")
    const senderAvatar = messageSender.querySelector("img.avatar")
    const senderLink = messageSender.querySelector("a.sender-link")
    const messageTime = messagePreview.querySelector(".message-time")
    const messageRecipients = messagePreview.querySelector(".message-recipients")
    const btnGroup = messagePreview.querySelector(".btn-group")
    const replyLink = btnGroup.querySelector("a.reply-link")
    const replyAllLink = btnGroup.querySelector("a.reply-all-link")
    const messageTitle = messagePreview.querySelector(".message-title")
    const messageBody = messagePreview.querySelector(".message-body")
    const loadingSpinner = messagePreview.querySelector(".loading")
    const recipientTemplate = body.querySelector("template.message-recipient-template")
    const reportButton = messagePreview.querySelector("button.report-btn")

    let abortController: AbortController | null = null
    let openTarget: HTMLElement = null
    let openMessageId: string | null = null

    /** Open a message in the sidebar preview panel */
    const openMessagePreview = (target: HTMLElement) => {
        const newMessageId = target.dataset.id
        if (openMessageId === newMessageId) return
        if (openTarget) closeMessagePreview()

        openTarget = target
        openMessageId = newMessageId
        console.debug("openMessagePreview", openMessageId)
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

        fetch(`/api/web/messages/${openMessageId}`, {
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
                const { sender, recipients, time, subject, body_rich, is_recipient } =
                    await resp.json()
                console.debug(
                    "Fetched message",
                    openMessageId,
                    sender,
                    recipients,
                    is_recipient,
                )

                senderAvatar.src = sender.avatar_url
                senderLink.href = `/user/${sender.display_name}`
                senderLink.textContent = sender.display_name
                messageTime.innerHTML = time

                // Add each recipient
                const messageRecipientsFragment = document.createDocumentFragment()
                for (const user of recipients) {
                    const userElement = recipientTemplate.content.cloneNode(
                        true,
                    ) as HTMLElement
                    const avatar = userElement.querySelector("img.avatar")
                    const link = userElement.querySelector("a.user-link")

                    avatar.src = user.avatar_url
                    link.href = `/user/${user.display_name}`
                    link.textContent = user.display_name

                    messageRecipientsFragment.appendChild(userElement)
                }
                messageRecipients.innerHTML = ""
                messageRecipients.appendChild(messageRecipientsFragment)
                if (replyAllLink && recipients.length > 1) {
                    replyAllLink.classList.remove("d-none")
                }

                // Hide button group when moderator viewing reported message
                btnGroup.classList.toggle("disabled", !is_recipient)

                messageTitle.textContent = subject
                messageBody.innerHTML = body_rich
                resolveDatetimeLazy(messageTime)

                // Configure report button
                configureReportButton(reportButton, {
                    type: "user",
                    typeId: sender.id,
                    action: "user_message",
                    actionId: openMessageId,
                })
            })
            .catch((error) => {
                if (error.name === "AbortError") return
                console.error("Failed to fetch message", error)
                messageBody.textContent = error.message
                alert(error.message)
            })
            .finally(() => {
                loadingSpinner.classList.add("d-none")
            })
    }

    /** Close the message sidebar preview panel */
    const closeMessagePreview = () => {
        console.debug("closeMessagePreview", openMessageId)
        messagePreviewContainer.classList.add("d-none")
        abortController?.abort()
        abortController = null
        openTarget.classList.remove("active")
        openTarget = null
        openMessageId = null

        // Remove show parameter from URL
        updatePageUrl(undefined)
    }

    /** Update the URL with the given message, without reloading the page */
    const updatePageUrl = (message: HTMLElement | undefined) => {
        if (message) {
            const messageLink = message.querySelector("a.stretched-link")
            window.history.replaceState(null, "", messageLink.href)
        } else {
            const url = new URL(window.location.href)
            url.searchParams.delete("show")
            window.history.replaceState(null, "", url)
        }
    }

    // Configure message header buttons
    const closePreviewButton = messagePreview.querySelector(".btn-close")
    closePreviewButton.addEventListener("click", closeMessagePreview)

    const unreadButton = messagePreview.querySelector("button.unread-btn")
    if (unreadButton) {
        const unreadForm = messagePreview.querySelector("form.unread-form")
        configureStandardForm(unreadForm, () => {
            // On success callback, mark the message as unread and update the badge
            console.debug("onUnreadFormSuccess", openMessageId)
            openTarget.classList.add("unread")
            changeUnreadMessagesBadge(1)
            closeMessagePreview()
        })

        // On unread button click, submit the form
        unreadButton.addEventListener("click", () => {
            console.debug("onUnreadButtonClick", openMessageId)
            unreadForm.action = `/api/web/messages/${openMessageId}/unread`
            unreadForm.requestSubmit()
        })
    }

    const deleteForm = messagePreview.querySelector("form.delete-form")
    configureStandardForm(deleteForm, () => {
        console.debug("onDeleteFormSuccess", openMessageId)
        openTarget.remove()
        closeMessagePreview()
    })

    const deleteButton = messagePreview.querySelector("button.delete-btn")
    deleteButton.addEventListener("click", () => {
        if (!confirm(t("messages.delete_confirmation"))) return
        deleteForm.action = `/api/web/messages/${openMessageId}/delete`
        deleteForm.requestSubmit()
    })

    // Configure message selection
    for (const message of messages) {
        const messageLink = message.querySelector("a.stretched-link")

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
