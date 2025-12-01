import { fromBinary } from "@bufbuild/protobuf"
import { type PasskeyChallenge, PasskeyChallengeSchema } from "./proto/shared_pb"

/** Fetch and parse passkey challenge from server. Returns challenge or error string. */
export const fetchPasskeyChallenge = async (
    formData?: FormData,
): Promise<PasskeyChallenge | string> => {
    const resp = await fetch("/api/web/user/login/passkey/challenge", {
        method: "POST",
        body: formData,
    })
    if (!resp.ok) return `Error: ${resp.status} ${resp.statusText}`
    return fromBinary(PasskeyChallengeSchema, new Uint8Array(await resp.arrayBuffer()))
}

/** Build credential descriptors for WebAuthn allowCredentials/excludeCredentials. */
export const buildCredentialDescriptors = (
    credentials: { credentialId: Uint8Array; transports: string[] }[],
): PublicKeyCredentialDescriptor[] =>
    credentials.map((c) => ({
        id: c.credentialId as BufferSource,
        transports: c.transports as AuthenticatorTransport[],
        type: "public-key" as const,
    }))
