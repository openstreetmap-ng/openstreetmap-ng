// Enable JSON.stringify for BigInt
// @ts-expect-error - extending built-in prototype
BigInt.prototype.toJSON ??= function toJSON() {
  return this.toString()
}

// oxlint-disable-next-line typescript/no-unnecessary-condition
window.requestAnimationFrame ??= (callback: FrameRequestCallback) =>
  window.setTimeout(() => callback(performance.now()), 30)

// oxlint-disable-next-line typescript/no-unnecessary-condition
window.cancelAnimationFrame ??= window.clearTimeout

// oxlint-disable-next-line typescript/no-unnecessary-condition
window.requestIdleCallback ??= (callback, _options) =>
  window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 0 }), 0)

// oxlint-disable-next-line typescript/no-unnecessary-condition
window.cancelIdleCallback ??= window.clearTimeout
