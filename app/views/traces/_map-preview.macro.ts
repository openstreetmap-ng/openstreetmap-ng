const DASH_A = 4
const DASH_B = 3
const DASH_LENGTH = DASH_A + DASH_B
const FRAME_COUNT = 192

const getDash = (offset: number) =>
  offset <= DASH_B
    ? [offset, DASH_A, DASH_B - offset]
    : [0, offset - DASH_B, DASH_B, DASH_LENGTH - offset]

export const getAntDashFrames = () =>
  Array.from({ length: FRAME_COUNT }, (_, index) =>
    getDash((index / FRAME_COUNT) * DASH_LENGTH),
  )
