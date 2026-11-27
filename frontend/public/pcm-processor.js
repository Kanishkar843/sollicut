class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._targetRate = 16000
    this._chunkSamples = 1600 // ~100ms at 16 kHz
    this._buffer = new Int16Array(this._chunkSamples)
    this._offset = 0
    this._phase = 0
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || !input[0] || input[0].length === 0) {
      return true
    }
    const channel = input[0]
    const ratio = sampleRate / this._targetRate

    if (Math.abs(ratio - 1) < 1e-4) {
      for (let i = 0; i < channel.length; i++) {
        this._pushSample(channel[i])
      }
    } else {
      let pos = this._phase
      while (pos < channel.length) {
        const idx = Math.floor(pos)
        const frac = pos - idx
        const s0 = channel[idx]
        const s1 = idx + 1 < channel.length ? channel[idx + 1] : s0
        this._pushSample(s0 + (s1 - s0) * frac)
        pos += ratio
      }
      this._phase = pos - channel.length
    }
    return true
  }

  _pushSample(sample) {
    const clamped = Math.max(-1, Math.min(1, sample))
    this._buffer[this._offset++] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff
    if (this._offset >= this._chunkSamples) {
      let sumSq = 0
      for (let i = 0; i < this._chunkSamples; i++) {
        const norm = this._buffer[i] / 32768
        sumSq += norm * norm
      }
      const rms = Math.sqrt(sumSq / this._chunkSamples)
      const out = this._buffer.slice(0)
      this.port.postMessage({ pcm: out.buffer, rms }, [out.buffer])
      this._offset = 0
    }
  }
}

registerProcessor('pcm-processor', PcmProcessor)
