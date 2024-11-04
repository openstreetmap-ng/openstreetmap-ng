import { create, toBinary } from "@bufbuild/protobuf"
import { base64Encode } from "@bufbuild/protobuf/wire"
import { pbkdf2Async } from "@noble/hashes/pbkdf2"
import { sha512 } from "@noble/hashes/sha2"
import { type TransmitUserPassword, TransmitUserPasswordSchema } from "./proto/shared_pb"

type PasswordSchema = "v1" | "legacy"

const defaultPasswordSchema: PasswordSchema = "v1"
const formUsePasswordSchemasMap: Map<HTMLFormElement, (PasswordSchema | string)[]> = new Map()

export const initPasswordsForm = (form: HTMLFormElement, passwordInputs: NodeListOf<HTMLInputElement>): void => {
    console.debug("Initializing passwords form with", passwordInputs.length, "inputs", form.action)
    formUsePasswordSchemasMap.set(form, [defaultPasswordSchema])

    for (const input of passwordInputs) {
        const inputName = input.dataset.name
        const passwordInput = document.createElement("input")
        passwordInput.classList.add("hidden-password-input", "d-none")
        passwordInput.type = "text" // as "text" to show standardForm feedback directly next to the original
        passwordInput.name = inputName
        input.parentElement.insertBefore(passwordInput, input.nextSibling)
    }
}

export const updatePasswordsFormHashes = async (
    form: HTMLFormElement,
    passwordInputs: NodeListOf<HTMLInputElement>,
): Promise<void> => {
    const passwordSchemas = formUsePasswordSchemasMap.get(form)
    console.debug("Updating passwords form with", passwordSchemas, "schemas", form.action)

    const tasks: Promise<void>[] = []
    for (const input of passwordInputs) {
        const inputName = input.dataset.name
        const passwordInput = form.elements.namedItem(input.dataset.name) as HTMLInputElement
        if (!inputName.endsWith("_confirm")) {
            tasks.push(
                wrappedClientHashPassword(passwordSchemas, input.value).then((result) => {
                    passwordInput.value = result
                    passwordInput.dispatchEvent(new Event("change"))
                }),
            )
        }
    }
    await Promise.all(tasks)
}

// TODO: harden against downgrade attacks
export const handlePasswordSchemaFeedback = (form: HTMLFormElement, response: PasswordSchema | string): boolean => {
    const currentPasswordSchemas = formUsePasswordSchemasMap.get(form)
    if (currentPasswordSchemas.length === 2 && currentPasswordSchemas[1] === response) return false
    const newPasswordSchemas = [currentPasswordSchemas[0], response]
    console.debug("Setting password schemas to", newPasswordSchemas, "for", form.action)
    formUsePasswordSchemasMap.set(form, newPasswordSchemas)
    return true
}

const wrappedClientHashPassword = async (
    passwordSchemas: (PasswordSchema | string)[],
    password: string,
): Promise<string> => {
    const transmitUserPassword = create(TransmitUserPasswordSchema)
    const tasks: Promise<void>[] = []
    for (const passwordSchema of passwordSchemas) {
        tasks.push(clientHashPassword(transmitUserPassword, passwordSchema, password))
    }
    await Promise.all(tasks)
    return base64Encode(toBinary(TransmitUserPasswordSchema, transmitUserPassword))
}

const clientHashPassword = async (
    transmitUserPassword: TransmitUserPassword,
    passwordSchema: PasswordSchema | string,
    password: string,
): Promise<void> => {
    if (passwordSchema === "v1") {
        // TODO: check performance on mobile
        // client-side pbkdf2 sha512, 100_000 iters, base64 encoded
        const salt = `${window.location.origin}/zaczero@osm.ng`
        let timer = performance.now()
        const hashBytes = await pbkdf2_sha512(password, salt, 100_000)
        timer = performance.now() - timer
        console.debug("pbkdf2_sha512 took", Number(timer.toFixed(1)), "ms")
        transmitUserPassword.v1 = hashBytes
    } else if (passwordSchema === "legacy") {
        // no client-side hashing
        transmitUserPassword.legacy = password
    } else {
        throw new Error(`Unsupported clientHash password schema: ${passwordSchema}`)
    }
}

const pbkdf2_sha512 = async (password: string, salt: string, iterations: number): Promise<Uint8Array> => {
    try {
        const passwordKey = await crypto.subtle.importKey(
            "raw", //
            new TextEncoder().encode(password),
            "PBKDF2",
            false,
            ["deriveBits"],
        )
        return new Uint8Array(
            await crypto.subtle.deriveBits(
                {
                    name: "PBKDF2",
                    hash: "SHA-512",
                    salt: new TextEncoder().encode(salt),
                    iterations,
                },
                passwordKey,
                512,
            ),
        )
    } catch (e: any) {
        if (e.name !== "NotSupportedError") throw e
    }
    console.warn("SubtleCrypto does not support PBKDF2 SHA-512, falling back to polyfill")
    return await pbkdf2Async(sha512, password, salt, { c: iterations, dkLen: 64 })
}
