import type { Signal } from "@preact/signals"
import type { UserSocialValid } from "@proto/shared_pb"
import { t } from "i18next"
import { PROFILE_DESCRIPTION_MODAL_ID } from "./_description-modal"
import {
  getSocialLink,
  knownSocials,
  SOCIAL_OPTIONS_BY_KEY,
  socialServiceTitle,
} from "./_socials-helpers"
import { PROFILE_SOCIALS_MODAL_ID } from "./_socials-modal"

const SocialLinks = ({
  socials,
  class: className,
}: {
  socials: readonly UserSocialValid[]
  class: string
}) => {
  if (!socials.length) return null

  return (
    <div class={`ms-1 d-flex flex-wrap gap-2 ${className}`}>
      {socials.map((social) => {
        const option = SOCIAL_OPTIONS_BY_KEY.get(social.service)!
        const serviceTitle = socialServiceTitle(option)
        const href = getSocialLink(social, option)
        const icon = option.icon ?? social.service

        return href ? (
          <a
            key={`${social.service}:${social.value}`}
            href={href}
            target="_blank"
            rel="noopener nofollow"
            title={serviceTitle}
            class="btn btn-sm btn-soft"
          >
            <i class={`bi bi-${icon} me-1-5`} />
            {social.value}
          </a>
        ) : (
          <span
            key={`${social.service}:${social.value}`}
            class="btn btn-sm btn-soft"
            title={serviceTitle}
          >
            <i class={`bi bi-${icon} me-1-5`} />
            {social.value}
          </span>
        )
      })}
    </div>
  )
}

export const AboutSection = ({
  isSelf,
  description,
  descriptionRich,
  socials: initialSocials,
}: {
  isSelf: boolean
  description: Signal<string | undefined>
  descriptionRich: Signal<string>
  socials: Signal<readonly UserSocialValid[]>
}) => {
  const hasDescription = Boolean(description.value)
  const socials = knownSocials(initialSocials.value)
  const hasSocials = socials.length > 0
  if (!(hasDescription || hasSocials || isSelf)) return null

  return (
    <>
      <h3 class={`ms-1 ${hasSocials ? "mb-2" : "mb-3"} d-flex align-items-center`}>
        {t("user.about_me")}
        {isSelf && (
          <>
            <button
              class="btn btn-sm btn-soft ms-3"
              type="button"
              data-bs-toggle="modal"
              data-bs-target={`#${PROFILE_SOCIALS_MODAL_ID}`}
            >
              <i class="bi bi-pencil-square me-1-5" />
              {t("user.edit_socials")}
            </button>
            <button
              class="btn btn-sm btn-soft ms-2"
              type="button"
              data-bs-toggle="modal"
              data-bs-target={`#${PROFILE_DESCRIPTION_MODAL_ID}`}
            >
              <i class="bi bi-pencil-square me-1-5" />
              {t("user.edit_description")}
            </button>
          </>
        )}
      </h3>

      <SocialLinks
        socials={socials}
        class={hasDescription || isSelf ? "mb-3" : "mb-4"}
      />

      {hasDescription ? (
        <div
          class="mb-4 ms-1 rich-text"
          dangerouslySetInnerHTML={{ __html: descriptionRich.value }}
        />
      ) : isSelf ? (
        <div class="mb-4 ms-1 form-text">
          {t("user.you_have_not_provided_a_description")}
        </div>
      ) : null}
    </>
  )
}
