import { Offcanvas } from "bootstrap"
import { mount } from "../lib/mount"
import { configureStandardForm } from "../lib/standard-form"
import { configureStandardPagination } from "../lib/standard-pagination"

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

// Custom scrollspy that activates based on which diary is most centered in viewport
const configureScrollspy = (
    body: HTMLElement,
    state?: { updateFn: () => void },
) => {
    const navLinks = document.querySelectorAll<HTMLAnchorElement>(
        "#diary-scroll-nav a.nav-link",
    )
    if (!navLinks.length) return

    const articles = body.querySelectorAll<HTMLElement>("article.diary")
    if (!articles.length) return

    let rafId: number | null = null
    let currentActiveLink: HTMLAnchorElement | null = null

    const updateActiveLink = () => {
        const viewportCenter = window.innerHeight / 2
        let closestArticle: HTMLElement | null = null
        let closestDistance = Number.POSITIVE_INFINITY

        // Find which article is closest to the center of the viewport
        for (const article of articles) {
            const rect = article.getBoundingClientRect()
            const articleCenter = rect.top + rect.height / 2
            const distance = Math.abs(articleCenter - viewportCenter)

            if (distance < closestDistance) {
                closestDistance = distance
                closestArticle = article
            }
        }

        // Update active state only if changed
        if (closestArticle) {
            const targetId = closestArticle.id
            const targetLink = Array.from(navLinks).find(
                (link) => link.getAttribute("href") === `#${targetId}`,
            )

            if (targetLink && targetLink !== currentActiveLink) {
                // Remove active from all links
                for (const link of navLinks) {
                    link.classList.remove("active")
                }
                // Add active to the target link
                targetLink.classList.add("active")
                currentActiveLink = targetLink
            }
        }
    }

    const onScroll = () => {
        if (rafId !== null) return
        rafId = requestAnimationFrame(() => {
            updateActiveLink()
            rafId = null
        })
    }

    // Initial update
    updateActiveLink()

    // Expose update function to state if provided
    if (state) {
        state.updateFn = updateActiveLink
    }

    // Listen to scroll events
    window.addEventListener("scroll", onScroll, { passive: true })

    // Return cleanup function
    return () => {
        window.removeEventListener("scroll", onScroll)
        if (rafId !== null) {
            cancelAnimationFrame(rafId)
        }
    }
}

// Listings page: diaries start collapsed; expand and lazy‑load comments per entry
mount("diary-index-body", (body) => {
    const disposers = new WeakMap<Element, () => void>()

    // Set up custom scrollspy
    const scrollspyState = { updateFn: () => {} }
    const disposeScrollspy = configureScrollspy(body, scrollspyState)

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
        const ro = new ResizeObserver(() => {
            updateClamp()
            // Update scrollspy when content size changes
            scrollspyState.updateFn()
        })
        ro.observe(diaryBody)
        article.addEventListener(
            "transitionend",
            () => {
                if (article.classList.contains("show")) {
                    ro.disconnect()
                }
                // Update scrollspy after expand/collapse animation
                scrollspyState.updateFn()
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

        const commentsCont = article.querySelector(".diary-comments")

        // Update scrollspy when comments section finishes expanding/collapsing
        commentsCont.addEventListener("shown.bs.collapse", () => {
            scrollspyState.updateFn()
        })
        commentsCont.addEventListener("hidden.bs.collapse", () => {
            scrollspyState.updateFn()
        })

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
        'article.diary .share a[data-action="copy-link"]',
    )) {
        link.addEventListener("click", (e) => {
            e.preventDefault()
            navigator.clipboard.writeText(link.href)
        })
    }
})
