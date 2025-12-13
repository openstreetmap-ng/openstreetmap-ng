import { mount } from "@lib/mount"
import { configureScrollspy } from "@lib/scrollspy"
import { configureStandardForm } from "@lib/standard-form"
import { configureStandardPagination } from "@lib/standard-pagination"
import { delay } from "@std/async/delay"
import { Collapse, Offcanvas } from "bootstrap"

// Details page: always expanded; comments live under #comments
mount("diary-details-body", (body) => {
    const comments = document.getElementById("comments")!
    let disposePagination = configureStandardPagination(comments)

    // Subscriptions affect global state; simple, reliable full reload
    configureStandardForm(body.querySelector("form.subscription-form"), () => {
        window.location.reload()
    })

    configureStandardForm(body.querySelector("form.comment-form"), () => {
        disposePagination()
        disposePagination = configureStandardPagination(comments)
    })
})

// Listings page: diaries start collapsed; expand and lazy‑load comments per entry
mount("diary-index-body", (body) => {
    const disposers = new WeakMap<Element, () => void>()

    for (const article of body.querySelectorAll("article.diary")) {
        const diaryBody = article.querySelector(".diary-body")!
        const readMore = article.querySelector(".diary-read-more")!

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
        readMore.addEventListener(
            "click",
            async () => {
                article.classList.add("show")
                readMore.classList.add("invisible")
                await delay(50)
                readMore.remove()
            },
            { once: true },
        )

        const commentsContainer = article.querySelector(".diary-comments")!

        commentsContainer.addEventListener(
            Collapse.Events.show,
            () => {
                // Initialize only once on first toggle; reuse DOM thereafter
                const dispose = configureStandardPagination(commentsContainer)
                disposers.set(commentsContainer, dispose)

                const subForm = commentsContainer.querySelector(
                    "form.subscription-form",
                )
                configureStandardForm(subForm, () => {
                    window.location.reload()
                })

                const commentForm = commentsContainer.querySelector("form.comment-form")
                configureStandardForm(commentForm, () => {
                    commentForm!.reset()
                    disposers.get(commentsContainer)?.()
                    const d2 = configureStandardPagination(commentsContainer)
                    disposers.set(commentsContainer, d2)
                })
            },
            { once: true },
        )
    }

    // Custom scrollspy for diary navigation
    const diaryList = body.querySelector(".diary-list")
    const scrollNav = document.getElementById("diary-scroll-nav")
    configureScrollspy(diaryList, scrollNav)

    // Hide the diary scroll navigation panel after any link click
    // (mobile view)
    const navOffcanvas = document.getElementById("diary-scroll-nav-offcanvas")
    if (navOffcanvas) {
        const navOffcanvasInstance = Offcanvas.getOrCreateInstance(navOffcanvas)
        navOffcanvas.addEventListener("click", (e) => {
            const target = e.target
            if (!(target instanceof Element)) return
            if (!target.closest("a[href]")) return
            navOffcanvasInstance.hide()
        })
    }
})

mount(["diary-details-body", "diary-index-body"], (body) => {
    for (const link of body.querySelectorAll(
        "article.diary .share a[data-action=copy-link]",
    )) {
        link.addEventListener("click", async (e) => {
            e.preventDefault()
            try {
                await navigator.clipboard.writeText(link.href)
                console.debug("DiaryIndex: Copied share link", link.href)
            } catch (error) {
                console.warn("DiaryIndex: Failed to copy share link", error)
                alert(error.message)
            }
        })
    }
})
