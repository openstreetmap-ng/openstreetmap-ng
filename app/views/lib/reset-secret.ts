import { configureStandardForm } from "@lib/standard-form"
import { t } from "i18next"

const onResetSecretButtonClick = (e: MouseEvent) => {
  console.debug("ResetSecret: Button clicked")
  const button = e.currentTarget as HTMLButtonElement
  const control = button.closest(".reset-secret-control")
  const form =
    control?.querySelector("form.reset-secret-form") ??
    document.querySelector("form.reset-secret-form")!

  if (confirm(t("settings.new_secret_question"))) {
    configureStandardForm(form, ({ secret }) => {
      // On success callback, display the new secret
      console.debug("ResetSecret: Success")
      const input = button.parentElement!.querySelector("input")!
      input.value = secret
      input.dispatchEvent(new Event("change"))
    })
    form.requestSubmit()
  }
}

for (const control of document.querySelectorAll(".reset-secret-control")) {
  const button = control.querySelector("button.reset-secret-btn")
  if (button) {
    button.addEventListener("click", onResetSecretButtonClick)
  } else {
    console.error("ResetSecret: Button not found", control)
  }
}
