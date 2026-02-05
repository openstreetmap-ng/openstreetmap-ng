import { base64Decode } from "@bufbuild/protobuf/wire"
import { mount } from "@lib/mount"
import { SettingsSecurityService } from "@lib/proto/settings_security_pb"
import { qsEncode } from "@lib/qs"
import { rpcUnary } from "@lib/rpc"
import {
  type APIDetail,
  configureStandardRpcForm,
  formDataBytes,
} from "@lib/standard-form"
import { resolveUserAgentIconsLazy } from "@lib/user-agent-icons"
import { getPasskeyRegistration } from "@lib/webauthn"
import { t } from "i18next"
import { getDisableAuthMethodModal } from "./security-disable-auth-method-modal"
import { getGenerateRecoveryCodesModal } from "./security-generate-recovery-codes-modal"
import { getSetupTotpModal } from "./security-setup-totp-modal"

mount("settings-security-body", (body) => {
  // Password change
  const passwordForm = body.querySelector("form.password-form")!
  const newPasswordInput = passwordForm.querySelector(
    "input[type=password][name=new_password]",
  )!
  const newPasswordConfirmInput = passwordForm.querySelector(
    "input[type=password][name=new_password_confirm]",
  )!

  configureStandardRpcForm(passwordForm, {
    method: SettingsSecurityService.method.changePassword,
    buildRequest: async ({ formData }) => ({
      oldPassword: await formDataBytes(formData, "old_password"),
      newPassword: await formDataBytes(formData, "new_password"),
      revokeOtherSessions: formData.get("revoke_other_sessions") === "true",
    }),
    resetOnSuccess: true,
    onSuccess: () => console.debug("Security: Password changed"),
    validationCallback: () => {
      const result: APIDetail[] = []
      if (newPasswordInput.value !== newPasswordConfirmInput.value) {
        const msg = t("validation.passwords_missmatch")
        result.push({ type: "error", loc: ["", "new_password"], msg })
        result.push({
          type: "error",
          loc: ["", "new_password_confirm"],
          msg,
        })
      }
      return result
    },
  })

  // Passkey registration
  const addPasskeyForm = body.querySelector("form.add-passkey-form")
  if (addPasskeyForm) {
    configureStandardRpcForm(addPasskeyForm, {
      method: SettingsSecurityService.method.registerPasskey,
      buildRequest: async () => ({
        registration: await getPasskeyRegistration(),
      }),
      onSuccess: () => window.location.reload(),
      formBody: addPasskeyForm.closest("li")!,
    })
  }

  // Passkey rename
  const renameButtons = body.querySelectorAll("button.passkey-rename-btn")
  for (const renameButton of renameButtons) {
    const nameSpan = renameButton.parentElement!.querySelector(".passkey-name")!
    renameButton.addEventListener("click", async () => {
      const oldName = nameSpan.textContent
      const newName = prompt(t("two_fa.enter_new_passkey_name"), oldName)?.trim() ?? ""
      if (newName === null) return

      const resp = await rpcUnary(SettingsSecurityService.method.renamePasskey)({
        credentialId: base64Decode(renameButton.dataset.credentialId!),
        name: newName,
      })
      nameSpan.textContent = resp.name
    })
  }

  const setupTotpButton = body.querySelector("button.setup-totp-btn")
  setupTotpButton?.addEventListener("click", () => {
    getSetupTotpModal().show()
  })

  const disableButtons = body.querySelectorAll("button.disable-auth-method-btn")
  for (const button of disableButtons) {
    button.addEventListener("click", () => {
      const { modal, ctx: disableCtx } = getDisableAuthMethodModal()
      const { authMethod, title, credentialId } = button.dataset
      if (authMethod === "passkey") {
        disableCtx.value = {
          method: "passkey",
          credentialId: credentialId!,
          title: title!,
        }
      } else if (authMethod === "totp") {
        disableCtx.value = {
          method: "totp",
          title: title!,
        }
      }
      modal.show()
    })
  }

  body
    .querySelector("button.generate-recovery-codes-btn")!
    .addEventListener("click", () => {
      getGenerateRecoveryCodesModal().show()
    })

  const revokeTokenForms = body.querySelectorAll("form.revoke-token-form")
  for (const form of revokeTokenForms) {
    configureStandardRpcForm(form, {
      method: SettingsSecurityService.method.revokeToken,
      buildRequest: ({ formData }) => ({
        tokenId: BigInt(formData.get("token_id") as string),
      }),
      onSuccess: () => {
        const row = form.closest("li")!
        const isCurrentSession = row.querySelector(".current-session") !== null
        console.debug(
          "Security: Token revoked",
          isCurrentSession ? "(current session)" : "(other session)",
        )

        if (isCurrentSession) {
          window.location.href = `/login${qsEncode({ referer: window.location.pathname + window.location.search })}`
        } else {
          row.remove()
        }
      },
    })
  }

  resolveUserAgentIconsLazy(body)
})
