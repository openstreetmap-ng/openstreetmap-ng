import { t } from "i18next"
import { changeUnreadMessagesBadge } from "../_navbar"
import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.messages-index-body")
if (body) {
    const messages = body.querySelectorAll(".messages-list li.social-action")
    const messagePreview = body.querySelector(".message-preview")
    const messageSender = messagePreview.querySelector(".message-sender")
    const senderAvatar = messageSender.querySelector("img.avatar")
    const senderLink = messageSender.querySelector("a.sender-link")
    const messageTime = messagePreview.querySelector(".message-time")
    const replyLink = messagePreview.querySelector("a.reply-link")
    const messageTitle = messagePreview.querySelector(".message-title")
    const messageBody = messagePreview.querySelector(".message-body")
    const loadingSpinner = messagePreview.querySelector(".loading")

    let abortController: AbortController | null = null
    let openTarget: Element = null
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
        messagePreview.classList.remove("d-none")
        loadingSpinner.classList.remove("d-none")

        // Set show parameter in URL
        updatePageUrl(openMessageId)

        // Update reply link
        replyLink.href = `/message/new?reply=${openMessageId}`

        // Abort any pending request
        if (abortController) abortController.abort()
        abortController = new AbortController()

        fetch(`/api/web/messages/${openMessageId}`, {
            method: "GET",
            mode: "same-origin",
            cache: "no-store",
            signal: abortController.signal,
            priority: "high",
        })
            .then(async (resp) => {
                if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
                console.debug("Fetched message", openMessageId)
                const { user_display_name, user_avatar_url, time, subject, body_rich } = await resp.json()
                senderAvatar.src = user_avatar_url
                senderLink.href = `/user/${user_display_name}`
                senderLink.textContent = user_display_name
                messageTime.textContent = time
                messageTitle.textContent = subject
                messageBody.innerHTML = body_rich
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
        messagePreview.classList.add("d-none")
        if (abortController) abortController.abort()
        abortController = null
        openTarget.classList.remove("active")
        openTarget = null
        openMessageId = null

        // Remove show parameter from URL
        updatePageUrl(undefined)
    }

    /** Update the URL with the given message id, without reloading the page */
    const updatePageUrl = (messageId: string | undefined) => {
        const url = new URL(location.href)
        url.searchParams.set("before", (messageIdMax + 1n).toString())
        url.searchParams.set("show", messageId)
        window.history.replaceState(null, "", url)
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
    let messageIdMax = 0n
    for (const message of messages) {
        const messageId = BigInt(message.dataset.id)
        messageIdMax = messageId > messageIdMax ? messageId : messageIdMax

        // On message click, open preview if target is not a link
        message.addEventListener("click", ({ target }) => {
            const tagName = (target as HTMLElement).tagName
            console.debug("onMessageClick", tagName)
            if (tagName === "A") return
            openMessagePreview(message)
        })
        message.addEventListener("keydown", (event: KeyboardEvent) => {
            if (event.key !== "Enter") return
            openMessagePreview(message)
        })

        // Auto-open the message if it's marked as active
        if (message.classList.contains("active")) {
            openMessagePreview(message)
        }
    }
    console.debug("Highest message id is", messageIdMax)
}
