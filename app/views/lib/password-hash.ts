import { create, toBinary } from "@bufbuild/protobuf"
import {
  type TransmitUserPassword,
  TransmitUserPasswordSchema,
} from "@lib/proto/shared_pb"
import { unreachable } from "@std/assert"
import { roundTo } from "@std/math/round-to"

type PasswordSchema = "v1" | "legacy"

const DEFAULT_PASSWORD_SCHEMA: PasswordSchema = "v1"
const formUsePasswordSchemasMap = new WeakMap<
  HTMLFormElement,
  (PasswordSchema | string)[]
>()

export const configurePasswordsForm = (
  form: HTMLFormElement,
  passwordInputs: NodeListOf<HTMLInputElement>,
) => {
  console.debug(
    "PasswordHash: Initializing",
    passwordInputs.length,
    "inputs",
    form.action,
  )
  formUsePasswordSchemasMap.set(form, [DEFAULT_PASSWORD_SCHEMA])

  for (const input of passwordInputs) {
    const inputName = input.dataset.name!
    const passwordInput = document.createElement("input")
    passwordInput.classList.add("hidden-password-input", "d-none")
    passwordInput.type = "text" // as "text" to show standardForm feedback directly next to the original
    passwordInput.name = inputName
    input.parentElement!.insertBefore(passwordInput, input.nextSibling)
  }
}

export const appendPasswordsToFormData = async (
  form: HTMLFormElement,
  formData: FormData,
  passwordInputs: NodeListOf<HTMLInputElement>,
) => {
  const passwordSchemas = formUsePasswordSchemasMap.get(form)!
  console.debug("PasswordHash: Updating with schemas", passwordSchemas, form.action)

  const tasks: Promise<void>[] = []
  for (const input of passwordInputs) {
    const inputName = input.dataset.name!
    if (!inputName.endsWith("_confirm") && input.value) {
      const buildAndSet = async () => {
        formData.set(
          inputName,
          new Blob([await buildTransmitPassword(passwordSchemas, input.value)], {
            type: "application/octet-stream",
          }),
        )
      }
      tasks.push(buildAndSet())
    }
  }
  await Promise.all(tasks)
}

// TODO: harden against downgrade attacks
export const handlePasswordSchemaFeedback = (
  form: HTMLFormElement,
  response: PasswordSchema | string,
) => {
  const currentPasswordSchemas = formUsePasswordSchemasMap.get(form)!
  if (currentPasswordSchemas.length === 2 && currentPasswordSchemas[1] === response)
    return false
  const newPasswordSchemas = [currentPasswordSchemas[0], response]
  console.debug("PasswordHash: Setting schemas", newPasswordSchemas, form.action)
  formUsePasswordSchemasMap.set(form, newPasswordSchemas)
  return true
}

const buildTransmitPassword = async (
  passwordSchemas: (PasswordSchema | string)[],
  password: string,
) => {
  const transmitUserPassword = create(TransmitUserPasswordSchema)
  const tasks: Promise<void>[] = []
  for (const passwordSchema of passwordSchemas) {
    tasks.push(clientHashPassword(transmitUserPassword, passwordSchema, password))
  }
  await Promise.all(tasks)
  return toBinary(TransmitUserPasswordSchema, transmitUserPassword)
}

const clientHashPassword = async (
  transmitUserPassword: TransmitUserPassword,
  passwordSchema: PasswordSchema | string,
  password: string,
) => {
  if (passwordSchema === "v1") {
    // TODO: check performance on mobile
    // client-side pbkdf2 sha512, 100_000 iters, base64 encoded
    const salt = `${window.location.origin}/zaczero@osm.ng`
    let timer = performance.now()
    const hashBytes = await pbkdf2_sha512(password, salt, 100_000)
    timer = performance.now() - timer
    console.debug("PasswordHash: PBKDF2 completed", roundTo(timer, 1), "ms")
    transmitUserPassword.v1 = hashBytes
  } else if (passwordSchema === "legacy") {
    // no client-side hashing
    transmitUserPassword.legacy = password
  } else {
    unreachable(`Unsupported clientHash password schema: ${passwordSchema}`)
  }
}

const pbkdf2_sha512 = async (password: string, salt: string, iterations: number) => {
  const encoder = new TextEncoder()
  try {
    const passwordKey = await crypto.subtle.importKey(
      "raw",
      encoder.encode(password),
      "PBKDF2",
      false,
      ["deriveBits"],
    )
    return new Uint8Array(
      await crypto.subtle.deriveBits(
        {
          name: "PBKDF2",
          hash: "SHA-512",
          salt: encoder.encode(salt),
          iterations,
        },
        passwordKey,
        512,
      ),
    )
  } catch (error) {
    if (error.name !== "NotSupportedError") throw error
  }
  console.warn("PasswordHash: SubtleCrypto not supported, using polyfill")
  const { pbkdf2Async, sha512 } = await import("@lib/polyfills-pbkdf2")
  return pbkdf2Async(sha512, password, salt, { c: iterations, dkLen: 64 })
}
