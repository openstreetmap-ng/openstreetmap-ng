import { base64Encode } from "@bufbuild/protobuf/wire"

import { pbkdf2Async } from "@noble/hashes/pbkdf2"
import { sha512 } from "@noble/hashes/sha2"

type PasswordSchema = "v1" | "legacy"

const currentPasswordSchema: PasswordSchema = "v1"
const formUsePasswordSchemaMap: Map<HTMLFormElement, PasswordSchema | string> = new Map()

export const initPasswordsForm = (form: HTMLFormElement, passwordInputs: NodeListOf<HTMLInputElement>): void => {
    console.debug("Initializing passwords form with", passwordInputs.length, "inputs", form.action)
    formUsePasswordSchemaMap.set(form, currentPasswordSchema)

    const passwordSchemaInput = document.createElement("input")
    passwordSchemaInput.type = "hidden"
    passwordSchemaInput.name = "password_schema"
    form.appendChild(passwordSchemaInput)

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
    const passwordSchema = formUsePasswordSchemaMap.get(form)
    console.debug("Updating passwords form with", passwordSchema, "schema", form.action)
    const passwordSchemaInput = form.elements.namedItem("password_schema") as HTMLInputElement
    if (passwordSchemaInput.value !== passwordSchema) {
        passwordSchemaInput.value = passwordSchema
        passwordSchemaInput.dispatchEvent(new Event("change"))
    }

    const tasks: Promise<void>[] = []
    for (const input of passwordInputs) {
        const inputName = input.dataset.name
        const passwordInput = form.elements.namedItem(input.dataset.name) as HTMLInputElement
        if (!inputName.endsWith("_confirm")) {
            tasks.push(
                clientHashPassword(passwordSchema, input.value).then((hashedPassword) => {
                    passwordInput.value = hashedPassword
                    passwordInput.dispatchEvent(new Event("change"))
                }),
            )
        }
    }
    await Promise.all(tasks)
}

export const handlePasswordSchemaFeedback = (form: HTMLFormElement, response: PasswordSchema | string): boolean => {
    if (formUsePasswordSchemaMap.get(form) === response) return false
    // TODO: harden against downgrade attacks
    console.debug("Setting password schema to", response, "for", form.action)
    formUsePasswordSchemaMap.set(form, response)
    return true
}

const clientHashPassword = async (passwordSchema: PasswordSchema | string, password: string): Promise<string> => {
    if (passwordSchema === "v1") {
        // TODO: check performance on mobile
        // client-side pbkdf2 sha512, 100_000 iters, base64 encoded
        const salt = `${window.location.origin}/zaczero@osm.ng`
        let timer = performance.now()
        const hashBytes = await pbkdf2_sha512(password, salt, 100_000)
        timer = performance.now() - timer
        console.debug("pbkdf2_sha512 took", Number(timer.toFixed(1)), "ms")
        return base64Encode(hashBytes)
    }
    if (passwordSchema === "legacy") {
        // no client-side hashing
        return password
    }
    throw new Error(`Unsupported password schema: ${passwordSchema}`)
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
