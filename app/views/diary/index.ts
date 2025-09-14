import { configureStandardForm } from "../lib/standard-form"
import { configureStandardPagination } from "../lib/standard-pagination"

// Details page: always expanded; comments live under #comments
const detailsBody = document.querySelector("body.diary-details-body")
if (detailsBody) {
    const comments = document.getElementById("comments")
    let disposePagination = configureStandardPagination(comments)

    // Subscriptions affect global state; simple, reliable full reload
    configureStandardForm(detailsBody.querySelector("form.subscription-form"), () => {
        window.location.reload()
    })

    configureStandardForm(detailsBody.querySelector("form.comment-form"), () => {
        const paginationElement = comments.querySelector("ul.pagination")
        if (paginationElement) paginationElement.dataset.numItems = "-1"
        disposePagination?.()
        disposePagination = configureStandardPagination(comments)
    })
}

// Listings page: diaries start collapsed; expand and lazy‑load comments per entry
const indexBody = document.querySelector("body.diary-index-body")
if (indexBody) {
    const disposers = new WeakMap<Element, () => void>()

    for (const article of indexBody.querySelectorAll("article.diary")) {
        const diaryBody = article.querySelector(".diary-body")
        const readMore = article.querySelector(".diary-read-more")

        // Mark entry clamped when rendered height < content height
        const updateClamp = () => {
            if (article.classList.contains("show")) return
            const clamped = diaryBody.scrollHeight - 1 > diaryBody.clientHeight
            article.classList.toggle("diary-clamped", clamped)
            readMore.classList.toggle("d-none", !clamped)
        }

        updateClamp()
        // Images and rich content may change height; observe and re-evaluate
        const ro = new ResizeObserver(updateClamp)
        ro.observe(diaryBody)
        article.addEventListener(
            "transitionend",
            () => {
                if (article.classList.contains("show")) ro.disconnect()
            },
            { once: true },
        )

        // Expand smoothly, then remove the button to avoid layout jitter
        readMore.addEventListener("click", () => {
            article.classList.add("show")
            readMore.classList.add("invisible")
            setTimeout(() => {
                readMore.remove()
            }, 50)
        })

        const toggleBtn = article.querySelector("button.diary-comments-toggle")
        const targetSel = toggleBtn?.dataset.target
        const container = targetSel ? article.querySelector(targetSel) : null

        if (toggleBtn && container) {
            const initCommentsIfNeeded = () => {
                // Initialize only once on first toggle; reuse DOM thereafter
                if (toggleBtn.dataset.initialized) return
                toggleBtn.dataset.initialized = "1"
                const dispose = configureStandardPagination(container)
                disposers.set(container, dispose)

                const subForm = container.querySelector("form.subscription-form")
                // Keep this simple; reloading reflects state everywhere
                configureStandardForm(subForm, () => {
                    window.location.reload()
                })

                const commentform = container.querySelector("form.comment-form")
                configureStandardForm(commentform, () => {
                    commentform.reset()
                    const paginationElement = container.querySelector("ul.pagination")
                    if (paginationElement) paginationElement.dataset.numItems = "-1"
                    disposers.get(container)?.()
                    const d2 = configureStandardPagination(container)
                    disposers.set(container, d2)
                })
            }

            toggleBtn.addEventListener("click", () => {
                const isHidden = container.classList.contains("d-none")
                if (isHidden) initCommentsIfNeeded()
                container.classList.toggle("d-none")
                const expanded = !container.classList.contains("d-none")
                toggleBtn.ariaExpanded = expanded ? "true" : "false"
            })
        }
    }
}

if (detailsBody || indexBody) {
    for (const link of (detailsBody ?? indexBody).querySelectorAll(
        'article.diary .share a[data-action="copy-link"]',
    )) {
        link.addEventListener("click", (e) => {
            e.preventDefault()
            navigator.clipboard.writeText(link.href)
        })
    }
}
