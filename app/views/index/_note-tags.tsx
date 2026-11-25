import { Tags } from "@components/tags"
import { t } from "i18next"

export const NoteTags = ({
  tags,
  snapshot = false,
}: {
  tags: Record<string, string>
  snapshot?: boolean
}) => {
  const hasTags = Object.keys(tags).length > 0
  if (!hasTags && !snapshot) return null

  const hashtags = [...new Set((tags.hashtags ?? "").split(";").filter(Boolean))]

  return (
    <div class="mb-3">
      {hashtags.length > 0 && (
        <div
          class="d-flex flex-wrap gap-1 mb-2"
          dir="auto"
        >
          {hashtags.map((hashtag) => (
            <span
              key={hashtag}
              class="badge text-bg-secondary text-break text-wrap"
            >
              {hashtag}
            </span>
          ))}
        </div>
      )}
      <details>
        <summary class="text-muted small">
          {snapshot ? t("note.tag_snapshot") : t("note.tags")}
        </summary>
        {hasTags ? <Tags tags={tags} /> : <p class="form-text">{t("note.no_tags")}</p>}
      </details>
    </div>
  )
}
