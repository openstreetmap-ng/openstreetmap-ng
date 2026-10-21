import { Tags } from "@components/tags"
import { useSignal } from "@preact/signals"
import { t } from "i18next"
import { useId, useLayoutEffect, useRef } from "preact/hooks"

const Editor = ({ tags }: { tags: Record<string, string> }) => {
  const rootRef = useRef<HTMLDivElement>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const textRef = useRef<HTMLTextAreaElement>(null)
  const editRef = useRef<HTMLButtonElement>(null)
  const wasEditing = useRef(false)
  const textId = useId()
  const commentId = useId()
  const editing = useSignal(false)

  useLayoutEffect(() => {
    if (editing.value) textRef.current!.focus()
    else if (wasEditing.current) editRef.current!.focus()
    wasEditing.current = editing.value
  }, [editing.value])

  const edit = () => {
    const rawTags = JSON.parse(rootRef.current!.dataset.tags!) as Record<string, string>
    textRef.current!.value = Object.entries(rawTags)
      .map(([key, value]) => `${key}=${value}`)
      .join("\n")
    editing.value = true
  }

  const discard = () => {
    formRef.current!.reset()
    editing.value = false
  }

  return (
    <div
      class="element-tags mt-3"
      data-tags={JSON.stringify(tags)}
      ref={rootRef}
    >
      <div class="d-flex align-items-center justify-content-between mb-2">
        <h4 class="mb-0">{t("browse.tag_details.tags")}</h4>
        <button
          class="btn btn-link"
          type="button"
          hidden={editing.value}
          onClick={edit}
          ref={editRef}
        >
          {t("element.edit_text")}
        </button>
      </div>
      <div hidden={editing.value}>
        <Tags tags={tags} />
      </div>
      {/* API 0.7 wiring is deferred; retain the requested native POST form. */}
      <form
        method="post"
        hidden={!editing.value}
        ref={formRef}
      >
        <label
          class="visually-hidden"
          for={textId}
        >
          {t("browse.tag_details.tags")}
        </label>
        <textarea
          class="form-control font-monospace mb-3"
          id={textId}
          name="tags"
          rows={8}
          spellcheck={false}
          ref={textRef}
        />
        <label
          class="form-label"
          for={commentId}
        >
          {t("action.comment")}
        </label>
        <input
          class="form-control mb-3"
          id={commentId}
          name="comment"
          required
        />
        <div class="d-flex justify-content-end gap-2">
          <button
            class="btn btn-light border"
            type="button"
            onClick={discard}
          >
            {t("element.discard")}
          </button>
          <button
            class="btn btn-primary"
            type="submit"
          >
            {t("action.submit")}
          </button>
        </div>
      </form>
    </div>
  )
}

export const ElementTags = ({
  tags,
  editable,
}: {
  tags: Record<string, string>
  editable: boolean
}) => (editable ? <Editor tags={tags} /> : <Tags tags={tags} />)
