import { useSignal } from "@preact/signals"
import { t } from "i18next"
import { useId, useRef } from "preact/hooks"
import { parseHashtagInput } from "./_note-hashtag-helpers"

export const NoteHashtagInput = ({
  initialValues = [],
}: {
  initialValues?: string[]
}) => {
  const id = useId()
  const helpId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const hashtags = useSignal(parseHashtagInput(initialValues))

  const commit = () => {
    const input = inputRef.current!
    hashtags.value = parseHashtagInput([...hashtags.peek(), input.value])
    input.value = ""
  }

  return (
    <div class="mb-4">
      <label
        class="form-label"
        for={id}
      >
        {t("note.hashtags_optional")}
      </label>
      <div class="form-control d-flex flex-wrap align-items-center gap-1">
        {hashtags.value.map((value) => (
          <span
            key={value}
            class="badge text-bg-secondary text-wrap text-break"
          >
            <span dir="auto">{value}</span>{" "}
            <button
              type="button"
              class="btn btn-sm p-0 text-reset"
              aria-label={`${t("action.remove")} ${value}`}
              onClick={() => {
                hashtags.value = hashtags.peek().filter((item) => item !== value)
                inputRef.current!.focus()
              }}
            >
              ×
            </button>
            <input
              type="hidden"
              name="hashtags"
              value={value}
            />
          </span>
        ))}
        <input
          ref={inputRef}
          id={id}
          name="hashtags"
          class="form-control"
          type="text"
          autoComplete="off"
          autoCapitalize="none"
          aria-describedby={helpId}
          placeholder="#survey #osm-ng"
          onKeyDown={(e) => {
            if (e.isComposing) return
            if (e.key === "Enter" || e.key === "," || e.key === ";") {
              e.preventDefault()
              commit()
            } else if (e.key === "Backspace" && !e.currentTarget.value) {
              const last = hashtags.peek().at(-1)
              if (!last) return
              e.preventDefault()
              hashtags.value = hashtags.peek().slice(0, -1)
              e.currentTarget.value = last
            }
          }}
        />
      </div>
      <div
        id={helpId}
        class="form-text"
      >
        {t("note.hashtags_help")}
      </div>
    </div>
  )
}
