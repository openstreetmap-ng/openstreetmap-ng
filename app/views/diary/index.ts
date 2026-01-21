import { createDisposeScope } from "@lib/dispose-scope"
import { mount } from "@lib/mount"
import { configureScrollspy } from "@lib/scrollspy"
import { configureStandardForm } from "@lib/standard-form"
import { configureStandardPagination } from "@lib/standard-pagination"
import { delay } from "@std/async/delay"
import { Offcanvas } from "bootstrap"
import { t } from "i18next"

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
  const diaryPagination = body.querySelector("div.diary-pagination")!
  const scrollNav = document.getElementById("diary-scroll-nav")!
  const navOffcanvas = document.getElementById("diary-scroll-nav-offcanvas")!
  const navContainer = navOffcanvas.querySelector("nav")!
  const navList = navContainer.querySelector("ul.nav")!
  const offcanvasButton = scrollNav.querySelector("button.btn-floating-bottom-left")!

  const navOffcanvasInstance = new Offcanvas(navOffcanvas)
  navOffcanvas.addEventListener("click", (e) => {
    const target = e.target
    if (!(target instanceof Element)) return
    if (!target.closest("a[href]")) return
    navOffcanvasInstance.hide()
  })

  const buildScrollNav = (renderContainer: HTMLElement) => {
    const diaries = renderContainer.querySelectorAll("article.diary")
    const hasDiaries = diaries.length > 0
    navContainer.hidden = !hasDiaries
    offcanvasButton.hidden = !hasDiaries

    const fragment = document.createDocumentFragment()

    for (const diary of diaries) {
      const diaryId = diary.id
      const title = diary.querySelector("a.diary-title-link")!.textContent!.trim()
      const badgeText = diary
        .querySelector(".diary-comments-btn .badge")!
        .textContent!.trim()
      const numComments = Number.parseInt(badgeText, 10)

      const li = document.createElement("li")
      li.className = "nav-item"

      const a = document.createElement("a")
      a.className = "nav-link d-flex justify-content-between align-items-center"
      a.href = `#${diaryId}`

      const spanTitle = document.createElement("span")
      spanTitle.className = "title"
      spanTitle.textContent = title

      const badge = document.createElement("span")
      badge.className = `badge ms-1 px-1-5 ${
        numComments ? "text-bg-green" : "text-bg-light"
      }`
      badge.title = t("diary.number_of_comments")
      badge.textContent = badgeText

      a.appendChild(spanTitle)
      a.appendChild(badge)
      li.appendChild(a)
      fragment.appendChild(li)
    }

    navList.replaceChildren(fragment)
  }

  const configureDiaryPage = (renderContainer: HTMLElement) => {
    const scope = createDisposeScope()

    for (const article of renderContainer.querySelectorAll("article.diary")) {
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
      scope.defer(() => ro.disconnect())
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
      let disposeCommentsPagination: (() => void) | undefined

      commentsContainer.addEventListener(
        "show.bs.collapse",
        () => {
          const reloadCommentsPagination = () => {
            disposeCommentsPagination?.()
            disposeCommentsPagination = configureStandardPagination(commentsContainer)
          }
          scope.defer(() => disposeCommentsPagination?.())
          reloadCommentsPagination()

          const subForm = commentsContainer.querySelector("form.subscription-form")
          configureStandardForm(subForm, () => {
            window.location.reload()
          })

          const commentForm = commentsContainer.querySelector("form.comment-form")
          if (commentForm) {
            configureStandardForm(commentForm, () => {
              commentForm.reset()
              reloadCommentsPagination()
            })
          }
        },
        { once: true },
      )
    }

    return scope.dispose
  }

  let pageScope: ReturnType<typeof createDisposeScope> | undefined
  configureStandardPagination(diaryPagination, {
    loadCallback: (renderContainer) => {
      pageScope?.dispose()
      pageScope = createDisposeScope()

      buildScrollNav(renderContainer)
      pageScope.defer(configureScrollspy(renderContainer, scrollNav))
      pageScope.defer(configureDiaryPage(renderContainer))
    },
  })
})

mount("diary-user-comments-body", (body) => {
  configureStandardPagination(body.querySelector("div.diary-user-comments-pagination")!)
})

mount(["diary-details-body", "diary-index-body"], (body) => {
  body.addEventListener("click", async (e) => {
    const target = e.target
    if (!(target instanceof Element)) return

    const link = target.closest("article.diary .share a[data-action=copy-link]")
    if (!link) return

    e.preventDefault()
    try {
      await navigator.clipboard.writeText(link.href)
      console.debug("DiaryIndex: Copied share link", link.href)
    } catch (error) {
      console.warn("DiaryIndex: Failed to copy share link", error)
      alert(error.message)
    }
  })
})
