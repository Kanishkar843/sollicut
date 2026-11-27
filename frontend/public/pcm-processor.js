/**
 * pcm-processor.js — PcmProcessor AudioWorkletProcessor (V2)
 *
 * Phase 1 upgrade:
 *  - Kaiser-windowed FIR polyphase resampler (replaces linear interpolation)
 *    Handles: 44100→16000, 48000→16000, 16000→16000 (passthrough)
 *    β = 5.65 (Kaiser), 64 taps per polyphase subfilter, L=147 phases
 *  - Flush state: on 'flush' control message, pads remainder with zeros and
 *    sends final chunk flagged {is_flush: true}, then sends 'flushed' reply
 *  - Diagnostics per chunk: input_rate, rms, peak, clip_ratio
 *
 * Message protocol (port.postMessage):
 *   Normal chunk : { pcm: Int16Array.buffer, rms, peak, clip_ratio, seq, is_flush: false }
 *   Flush chunk  : { pcm: Int16Array.buffer, rms, peak, clip_ratio, seq, is_flush: true }
 *   After flush  : { type: 'flushed', seq }
 *
 * Control messages (port.onmessage):
 *   { type: 'flush' } — flush remaining buffer and report 'flushed'
 */

// ---------------------------------------------------------------------------
// Kaiser-windowed sinc FIR polyphase resampler
// ---------------------------------------------------------------------------

const TARGET_RATE = 16000
const CHUNK_SAMPLES = 1600 // 100 ms at 16 kHz

/**
 * Compute modified Bessel function I0(x) via power series (accurate for β≤10)
 */
function besselI0(x) {
  let sum = 1.0
  let term = 1.0
  const half_x = x / 2.0
  for (let k = 1; k <= 30; k++) {
    term *= (half_x / k) * (half_x / k)
    sum += term
    if (term < sum * 1e-10) break
  }
  return sum
}

/**
 * Build a Kaiser-windowed sinc lowpass filter.
 * @param {number} numTaps — total taps (odd recommended)
 * @param {number} cutoff  — normalized cutoff (0..0.5), fc/fs
 * @param {number} beta    — Kaiser shape factor (5.65 ≈ -60 dB stopband)
 * @returns {Float64Array}
 */
function kaiserSincFilter(numTaps, cutoff, beta) {
  const h = new Float64Array(numTaps)
  const M = numTaps - 1
  const halfM = M / 2
  const i0Beta = besselI0(beta)
  for (let n = 0; n < numTaps; n++) {
    const x = n - halfM
    // Kaiser window
    const r = 1 - ((x / halfM) * (x / halfM))
    const w = besselI0(beta * Math.sqrt(Math.max(0, r))) / i0Beta
    // Sinc
    const s = x === 0 ? 2 * cutoff : Math.sin(2 * Math.PI * cutoff * x) / (Math.PI * x)
    h[n] = w * s
  }
  return h
}

/**
 * Split prototype filter h[] into L polyphase subfilters, each of length P.
 * subfilter[p][k] = h[p + k*L]
 * @param {Float64Array} h
 * @param {number} L — number of polyphase phases (== up-sampling factor)
 * @param {number} P — subfilter length (taps per phase)
 * @returns {Float64Array[]}
 */
function buildPolyphaseBank(h, L, P) {
  const bank = []
  for (let p = 0; p < L; p++) {
    const sub = new Float64Array(P)
    for (let k = 0; k < P; k++) {
      const idx = p + k * L
      sub[k] = idx < h.length ? h[idx] * L : 0
    }
    bank.push(sub)
  }
  return bank
}

// ---------------------------------------------------------------------------
// Rational approximation gcd helper
// ---------------------------------------------------------------------------
function gcd(a, b) { return b === 0 ? a : gcd(b, a % b) }

// ---------------------------------------------------------------------------
// PcmProcessor
// ---------------------------------------------------------------------------
class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super()

    // Resampler configuration (lazy-init on first process call)
    this._initialized = false
    this._passthrough = false
    this._L = 1          // up-sampling factor
    this._M = 1          // down-sampling factor
    this._bank = null    // polyphase filter bank
    this._P = 0          // taps per polyphase filter
    this._state = null   // filter state (input history), length P-1
    this._phase = 0      // current polyphase index
    this._inFrac = 0     // fractional input position accumulator
    this._linearMode = false
    this._linPrev = 0
    this._linHasPrev = false
    this._linPos = 0

    this._buffer = new Int16Array(CHUNK_SAMPLES)
    this._offset = 0
    this._seq = 0
    this._flushing = false
    this._inputSampleRate = 0

    this.port.onmessage = (ev) => {
      if (!ev.data) return
      if (ev.data.type === 'flush') {
        this._flushing = true
      } else if (ev.data.type === 'config' && ev.data.resampler === 'linear') {
        this._linearMode = true
      }
    }
  }

  _initResampler(inputRate) {
    this._inputSampleRate = inputRate
    const g = gcd(TARGET_RATE, inputRate)
    const L = TARGET_RATE / g   // up factor
    const M = inputRate / g     // down factor

    if (L === M) {
      // Exact ratio 1:1 — passthrough
      this._passthrough = true
      this._initialized = true
      return
    }

    this._L = L
    this._M = M
    this._passthrough = false

    // Cutoff = 0.5/max(L,M) — anti-alias for the dominant decimation
    const cutoff = 0.5 / Math.max(L, M)
    // Keep taps per polyphase subfilter small but sufficient (≥ 4 periods of cutoff)
    // For 44100→16000: L=160, M=441, P=8 → 160*8=1280 total taps  (sub-ms latency)
    // For 48000→16000: L=1,   M=3,   P=64 → 64 total taps (passthrough Lp filter)
    const P = Math.min(64, Math.max(8, Math.round(4 / cutoff / L)))
    this._P = P

    const numTaps = L * P
    const beta = 5.65
    const h = kaiserSincFilter(numTaps, cutoff, beta)
    this._bank = buildPolyphaseBank(h, L, P)
    this._state = new Float64Array(P - 1)  // ring of past input samples
    this._phase = 0
    this._inFrac = 0
    this._initialized = true
  }

  /**
   * Resample one input float32 channel → push output samples to _pushSample
   * Uses rational polyphase (L:M) with ring-buffer state.
   */
  _resampleChannel(channel) {
    if (this._passthrough) {
      for (let i = 0; i < channel.length; i++) {
        this._pushSample(channel[i])
      }
      return
    }

    if (this._linearMode) {
      const ratio = this._inputSampleRate / TARGET_RATE
      if (!this._linHasPrev) {
        this._linPrev = channel[0]
        this._linHasPrev = true
      }
      let pos = this._linPos
      while (pos < channel.length) {
        const idx = Math.floor(pos)
        const frac = pos - idx
        const s0 = idx === 0 ? this._linPrev : channel[idx - 1]
        const s1 = channel[idx]
        this._pushSample(s0 + (s1 - s0) * frac)
        pos += ratio
      }
      this._linPrev = channel[channel.length - 1]
      this._linPos = pos - channel.length
      return
    }

    const L = this._L
    const M = this._M
    const bank = this._bank
    const P = this._P
    const state = this._state

    // Append new input samples to state ring and process
    // We iterate over input samples; for each input sample we append to history
    // and then output any output samples whose next input pointer is now available.
    for (let i = 0; i < channel.length; i++) {
      // Shift state left and push new sample at end
      for (let k = 0; k < P - 1; k++) state[k] = state[k + 1]
      state[P - 1] = channel[i]

      // Advance inFrac by L; output a sample for each M accumulated
      this._inFrac += L
      while (this._inFrac >= M) {
        this._inFrac -= M
        // phase index = round((inFrac / M) * L)  — but we can track it directly
        const sub = bank[this._phase]
        let acc = 0
        for (let k = 0; k < P; k++) acc += state[k] * sub[k]
        this._pushSample(acc)
        this._phase = (this._phase + M) % L
      }
    }
  }

  _pushSample(sample) {
    const clamped = Math.max(-1, Math.min(1, sample))
    this._buffer[this._offset++] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff
    if (this._offset >= CHUNK_SAMPLES) {
      this._emitChunk(false)
    }
  }

  _emitChunk(isFinal) {
    const count = this._offset
    if (count === 0 && !isFinal) return

    // Fill remainder with zeros for flush chunk
    for (let i = count; i < CHUNK_SAMPLES; i++) this._buffer[i] = 0

    let sumSq = 0
    let peak = 0
    let clipCount = 0
    for (let i = 0; i < count || (isFinal && i < CHUNK_SAMPLES); i++) {
      const idx = Math.min(i, CHUNK_SAMPLES - 1)
      const norm = this._buffer[idx] / 32768
      sumSq += norm * norm
      const abs = Math.abs(norm)
      if (abs > peak) peak = abs
      if (abs >= 0.99) clipCount++
    }
    const effectiveLen = isFinal ? Math.max(1, count) : CHUNK_SAMPLES
    const rms = Math.sqrt(sumSq / effectiveLen)
    const clip_ratio = clipCount / effectiveLen

    const out = this._buffer.slice(0)
    this.port.postMessage(
      {
        pcm: out.buffer,
        rms,
        peak,
        clip_ratio,
        seq: this._seq++,
        is_flush: isFinal,
        input_rate: this._inputSampleRate,
      },
      [out.buffer],
    )
    this._offset = 0
  }

  process(inputs) {
    const input = inputs[0]

    if (this._flushing) {
      // Flush: drain remaining buffered output samples, then notify
      if (this._offset > 0) {
        this._emitChunk(true)
      }
      this.port.postMessage({ type: 'flushed', seq: this._seq })
      this._flushing = false
      return false // stop processing
    }

    if (!input || !input[0] || input[0].length === 0) {
      return true
    }

    const channel = input[0]

    if (!this._initialized) {
      this._initResampler(sampleRate)
    }

    this._resampleChannel(channel)
    return true
  }
}

registerProcessor('pcm-processor', PcmProcessor)
