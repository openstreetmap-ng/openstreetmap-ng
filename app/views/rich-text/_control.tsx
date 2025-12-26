import { useSignal, useSignalEffect } from "@preact/signals"
import { assert, assertExists } from "@std/assert"
import { t } from "i18next"
import { render } from "preact"
import { memo } from "preact/compat"
import { useRef } from "preact/hooks"

type RichTextMode = "idle" | "edit" | "preview" | "help"

type RichTextConfig = {
  name: string
  value: string
  maxLength: number | undefined
  rows: number
  required: boolean
}

const parseNumber = (value: string | undefined) =>
  value ? Number.parseInt(value, 10) : undefined

const parseBoolean = (value: string | undefined) =>
  value === "true" || value === "1" || value === "yes"

const getConfig = (root: HTMLElement): RichTextConfig => {
  const { name, value, maxlength, rows, required } = root.dataset
  assertExists(name, "RichTextControl: Missing data-name")

  return {
    name,
    value: value ?? "",
    rows: parseNumber(rows) ?? 18,
    required: parseBoolean(required),
    maxLength: parseNumber(maxlength),
  }
}

const RichTextControl = ({ config }: { config: RichTextConfig }) => {
  const mode = useSignal<RichTextMode>("idle")
  const previewHtml = useSignal("")
  const textAreaRef = useRef<HTMLTextAreaElement>(null)

  // Effect: Fetch preview HTML when in preview mode
  useSignalEffect(() => {
    if (mode.value !== "preview") {
      previewHtml.value = ""
      return
    }

    const abortController = new AbortController()
    const formData = new FormData()
    formData.append("text", textAreaRef.current!.value)
    previewHtml.value = t("browse.start_rjs.loading")

    const fetchPreview = async () => {
      try {
        const resp = await fetch("/api/web/rich-text", {
          method: "POST",
          body: formData,
          signal: abortController.signal,
          priority: "high",
        })
        const respText = await resp.text()
        abortController.signal.throwIfAborted()
        previewHtml.value = respText
      } catch (error) {
        if (error.name === "AbortError") return
        console.error("RichTextControl: Preview fetch failed", error)
        previewHtml.value = error.message
      }
    }

    fetchPreview()
    return () => abortController.abort()
  })

  const isEditing = mode.value === "idle" || mode.value === "edit"
  const isPreviewing = mode.value === "preview"
  const isHelp = mode.value === "help"

  return (
    <div class="row flex-column-reverse flex-md-row">
      <div class="col-md-8">
        <textarea
          class="form-control"
          name={config.name}
          rows={config.rows}
          maxLength={config.maxLength}
          required={config.required}
          defaultValue={config.value}
          ref={textAreaRef}
          hidden={!isEditing}
        />
        {isPreviewing && (
          <div
            class="RichTextPreview rich-text"
            dangerouslySetInnerHTML={{ __html: previewHtml.value }}
          />
        )}
      </div>
      <div class="col-md-4">
        <div class="sticky-top pt-md-2">
          <fieldset class="btn-group mb-4 d-none d-md-inline-flex border-0 p-0 m-0">
            <button
              class="btn btn-primary"
              type="button"
              disabled={isEditing}
              onClick={() => (mode.value = "edit")}
            >
              {t("layouts.edit")}
            </button>
            <button
              class="btn btn-primary"
              type="button"
              disabled={isPreviewing}
              onClick={() => (mode.value = "preview")}
            >
              {t("shared.richtext_field.preview")}
            </button>
          </fieldset>
          <fieldset class="btn-group mb-2 d-flex d-sm-inline-flex d-md-none border-0 p-0 m-0">
            <button
              class="btn btn-primary px-sm-3"
              type="button"
              disabled={isEditing}
              onClick={() => (mode.value = "edit")}
            >
              {t("layouts.edit")}
            </button>
            <button
              class="btn btn-primary px-sm-3"
              type="button"
              disabled={isPreviewing}
              onClick={() => (mode.value = "preview")}
            >
              {t("shared.richtext_field.preview")}
            </button>
            <button
              class="btn btn-soft px-sm-3"
              type="button"
              disabled={isHelp}
              onClick={() => (mode.value = "help")}
            >
              {t("rich_text.formatting_tips")}
            </button>
          </fieldset>
          {isHelp && <RichTextHelp class="d-md-none" />}
          <RichTextHelp class="d-none d-md-block" />
        </div>
      </div>
    </div>
  )
}

const RichTextHelp = memo(({ class: extraClass }: { class?: string }) => (
  <div class={`RichTextHelp p-2 p-md-0 ${extraClass ?? ""}`}>
    <h5>
      <img
        class="markdown-logo me-2"
        src="/static/img/brand/markdown.webp"
        alt="Markdown"
        title="Markdown"
      />
      {t("rich_text.formatting_tips")}
    </h5>
    <dl>
      <dt>{t("shared.markdown_help.headings")}</dt>
      <dd>
        # {t("shared.markdown_help.heading")}
        <br />
        ## {t("shared.markdown_help.subheading")}
      </dd>
    </dl>
    <dl>
      <dt>{t("shared.markdown_help.link")}</dt>
      <dd>
        [{t("shared.markdown_help.text")}]({t("shared.markdown_help.url")})
      </dd>
    </dl>
    <dl>
      <dt>{t("shared.markdown_help.image")}</dt>
      <dd>
        ![{t("shared.markdown_help.alt")}]({t("shared.markdown_help.url")})
      </dd>
    </dl>
    <dl>
      <dt>{t("shared.markdown_help.unordered")}</dt>
      <dd>
        * {t("shared.markdown_help.first")}
        <br />* {t("shared.markdown_help.second")}
      </dd>
    </dl>
    <dl>
      <dt>{t("shared.markdown_help.ordered")}</dt>
      <dd>
        1. {t("shared.markdown_help.first")}
        <br />
        2. {t("shared.markdown_help.second")}
      </dd>
    </dl>
    <p class="small text-end mb-1">
      <a
        href="https://commonmark.org/help/"
        target="_blank"
        rel="noopener help"
      >
        {t("rich_text.detailed_formatting_guide")}
        <i class="bi bi-box-arrow-up-right ms-2" />
      </a>
    </p>
  </div>
))

const roots = document.querySelectorAll<HTMLElement>(".RichTextControl")
console.debug("RichTextControl: Initializing", roots.length, "containers")
for (const root of roots) {
  render(<RichTextControl config={getConfig(root)} />, root)
}
