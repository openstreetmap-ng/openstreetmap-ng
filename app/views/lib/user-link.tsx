import { t } from "i18next"
import type { AnchorHTMLAttributes } from "preact"

// Structural shape: any proto message carrying the three user-identity fields
// (User, Account, etc.). Avoids forcing callers to convert between proto types
// just to use this component.
type UserShape = {
  id: bigint
  displayName: string
  avatarUrl: string
}

/**
 * Profile URL helper. Use `userHref(user, admin)` when you need just the URL
 * (e.g. building `tRich` slots) and `<UserLink>` for the full anchor+content.
 */
export const userHref = (user: UserShape, admin = false) =>
  admin ? `/user-id/${user.id}` : `/user/${user.displayName}`

/**
 * Standard "this is user X" widget: avatar + display name inside one anchor
 * pointing at the user's profile. Covers the 20+ verbatim repetitions of this
 * pattern across the app. Toggle `showAvatar` / `showName` to render only one
 * half (e.g. an avatar-only chip in a recipient stack, or a name-only link in
 * inline prose).
 */
export const UserLink = ({
  user,
  admin,
  avatarClass = "",
  showName = true,
  showAvatar = true,
  ...props
}: Omit<AnchorHTMLAttributes, "href"> & {
  user: UserShape
  /** Use `/user-id/{id}` (admin/moderation) instead of `/user/{displayName}`. */
  admin?: boolean
  /** Extra class for the avatar `<img>` (e.g. `me-1-5`, `d-md-none`). */
  avatarClass?: string
  /** Render only the avatar (no display name). Default true. */
  showName?: boolean
  /** Render only the name (no avatar). Default true. */
  showAvatar?: boolean
}) => (
  <a
    href={userHref(user, admin)}
    {...props}
  >
    {showAvatar && (
      <img
        class={`avatar ${avatarClass}`}
        src={user.avatarUrl}
        alt={t("alt.profile_picture")}
        loading="lazy"
      />
    )}
    {showName && user.displayName}
  </a>
)
