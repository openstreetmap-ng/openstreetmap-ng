import { t } from "i18next"
import { changeUnreadMessagesBadge } from "../_navbar.js"
import { qsEncode, qsParse } from "../_qs.js"
import { configureStandardForm } from "../_standard-form"

const body = document.querySelector("body.messages-index-body")
if (body) {
    const messages = body.querySelectorAll(".messages-list .social-action")
    const messagePreview = body.querySelector(".message-preview")
    const messageSender = messagePreview.querySelector(".message-sender")
    const senderAvatar = messageSender.querySelector("img.avatar")
    const senderLink = messageSender.querySelector("a.sender-link")
    const messageTime = messagePreview.querySelector(".message-time")
    const replyLink = messagePreview.querySelector("a.reply-link")
    const messageTitle = messagePreview.querySelector(".message-title")
    const messageBody = messagePreview.querySelector(".message-body")
    const loadingSpinner = messagePreview.querySelector(".loading")

    let abortController = null
    let openTarget = null
    let openMessageId = null

    /**
     * Open a message in the sidebar preview panel.
     * @param {HTMLElement} target
     * @returns {void}
     */
    const openMessagePreview = (target) => {
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

    /**
     * Close the message sidebar preview panel.
     * @returns {void}
     */
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

    /**
     * Update the URL with the given message id, without reloading the page
     * @param {number|undefined} messageId Message id
     * @returns {void}
     */
    const updatePageUrl = (messageId) => {
        const searchParams = qsParse(window.location.search.substring(1))
        searchParams.before = maxMessageId + 1n
        searchParams.show = messageId
        const url = `${window.location.pathname}?${qsEncode(searchParams)}${window.location.hash}`
        window.history.replaceState(null, "", url)
    }

    // Configure message header buttons
    const closePreviewButton = messagePreview.querySelector(".btn-close")
    closePreviewButton.addEventListener("click", closeMessagePreview)

    const unreadButton = messagePreview.querySelector(".unread-button")
    const unreadForm = messagePreview.querySelector("form.unread-form")
    if (unreadButton) {
        unreadButton.addEventListener("click", () => {
            unreadForm.action = `/api/web/messages/${openMessageId}/unread`
            unreadForm.requestSubmit()
        })
        configureStandardForm(unreadForm, () => {
            console.debug("onUnreadFormSuccess", openMessageId)
            openTarget.classList.add("unread")
            changeUnreadMessagesBadge(1)
            closeMessagePreview()
        })
    }

    const deleteButton = messagePreview.querySelector(".delete-button")
    const deleteForm = messagePreview.querySelector("form.delete-form")
    deleteButton.addEventListener("click", () => {
        if (!confirm(t("messages.delete_confirmation"))) return
        deleteForm.action = `/api/web/messages/${openMessageId}/delete`
        deleteForm.requestSubmit()
    })
    configureStandardForm(deleteForm, () => {
        console.debug("onDeleteFormSuccess", openMessageId)
        openTarget.remove()
        closeMessagePreview()
    })

    // Configure message selection
    let maxMessageId = 0n
    for (const message of messages) {
        const messageId = BigInt(message.dataset.id)
        maxMessageId = messageId > maxMessageId ? messageId : maxMessageId
        message.addEventListener("click", ({ target }) => {
            if (target.tagName === "A") return
            openMessagePreview(message)
        })
        message.addEventListener("keydown", (event) => {
            if (event.key !== "Enter") return
            openMessagePreview(message)
        })
        if (message.classList.contains("active")) {
            openMessagePreview(message)
        }
    }
    console.debug("Highest message id is", maxMessageId)
}
