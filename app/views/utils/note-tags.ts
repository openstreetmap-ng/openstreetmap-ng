export const noteHashtags = (values: readonly string[]) =>
  [
    ...new Set(
      values.map((value) => {
        const text = value.trim()
        return text.startsWith("#") ? text : `#${text}`
      }),
    ),
  ].join(";")

export const noteTagsFromForm = (
  formData: FormData,
  current: Record<string, string>,
) => {
  const tags = { ...current }
  const hashtags = noteHashtags(formData.getAll("hashtags") as string[])
  if (hashtags) tags.hashtags = hashtags
  else delete tags.hashtags
  return tags
}
