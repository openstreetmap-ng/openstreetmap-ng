import { create, toBinary } from "@bufbuild/protobuf"
import {
    type TransmitUserPassword,
    TransmitUserPasswordSchema,
} from "@lib/proto/shared_pb"
import { pbkdf2Async } from "@noble/hashes/pbkdf2.js"
import { sha512 } from "@noble/hashes/sha2.js"

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
        "Initializing passwords form with",
        passwordInputs.length,
        "inputs",
        form.action,
    )
    formUsePasswordSchemasMap.set(form, [DEFAULT_PASSWORD_SCHEMA])

    for (const input of passwordInputs) {
        const inputName = input.dataset.name
        const passwordInput = document.createElement("input")
        passwordInput.classList.add("hidden-password-input", "d-none")
        passwordInput.type = "text" // as "text" to show standardForm feedback directly next to the original
        passwordInput.name = inputName
        input.parentElement.insertBefore(passwordInput, input.nextSibling)
    }
}

export const appendPasswordsToFormData = async (
    form: HTMLFormElement,
    formData: FormData,
    passwordInputs: NodeListOf<HTMLInputElement>,
) => {
    const passwordSchemas = formUsePasswordSchemasMap.get(form)
    console.debug(
        "Updating passwords form with",
        passwordSchemas,
        "schemas",
        form.action,
    )

    const tasks: Promise<void>[] = []
    for (const input of passwordInputs) {
        const inputName = input.dataset.name
        if (!inputName.endsWith("_confirm") && input.value) {
            const buildAndSet = async () => {
                formData.set(
                    inputName,
                    new Blob(
                        [await buildTransmitPassword(passwordSchemas, input.value)],
                        { type: "application/octet-stream" },
                    ),
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
    const currentPasswordSchemas = formUsePasswordSchemasMap.get(form)
    if (currentPasswordSchemas.length === 2 && currentPasswordSchemas[1] === response)
        return false
    const newPasswordSchemas = [currentPasswordSchemas[0], response]
    console.debug("Setting password schemas to", newPasswordSchemas, "for", form.action)
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
        let origin = window.location.origin
        // TODO: remove during test db reset
        if (origin === "https://test.openstreetmap.ng") {
            origin = "https://www.openstreetmap.ng"
        }
        const salt = `${origin}/zaczero@osm.ng`
        let timer = performance.now()
        const hashBytes = await pbkdf2_sha512(password, salt, 100_000)
        timer = performance.now() - timer
        console.debug("pbkdf2_sha512 took", Math.round(timer * 10) / 10, "ms")
        transmitUserPassword.v1 = hashBytes
    } else if (passwordSchema === "legacy") {
        // no client-side hashing
        transmitUserPassword.legacy = password
    } else {
        throw new Error(`Unsupported clientHash password schema: ${passwordSchema}`)
    }
}

const pbkdf2_sha512 = async (password: string, salt: string, iterations: number) => {
    try {
        const encoder = new TextEncoder()
        const passwordKey = await crypto.subtle.importKey(
            "raw", //
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
    console.warn(
        "SubtleCrypto does not support PBKDF2 SHA-512, falling back to polyfill",
    )
    return await pbkdf2Async(sha512, password, salt, { c: iterations, dkLen: 64 })
}
