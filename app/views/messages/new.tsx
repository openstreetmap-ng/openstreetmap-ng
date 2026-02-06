import {
  DISPLAY_NAME_MAX_LENGTH,
  MESSAGE_BODY_MAX_LENGTH,
  MESSAGE_RECIPIENTS_LIMIT,
  MESSAGE_SUBJECT_MAX_LENGTH,
} from "@lib/config"
import { mount } from "@lib/mount"
import { MultiInput } from "@lib/multi-input"
import { MessageService } from "@lib/proto/message_pb"
import { StandardForm } from "@lib/standard-form"
import { t } from "i18next"
import { render } from "preact"
import { useEffect, useRef } from "preact/hooks"
import { RichTextControl } from "../rich-text/_control"

type MessagesNewProps = {
  recipients: string
  subject: string
  body: string
}

const MessagesNew = ({ recipients, subject, body }: MessagesNewProps) => {
  const messageBodyRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const messageBody = messageBodyRef.current!
    if (messageBody.value) {
      // When body is present, autofocus at the beginning
      messageBody.focus()
      messageBody.setSelectionRange(0, 0)
    }
  }, [])

  return (
    <>
      <div class="content-header">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <h1>{t("action.send_a_message")}</h1>
          <p class="mb-2">{t("messages.compose.description")}</p>
        </div>
      </div>
      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <StandardForm
            class="message-form"
            method={MessageService.method.sendMessage}
            buildRequest={({ formData }) => ({
              subject: formData.get("subject") as string,
              body: formData.get("body") as string,
              recipient: formData.getAll("recipient") as string[],
            })}
            onSuccess={({ redirectUrl }) => {
              console.debug("NewMessage: Success", redirectUrl)
              window.location.href = redirectUrl
            }}
          >
            <label
              class="form-label d-block mb-3"
              for="multi-input-recipient"
            >
              <span class="required">{t("messages.compose.recipients")}</span>
              <div class="mt-2">
                <MultiInput
                  name="recipient"
                  id="multi-input-recipient"
                  placeholder={t("messages.compose.recipient_placeholder")}
                  defaultValue={recipients}
                  required
                  maxItems={[
                    MESSAGE_RECIPIENTS_LIMIT,
                    t("validation.you_can_send_message_to_at_most_limit_recipients", {
                      limit: MESSAGE_RECIPIENTS_LIMIT,
                    }),
                  ]}
                  maxItemLength={DISPLAY_NAME_MAX_LENGTH}
                />
              </div>
            </label>

            <label class="form-label d-block mb-3">
              <span class="required">{t("messages.compose.subject")}</span>
              <input
                type="text"
                name="subject"
                class="form-control mt-2"
                defaultValue={subject}
                placeholder={t("messages.compose.subject_placeholder")}
                maxLength={MESSAGE_SUBJECT_MAX_LENGTH}
                required
              />
            </label>

            <label class="form-label d-block">
              <span class="required">{t("messages.compose.body")}</span>
            </label>
            <RichTextControl
              name="body"
              value={body}
              maxLength={MESSAGE_BODY_MAX_LENGTH}
              required
              textareaRef={messageBodyRef}
            />

            <div class="mt-3">
              <button
                class="btn btn-lg btn-primary px-3"
                type="submit"
              >
                <i class="bi bi-send-fill me-2" />
                {t("action.send")}
              </button>
            </div>
          </StandardForm>
        </div>
      </div>
    </>
  )
}

mount("messages-new-body", () => {
  const root = document.getElementById("MessagesNewRoot")!
  const { recipients, subject, body } = root.dataset
  render(
    <MessagesNew
      recipients={recipients!}
      subject={subject!}
      body={body!}
    />,
    root,
  )
})
