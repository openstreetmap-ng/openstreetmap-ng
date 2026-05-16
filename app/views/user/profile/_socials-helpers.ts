import type { Message } from "@bufbuild/protobuf"
import type { UserSocialValid } from "@proto/shared_pb"
import { t } from "i18next"
import type { ProfileSocialOptionConfig } from "./_social-options.macro"
import { getProfileSocialOptions } from "./_social-options.macro" with { type: "macro" }

export type SocialValue = Omit<UserSocialValid, keyof Message>

export const SOCIAL_OPTIONS = getProfileSocialOptions()
export const SOCIAL_OPTIONS_BY_KEY = new Map(
  SOCIAL_OPTIONS.map((option) => [option.key, option]),
)

export const socialServiceTitle = (option: ProfileSocialOptionConfig) =>
  t(`service.${option.key.replaceAll("-", "_")}.title`)

export const socialLabelText = (option: ProfileSocialOptionConfig) =>
  t(`socials.label.${option.label}`)

export const knownSocials = (socials: readonly UserSocialValid[]) =>
  socials.filter((social) => SOCIAL_OPTIONS_BY_KEY.has(social.service))

export const getSocialLink = (
  social: SocialValue,
  option: ProfileSocialOptionConfig,
) => {
  const { template } = option
  if (template === undefined) return social.value
  return template ? template.replace("{}", social.value) : null
}
