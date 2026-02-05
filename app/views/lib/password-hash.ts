import { create, toBinary } from "@bufbuild/protobuf"
import {
  type TransmitUserPassword,
  TransmitUserPasswordSchema,
} from "@lib/proto/shared_pb"
import { roundTo } from "@std/math/round-to"

type PasswordSchema = keyof TransmitUserPassword

const DEFAULT_SCHEMA: PasswordSchema = "v1"

// TODO: harden against downgrade attacks

const updatePasswordSchemas = (schemas: readonly PasswordSchema[], schema: string) => {
  if (!(schema === "v1" || schema === "legacy")) return null
  if (schemas.includes(schema)) return null
  return [...schemas, schema] satisfies PasswordSchema[]
}

const getPasswordFieldNames = (form: HTMLFormElement) =>
  Array.from(form.querySelectorAll("input[type=password][name]"), (input) => input.name)

export const createPasswordTransformState = (form: HTMLFormElement) => {
  const passwordFieldNames = getPasswordFieldNames(form)
  let schemas: PasswordSchema[] = [DEFAULT_SCHEMA]

  return {
    apply: async (formData: FormData) => {
      if (!passwordFieldNames.length) return

      const tasks = []

      for (const name of passwordFieldNames) {
        if (name.endsWith("_confirm")) {
          formData.delete(name)
          continue
        }

        const value = formData.get(name) as string
        if (!value) {
          formData.delete(name)
          continue
        }

        tasks.push(
          (async () => {
            const bytes = await buildTransmitPassword(schemas, value)
            formData.set(
              name,
              new Blob([bytes], {
                type: "application/octet-stream",
              }),
            )
          })(),
        )
      }

      await Promise.all(tasks)
    },
    tryUpdateSchema: (detail: unknown) => {
      if (!Array.isArray(detail)) return false

      let schema: unknown
      for (const entry of detail) {
        if (entry.field === "password_schema") {
          schema = entry.message
          break
        }
        if (entry.loc?.[1] === "password_schema") {
          schema = entry.msg
          break
        }
      }

      if (typeof schema !== "string") return false
      const next = updatePasswordSchemas(schemas, schema)
      if (!next) return false
      schemas = next
      return true
    },
  }
}

const buildTransmitPassword = async (
  schemas: readonly PasswordSchema[],
  password: string,
) => {
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
