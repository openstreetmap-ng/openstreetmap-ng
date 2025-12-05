import { mount } from "@lib/mount"
import { configureScrollspy } from "@lib/scrollspy"
import { configureStandardForm } from "@lib/standard-form"
import { configureStandardPagination } from "@lib/standard-pagination"
import { Offcanvas } from "bootstrap"

// Details page: always expanded; comments live under #comments
mount("diary-details-body", (body) => {
    const comments = body.querySelector("#comments")
    let disposePagination = configureStandardPagination(comments)

    // Subscriptions affect global state; simple, reliable full reload
    configureStandardForm(body.querySelector("form.subscription-form"), () => {
        window.location.reload()
    })

    configureStandardForm(body.querySelector("form.comment-form"), () => {
        const paginationElement = comments.querySelector("ul.pagination")
        if (paginationElement) paginationElement.dataset.numItems = "-1"
        disposePagination?.()
        disposePagination = configureStandardPagination(comments)
    })
})

// Listings page: diaries start collapsed; expand and lazy‑load comments per entry
mount("diary-index-body", (body) => {
    const disposers = new WeakMap<Element, () => void>()

    for (const article of body.querySelectorAll("article.diary")) {
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
        readMore.addEventListener(
            "click",
            () => {
                article.classList.add("show")
                readMore.classList.add("invisible")
                setTimeout(() => {
                    readMore.remove()
                }, 50)
            },
            { once: true },
        )

        const commentsCont = article.querySelector(".diary-comments")

        commentsCont.addEventListener(
            "show.bs.collapse",
            () => {
                // Initialize only once on first toggle; reuse DOM thereafter
                const dispose = configureStandardPagination(commentsCont)
                disposers.set(commentsCont, dispose)

                const subForm = commentsCont.querySelector("form.subscription-form")
                // Keep this simple; reloading reflects state everywhere
                configureStandardForm(subForm, () => {
                    window.location.reload()
                })

                const commentform = commentsCont.querySelector("form.comment-form")
                configureStandardForm(commentform, () => {
                    commentform.reset()
                    const paginationElement =
                        commentsCont.querySelector("ul.pagination")
                    if (paginationElement) paginationElement.dataset.numItems = "-1"
                    disposers.get(commentsCont)?.()
                    const d2 = configureStandardPagination(commentsCont)
                    disposers.set(commentsCont, d2)
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
    const navOffcanvasInstance = Offcanvas.getOrCreateInstance(navOffcanvas)
    navOffcanvas.addEventListener("click", ({ target }) => {
        if (!(target instanceof Element)) return
        const link = target.closest("a[href]")
        if (!(link instanceof HTMLAnchorElement)) return
        navOffcanvasInstance.hide()
    })
})

mount(["diary-details-body", "diary-index-body"], (body) => {
    for (const link of body.querySelectorAll(
        "article.diary .share a[data-action=copy-link]",
    )) {
        link.addEventListener("click", (e) => {
            e.preventDefault()
            navigator.clipboard.writeText(link.href)
        })
    }
})
