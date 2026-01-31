// Enable JSON.stringify for BigInt
// @ts-expect-error - extending built-in prototype
BigInt.prototype.toJSON ??= function toJSON() {
  return this.toString()
}

window.requestAnimationFrame ??= (callback: FrameRequestCallback) =>
  window.setTimeout(() => callback(performance.now()), 30)

window.cancelAnimationFrame ??= window.clearTimeout

window.requestIdleCallback ??= (callback, _options) =>
  window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 0 }), 0)

window.cancelIdleCallback ??= window.clearTimeout
