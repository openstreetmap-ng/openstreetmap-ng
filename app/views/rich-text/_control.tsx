import { ConnectError } from "@connectrpc/connect"
import { useDisposeSignalEffect } from "@lib/dispose-scope"
import { RichTextService } from "@lib/proto/rich_text_pb"
import { connectErrorToMessage, rpcUnary } from "@lib/rpc"
import { type Signal, useSignal } from "@preact/signals"
import { t } from "i18next"
import { type Ref, render } from "preact"
import { memo } from "preact/compat"
import { useRef } from "preact/hooks"

type RichTextMode = "edit" | "preview" | "help"

export const RichTextControl = ({
  name,
  value = "",
  maxLength,
  required = false,
  textareaRef,
}: {
  name: string
  value?: string | undefined
  maxLength?: number | undefined
  required?: boolean | undefined
  textareaRef?: Ref<HTMLTextAreaElement> | undefined
}) => {
  const mode = useSignal<RichTextMode>("edit")
  const previewHtml = useSignal("")
  const textAreaRef = useRef<HTMLTextAreaElement>(null)

  // Effect: Fetch preview HTML when in preview mode
  useDisposeSignalEffect((scope) => {
    if (mode.value !== "preview") {
      previewHtml.value = ""
      return
    }

    previewHtml.value = t("browse.start_rjs.loading")

    const fetchPreview = async () => {
      try {
        const resp = await rpcUnary(RichTextService.method.renderMarkdown)(
          { text: textAreaRef.current!.value },
          {
            signal: scope.signal,
          },
        )
        scope.signal.throwIfAborted()
        previewHtml.value = resp.html
      } catch (error) {
        if (error.name === "AbortError") return
        console.error("RichTextControl: Preview fetch failed", error)
        previewHtml.value =
          error instanceof ConnectError ? connectErrorToMessage(error) : error.message
      }
    }
    void fetchPreview()
  })

  return (
    <div class="row flex-column-reverse flex-md-row">
      <div class="col-md-8">
        <textarea
          class="form-control"
          name={name}
          rows={18}
          maxLength={maxLength}
          required={required}
          defaultValue={value}
          ref={(el) => {
            textAreaRef.current = el
            if (typeof textareaRef === "function") {
              textareaRef(el)
            } else if (textareaRef) {
              textareaRef.current = el
            }
          }}
          hidden={mode.value !== "edit"}
        />
        {mode.value === "preview" && (
          <div
            class="RichTextPreview rich-text"
            dangerouslySetInnerHTML={{ __html: previewHtml.value }}
          />
        )}
      </div>
      <div class="col-md-4">
        <div class="sticky-top pt-md-2">
          <ModeButtons
            class="mb-4 d-none d-md-inline-flex"
            mode={mode}
          />
          <ModeButtons
            class="mb-2 d-flex d-sm-inline-flex d-md-none"
            mode={mode}
            showHelp
            mobile
          />
          {mode.value === "help" && <RichTextHelp class="d-md-none" />}
          <RichTextHelp class="d-none d-md-block" />
        </div>
      </div>
    </div>
  )
}

const ModeButtons = ({
  class: className,
  mode,
  showHelp = false,
  mobile = false,
}: {
  class: string
  mode: Signal<RichTextMode>
  showHelp?: boolean | undefined
  mobile?: boolean | undefined
}) => (
  <fieldset class={`btn-group ${className} border-0 p-0 m-0`}>
    <button
      class={mobile ? "btn btn-primary px-sm-3" : "btn btn-primary"}
      type="button"
      disabled={mode.value === "edit"}
      onClick={() => (mode.value = "edit")}
    >
      {t("layouts.edit")}
    </button>
    <button
      class={mobile ? "btn btn-primary px-sm-3" : "btn btn-primary"}
      type="button"
      disabled={mode.value === "preview"}
      onClick={() => (mode.value = "preview")}
    >
      {t("shared.richtext_field.preview")}
    </button>
    {showHelp && (
      <button
        class={mobile ? "btn btn-soft px-sm-3" : "btn btn-soft"}
        type="button"
        disabled={mode.value === "help"}
        onClick={() => (mode.value = "help")}
      >
        {t("rich_text.formatting_tips")}
      </button>
    )}
  </fieldset>
)

const RichTextHelp = memo(({ class: className = "" }: { class?: string }) => (
  <div class={`RichTextHelp p-2 p-md-0 ${className}`}>
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
  const { name, value, maxlength, required } = root.dataset
  render(
    <RichTextControl
      name={name!}
      value={value}
      maxLength={maxlength ? Number.parseInt(maxlength, 10) : undefined}
      required={Boolean(required)}
    />,
    root,
  )
}
