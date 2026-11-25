import { MultiInput } from "@components/multi-input"
import { Tags } from "@components/tags"
import { NOTE_TAGS_MAX_NUM, NOTE_TAG_VALUE_MAX_LENGTH } from "@utils/config"
import { t } from "i18next"

export const NoteTags = ({
  tags,
  current = false,
}: {
  tags: Record<string, string>
  current?: boolean
}) => (
  <div class="mb-3">
    {tags.hashtags && (
      <div class="d-flex flex-wrap gap-1 mb-2">
        {tags.hashtags.split(";").map((hashtag) => (
          <span class="badge text-bg-secondary">{hashtag}</span>
        ))}
      </div>
    )}
    <details>
      <summary>{t(current ? "note_tags.current_tags" : "note_tags.tags")}</summary>
      {Object.keys(tags).length ? <Tags tags={tags} /> : <p>{t("note_tags.empty")}</p>}
    </details>
  </div>
)

export const NoteHashtagInput = ({
  value,
  onChange,
}: {
  value: string
  onChange?: (values: readonly string[]) => void
}) => (
  <fieldset class="mb-3">
    <legend class="fs-6">{t("note_tags.hashtags")}</legend>
    <MultiInput
      name="hashtags"
      defaultValue={value.replaceAll(";", ",")}
      placeholder={t("note_tags.placeholder")}
      maxItems={[NOTE_TAGS_MAX_NUM, t("note_tags.limit", { count: NOTE_TAGS_MAX_NUM })]}
      maxItemLength={NOTE_TAG_VALUE_MAX_LENGTH}
      {...(onChange ? { onChange } : {})}
    />
  </fieldset>
)
