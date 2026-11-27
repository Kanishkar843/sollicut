import { useEffect, useRef, useState } from 'react'
import { buildVoiceWsUrl, encodeWav16k, type AsrMode, type Command } from '../api'

export function microphoneError(error: unknown): string {
  const name = error && typeof error === 'object' && 'name' in error ? String(error.name) : ''
  if (name === 'NotAllowedError') return 'Microphone permission was denied. Allow microphone access in your browser and try again.'
  if (name === 'NotFoundError') return 'No microphone found. Connect a microphone and try again.'
  if (name === 'NotReadableError') return 'Your microphone is busy or disconnected. Check it and try again.'
  return error instanceof Error ? error.message : 'Recording was interrupted. Please try again.'
}

type StartOptions = {
  projectId?: string
  mode: AsrMode
  onStreamResult?: (command: Command) => void
  onProcessing?: () => void
  onAudio: (blob: Blob, extension: string) => void
  onError: (message: string) => void
}

const MAX_RECORD_SECONDS = 30
const SILENCE_ENDPOINT_MS = 1800

export function useRecorder() {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [rmsLevel, setRmsLevel] = useState(0)

  const alive = useRef(true)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const workletRef = useRef<AudioWorkletNode | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stoppingRef = useRef(false)
  const stopActionRef = useRef<(() => void) | null>(null)

  function cleanupAudio() {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
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
      setRecording(false)
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
      setRecording(false)
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
    setRecording(true)
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

  async function start(opts: StartOptions) {
    const { projectId, mode, onStreamResult, onProcessing, onAudio, onError } = opts
    stoppingRef.current = false
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('This browser cannot record audio. Use a current browser on localhost or HTTPS.')
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      if (!alive.current) {
        stream.getTracks().forEach((t) => t.stop())
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
      setRecording(false)
      onError(microphoneError(error))
    }
  }

  async function tryStartWorkletStream(
    stream: MediaStream,
    projectId: string,
    mode: AsrMode,
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

    try {
      audioCtx = new AudioContext()
      if (!audioCtx.audioWorklet) {
        void audioCtx.close().catch(() => {})
        return false
      }
      await audioCtx.audioWorklet.addModule('/pcm-processor.js')
      if (!alive.current) {
        void audioCtx.close().catch(() => {})
        return false
      }

      ws = new WebSocket(buildVoiceWsUrl(projectId, mode))
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
      workletRef.current = node
      source.connect(node)

      let speechDetected = false
      let silenceMs = 0

      const finalizeStop = () => {
        if (stoppingRef.current) return
        stoppingRef.current = true
        cleanupAudio()
        setRecording(false)
        if (ws && ws.readyState === WebSocket.OPEN && !wsFailed) {
          onProcessing?.()
          try {
            ws.send(JSON.stringify({ event: 'stop' }))
          } catch {
            wsFailed = true
          }
        }
        if (wsFailed && capturedPcm.length) {
          onAudio(encodeWav16k(capturedPcm), 'wav')
        }
      }

      stopActionRef.current = finalizeStop

      ws.onmessage = (ev) => {
        wsFinalized = true
        try {
          const data = JSON.parse(String(ev.data)) as Command & { error?: string }
          if (data.error) {
            onError(data.error)
          } else {
            onStreamResult(data)
          }
        } catch {
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
          onError('Lost connection to the speech stream. Please try again.')
        }
      }

      ws.onclose = () => {
        if (!wsFinalized && stoppingRef.current && wsFailed && capturedPcm.length) {
          onAudio(encodeWav16k(capturedPcm), 'wav')
        }
        wsRef.current = null
      }

      node.port.onmessage = (ev: MessageEvent<{ pcm: ArrayBuffer; rms: number }>) => {
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

      setRecording(true)
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

  return { recording, seconds, rmsLevel, start, stop }
}
