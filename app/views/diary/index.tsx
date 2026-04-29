import { config, primaryLanguage } from "@lib/config"
import { useDisposeSignalEffect } from "@lib/dispose-scope"
import { getLocaleDisplayNameByCode } from "@lib/locale"
import { mountProtoPage } from "@lib/proto-page"
import {
  type EntryValid,
  type GetPageResponseValid,
  type IndexPageValid,
  IndexPageSchema,
  Service,
} from "@lib/proto/diary_pb"
import type { UserValid } from "@lib/proto/shared_pb"
import { configureScrollspy } from "@lib/scrollspy"
import { StandardPagination } from "@lib/standard-pagination"
import { useSignal } from "@preact/signals"
import { assertNever } from "@std/assert/unstable-never"
import { Offcanvas } from "bootstrap"
import { t } from "i18next"
import { useId, useRef } from "preact/hooks"
import { EntryCard } from "./_entry"
import { DiaryTab, Nav } from "./_nav"

const getHeading = (
  context: IndexPageValid["context"],
  user: UserValid | undefined,
) => {
  switch (context.case) {
    case undefined:
      return t("layouts.user_diaries")
    case "language":
      return t("diary_entries.index.in_language_title", {
        language: getLocaleDisplayNameByCode(context.value),
      })
    case "self":
      return t("diary_entries.index.my_diary")
    case "profile":
      return t("diary_entries.index.user_title", {
        user: user!.displayName,
      })
    default:
      assertNever(context)
  }
}

const getActiveTab = (context: IndexPageValid["context"]) => {
  switch (context.case) {
    case undefined:
      return DiaryTab.all
    case "language":
      return context.value === primaryLanguage
        ? DiaryTab.primary_language
        : DiaryTab.other_language
    case "profile":
      return DiaryTab.profile
    case "self":
      return DiaryTab.self
    default:
      assertNever(context)
  }
}

mountProtoPage(IndexPageSchema, ({ context }) => {
  const currentUser = config.userConfig?.user
  const activeTab = getActiveTab(context)
  const entries = useSignal<readonly EntryValid[]>([])
  const listRef = useRef<HTMLDivElement>(null)
  const scrollNavRef = useRef<HTMLDivElement>(null)
  const offcanvasRef = useRef<HTMLDivElement>(null)
  const offcanvasId = useId()
  const language = context.case === "language" ? context.value : undefined
  const user =
    context.case === "profile"
      ? context.value
      : context.case === "self"
        ? currentUser
        : undefined
  const hasEntries = entries.value.length > 0

  useDisposeSignalEffect((scope) => {
    if (!entries.value.length) return

    const offcanvasElement = offcanvasRef.current!
    const offcanvas = new Offcanvas(offcanvasElement)
    scope.defer(() => offcanvas.dispose())
    scope.dom(offcanvasElement, "click", (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      if (!target.closest("a[href]")) return
      offcanvas.hide()
    })
  })

  useDisposeSignalEffect(() => {
    if (!entries.value.length) return
    return configureScrollspy(listRef.current, scrollNavRef.current)
  })

  const heading = getHeading(context, user)

  return (
    <>
      <div class="content-header pb-0">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <div class="row mb-3">
            {user && (
              <div class="col-auto">
                <a href={`/user/${user.displayName}`}>
                  <img
                    class="avatar"
                    src={user.avatarUrl}
                    alt={t("alt.profile_picture")}
                  />
                </a>
              </div>
            )}
            <div class="col">
              <h1>{heading}</h1>
              <p class="mb-0">{t("diary.index.description")}</p>
            </div>
          </div>

          <Nav
            activeTab={activeTab}
            language={language}
            user={user}
          />
        </div>
      </div>

      <div class="content-body">
        <div class="row g-0">
          {hasEntries && (
            <div
              key="nav"
              class="diary-scroll-nav col-lg-3 sticky-top"
              ref={scrollNavRef}
            >
              <div
                id={offcanvasId}
                class="offcanvas-lg offcanvas-start offset-xxl-1"
                tabIndex={-1}
                ref={offcanvasRef}
              >
                <div class="text-end d-lg-none">
                  <button
                    type="button"
                    class="btn-close p-3 d-lg-none"
                    data-bs-dismiss="offcanvas"
                    data-bs-target={`#${offcanvasId}`}
                    aria-label={t("javascripts.close")}
                  />
                </div>
                <nav class="pt-3 pe-4">
                  <h5 class="fw-bold ms-3 mb-2">{t("diary.jump_to")}</h5>
                  <ul class="nav flex-column">
                    {entries.value.map((entry) => (
                      <li
                        key={entry.id}
                        class="nav-item"
                      >
                        <a
                          class="nav-link d-flex justify-content-between align-items-center"
                          href={`#diary${entry.id}`}
                        >
                          <span class="title">{entry.title}</span>
                          <span
                            class={`badge ms-1 px-1-5 ${
                              entry.numComments ? "text-bg-green" : "text-bg-light"
                            }`}
                            title={t("diary.number_of_comments")}
                          >
                            {entry.numComments}
                          </span>
                        </a>
                      </li>
                    ))}
                  </ul>
                </nav>
              </div>
              <button
                class="btn btn-primary btn-floating-bottom-left d-lg-none"
                type="button"
                data-bs-toggle="offcanvas"
                data-bs-target={`#${offcanvasId}`}
                aria-controls={offcanvasId}
              >
                <i class="bi bi-list me-2" />
                {t("diary.jump_to")}
              </button>
            </div>
          )}

          <div
            key="content"
            class={
              hasEntries
                ? "col-lg-9 col-xl-8 col-xxl-6"
                : "col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3"
            }
          >
            <div class="diary-pagination">
              <StandardPagination
                method={Service.method.getPage}
                request={(() => {
                  switch (context.case) {
                    case undefined:
                      return { filter: { case: undefined } }
                    case "language":
                      return {
                        filter: { case: "language" as const, value: context.value },
                      }
                    case "profile":
                      return {
                        filter: { case: "userId" as const, value: context.value.id },
                      }
                    case "self":
                      return {
                        filter: { case: "userId" as const, value: currentUser!.id },
                      }
                    default:
                      assertNever(context)
                  }
                })()}
                urlKey="page"
                navTop
                navClassBottom="mb-0"
                onLoad={(data: GetPageResponseValid) => {
                  entries.value = data.diaries
                }}
              >
                {(data: GetPageResponseValid) => (
                  <div
                    ref={listRef}
                    class="diary-list mb-3"
                  >
                    {data.diaries.length ? (
                      data.diaries.map((entry) => (
                        <EntryCard
                          key={entry.id}
                          entry={entry}
                          profilePage={Boolean(user)}
                          onNumCommentsChange={(numComments) => {
                            const nextEntries = [...entries.value]
                            const currentEntry = nextEntries.find(
                              (currentEntry) => currentEntry.id === entry.id,
                            )
                            if (!currentEntry) return
                            currentEntry.numComments = numComments
                            entries.value = nextEntries
                          }}
                        />
                      ))
                    ) : (
                      <h3>{t("traces.index.empty_title")}</h3>
                    )}
                  </div>
                )}
              </StandardPagination>
            </div>
          </div>
        </div>
      </div>
    </>
  )
})
