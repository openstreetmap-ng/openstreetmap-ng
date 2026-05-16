import { parse } from "@std/toml"
import { readFileSync } from "node:fs"

type SocialConfig = {
  icon?: string
  label: string
  placeholder: string
  template?: string
}

type SocialsToml = Record<string, SocialConfig>

export type ProfileSocialOptionConfig = {
  key: string
  icon: string | undefined
  label: string
  placeholder: string
  template: string | undefined
}

/** Build-time macro: embed profile social options from config/socials.toml */
export const getProfileSocialOptions = (): ProfileSocialOptionConfig[] => {
  const socialsToml = parse(readFileSync("config/socials.toml", "utf8")) as SocialsToml

  return Object.entries(socialsToml).map(([key, value]) => ({
    key,
    icon: value.icon,
    label: value.label,
    placeholder: value.placeholder,
    template: value.template,
  }))
}
