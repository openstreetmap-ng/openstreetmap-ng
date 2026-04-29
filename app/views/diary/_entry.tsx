import { config, DIARY_COMMENT_BODY_MAX_LENGTH, isLoggedIn } from "@lib/config"
import { formatPoint } from "@lib/coords"
import { Time } from "@lib/datetime-inputs"
import { useDisposeEffect, useDisposeLayoutEffect } from "@lib/dispose-scope"
import { getLocaleDisplayNameByCode } from "@lib/locale"
import type {
  CommentValid,
  EntryValid,
  GetCommentsResponseValid,
} from "@lib/proto/diary_pb"
import { Service } from "@lib/proto/diary_pb"
import { ReportButton } from "@lib/report"
import { StandardForm } from "@lib/standard-form"
import { StandardPagination } from "@lib/standard-pagination"
import type { Signal } from "@preact/signals"
import { useSignal } from "@preact/signals"
import { Collapse } from "bootstrap"
import { t } from "i18next"
import { useEffect, useRef } from "preact/hooks"
import { RichTextControl } from "../rich-text/_control"
import { showLoginModal } from "../user/login"

const ShareMenu = ({ entry }: { entry: EntryValid }) => {
  const diaryLink = `${window.location.origin}/diary/${entry.id}`

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(diaryLink)
    } catch (error) {
      console.warn("Diary: Failed to copy share link", error)
      alert(error.message)
    }
  }

  return (
    <div class="share btn-group dropdown">
      <button
        class="btn btn-soft dropdown-toggle"
        type="button"
        data-bs-toggle="dropdown"
        aria-expanded="false"
      >
        <i class="bi bi-share me-2" />
        {t("javascripts.share.title")}
      </button>
      <ul class="dropdown-menu">
        <li>
          <button
            class="dropdown-item"
            type="button"
            onClick={() => void copyLink()}
          >
            <i class="bi bi-link-45deg" />
            {t("action.copy_link")}
          </button>
        </li>
        {[
          {
            href: `mailto:?subject=${encodeURIComponent(
              entry.title,
            )}&body=${encodeURIComponent(diaryLink)}`,
            icon: "envelope-at-fill",
            label: t("activerecord.attributes.user.email"),
          },
          {
            href: `https://mastodonshare.com/?text=${encodeURIComponent(
              entry.title,
            )}&url=${encodeURIComponent(diaryLink)}`,
            icon: "mastodon",
            label: t("service.mastodon.title"),
          },
          {
            href: `https://bsky.app/intent/compose?text=${encodeURIComponent(
              `${entry.title} ${diaryLink}`,
            )}`,
            icon: "bluesky",
            label: t("service.bluesky.title"),
          },
          {
            href: `https://x.com/intent/post?text=${encodeURIComponent(
              entry.title,
            )}&url=${encodeURIComponent(diaryLink)}`,
            icon: "twitter-x",
            label: t("service.x.title"),
          },
          {
            href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(
              diaryLink,
            )}`,
            icon: "linkedin",
            label: t("service.linkedin.title"),
          },
          {
            href: `https://www.facebook.com/sharer/sharer.php?t=${encodeURIComponent(
              entry.title,
            )}&u=${encodeURIComponent(diaryLink)}`,
            icon: "facebook",
            label: t("service.facebook.title"),
          },
          {
            href: `https://t.me/share/url?text=${encodeURIComponent(
              entry.title,
            )}&url=${encodeURIComponent(diaryLink)}`,
            icon: "telegram",
            label: t("service.telegram.title"),
          },
        ].map(({ href, icon, label }) => (
          <li>
            <a
              class="dropdown-item"
              href={href}
              target="_blank"
              rel="noopener noreferrer"
            >
              <i class={`bi bi-${icon}`} />
              {label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

const DiaryCommentItem = ({ comment }: { comment: CommentValid }) => (
  <li
    id={`comment${comment.id}`}
    class="social-entry"
  >
    <p class="header text-muted">
      <a href={`/user/${comment.user.displayName}`}>
        <img
          class="avatar"
          src={comment.user.avatarUrl}
          alt={t("alt.profile_picture")}
          loading="lazy"
        />
        {comment.user.displayName}
      </a>{" "}
      {t("action.commented")}{" "}
      <Time
        unix={comment.createdAt}
        relativeStyle="long"
      />
    </p>
    <div
      class="rich-text body"
      dangerouslySetInnerHTML={{ __html: comment.bodyRich }}
    />
  </li>
)

const DiaryCommentsContent = ({
  entry,
  numComments,
  onNumCommentsChange,
}: {
  entry: EntryValid
  numComments: Signal<number>
  onNumCommentsChange: ((numComments: number) => void) | undefined
}) => {
  const isSubscribed = useSignal(entry.isSubscribed)
  const reloadKey = useSignal(0)

  return (
    <div class="pt-3">
      <div class="row g-1 mb-1">
        <div class="col">
          <h4>{t("diary.comments")}</h4>
        </div>
        {isLoggedIn && (
          <div class="col-auto">
            <StandardForm
              method={Service.method.updateSubscription}
              buildRequest={() => ({
                diaryId: entry.id,
                isSubscribed: !isSubscribed.value,
              })}
              onSuccess={(_, ctx) => {
                isSubscribed.value = ctx.request.isSubscribed
              }}
              class="d-inline"
            >
              <button
                class="btn btn-sm btn-soft"
                type="submit"
              >
                {isSubscribed.value ? (
                  <>
                    <i class="bi bi-bookmark-check me-1" />
                    {t("javascripts.changesets.show.unsubscribe")}
                  </>
                ) : (
                  t("javascripts.changesets.show.subscribe")
                )}
              </button>
            </StandardForm>
          </div>
        )}
      </div>

      <StandardPagination
        key={reloadKey.value}
        method={Service.method.getComments}
        request={{ diaryId: entry.id }}
        small
        navTop
        navClassBottom="mb-0"
        ariaLabel={t("alt.comments_page_navigation")}
      >
        {(data: GetCommentsResponseValid) => (
          <ul class="social-list-sm list-unstyled mb-2">
            {data.comments.map((comment) => (
              <DiaryCommentItem
                key={comment.id}
                comment={comment}
              />
            ))}
          </ul>
        )}
      </StandardPagination>

      {isLoggedIn ? (
        <StandardForm
          method={Service.method.addComment}
          buildRequest={({ formData }) => ({
            diaryId: entry.id,
            body: formData.get("body") as string,
          })}
          onSuccess={() => {
            const nextNumComments = numComments.value + 1
            numComments.value = nextNumComments
            onNumCommentsChange?.(nextNumComments)
            reloadKey.value++
          }}
          resetOnSuccess
          class="comment-form"
        >
          <label class="form-label d-block">
            {t("diary_entries.show.leave_a_comment")}
          </label>
          <div class="mb-3">
            <RichTextControl
              name="body"
              maxLength={DIARY_COMMENT_BODY_MAX_LENGTH}
              required
            />
          </div>
          <div class="text-end">
            <button
              class="btn btn-primary"
              type="submit"
            >
              {t("action.comment")}
            </button>
          </div>
        </StandardForm>
      ) : (
        <div class="text-center">
          <button
            class="btn btn-link"
            type="button"
            onClick={showLoginModal}
          >
            {t("browse.changeset.join_discussion")}
          </button>
        </div>
      )}
    </div>
  )
}

const getLocationText = (entry: EntryValid) => {
  const location = entry.location
  return location ? formatPoint([location.lon, location.lat], 5) : ""
}

export const EntryMeta = ({
  entry,
  class: className,
  showAvatar = true,
}: {
  entry: EntryValid
  class: string
  showAvatar?: boolean
}) => (
  <>
    <p class={className}>
      <a
        href={`/user/${entry.user.displayName}`}
        rel="author"
      >
        {showAvatar && (
          <img
            class="avatar d-md-none"
            src={entry.user.avatarUrl}
            alt={t("alt.profile_picture")}
            loading="lazy"
          />
        )}
        {entry.user.displayName}
      </a>{" "}
      {t("action.posted")}{" "}
      <Time
        unix={entry.createdAt}
        dateStyle="long"
        timeStyle="short"
      />
      <span
        class="mx-1"
        aria-hidden="true"
      >
        ·
      </span>
      <a href={`/diary/${entry.language}`}>
        {getLocaleDisplayNameByCode(entry.language)}
      </a>
    </p>
    {entry.updatedAt > entry.createdAt && (
      <p class="small text-muted fst-italic mb-3">
        {t("action.updated")}{" "}
        <Time
          unix={entry.updatedAt}
          dateStyle="long"
          timeStyle="short"
        />
      </p>
    )}
  </>
)

export const EntryCard = ({
  entry,
  details = false,
  profilePage = false,
  onNumCommentsChange,
}: {
  entry: EntryValid
  details?: boolean
  profilePage?: boolean
  onNumCommentsChange?: (numComments: number) => void
}) => {
  const expanded = useSignal(details)
  const isClamped = useSignal(false)
  const commentsOpen = useSignal(details)
  const commentsMounted = useSignal(details)
  const numComments = useSignal(entry.numComments)
  const bodyRef = useRef<HTMLDivElement>(null)
  const commentsRef = useRef<HTMLDivElement>(null)
  const currentUser = config.userConfig?.user
  const canEdit = currentUser?.id === entry.user.id
  const commentsId = details ? "comments" : `diary-comments-${entry.id}`

  useEffect(() => {
    numComments.value = entry.numComments
  }, [entry.id, entry.numComments])

  useDisposeLayoutEffect(
    (scope) => {
      if (details) return
      const body = bodyRef.current!

      const updateClamp = () => {
        if (expanded.value) return
        isClamped.value = body.scrollHeight - 1 > body.clientHeight
      }

      updateClamp()
      const observer = new ResizeObserver(updateClamp)
      observer.observe(body)
      scope.defer(() => observer.disconnect())
    },
    [details],
  )

  useDisposeEffect(
    (scope) => {
      if (details) return

      const element = commentsRef.current!
      const collapse = new Collapse(element, { toggle: false })
      scope.defer(() => collapse.dispose())
      scope.dom(element, "show.bs.collapse", () => {
        commentsMounted.value = true
        commentsOpen.value = true
      })
      scope.dom(element, "hidden.bs.collapse", () => {
        commentsOpen.value = false
      })
    },
    [details],
  )

  const showHeader = !details
  const showSideAvatar = !details && !profilePage
  const locationText = getLocationText(entry)

  return (
    <article
      id={`diary${entry.id}`}
      class={`diary ${expanded.value ? "show" : ""} ${
        isClamped.value ? "diary-clamped" : ""
      }`}
    >
      <div class="row">
        {showSideAvatar && (
          <div class="col-auto d-none d-md-block">
            <a
              class="d-block"
              href={`/user/${entry.user.displayName}`}
              rel="author"
            >
              <img
                class="side-avatar avatar"
                src={entry.user.avatarUrl}
                alt={t("alt.profile_picture")}
                loading="lazy"
              />
            </a>
          </div>
        )}
        <div class="col align-content-center">
          {showHeader && (
            <>
              <h3>
                <a
                  class="diary-title-link"
                  href={`/diary/${entry.id}`}
                >
                  {entry.title}
                </a>
              </h3>
              <EntryMeta
                entry={entry}
                class="small mb-2"
              />
            </>
          )}

          <div
            ref={bodyRef}
            class="diary-body"
          >
            <div
              class={`rich-text mx-1 ${showHeader ? "mt-3" : ""}`}
              dangerouslySetInnerHTML={{ __html: entry.bodyRich }}
            />
          </div>

          {!details && isClamped.value && !expanded.value && (
            <div class="text-center">
              <button
                type="button"
                class="btn btn-link diary-read-more"
                onClick={() => (expanded.value = true)}
              >
                {t("action.continue_reading")}
                <i class="bi bi-chevron-down small ms-1-5" />
              </button>
            </div>
          )}

          {entry.location && (
            <p class="diary-location fw-medium mb-3">
              <i class="bi bi-compass" />
              {t("diary_entries.form.location")}:{" "}
              <a
                href={`/?mlat=${entry.location.lat.toFixed(5)}&mlon=${entry.location.lon.toFixed(5)}&zoom=14`}
                target="_blank"
              >
                {entry.locationName ? (
                  <abbr title={locationText}>{entry.locationName}</abbr>
                ) : (
                  locationText
                )}
              </a>
            </p>
          )}

          <div class="text-end">
            <div class="btn-group">
              <ShareMenu entry={entry} />

              {details ? (
                <a
                  class="btn btn-soft diary-comments-btn"
                  href="#comments"
                >
                  {t("diary.comments")}
                  <span
                    class={`badge ms-2 ${
                      numComments.value ? "text-bg-green" : "text-bg-light"
                    }`}
                  >
                    {numComments.value}
                  </span>
                </a>
              ) : (
                <button
                  type="button"
                  class={`btn btn-soft diary-comments-btn dropdown-toggle ${
                    commentsOpen.value ? "" : "collapsed"
                  }`}
                  data-bs-toggle="collapse"
                  data-bs-target={`#${commentsId}`}
                  aria-expanded={commentsOpen.value}
                  aria-controls={commentsId}
                >
                  {t("diary.comments")}
                  <span
                    class={`badge ms-2 ${
                      numComments.value ? "text-bg-green" : "text-bg-light"
                    }`}
                  >
                    {numComments.value}
                  </span>
                </button>
              )}

              {currentUser && (
                <>
                  <button
                    type="button"
                    class="btn btn-soft dropdown-toggle dropdown-toggle-split"
                    data-bs-toggle="dropdown"
                    aria-expanded="false"
                    aria-label={t("action.show_more")}
                  />
                  <ul class="dropdown-menu">
                    {!canEdit && (
                      <li>
                        <a
                          class="dropdown-item"
                          href={`/message/new?reply_diary=${entry.id}`}
                        >
                          {t("diary.send_author_a_message")}
                        </a>
                      </li>
                    )}
                    {!canEdit && (
                      <li>
                        <ReportButton
                          class="dropdown-item"
                          reportType="user"
                          reportTypeId={entry.user.id}
                          reportAction="user_diary"
                          reportActionId={entry.id}
                        >
                          {t("report.report_problem")}
                        </ReportButton>
                      </li>
                    )}
                    {canEdit && (
                      <li>
                        <a
                          class="dropdown-item"
                          href={`/diary/${entry.id}/edit`}
                        >
                          {t("diary_entries.diary_entry.edit_link")}
                        </a>
                      </li>
                    )}
                  </ul>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div
        id={commentsId}
        ref={commentsRef}
        class={`diary-comments ${details ? "" : "collapse"}`}
      >
        {(details || commentsMounted.value) && (
          <DiaryCommentsContent
            entry={entry}
            numComments={numComments}
            onNumCommentsChange={onNumCommentsChange}
          />
        )}
      </div>
    </article>
  )
}
