// oxlint-disable typescript/no-unnecessary-condition
import { create } from "@bufbuild/protobuf"
import {
  CredentialsSchema,
  PasskeyAssertionSchema,
  PasskeyRegistrationSchema,
  Service,
} from "@lib/proto/auth_pb"
import { connectErrorToMessage, type LooseMessageInitShape, rpcUnary } from "@lib/rpc"
import { t } from "i18next"

type PasskeyChallengeCredentials = LooseMessageInitShape<typeof CredentialsSchema>

const fetchPasskeyChallenge = async (credentials?: PasskeyChallengeCredentials) => {
  try {
    const response = await rpcUnary(Service.method.getPasskeyChallenge)({
      credentials,
    })
    return response.challenge
  } catch (error) {
    throw new Error(connectErrorToMessage(error), { cause: error })
  }
}

const buildCredentialDescriptors = (
  credentials: { credentialId: Uint8Array; transports: string[] }[],
) =>
  credentials.map((c) => ({
    id: c.credentialId as BufferSource,
    transports: c.transports as AuthenticatorTransport[],
    type: "public-key" as const,
  }))

const buildAssertion = (credential: PublicKeyCredential) => {
  const response = credential.response as AuthenticatorAssertionResponse
  return create(PasskeyAssertionSchema, {
    credentialId: new Uint8Array(credential.rawId),
    clientDataJson: new Uint8Array(response.clientDataJSON),
    authenticatorData: new Uint8Array(response.authenticatorData),
    signature: new Uint8Array(response.signature),
  })
}

export const getPasskeyRegistration = async () => {
  const challenge = await fetchPasskeyChallenge()

  const userIdBytes = new Uint8Array(8)
  new DataView(userIdBytes.buffer).setBigUint64(0, challenge.userId)

  let credential: PublicKeyCredential | null = null
  try {
    credential = (await navigator.credentials.create({
      publicKey: {
        challenge: challenge.challenge as BufferSource,
        rp: { name: t("project_name") },
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
    console.warn("WebAuthn: Registration failed", error)
  }
  if (!credential) throw new Error(t("two_fa.could_not_complete_passkey_registration"))

  const response = credential.response as AuthenticatorAttestationResponse
  const registration = create(PasskeyRegistrationSchema, {
    clientDataJson: new Uint8Array(response.clientDataJSON),
    attestationObject: new Uint8Array(response.attestationObject),
    // oxlint-disable-next-line typescript/no-unnecessary-condition
    transports: response.getTransports?.() ?? [],
  })
  return registration
}

export const getPasskeyAssertion = async (
  credentials: PasskeyChallengeCredentials | undefined,
  userVerification: UserVerificationRequirement = "required",
) => {
  const challenge = await fetchPasskeyChallenge(credentials)

  try {
    const credential = (await navigator.credentials.get({
      publicKey: {
        challenge: challenge.challenge as BufferSource,
        userVerification,
        allowCredentials: buildCredentialDescriptors(challenge.credentials),
      },
    })) as PublicKeyCredential | null

    return credential ? buildAssertion(credential) : undefined
  } catch (error) {
    console.warn("WebAuthn: Assertion failed", error)
    return
  }
}

export const startConditionalMediation = async (signal: AbortSignal) => {
  console.debug("WebAuthn: Starting conditional mediation")

  if (
    !(
      PublicKeyCredential?.isConditionalMediationAvailable &&
      (await PublicKeyCredential.isConditionalMediationAvailable())
    )
  )
    return

  let challenge
  try {
    challenge = await fetchPasskeyChallenge()
  } catch (error) {
    console.error("WebAuthn: Conditional mediation challenge failed", error)
    return
  }

  try {
    const credential = (await navigator.credentials.get({
      publicKey: {
        challenge: challenge.challenge as BufferSource,
        userVerification: "required",
      },
      mediation: "conditional",
      signal,
    })) as PublicKeyCredential | null
    return credential ? buildAssertion(credential) : undefined
  } catch (error) {
    if (error.name !== "AbortError") {
      console.warn("WebAuthn: Conditional mediation error", error)
    }
    return
  }
}
