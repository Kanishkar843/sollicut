import { useEffect, useRef, useState } from 'react'
import { buildVoiceWsUrl, encodeWav16k, type AsrMode, type Command } from '../api'

export function microphoneError(error: unknown): string {
  const name = error && typeof error === 'object' && 'name' in error ? String(error.name) : ''
  if (name === 'NotAllowedError') return 'Microphone permission was denied. Allow microphone access in your browser and try again.'
  if (name === 'NotFoundError') return 'No microphone found. Connect a microphone and try again.'
  if (name === 'NotReadableError') return 'Your microphone is busy or disconnected. Check it and try again.'
  return error instanceof Error ? error.message : 'Recording was interrupted. Please try again.'
}

/** V2 lifecycle states visible to consumers */
export type RecorderState =
  | 'idle'
  | 'initializing'
  | 'recording'
  | 'stopping'
  | 'flushing'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled'

type SpeechRecognitionAlternativeLike = { transcript: string }
type SpeechRecognitionResultLike = { 0: SpeechRecognitionAlternativeLike; isFinal: boolean; length: number }
type SpeechRecognitionEventLike = { resultIndex: number; results: ArrayLike<SpeechRecognitionResultLike> }
type SpeechRecognitionInstanceLike = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: SpeechRecognitionEventLike) => void) | null
  onerror: ((e: { error?: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort?: () => void
}
type SpeechRecognitionCtorLike = new () => SpeechRecognitionInstanceLike

function getSpeechRecognitionCtor(): SpeechRecognitionCtorLike | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as Record<string, unknown>
  const ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition
  return typeof ctor === 'function' ? (ctor as SpeechRecognitionCtorLike) : null
}

export function hasBrowserSpeechRecognition(): boolean {
  return getSpeechRecognitionCtor() !== null
}

type StartOptions = {
  projectId?: string
  mode: AsrMode
  previewOnly?: boolean
  resampler?: 'linear' | 'fir_kaiser'
  deviceId?: string
  preferBrowserSpeech?: boolean
  onBrowserTranscript?: (transcript: string) => void
  onStreamResult?: (command: Command) => void
  onProcessing?: () => void
  onAudio: (blob: Blob, extension: string) => void
  onError: (message: string) => void
}

const MAX_RECORD_SECONDS = 30
const SILENCE_ENDPOINT_MS = 1800
const FLUSH_ACK_TIMEOUT_MS = 1500

export function useRecorder() {
  const [recorderState, setRecorderState] = useState<RecorderState>('idle')
  const [seconds, setSeconds] = useState(0)
  const [rmsLevel, setRmsLevel] = useState(0)

  // Derived boolean for compatibility with existing callers
  const recording = recorderState === 'recording'

  const alive = useRef(true)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const recognitionRef = useRef<SpeechRecognitionInstanceLike | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stoppingRef = useRef(false)
  const stopActionRef = useRef<(() => void) | null>(null)

  function cleanupAudio() {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    try {
      recognitionRef.current?.abort?.()
    } catch {
      // ignore
    }
    recognitionRef.current = null
    try {
      workletRef.current?.disconnect()
    } catch {
      // ignore
    }
    workletRef.current = null
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      void audioCtxRef.current.close().catch(() => {})
    }
    audioCtxRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setRmsLevel(0)
  }

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify({ event: 'cancel' }))
        } catch {
          // ignore
        }
        wsRef.current.close()
      }
      wsRef.current = null
      if (recorderRef.current?.state === 'recording') {
        recorderRef.current.stop()
      }
      cleanupAudio()
    }
  }, [])

  function startMediaRecorderFallback(
    stream: MediaStream,
    onAudio: (blob: Blob, extension: string) => void,
    onError: (message: string) => void,
  ) {
    if (typeof MediaRecorder === 'undefined') {
      throw new Error('This browser cannot record audio. Use a current browser on localhost or HTTPS.')
    }
    const type = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm'].find((t) =>
      MediaRecorder.isTypeSupported(t),
    )
    if (!type) {
      throw new Error('No supported microphone recording format. Try Chrome, Edge, Firefox or Safari.')
    }
    const chunks: BlobPart[] = []
    const r = new MediaRecorder(stream, { mimeType: type })
    recorderRef.current = r
    let interrupted = false
    r.ondataavailable = (e) => {
      if (e.data.size) chunks.push(e.data)
    }
    r.onerror = () => {
      interrupted = true
      onError('Recording was interrupted. Please record again.')
      cleanupAudio()
      setRecorderState('failed')
    }
    stream.getAudioTracks()[0].onended = () => {
      if (r.state === 'recording') {
        interrupted = true
        r.stop()
        onError('The microphone disconnected. Please record again.')
      }
    }
    r.onstop = () => {
      cleanupAudio()
      if (!alive.current) return
      setRecorderState(interrupted ? 'failed' : 'completed')
      if (interrupted) return
      const blob = new Blob(chunks, { type: r.mimeType })
      if (!blob.size) {
        onError('The recording is empty. Please try again.')
        return
      }
      onAudio(blob, type.includes('mp4') ? 'mp4' : type.includes('ogg') ? 'ogg' : 'webm')
    }
    stopActionRef.current = () => {
      if (r.state === 'recording') r.stop()
    }
    r.start(250)
    setRecorderState('recording')
    setSeconds(0)
    const began = Date.now()
    timerRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - began) / 1000)
      setSeconds(elapsed)
      if (elapsed >= MAX_RECORD_SECONDS - 1 && r.state === 'recording') {
        r.stop()
      }
    }, 200)
  }

  function startBrowserRecognition(opts: StartOptions): boolean {
    const Ctor = getSpeechRecognitionCtor()
    if (!Ctor) return false
    try {
      const rec = new Ctor()
      rec.lang = opts.mode === 'ta' ? 'ta-IN' : 'en-IN'
      rec.interimResults = true
      rec.continuous = true
      let finalText = ''
      let latestText = ''
      let errored = false

      rec.onresult = (ev) => {
        let interim = ''
        for (let i = ev.resultIndex; i < ev.results.length; i += 1) {
          const item = ev.results[i]
          const chunk = item[0]?.transcript ?? ''
          if (item.isFinal) {
            finalText = `${finalText} ${chunk}`.trim()
          } else {
            interim = `${interim} ${chunk}`.trim()
          }
        }
        latestText = `${finalText} ${interim}`.trim()
      }

      rec.onerror = (ev) => {
        if (ev?.error === 'aborted') return
        errored = true
        cleanupAudio()
        if (!alive.current) return
        setRecorderState('failed')
        if (ev?.error === 'not-allowed' || ev?.error === 'service-not-allowed') {
          opts.onError('Microphone permission was denied. Allow microphone access in your browser and try again.')
        } else if (ev?.error === 'no-speech') {
          opts.onError('No speech detected. Speak clearly and try again.')
        } else if (ev?.error === 'network') {
          opts.onError('Browser voice recognition needs an internet connection. Type your command below instead.')
        } else {
          opts.onError('Voice recognition could not hear you. Speak again or type your command below.')
        }
      }

      rec.onend = () => {
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        recognitionRef.current = null
        if (!alive.current || errored) return
        const spoken = (finalText || latestText).trim()
        if (!spoken) {
          setRecorderState('failed')
          opts.onError('No speech detected. Tap the mic and speak clearly, or type your command below.')
          return
        }
        setRecorderState('completed')
        opts.onBrowserTranscript?.(spoken)
      }

      recognitionRef.current = rec
      stopActionRef.current = () => {
        setRecorderState('stopping')
        try {
          rec.stop()
        } catch {
          cleanupAudio()
        }
      }

      setRecorderState('recording')
      setSeconds(0)
      const began = Date.now()
      timerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - began) / 1000)
        setSeconds(elapsed)
        if (elapsed >= MAX_RECORD_SECONDS - 1) {
          try {
            rec.stop()
          } catch {
            // ignore
          }
        }
      }, 200)
      rec.start()
      return true
    } catch {
      recognitionRef.current = null
      return false
    }
  }

  async function start(opts: StartOptions) {
    const { projectId, mode, previewOnly = false, resampler = 'fir_kaiser', deviceId, preferBrowserSpeech = false, onBrowserTranscript, onStreamResult, onProcessing, onAudio, onError } = opts
    stoppingRef.current = false
    if (preferBrowserSpeech) {
      if (startBrowserRecognition(opts)) return
      setRecorderState('failed')
      onError('Speech recognition is not available in this browser. Type your command below or use Chrome/Edge.')
      return
    }
    setRecorderState('initializing')
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('This browser cannot record audio. Use a current browser on localhost or HTTPS.')
      }
      const audioConstraints: MediaTrackConstraints = {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      }
      if (deviceId) {
        audioConstraints.deviceId = { exact: deviceId }
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints })
      if (!alive.current) {
        stream.getTracks().forEach((t) => t.stop())
        setRecorderState('cancelled')
        return
      }
      streamRef.current = stream

      const canWorkletStream =
        Boolean(projectId && onStreamResult) &&
        typeof AudioContext !== 'undefined' &&
        typeof WebSocket !== 'undefined'

      if (canWorkletStream && projectId && onStreamResult) {
        const startedStream = await tryStartWorkletStream(
          stream,
          projectId,
          mode,
          previewOnly,
          resampler,
          onStreamResult,
          onProcessing,
          onAudio,
          onError,
        )
        if (startedStream) return
      }

      startMediaRecorderFallback(stream, onAudio, onError)
    } catch (error) {
      cleanupAudio()
      setRecorderState('failed')
      onError(microphoneError(error))
    }
  }

  async function tryStartWorkletStream(
    stream: MediaStream,
    projectId: string,
    mode: AsrMode,
    previewOnly: boolean,
    resampler: 'linear' | 'fir_kaiser',
    onStreamResult: (command: Command) => void,
    onProcessing: (() => void) | undefined,
    onAudio: (blob: Blob, extension: string) => void,
    onError: (message: string) => void,
  ): Promise<boolean> {
    let audioCtx: AudioContext | null = null
    let ws: WebSocket | null = null
    const capturedPcm: Int16Array[] = []
    let wsFailed = false
    let wsFinalized = false
    let flushAckReceived = false

    try {
      audioCtx = new AudioContext()
      if (audioCtx.state === 'suspended' && typeof audioCtx.resume === 'function') {
        await audioCtx.resume()
      }
      if (!audioCtx.audioWorklet) {
        void audioCtx.close().catch(() => {})
        return false
      }
      await audioCtx.audioWorklet.addModule('/pcm-processor.js?v=2')
      if (!alive.current) {
        void audioCtx.close().catch(() => {})
        setRecorderState('cancelled')
        return false
      }

      ws = new WebSocket(buildVoiceWsUrl(projectId, mode, crypto.randomUUID(), !previewOnly))
      ws.binaryType = 'arraybuffer'
      await new Promise<void>((resolve, reject) => {
        if (!ws) return reject(new Error('No WebSocket'))
        const timeout = setTimeout(() => reject(new Error('WebSocket connection timeout')), 2500)
        ws.onopen = () => {
          clearTimeout(timeout)
          resolve()
        }
        ws.onerror = () => {
          clearTimeout(timeout)
          reject(new Error('WebSocket connection failed'))
        }
      })

      audioCtxRef.current = audioCtx
      wsRef.current = ws
      const source = audioCtx.createMediaStreamSource(stream)
      const node = new AudioWorkletNode(audioCtx, 'pcm-processor')
      if (resampler === 'linear') {
        node.port.postMessage({ type: 'config', resampler: 'linear' })
      }
      workletRef.current = node
      source.connect(node)

      let speechDetected = false
      let silenceMs = 0

      /**
       * Phase 1: Send 'flush' to worklet, wait for 'flushed' ack before
       * disconnecting AudioContext and sending 'stop' to WS.
       */
      const finalizeStop = () => {
        if (stoppingRef.current) return
        stoppingRef.current = true
        setRecorderState('stopping')

        // Stop the timer and mic tracks so the browser shows mic as inactive
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        streamRef.current?.getTracks().forEach((t) => t.stop())
        streamRef.current = null

        // Signal worklet to flush its partial buffer
        setRecorderState('flushing')
        node.port.postMessage({ type: 'flush' })

        // Guard: if worklet flush ack doesn't arrive within timeout, proceed anyway
        const flushTimeout = setTimeout(() => {
          if (!flushAckReceived) {
            flushAckReceived = true
            sendStop()
          }
        }, FLUSH_ACK_TIMEOUT_MS)

        node.port.onmessage = (ev: MessageEvent) => {
          const d = ev.data as Record<string, unknown>
          if (d.type === 'flushed') {
            clearTimeout(flushTimeout)
            flushAckReceived = true
            sendStop()
            return
          }
          // Handle any final PCM chunk from flush
          if (d.pcm) {
            const { pcm, rms } = d as { pcm: ArrayBuffer; rms: number }
            capturedPcm.push(new Int16Array(pcm.slice(0)))
            if (ws && ws.readyState === WebSocket.OPEN && !wsFailed) {
              ws.send(pcm)
            }
            setRmsLevel(rms)
          }
        }

        function sendStop() {
          // Now safe to close AudioContext (all PCM sent)
          try {
            workletRef.current?.disconnect()
          } catch {
            // ignore
          }
          workletRef.current = null
          if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
            void audioCtxRef.current.close().catch(() => {})
          }
          audioCtxRef.current = null
          setRmsLevel(0)

          if (ws && ws.readyState === WebSocket.OPEN && !wsFailed) {
            setRecorderState('processing')
            onProcessing?.()
            try {
              const stopPayload: Record<string, unknown> = { event: 'stop', command_id: crypto.randomUUID() }
              if (previewOnly) stopPayload.preview = true
              ws.send(JSON.stringify(stopPayload))
            } catch {
              wsFailed = true
            }
          }
          if (wsFailed && capturedPcm.length) {
            setRecorderState('completed')
            onAudio(encodeWav16k(capturedPcm), 'wav')
          }
        }
      }

      stopActionRef.current = finalizeStop

      ws.onmessage = (ev) => {
        wsFinalized = true
        try {
          const data = JSON.parse(String(ev.data)) as Command & { error?: string }
          if (data.error) {
            setRecorderState('failed')
            onError(data.error)
          } else {
            setRecorderState('completed')
            onStreamResult(data)
          }
        } catch {
          setRecorderState('failed')
          onError('Received an unreadable speech response from the server.')
        } finally {
          ws?.close()
          wsRef.current = null
        }
      }

      ws.onerror = () => {
        if (!wsFinalized && !stoppingRef.current) {
          wsFailed = true
        } else if (!wsFinalized) {
          setRecorderState('failed')
          onError('Lost connection to the speech stream. Please try again.')
        }
      }

      ws.onclose = () => {
        if (!wsFinalized && stoppingRef.current && wsFailed && capturedPcm.length) {
          setRecorderState('completed')
          onAudio(encodeWav16k(capturedPcm), 'wav')
        }
        wsRef.current = null
      }

      node.port.onmessage = (ev: MessageEvent<{ pcm: ArrayBuffer; rms: number; peak?: number; clip_ratio?: number; seq?: number; is_flush?: boolean }>) => {
        if (stoppingRef.current) return
        const { pcm, rms } = ev.data
        setRmsLevel(rms)
        capturedPcm.push(new Int16Array(pcm.slice(0)))
        if (ws && ws.readyState === WebSocket.OPEN && !wsFailed) {
          ws.send(pcm)
        }
        if (rms >= 0.015) {
          speechDetected = true
          silenceMs = 0
        } else if (speechDetected && rms < 0.006) {
          silenceMs += 100
          if (silenceMs >= SILENCE_ENDPOINT_MS) {
            finalizeStop()
          }
        }
      }

      stream.getAudioTracks()[0].onended = () => {
        if (!stoppingRef.current) {
          onError('The microphone disconnected. Please record again.')
          finalizeStop()
        }
      }

      setRecorderState('recording')
      setSeconds(0)
      const began = Date.now()
      timerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - began) / 1000)
        setSeconds(elapsed)
        if (elapsed >= MAX_RECORD_SECONDS - 1) {
          finalizeStop()
        }
      }, 200)
      return true
    } catch {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
      if (audioCtx && audioCtx.state !== 'closed') {
        void audioCtx.close().catch(() => {})
      }
      return false
    }
  }

  function stop() {
    stopActionRef.current?.()
  }

  return { recording, recorderState, seconds, rmsLevel, start, stop }
}
