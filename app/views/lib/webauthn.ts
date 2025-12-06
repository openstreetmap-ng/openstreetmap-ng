import { create, fromBinary, toBinary } from "@bufbuild/protobuf"
import {
    PasskeyAssertionSchema,
    PasskeyChallengeSchema,
    PasskeyRegistrationSchema,
} from "@lib/proto/shared_pb"
import i18next from "i18next"

/** Fetch and parse passkey challenge from server, returns challenge or error string */
const fetchPasskeyChallenge = async (formData?: FormData) => {
    const resp = await fetch("/api/web/user/login/passkey/challenge", {
        method: "POST",
        body: formData ?? null,
        priority: "high",
    })
    if (!resp.ok) return `Error: ${resp.status} ${resp.statusText}`
    return fromBinary(PasskeyChallengeSchema, new Uint8Array(await resp.arrayBuffer()))
}

/** Build credential descriptors for WebAuthn allowCredentials/excludeCredentials */
const buildCredentialDescriptors = (
    credentials: { credentialId: Uint8Array; transports: string[] }[],
) =>
    credentials.map((c) => ({
        id: c.credentialId as BufferSource,
        transports: c.transports as AuthenticatorTransport[],
        type: "public-key" as const,
    }))

/** Build assertion blob from credential response */
const buildAssertionBlob = (credential: PublicKeyCredential) => {
    const response = credential.response as AuthenticatorAssertionResponse
    const assertion = create(PasskeyAssertionSchema, {
        credentialId: new Uint8Array(credential.rawId),
        clientDataJson: new Uint8Array(response.clientDataJSON),
        authenticatorData: new Uint8Array(response.authenticatorData),
        signature: new Uint8Array(response.signature),
    })
    return new Blob([toBinary(PasskeyAssertionSchema, assertion)])
}

/** Register a new passkey, returning registration blob or error string */
export const getPasskeyRegistration = async () => {
    const challenge = await fetchPasskeyChallenge()
    if (typeof challenge === "string") return challenge

    // Convert user ID to bytes for WebAuthn
    const userIdBytes = new Uint8Array(8)
    new DataView(userIdBytes.buffer).setBigUint64(0, challenge.userId)

    let credential: PublicKeyCredential | null = null
    try {
        credential = (await navigator.credentials.create({
            publicKey: {
                challenge: challenge.challenge as BufferSource,
                rp: { name: i18next.t("project_name") },
                user: {
                    id: userIdBytes,
                    name: challenge.userEmail,
                    displayName: challenge.userDisplayName,
                },
                pubKeyCredParams: [
                    { alg: -8, type: "public-key" }, // EdDSA
                    { alg: -7, type: "public-key" }, // ES256
                ],
                excludeCredentials: buildCredentialDescriptors(challenge.credentials),
                authenticatorSelection: {
                    residentKey: "preferred",
                    userVerification: "required",
                },
                attestation: "indirect",
            },
        })) as PublicKeyCredential | null
    } catch (error) {
        console.warn("WebAuthn:", error)
    }
    if (!credential) return i18next.t("two_fa.could_not_complete_passkey_registration")

    const response = credential.response as AuthenticatorAttestationResponse
    const registration = create(PasskeyRegistrationSchema, {
        clientDataJson: new Uint8Array(response.clientDataJSON),
        attestationObject: new Uint8Array(response.attestationObject),
        transports: response.getTransports?.() ?? [],
    })
    return new Blob([toBinary(PasskeyRegistrationSchema, registration)])
}

/** Perform WebAuthn authentication, returning assertion blob or error string */
export const getPasskeyAssertion = async (
    formData?: FormData,
    userVerification: UserVerificationRequirement = "required",
) => {
    const challenge = await fetchPasskeyChallenge(formData)
    if (typeof challenge === "string") return challenge

    let credential: PublicKeyCredential | null = null
    try {
        credential = (await navigator.credentials.get({
            publicKey: {
                challenge: challenge.challenge as BufferSource,
                userVerification,
                allowCredentials: buildCredentialDescriptors(challenge.credentials),
            },
        })) as PublicKeyCredential | null
    } catch (error) {
        console.warn("WebAuthn:", error)
    }
    if (!credential) return ""

    return buildAssertionBlob(credential)
}

/**
 * Start conditional mediation for passkey autofill.
 * Resolves when user selects a passkey from autofill, or never if they don't.
 * Returns assertion blob on success, null on cancel/error.
 */
export const startConditionalMediation = async (signal: AbortSignal) => {
    console.debug("startConditionalMediation")

    // Feature detection
    if (
        !(
            PublicKeyCredential?.isConditionalMediationAvailable &&
            (await PublicKeyCredential.isConditionalMediationAvailable())
        )
    )
        return null

    // Fetch challenge
    const challenge = await fetchPasskeyChallenge()
    if (typeof challenge === "string") {
        console.error("Conditional WebAuthn:", challenge)
        return null
    }

    let credential: PublicKeyCredential | null = null
    try {
        credential = (await navigator.credentials.get({
            publicKey: {
                challenge: challenge.challenge as BufferSource,
                userVerification: "required",
            },
            mediation: "conditional",
            signal,
        })) as PublicKeyCredential | null
    } catch (error) {
        if (error.name !== "AbortError") {
            console.warn("Conditional WebAuthn:", error)
        }
    }
    if (!credential) return null

    return buildAssertionBlob(credential)
}
