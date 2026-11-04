export const REQUEST_BODY_MAX_SIZE = 8
export const StandardFeedbackDetail_Severity = {}
export const assertExists = (value: unknown) => {
  if (value == null) throw new Error("Missing value")
}
export const assertFalse = (value: unknown) => {
  if (value) throw new Error("Unexpected value")
}
export const unreachable = () => {
  throw new Error("Unreachable")
}
export const parseMediaType = () => ["application/json"]
export const addMapLayer = () => {},
  removeMapLayer = () => {}
export const createPasswordTransformState = () => ({
  collect: async () => ({}),
  tryUpdateSchema: () => false,
})
export const connectErrorToMessage = (error: Error) => error.message
export const connectErrorToStandardFeedback = () => null
export const fromBinaryValid = () => ({})
export class ConnectError extends Error {
  static from(error: Error) {
    return error
  }
}
export const rpcUnary = () => async (request: { file: Uint8Array }) => {
  const state = window as any
  state.rpcCalls++
  state.lastBytes = Array.from(request.file)
  return {}
}
export const t = (key: string) =>
  key === "validation.file_too_large"
    ? "This file is too large. Please choose a smaller file."
    : key
