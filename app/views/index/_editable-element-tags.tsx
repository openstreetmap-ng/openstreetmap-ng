import { Tags } from "@components/tags"
import { useSignal } from "@preact/signals"
import { isLoggedIn } from "@utils/config"
import { useDisposeLayoutEffect } from "@utils/dispose-scope"
import { t } from "i18next"
import { useRef } from "preact/hooks"
import { configureTagEditor } from "./_tag-editor"

export const EditableElementTags = ({
  tags,
  action,
  version,
  latest,
  visible,
}: {
  tags: Record<string, string>
  action: string
  version: bigint
  latest: boolean
  visible: boolean
}) => {
  const editing = useSignal(false)
  const host = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const editor = useRef<ReturnType<typeof configureTagEditor>>()
  const allowed = isLoggedIn && latest && visible
  useDisposeLayoutEffect(() => {
    if (!allowed) return
    const controller = configureTagEditor(host.current!, () => {
      editing.value = false
      if (button.current) {
        button.current.hidden = false
        button.current.focus()
      }
    })
    editor.current = controller
    return () => {
      controller.dispose()
      editor.current = undefined
    }
  }, [allowed])
  return (
    <section>
      <div class="d-flex align-items-center justify-content-between">
        <h4>{t("tag_editor.tags")}</h4>
        {allowed && (
          <button
            ref={button}
            class="btn btn-link"
            type="button"
            hidden={editing.value}
            onClick={() => {
              editing.value = true
              // Unhide before focusing the native textarea.
              host.current!.hidden = false
              editor.current?.start()
            }}
          >
            {t("tag_editor.edit")}
          </button>
        )}
      </div>
      <div hidden={editing.value}>
        <Tags tags={tags} />
      </div>
      {allowed && (
        <div
          ref={host}
          hidden={!editing.value}
          data-tags={JSON.stringify(tags)}
          data-action={action}
          data-version={version.toString()}
        />
      )}
    </section>
  )
}
