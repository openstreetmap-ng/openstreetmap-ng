import { create, toBinary } from "@bufbuild/protobuf"
import {
  type TransmitUserPassword,
  TransmitUserPasswordSchema,
} from "@lib/proto/shared_pb"
import { roundTo } from "@std/math/round-to"

type PasswordSchema = keyof TransmitUserPassword

const DEFAULT_SCHEMA: PasswordSchema = "v1"

const formSchemasMap = new WeakMap<HTMLFormElement, PasswordSchema[]>()

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
  formSchemasMap.set(form, [DEFAULT_SCHEMA])

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
  const schemas = formSchemasMap.get(form)!
  console.debug("PasswordHash: Updating with schemas", schemas, form.action)

  const tasks: Promise<void>[] = []
  for (const input of passwordInputs) {
    const inputName = input.dataset.name!
    if (!inputName.endsWith("_confirm") && input.value) {
      const buildAndSet = async () => {
        formData.set(
          inputName,
          new Blob([await buildTransmitPassword(schemas, input.value)], {
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
export const handlePasswordSchemaFeedback = (form: HTMLFormElement, schema: string) => {
  if (!(schema === "v1" || schema === "legacy")) return false

  const currentSchemas = formSchemasMap.get(form)!
  if (currentSchemas.length === 2 && currentSchemas[1] === schema) return false

  const newSchemas = [currentSchemas[0], schema] satisfies PasswordSchema[]
  console.debug("PasswordHash: Setting schemas", newSchemas, form.action)
  formSchemasMap.set(form, newSchemas)
  return true
}

const buildTransmitPassword = async (schemas: PasswordSchema[], password: string) => {
  const transmitUserPassword = create(TransmitUserPasswordSchema)
  const tasks: Promise<void>[] = []
  for (const schema of schemas) {
    tasks.push(clientHashPassword(transmitUserPassword, schema, password))
  }
  await Promise.all(tasks)
  return toBinary(TransmitUserPasswordSchema, transmitUserPassword)
}

const clientHashPassword = async (
  transmitUserPassword: TransmitUserPassword,
  schema: PasswordSchema,
  password: string,
) => {
  if (schema === "v1") {
    // TODO: check performance on mobile
    // client-side pbkdf2 sha512, 100_000 iters, base64 encoded
    const salt = `${window.location.origin}/zaczero@osm.ng`
    let timer = performance.now()
    const hashBytes = await pbkdf2_sha512(password, salt, 100_000)
    timer = performance.now() - timer
    console.debug("PasswordHash: PBKDF2 completed", roundTo(timer, 1), "ms")
    transmitUserPassword.v1 = hashBytes
  } else {
    transmitUserPassword.legacy = password
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
