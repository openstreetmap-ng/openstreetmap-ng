import { BTooltip } from "@lib/bootstrap"
import { config, USER_RECENT_ACTIVITY_ENTRIES } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { FollowToggleForm } from "@lib/follow-toggle-form"
import { tRich } from "@lib/i18n"
import { mountProtoPage } from "@lib/proto-page"
import { PageSchema, type PageValid } from "@lib/proto/profile_pb"
import { Service, UpdateAvatarRequest_Preset } from "@lib/proto/settings_pb"
import { ReportButton } from "@lib/report"
import { formDataBytes, StandardForm } from "@lib/standard-form"
import type { Signal } from "@preact/signals"
import { useSignal } from "@preact/signals"
import { toSentenceCase } from "@std/text/unstable-to-sentence-case"
import { t } from "i18next"
import type { ComponentChildren } from "preact"
import { useRef } from "preact/hooks"
import { SummaryRow } from "../../traces/_summary"
import { Activity } from "./_activity"
import { DescriptionModal, AboutSection, SocialsModal } from "./_edit-modals"

type ChangesetSummary = PageValid["changesets"][number]
type NoteSummary = PageValid["notes"][number]
type TraceSummary = PageValid["traces"][number]
type DiarySummary = PageValid["diaries"][number]

type GroupExample = {
  type: string
  members: string
  slug: string
  title: string
  description: string
  banner: string
  exclusive?: boolean
}

const GROUP_EXAMPLES: readonly GroupExample[] = [
  {
    type: "Invite-only",
    members: "32 members",
    slug: "osmng-founders",
    title: "OpenStreetMap-NG Founders",
    description:
      "The OpenStreetMap-NG Founders is a group of early-stage contributors who helped shape the future of OpenStreetMap. We build the next generation of the OpenStreetMap project.",
    banner: "/static/img/banner/example1.webp",
    exclusive: true,
  },
  {
    type: "Public",
    members: "13,540 members",
    slug: "osm-community",
    title: "OpenStreetMap Community",
    description:
      "The OpenStreetMap Community is a group of volunteers who are dedicated to improving the OpenStreetMap project. We work together to create and maintain a free and open map of the world, and we are always looking for new members to join our community.",
    banner: "/static/img/banner/example2.webp",
  },
  {
    type: "Public",
    members: "128 members",
    slug: "osm-pl",
    title: "OpenStreetMap Polska",
    description:
      "Polska grupa fanow i kontrybutorow OpenStreetMap. Jestesmy w stanie pomoc w rozwijaniu i poprawieniu mapy na terenie Polski.",
    banner: "/static/img/banner/example1.webp",
  },
]

const CommentCountBadge = ({ count }: { count: number }) =>
  count > 0 ? (
    <div class="num-comments">
      {count}
      <i class="bi bi-chat-left-text" />
    </div>
  ) : (
    <div class="num-comments no-comments">
      0
      <i class="bi bi-chat-left" />
    </div>
  )

const ContributionCard = ({
  titleHref,
  title,
  count,
  viewMoreHref,
  listClassName,
  small = false,
  menuItem,
  children,
}: {
  titleHref: string
  title: ComponentChildren
  count: number
  viewMoreHref: string
  listClassName?: string
  small?: boolean
  menuItem?: {
    href: string
    label: ComponentChildren
  }
  children: ComponentChildren
}) => {
  const titleClass = menuItem
    ? "card-title d-flex justify-content-between align-items-center ms-1"
    : "card-title ms-1"
  const listClass = `content-list${small ? " content-list-sm" : ""} social-list-sm list-unstyled${listClassName ? ` ${listClassName}` : ""}`

  return (
    <div class="card">
      <div class="card-body pb-0">
        <h5 class={titleClass}>
          <a href={titleHref}>{title}</a>
          {menuItem && (
            <span class="dropdown">
              <button
                class="btn btn-sm btn-soft py-0"
                type="button"
                data-bs-toggle="dropdown"
                aria-expanded="false"
              >
                <i class="bi bi-three-dots" />
              </button>
              <ul class="dropdown-menu">
                <li>
                  <a
                    class="dropdown-item"
                    href={menuItem.href}
                  >
                    {menuItem.label}
                  </a>
                </li>
              </ul>
            </span>
          )}
        </h5>

        <ul class={listClass}>
          {children}
          {count > USER_RECENT_ACTIVITY_ENTRIES ? (
            <li class="view-more">
              <a
                class="btn btn-sm btn-soft"
                href={viewMoreHref}
              >
                {t("action.view_more")}
              </a>
            </li>
          ) : count === 0 ? (
            <li class="no-activity">{t("user.no_activity_yet")}</li>
          ) : null}
        </ul>
      </div>
    </div>
  )
}

const BackgroundForm = ({
  isSelf,
  backgroundUrl,
}: {
  isSelf: boolean
  backgroundUrl: Signal<string | undefined>
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null)

  return (
    <StandardForm
      class="background-form"
      method={Service.method.updateBackground}
      buildRequest={async ({ formData }) => ({
        backgroundFile: await formDataBytes(formData, "background_file"),
      })}
      onSuccess={(resp) => (backgroundUrl.value = resp.backgroundUrl)}
    >
      <input
        class="visually-hidden"
        type="file"
        name="background_file"
        accept="image/*"
        ref={fileInputRef}
        onChange={(e) => {
          e.currentTarget.form!.requestSubmit()
        }}
      />
      <img
        class="background"
        src={backgroundUrl.value}
        alt={t("alt.background_image")}
      />

      {isSelf && (
        <div class="dropdown">
          <button
            class="btn btn-sm btn-soft dropdown-toggle"
            type="button"
            data-bs-toggle="dropdown"
            aria-expanded="false"
          >
            <i class="bi bi-image text-muted me-1-5" />
            {t("user.edit_background")}
          </button>
          <ul class="dropdown-menu dropdown-menu-end">
            <li>
              <h6 class="dropdown-header">{t("alt.background_image")}</h6>
            </li>
            <li>
              <button
                class="dropdown-item"
                type="button"
                onClick={() => {
                  fileInputRef.current!.click()
                }}
              >
                {t("action.upload_image")}...
              </button>
            </li>
            <li>
              <button
                class="dropdown-item"
                type="button"
                onClick={() => {
                  fileInputRef.current!.value = ""
                  fileInputRef.current!.form!.requestSubmit()
                }}
              >
                {t("action.remove_image")}
              </button>
            </li>
          </ul>
        </div>
      )}
    </StandardForm>
  )
}

const AvatarForm = ({
  isSelf,
  avatarUrl,
}: {
  isSelf: boolean
  avatarUrl: Signal<string>
}) => {
  const avatarPresetRef = useRef(UpdateAvatarRequest_Preset.default)
  const fileInputRef = useRef<HTMLInputElement>(null)

  return (
    <StandardForm
      class="avatar-form"
      method={Service.method.updateAvatar}
      buildRequest={async ({ formData }) => {
        const avatarFile = await formDataBytes(formData, "avatar_file")
        if (avatarFile.length) {
          return {
            avatar: {
              case: "avatarFile" as const,
              value: avatarFile,
            },
          }
        }

        return {
          avatar: {
            case: "preset" as const,
            value: avatarPresetRef.current,
          },
        }
      }}
      onSuccess={(resp) => (avatarUrl.value = resp.avatarUrl)}
    >
      <input
        class="visually-hidden"
        type="file"
        name="avatar_file"
        accept="image/*"
        ref={fileInputRef}
        onChange={(e) => {
          e.currentTarget.form!.requestSubmit()
        }}
      />
      <img
        class="avatar"
        src={avatarUrl.value}
        alt={t("alt.profile_picture")}
      />

      {isSelf && (
        <div class="dropdown">
          <button
            class="btn btn-sm btn-soft dropdown-toggle"
            type="button"
            data-bs-toggle="dropdown"
            aria-expanded="false"
          >
            <i class="bi bi-person-circle text-muted me-1-5" />
            {t("layouts.edit")}
          </button>
          <ul class="dropdown-menu">
            <li>
              <h6 class="dropdown-header">{t("alt.profile_picture")}</h6>
            </li>
            <li>
              <button
                class="dropdown-item"
                type="button"
                onClick={() => {
                  fileInputRef.current!.click()
                }}
              >
                {t("action.upload_image")}...
              </button>
            </li>
            <li>
              <button
                class="dropdown-item"
                type="button"
                onClick={() => {
                  avatarPresetRef.current = UpdateAvatarRequest_Preset.gravatar
                  fileInputRef.current!.value = ""
                  fileInputRef.current!.form!.requestSubmit()
                }}
              >
                {t("profiles.edit.gravatar.gravatar")}
              </button>
            </li>
            <li>
              <button
                class="dropdown-item"
                type="button"
                onClick={() => {
                  avatarPresetRef.current = UpdateAvatarRequest_Preset.default
                  fileInputRef.current!.value = ""
                  fileInputRef.current!.form!.requestSubmit()
                }}
              >
                {t("action.remove_image")}
              </button>
            </li>
            <li>
              <hr class="dropdown-divider" />
            </li>
            <li>
              <a
                class="dropdown-item"
                href="https://wiki.openstreetmap.org/wiki/Gravatar"
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("profiles.edit.gravatar.what_is_gravatar")}
              </a>
            </li>
          </ul>
        </div>
      )}
    </StandardForm>
  )
}

const FollowSection = ({
  targetUserId,
  isFollowedBy,
  initialIsFollowing,
}: {
  targetUserId: bigint
  isFollowedBy: boolean
  initialIsFollowing: boolean
}) => {
  const isFollowing = useSignal(initialIsFollowing)

  return (
    <>
      <FollowToggleForm
        targetUserId={targetUserId}
        isFollowing={isFollowing}
        class="btn btn-soft w-100 mt-4"
      >
        {({ isFollowing }) =>
          isFollowing ? (
            <>
              {t("action.unfollow_user")}
              <i class="bi bi-bookmark-dash ms-1-5" />
            </>
          ) : isFollowedBy ? (
            <>
              {t("follows.follow_back")}
              <i class="bi bi-bookmark-plus ms-1-5" />
            </>
          ) : (
            <>
              {t("action.follow_user")}
              <i class="bi bi-bookmark-plus ms-1-5" />
            </>
          )
        }
      </FollowToggleForm>
      <p class="form-text mx-1 mb-4">{t("follows.description")}</p>
    </>
  )
}

const ChangesetRow = ({ changeset }: { changeset: ChangesetSummary }) => (
  <li class="social-entry clickable">
    <p class="header text-muted d-flex justify-content-between">
      <span>
        {t("browse.created")}{" "}
        <Time
          unix={changeset.createdAt}
          relativeStyle="long"
        />
      </span>
      <a
        class="stretched-link"
        href={`/changeset/${changeset.id}`}
      >
        {changeset.id}
      </a>
    </p>
    <div class="body">
      <div class="d-flex justify-content-between">
        <div class="comment">{changeset.comment ?? t("browse.no_comment")}</div>
        <CommentCountBadge count={changeset.numComments} />
      </div>
      <div class="changeset-stats">
        {changeset.numCreate > 0 && (
          <span class="stat-create">{changeset.numCreate}</span>
        )}
        {changeset.numModify > 0 && (
          <span class="stat-modify">{changeset.numModify}</span>
        )}
        {changeset.numDelete > 0 && (
          <span class="stat-delete">{changeset.numDelete}</span>
        )}
      </div>
    </div>
  </li>
)

const ChangesetsCard = ({
  userPath,
  changesetsCount,
  changesetsCommentsCount,
  changesets,
}: {
  userPath: string
  changesetsCount: number
  changesetsCommentsCount: number
  changesets: readonly ChangesetSummary[]
}) => (
  <ContributionCard
    titleHref={`${userPath}/history`}
    title={
      <>
        <b>{changesetsCount}</b> {t("changeset.count", { count: changesetsCount })}
      </>
    }
    count={changesetsCount}
    viewMoreHref={`${userPath}/history`}
    listClassName="changesets-list"
    menuItem={{
      href: `${userPath}/history/comments`,
      label: (
        <>
          {changesetsCommentsCount}{" "}
          {t("comment.count", { count: changesetsCommentsCount })}
        </>
      ),
    }}
  >
    {changesets.map((changeset) => (
      <ChangesetRow
        key={changeset.id}
        changeset={changeset}
      />
    ))}
  </ContributionCard>
)

const NoteRow = ({ note }: { note: NoteSummary }) => {
  const otherComments = Math.max(0, note.numComments - 1)
  const wasUpdated = note.updatedAt > note.createdAt

  return (
    <li class="row g-2">
      <div class="col-auto">
        <img
          class="marker"
          src={
            note.isClosed
              ? "/static/img/marker/closed.webp"
              : "/static/img/marker/open.webp"
          }
          alt={note.isClosed ? t("state.resolved") : t("state.unresolved")}
          draggable={false}
        />
      </div>
      <div class="col">
        <div class="social-entry clickable h-100">
          <p class="header text-muted d-flex justify-content-between">
            <span>
              {wasUpdated ? toSentenceCase(t("action.updated")) : t("browse.created")}{" "}
              <Time
                unix={wasUpdated ? note.updatedAt : note.createdAt}
                relativeStyle="long"
              />
            </span>
            <a
              class="stretched-link"
              href={`/note/${note.id}`}
            >
              {note.id}
            </a>
          </p>
          <div class="body d-flex justify-content-between">
            <div>{note.body}</div>
            <CommentCountBadge count={otherComments} />
          </div>
        </div>
      </div>
    </li>
  )
}

const NotesCard = ({
  userPath,
  notesCount,
  notesCommentsCount,
  notes,
}: {
  userPath: string
  notesCount: number
  notesCommentsCount: number
  notes: readonly NoteSummary[]
}) => (
  <ContributionCard
    titleHref={`${userPath}/notes`}
    title={
      <>
        <b>{notesCount}</b> {t("note.count", { count: notesCount })}
      </>
    }
    count={notesCount}
    viewMoreHref={`${userPath}/notes`}
    listClassName="notes-list"
    menuItem={{
      href: `${userPath}/notes/commented`,
      label: (
        <>
          {notesCommentsCount} {t("comment.count", { count: notesCommentsCount })}
        </>
      ),
    }}
  >
    {notes.map((note) => (
      <NoteRow
        key={note.id}
        note={note}
      />
    ))}
  </ContributionCard>
)

const TracesCard = ({
  userPath,
  tracesCount,
  traces,
}: {
  userPath: string
  tracesCount: number
  traces: readonly TraceSummary[]
}) => (
  <ContributionCard
    titleHref={`${userPath}/traces`}
    title={
      <>
        <b>{tracesCount}</b> {t("trace.count", { count: tracesCount })}
      </>
    }
    count={tracesCount}
    viewMoreHref={`${userPath}/traces`}
    listClassName="traces-list"
    small
  >
    {traces.map((trace) => (
      <SummaryRow
        key={trace.id}
        summary={trace}
        href={`/trace/${trace.id}`}
        tagBasePath={`${userPath}/traces`}
        header={
          <>
            {toSentenceCase(t("action.uploaded"))}{" "}
            <Time
              unix={trace.createdAt}
              relativeStyle="long"
            />
          </>
        }
        title={
          <a
            class="stretched-link"
            href={`/trace/${trace.id}`}
          >
            {trace.id}
          </a>
        }
        showPointIcon
      />
    ))}
  </ContributionCard>
)

const DiaryRow = ({ diary }: { diary: DiarySummary }) => (
  <li class="social-entry clickable">
    <p class="header text-muted d-flex justify-content-between">
      <span>
        {toSentenceCase(t("action.posted"))}{" "}
        <Time
          unix={diary.createdAt}
          relativeStyle="long"
        />
      </span>
      <a
        class="stretched-link"
        href={`/diary/${diary.id}`}
      >
        {diary.id}
      </a>
    </p>
    <div class="body d-flex justify-content-between">
      <div class="title">{diary.title}</div>
      <CommentCountBadge count={diary.numComments} />
    </div>
  </li>
)

const DiariesCard = ({
  userPath,
  diariesCount,
  diariesCommentsCount,
  diaries,
}: {
  userPath: string
  diariesCount: number
  diariesCommentsCount: number
  diaries: readonly DiarySummary[]
}) => (
  <ContributionCard
    titleHref={`${userPath}/diary`}
    title={
      <>
        <b>{diariesCount}</b> {t("diary.entry.count", { count: diariesCount })}
      </>
    }
    count={diariesCount}
    viewMoreHref={`${userPath}/diary`}
    listClassName="diary-list"
    small
    menuItem={{
      href: `${userPath}/diary/comments`,
      label: (
        <>
          {diariesCommentsCount} {t("comment.count", { count: diariesCommentsCount })}
        </>
      ),
    }}
  >
    {diaries.map((diary) => (
      <DiaryRow
        key={diary.id}
        diary={diary}
      />
    ))}
  </ContributionCard>
)

const GroupsSection = ({
  userPath,
  groupsCount,
}: {
  userPath: string
  groupsCount: number
}) => {
  const groupsHeading = tRich("group.member_of_count", {
    count: groupsCount,
    text: <b>{groupsCount}</b>,
  })

  return (
    <>
      <h5 class="ms-1">
        <a href={`${userPath}/groups`}>{groupsHeading}</a>
      </h5>

      <ul class="groups-list social-list-sm list-unstyled">
        {GROUP_EXAMPLES.map((group) => (
          <li class="row g-2">
            <div class="col-auto">
              <img
                src={group.banner}
                draggable={false}
              />
            </div>
            <div class="col">
              <div class="social-entry clickable h-100">
                <p class="header text-muted d-flex justify-content-between">
                  <span>
                    {group.type}
                    <i class="bi bi-dot" />
                    {group.members}
                  </span>
                  <a
                    class="stretched-link text-end"
                    href="/group/TODO"
                  >
                    {group.slug}
                  </a>
                </p>
                <div class="body">
                  <h6 class="title">
                    {group.title}
                    {group.exclusive && <i class="bi bi-stars exclusive" />}
                  </h6>
                  <p class="description">{group.description}</p>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div class="d-flex justify-content-between align-items-center">
        <a
          class="btn btn-sm btn-outline-primary"
          href="/groups"
        >
          <i class="bi bi-globe2 me-2" />
          Discover groups
        </a>
        <a
          class="me-1"
          href={`${userPath}/groups`}
        >
          {t("action.view_all")}
          <i class="bi bi-arrow-right-short" />
        </a>
      </div>
    </>
  )
}

mountProtoPage(
  PageSchema,
  ({
    user: profile,
    isNewUser,
    isAdministrator,
    isModerator,
    backgroundUrl: initialBackgroundUrl,
    createdAt,
    chart,
    follow,
    description: initialDescription,
    descriptionRich: initialDescriptionRich,
    socials: initialSocials,
    changesetsCount,
    changesetsCommentsCount,
    changesets,
    notesCount,
    notesCommentsCount,
    notes,
    tracesCount,
    traces,
    diariesCount,
    diariesCommentsCount,
    diaries,
    groupsCount,
  }) => {
    const avatarUrl = useSignal(profile.avatarUrl)
    const backgroundUrl = useSignal(initialBackgroundUrl)

    const description = useSignal(initialDescription)
    const descriptionRich = useSignal(initialDescriptionRich)
    const socials = useSignal(initialSocials)

    const isSelf = config.userConfig?.user.id === profile.id
    const userPath = `/user/${encodeURIComponent(profile.displayName)}`

    return (
      <>
        <div class="content-header px-0">
          <BackgroundForm
            isSelf={isSelf}
            backgroundUrl={backgroundUrl}
          />

          <div class="header-footer">
            <div class="container">
              <div class="d-flex offset-xxl-1">
                <AvatarForm
                  isSelf={isSelf}
                  avatarUrl={avatarUrl}
                />

                <div class="info">
                  <div class="row g-2 g-md-3 h1">
                    <h1 class="col-auto d-flex align-items-center mb-0">
                      {profile.displayName}
                      {isAdministrator ? (
                        <BTooltip title={t("users.show.role.administrator")}>
                          <i class="role bi bi-star-fill text-danger ms-2" />
                        </BTooltip>
                      ) : isModerator ? (
                        <BTooltip title={t("users.show.role.moderator")}>
                          <i class="role bi bi-star-fill text-blue ms-2" />
                        </BTooltip>
                      ) : null}
                    </h1>
                    {isNewUser && (
                      <div class="col-auto d-flex align-items-center">
                        <BTooltip title={t("user.i_am_new_here")}>
                          <span class="badge rounded-pill text-bg-green">
                            {t("user.new")}
                          </span>
                        </BTooltip>
                      </div>
                    )}
                  </div>
                  <p class="mapper-since mb-2">
                    {toSentenceCase(t("users.show.mapper since"))}{" "}
                    <Time
                      unix={createdAt}
                      dateStyle="long"
                    />
                  </p>
                  <div class="user-actions mb-2">
                    {follow && (
                      <address>
                        <a
                          href={`/message/new?to_id=${profile.id}`}
                          class="btn btn-sm btn-soft"
                        >
                          <i class="bi bi-envelope-plus me-2" />
                          {t("action.send_a_message")}
                        </a>
                      </address>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="content-body">
          <div class="container">
            <div class="row g-4 g-xl-5">
              <div class="col-lg-7">
                <AboutSection
                  isSelf={isSelf}
                  description={description}
                  descriptionRich={descriptionRich}
                  socials={socials}
                />

                <h3 class="ms-1 mb-3">{t("user.contributions")}</h3>
                <div class="row row-cols-sm-2 g-3">
                  <div>
                    <ChangesetsCard
                      userPath={userPath}
                      changesetsCount={Number(changesetsCount)}
                      changesetsCommentsCount={Number(changesetsCommentsCount)}
                      changesets={changesets}
                    />
                  </div>
                  <div>
                    <NotesCard
                      userPath={userPath}
                      notesCount={Number(notesCount)}
                      notesCommentsCount={Number(notesCommentsCount)}
                      notes={notes}
                    />
                  </div>
                  <div>
                    <TracesCard
                      userPath={userPath}
                      tracesCount={Number(tracesCount)}
                      traces={traces}
                    />
                  </div>
                  <div>
                    <DiariesCard
                      userPath={userPath}
                      diariesCount={Number(diariesCount)}
                      diariesCommentsCount={Number(diariesCommentsCount)}
                      diaries={diaries}
                    />
                  </div>
                </div>
              </div>
              <div class="col-lg-5">
                <Activity
                  chart={chart}
                  displayName={profile.displayName}
                />
                <hr />

                <GroupsSection
                  userPath={userPath}
                  groupsCount={Number(groupsCount)}
                />

                {follow && (
                  <>
                    <FollowSection
                      targetUserId={follow.targetUserId}
                      isFollowedBy={follow.isFollowedBy}
                      initialIsFollowing={follow.isFollowing}
                    />

                    <div class="text-end">
                      <div
                        class="btn-group"
                        role="group"
                      >
                        <ReportButton
                          class="btn btn-sm btn-outline-secondary"
                          reportType="user"
                          reportTypeId={profile.id}
                          reportAction="user_profile"
                        >
                          {t("report.report_object", {
                            object: t("activerecord.models.user"),
                          })}
                        </ReportButton>
                        <button
                          type="button"
                          class="btn btn-sm btn-outline-secondary dropdown-toggle dropdown-toggle-split"
                          data-bs-toggle="dropdown"
                          aria-expanded="false"
                          aria-label={t("action.show_more")}
                        />
                        <ul class="dropdown-menu">
                          <li>
                            <button
                              class="dropdown-item"
                              type="button"
                            >
                              TODO: {t("action.block_user")}
                            </button>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {isSelf && (
          <>
            <DescriptionModal
              description={description}
              descriptionRich={descriptionRich}
            />
            <SocialsModal socials={socials} />
          </>
        )}
      </>
    )
  },
)
