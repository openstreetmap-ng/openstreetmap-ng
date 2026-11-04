import { NOTE_COMMENT_BODY_MAX_LENGTH } from "@utils/config"
import { t } from "i18next"

export const parseHashtagInput = (values: string[]) =>
  [...new Set(values.flatMap((value) => value.split(/[\s,;]+/u)))]
    .filter(Boolean)
    .map((value) => (value.startsWith("#") ? value : `#${value}`))
    .filter((value, index, all) => all.indexOf(value) === index)

export const buildNoteBody = (body: string, values: string[]) => {
  const hashtags = parseHashtagInput(values)
  if (!hashtags.length) return body

  if (
    hashtags.some(
      (value) => !/^#[\p{L}\p{N}\p{M}_-]+$/u.test(value) || !/[\p{L}\p{N}]/u.test(value),
    )
  ) {
    throw new Error(t("note.hashtags_invalid"))
  }

  // Match the storage extractor, including hashtags already in the description.
  const existing = [
    // Python str.isspace() also recognizes the U+001C–U+001F separators.
    // eslint-disable-next-line no-control-regex
    ...body.matchAll(/(?:^|[\p{White_Space}\u001c-\u001f])(#[\p{L}\p{N}\p{M}_-]+)/gu),
  ]
    .map((match) => match[1]!)
    .filter((value) => /[\p{L}\p{N}]/u.test(value))
  const all = [...new Set([...existing, ...hashtags])]
  // Hstore tag values and extract_note_hashtags use a 255-code-point limit.
  if ([...all.join(";")].length > 255) {
    throw new Error(t("note.hashtags_too_long"))
  }

  const added = hashtags.filter((value) => !existing.includes(value))
  const result = added.length ? `${body}\n${added.join(" ")}` : body
  if ([...result].length > NOTE_COMMENT_BODY_MAX_LENGTH) {
    throw new Error(t("note.description_and_hashtags_too_long"))
  }
  return result
}

export const buildNoteTagUpdate = (
  current: Record<string, string>,
  values: string[],
) => {
  // Reuse the input validation without appending anything to the comment body.
  buildNoteBody("", values)
  const hashtags = parseHashtagInput(values)
  const tags = { ...current }
  if (hashtags.length) tags.hashtags = hashtags.join(";")
  else delete tags.hashtags
  return tags
}
