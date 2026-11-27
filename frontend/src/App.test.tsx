import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App, { validateMedia } from './App'
import Landing from './Landing'
import VoiceButton, { microphoneError } from './VoiceButton'
import { TranscriptReview } from './components/voice/TranscriptReview'
import { MicrophoneSettings } from './components/voice/MicrophoneSettings'
import { operationLabel, type Command } from './api'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  localStorage.clear()
})

test('photo and video formats, sizes and count are checked before uploading', () => {
  expect(validateMedia([new File(['data'], 'x.exe', { type: 'application/octet-stream' })], 0)).toMatch('JPEG')
  expect(validateMedia([new File(['data'], 'x.png', { type: 'image/png' })], 5)).toMatch('5')
  expect(validateMedia([new File(['data'], 'x.png', { type: 'image/png' })], 0)).toBeNull()
  expect(validateMedia([new File(['data'], 'clip.mp4', { type: 'video/mp4' })], 0)).toBeNull()
})

test('permission and missing microphone errors are useful', () => {
  expect(microphoneError(new DOMException('denied', 'NotAllowedError'))).toMatch('permission')
  expect(microphoneError(new DOMException('absent', 'NotFoundError'))).toMatch('No microphone')
})

test('operation cards display extracted fields', () => {
  expect(operationLabel({ id: 'x', type: 'set_text_overlay', parameters: { text: '25 percent offer', placement: 'end_card' } })).toBe('“25 percent offer” · at the end')
  expect(operationLabel({ id: 'y', type: 'set_music_volume', parameters: { direction: 'decrease' } })).toBe('Softer background music')
  expect(operationLabel({ id: 'z', type: 'trim_clip', parameters: { clip_index: 1 } })).toBe('Trimmed clip 1')
})

test('microphone permission rejection reaches visible error handler', async () => {
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockRejectedValue(new DOMException('denied', 'NotAllowedError')) },
  })
  vi.stubGlobal('MediaRecorder', { isTypeSupported: () => true })
  const error = vi.fn()
  render(<VoiceButton disabled={false} onAudio={vi.fn()} onError={error} />)
  fireEvent.click(screen.getByRole('button', { name: 'Start recording' }))
  await waitFor(() => expect(error).toHaveBeenCalledWith(expect.stringContaining('permission was denied')))
})

function mockServer(output: string | null = null, configured = false) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => ({
      ok: true,
      json: async () =>
        String(input).includes('capabilities')
          ? {
              generation: { configured, status: configured ? 'ready' : 'key_not_set', model: 'gemini-omni-1.2-flash' },
              renderer: { available: true },
              speech: { status: 'ready', error: null },
            }
          : {
              id: 'project',
              assets: [],
              current_output: output,
              current_render_revision: 1,
              settings: {
                duration_seconds: 15,
                zoom_style: 'smooth',
                music_enabled: true,
                music_volume: 0.2,
                keep_clip_audio: false,
                clip_audio_volume: 0.7,
                fit_mode: 'contain',
                overlay_text: null,
                overlay_position: 'end_card',
                overlay_color: 'lime',
                brightness: 0,
              },
              undo_stack: output ? [{}] : [],
            },
    })),
  )
}

test('empty screen has upload, timeline, and disabled download/undo', async () => {
  mockServer()
  render(<App />)
  await screen.findByText('Drop photos or video clips here')
  expect(screen.getByLabelText('Upload photos or videos')).toBeInTheDocument()
  expect(screen.getByLabelText('Reel timeline')).toBeInTheDocument()
  expect(screen.getByText('Download MP4').closest('a')).toHaveAttribute('aria-disabled', 'true')
  expect(screen.getByRole('button', { name: 'Undo' })).toBeDisabled()
})

test('completed reel displays video, transport controls, undo and download', async () => {
  mockServer('renders/revision-1.mp4')
  render(<App />)
  await screen.findByLabelText('Rendered reel preview')
  expect(screen.getByRole('button', { name: 'Play preview' })).not.toBeDisabled()
  expect(screen.getByRole('button', { name: 'Undo' })).not.toBeDisabled()
  expect(screen.getByText('Download MP4').closest('a')).toHaveAttribute('href', '/api/projects/project/download')
})

test('AI Ad tab clearly displays Key not set when server has no Gemini key', async () => {
  mockServer(null, false)
  render(<App />)
  await screen.findByText('Drop photos or video clips here')
  fireEvent.click(screen.getByRole('tab', { name: 'AI Ad' }))
  expect(await screen.findAllByText(/Key not set/i)).not.toHaveLength(0)
})

test('landing page lookbook supports keyboard toggle and shows local campaign cards', () => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      cb: ResizeObserverCallback
      constructor(cb: ResizeObserverCallback) {
        this.cb = cb
      }
      observe() {
        this.cb([{ contentRect: { width: 1024, height: 640 } } as ResizeObserverEntry], this as unknown as ResizeObserver)
      }
      disconnect() {}
    },
  )
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: () => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }),
  })
  render(<Landing />)
  const buttons = screen.getAllByRole('button', { name: 'Open your possibilities' })
  expect(buttons).toHaveLength(2) // Folder shell + hint button are both keyboard accessible
  fireEvent.keyDown(buttons[0], { key: 'Enter' })
  expect(screen.getAllByRole('button', { name: 'Close collection' })[0]).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByAltText('Boutique apparel and woven silk showcase card')).toHaveAttribute('src', '/lookbook/retail.png')
})

test('timeline quick audio mute button sends real edit request', async () => {
  const fetchSpy = vi.fn(async (input: string) => ({
    ok: true,
    json: async () =>
      String(input).includes('capabilities')
        ? {
            generation: { configured: false, status: 'key_not_set', model: 'gemini-omni-1.2-flash' },
            renderer: { available: true },
            speech: { status: 'ready', error: null },
          }
        : String(input).endsWith('/edit')
          ? {
              project: {
                id: 'project',
                assets: [{ id: 'a1', filename: 'photo.png', media_type: 'image' }],
                current_output: null,
                current_render_revision: 1,
                undo_stack: [{}],
                settings: {
                  duration_seconds: 15,
                  zoom_style: 'smooth',
                  music_enabled: false,
                  music_volume: 0.2,
                  keep_clip_audio: false,
                  clip_audio_volume: 0.7,
                  fit_mode: 'contain',
                  overlay_text: null,
                  overlay_position: 'end_card',
                  overlay_color: 'lime',
                  brightness: 0,
                },
              },
            }
          : {
              id: 'project',
              assets: [{ id: 'a1', filename: 'photo.png', media_type: 'image' }],
              current_output: null,
              current_render_revision: 1,
              undo_stack: [],
              settings: {
                duration_seconds: 15,
                zoom_style: 'smooth',
                music_enabled: true,
                music_volume: 0.2,
                keep_clip_audio: false,
                clip_audio_volume: 0.7,
                fit_mode: 'contain',
                overlay_text: null,
                overlay_position: 'end_card',
                overlay_color: 'lime',
                brightness: 0,
              },
            },
  }))
  vi.stubGlobal('fetch', fetchSpy)
  render(<App />)
  const muteBtn = await screen.findByRole('button', { name: 'Mute background music' })
  fireEvent.click(muteBtn)
  await waitFor(() =>
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/projects/project/edit',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ music_enabled: false, render: false }),
      }),
    ),
  )
  await screen.findByRole('button', { name: 'Unmute background music' })
})

test('AI Ad reference picker caps Gemini duration at 10s when 2 photos selected', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string) => ({
      ok: true,
      json: async () =>
        String(input).includes('capabilities')
          ? {
              generation: { configured: false, status: 'key_not_set', model: 'gemini-omni-1.2-flash' },
              renderer: { available: true },
              speech: { status: 'ready', error: null },
            }
          : {
              id: 'project',
              assets: [
                { id: 'p1', filename: 'one.png', media_type: 'image' },
                { id: 'p2', filename: 'two.png', media_type: 'image' },
              ],
              current_output: null,
              current_render_revision: 1,
              undo_stack: [],
              settings: {
                duration_seconds: 15,
                zoom_style: 'smooth',
                music_enabled: true,
                music_volume: 0.2,
                keep_clip_audio: false,
                clip_audio_volume: 0.7,
                fit_mode: 'contain',
                overlay_text: null,
                overlay_position: 'end_card',
                overlay_color: 'lime',
                brightness: 0,
              },
            },
    })),
  )
  render(<App />)
  fireEvent.click(await screen.findByRole('tab', { name: 'AI Ad' }))
  const slider = screen.getByLabelText(/Duration:/) as HTMLInputElement
  fireEvent.change(slider, { target: { value: '14' } })
  expect(slider.value).toBe('14')
  fireEvent.click(screen.getByRole('button', { name: /#1/ }))
  fireEvent.click(screen.getByRole('button', { name: /#2/ }))
  expect(slider.max).toBe('10')
  expect(slider.value).toBe('10')
})

test('3-way language mode selector defaults to Tanglish and switches modes', () => {
  const onModeChange = vi.fn()
  render(<VoiceButton disabled={false} mode="tanglish" onModeChange={onModeChange} onAudio={vi.fn()} onError={vi.fn()} />)
  const tanglishBtn = screen.getByRole('button', { name: 'Tanglish' })
  const tamilBtn = screen.getByRole('button', { name: 'தமிழ்' })
  const englishBtn = screen.getByRole('button', { name: 'English' })
  expect(tanglishBtn).toHaveAttribute('aria-pressed', 'true')
  expect(tamilBtn).toHaveAttribute('aria-pressed', 'false')
  fireEvent.click(tamilBtn)
  expect(onModeChange).toHaveBeenCalledWith('ta')
  fireEvent.click(englishBtn)
  expect(onModeChange).toHaveBeenCalledWith('en')
})

test('WebSocket AudioWorklet streaming sends PCM frames, stop control, and renders dual transcript', async () => {
  const sentMessages: unknown[] = []
  const wsRef: {
    current: {
      binaryType: string
      readyState: number
      onopen: (() => void) | null
      onmessage: ((ev: { data: string }) => void) | null
      onerror: (() => void) | null
      onclose: (() => void) | null
      send: (data: unknown) => void
      close: () => void
    } | null
  } = { current: null }

  class MockWebSocket {
    static OPEN = 1
    binaryType = 'blob'
    readyState = 1
    onopen: (() => void) | null = null
    onmessage: ((ev: { data: string }) => void) | null = null
    onerror: (() => void) | null = null
    onclose: (() => void) | null = null
    url: string
    constructor(url: string) {
      this.url = url
      wsRef.current = this
      queueMicrotask(() => this.onopen?.())
    }
    send(data: unknown) {
      sentMessages.push(data)
    }
    close() {
      this.readyState = 3
    }
  }

  // Track the current onmessage handler (reassigned during flush phase)
  let currentOnMessage: ((ev: { data: unknown }) => void) | null = null
  const workletRef: { onmessage: ((ev: { data: { pcm: ArrayBuffer; rms: number } }) => void) | null } = {
    get onmessage() { return currentOnMessage as ((ev: { data: { pcm: ArrayBuffer; rms: number } }) => void) | null },
    set onmessage(fn) { currentOnMessage = fn as ((ev: { data: unknown }) => void) | null },
  }
  class MockWorkletNode {
    port = {
      get onmessage() { return currentOnMessage },
      set onmessage(fn: ((ev: { data: unknown }) => void) | null) { currentOnMessage = fn },
      postMessage(msg: unknown) {
        // Simulate flush ack: when worklet receives {type:'flush'}, immediately reply {type:'flushed'}
        if (msg && typeof msg === 'object' && (msg as Record<string, unknown>).type === 'flush') {
          queueMicrotask(() => { currentOnMessage?.({ data: { type: 'flushed', seq: 0 } }) })
        }
      },
    }
    disconnect() {}
  }
  class MockAudioContext {
    state = 'running'
    audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) }
    createMediaStreamSource() {
      return { connect: vi.fn() }
    }
    close() {
      this.state = 'closed'
      return Promise.resolve()
    }
  }

  vi.stubGlobal('WebSocket', MockWebSocket)
  vi.stubGlobal('AudioContext', MockAudioContext)
  vi.stubGlobal('AudioWorkletNode', MockWorkletNode)
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({
        getTracks: () => [{ stop: vi.fn() }],
        getAudioTracks: () => [{ onended: null }],
      }),
    },
  })

  const onStreamResult = vi.fn()
  const onProcessing = vi.fn()
  render(
    <VoiceButton
      disabled={false}
      projectId="proj-123"
      mode="tanglish"
      onModeChange={vi.fn()}
      onStreamResult={onStreamResult}
      onProcessing={onProcessing}
      onAudio={vi.fn()}
      onError={vi.fn()}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Start recording' }))
  await screen.findByRole('button', { name: 'Stop recording' })

  expect(wsRef.current).not.toBeNull()
  const pcmBuf = new Int16Array([1000, -1000, 1200, -1200]).buffer
  workletRef.onmessage?.({ data: { pcm: pcmBuf, rms: 0.08 } })
  expect(sentMessages[0]).toBe(pcmBuf)

  fireEvent.click(screen.getByRole('button', { name: 'Stop recording' }))
  await waitFor(() => expect(onProcessing).toHaveBeenCalled())
  await waitFor(() => {
    const stopMsg = sentMessages.find((m) => typeof m === 'string' && (m as string).includes('"stop"'))
    expect(stopMsg).toBeDefined()
    const parsed = JSON.parse(stopMsg as string)
    expect(parsed.event).toBe('stop')
    // command_id is optional UUID — just verify it's a string if present
    if (parsed.command_id !== undefined) {
      expect(typeof parsed.command_id).toBe('string')
    }
  })

  wsRef.current?.onmessage?.({
    data: JSON.stringify({
      transcript: 'Offer ah 25 percent nu maathu.',
      secondary_transcript: 'மியூசிக் கம்மி பண்ணு',
      parsed_command: {
        original_transcript: 'Offer ah 25 percent nu maathu.',
        operations: [{ id: 'op1', type: 'set_text_overlay', parameters: { text: '25 percent offer', placement: 'end_card' } }],
        requires_clarification: false,
        clarification_question: null,
        warnings: [],
      },
    }),
  })
  expect(onStreamResult).toHaveBeenCalledWith(expect.objectContaining({ transcript: 'Offer ah 25 percent nu maathu.' }))
})

test('falls back to MediaRecorder when AudioWorklet is unavailable', async () => {
  class MockMediaRecorder {
    static isTypeSupported = () => true
    state = 'inactive'
    mimeType = 'audio/webm'
    ondataavailable: ((e: { data: Blob }) => void) | null = null
    onerror: (() => void) | null = null
    onstop: (() => void) | null = null
    start() {
      this.state = 'recording'
    }
    stop() {
      this.state = 'inactive'
      this.ondataavailable?.({ data: new Blob(['abc'], { type: 'audio/webm' }) })
      this.onstop?.()
    }
  }
  vi.stubGlobal('AudioContext', undefined)
  vi.stubGlobal('MediaRecorder', MockMediaRecorder)
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({
        getTracks: () => [{ stop: vi.fn() }],
        getAudioTracks: () => [{ onended: null }],
      }),
    },
  })

  const onAudio = vi.fn()
  render(<VoiceButton disabled={false} projectId="proj-123" mode="en" onAudio={onAudio} onError={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Start recording' }))
  await screen.findByRole('button', { name: 'Stop recording' })
  fireEvent.click(screen.getByRole('button', { name: 'Stop recording' }))
  expect(onAudio).toHaveBeenCalledWith(expect.any(Blob), 'webm')
})

test('Phase 8 TranscriptReview shows operations and requires explicit Apply click', () => {
  const onApply = vi.fn()
  const onCancel = vi.fn()
  const cmd: Command = {
    transcript: 'Offer ah 25 percent nu maathu. Smooth zoom podu.',
    secondary_transcript: 'ஸ்மூத் ஜூம்',
    asr_mode: 'tanglish',
    engines_used: ['faster-whisper', 'indicconformer-ta'],
    preview: true,
    parsed_command: {
      original_transcript: 'Offer ah 25 percent nu maathu. Smooth zoom podu.',
      operations: [
        { id: 'op1', type: 'set_text_overlay', parameters: { text: '25 percent offer', placement: 'end_card' } },
        { id: 'op2', type: 'set_zoom_style', parameters: { style: 'smooth' } },
      ],
      requires_clarification: false,
      clarification_question: null,
      warnings: [],
      matched_sources: { set_text_overlay: 'faster-whisper', set_zoom_style: 'faster-whisper' },
    },
  }
  render(<TranscriptReview result={cmd} onApply={onApply} onCancel={onCancel} />)
  expect(screen.getByText('Offer ah 25 percent nu maathu. Smooth zoom podu.')).toBeInTheDocument()
  expect(screen.getByText('Smooth photo zoom')).toBeInTheDocument()
  expect(onApply).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: 'Apply all 2' }))
  expect(onApply).toHaveBeenCalledWith(cmd, undefined)
})

test('Phase 8 TranscriptReview supports inline transcript editing and Cancel', () => {
  const onApply = vi.fn()
  const onCancel = vi.fn()
  const cmd: Command = {
    parsed_command: {
      original_transcript: 'Offer ah 20 percent',
      operations: [
        { id: 'op1', type: 'set_text_overlay', parameters: { text: '20 percent', placement: 'end_card' } },
      ],
      requires_clarification: false,
      clarification_question: null,
      warnings: [],
    },
  }
  render(<TranscriptReview result={cmd} onApply={onApply} onCancel={onCancel} />)
  fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
  const box = screen.getByLabelText('Edit voice command transcript') as HTMLTextAreaElement
  fireEvent.change(box, { target: { value: 'Offer ah 30 percent nu maathu' } })
  fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
  expect(onApply).toHaveBeenCalledWith(cmd, 'Offer ah 30 percent nu maathu')

  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(onCancel).toHaveBeenCalledTimes(1)
})

test('Phase 8 Clarification renders question and hides Apply button', () => {
  const cmd: Command = {
    parsed_command: {
      original_transcript: 'make reel',
      operations: [],
      requires_clarification: true,
      clarification_question: 'How long should the reel be?',
      warnings: [],
    },
  }
  render(<TranscriptReview result={cmd} onApply={vi.fn()} onCancel={vi.fn()} />)
  expect(screen.getByText('How long should the reel be?')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Apply/i })).not.toBeInTheDocument()
})

test('Phase 8 App defers execution until user clicks Apply on preview WS result', async () => {
  const fetchSpy = vi.fn(async (input: string) => {
    const url = String(input)
    if (url.includes('capabilities')) {
      return {
        ok: true,
        json: async () => ({
          generation: { configured: false, status: 'key_not_set', model: 'gemini-omni-1.2-flash' },
          renderer: { available: true },
          speech: { status: 'ready', error: null },
        }),
      }
    }
    if (url.endsWith('/apply')) {
      return {
        ok: true,
        json: async () => ({
          job_id: 'job-applied-1',
          parsed_command: {
            original_transcript: 'Create a 15 seconds reel',
            operations: [{ id: 'op1', type: 'create_reel', parameters: { duration_seconds: 15 } }],
            requires_clarification: false,
            clarification_question: null,
            warnings: [],
          },
        }),
      }
    }
    if (url.includes('/jobs/')) {
      return { ok: true, json: async () => ({ status: 'done', stage: 'Ready to preview' }) }
    }
    return {
      ok: true,
      json: async () => ({
        id: 'project',
        assets: [{ id: 'a1', filename: 'photo.png', media_type: 'image' }],
        current_output: null,
        current_render_revision: 1,
        undo_stack: [],
        settings: {
          duration_seconds: 15,
          zoom_style: 'smooth',
          music_enabled: true,
          music_volume: 0.2,
          keep_clip_audio: false,
          clip_audio_volume: 0.7,
          fit_mode: 'contain',
          overlay_text: null,
          overlay_position: 'end_card',
          overlay_color: 'lime',
          brightness: 0,
        },
      }),
    }
  })
  vi.stubGlobal('fetch', fetchSpy)

  const wsRef: { current: { onopen: (() => void) | null; onmessage: ((ev: { data: string }) => void) | null } | null } = { current: null }
  let currentOnMessage: ((ev: { data: unknown }) => void) | null = null
  class MockWebSocket {
    static OPEN = 1
    binaryType = 'blob'
    readyState = 1
    onopen: (() => void) | null = null
    onmessage: ((ev: { data: string }) => void) | null = null
    onerror: (() => void) | null = null
    onclose: (() => void) | null = null
    constructor() {
      wsRef.current = this
      queueMicrotask(() => this.onopen?.())
    }
    send() {}
    close() { this.readyState = 3 }
  }
  class MockWorkletNode {
    port = {
      get onmessage() { return currentOnMessage },
      set onmessage(fn: ((ev: { data: unknown }) => void) | null) { currentOnMessage = fn },
      postMessage(msg: unknown) {
        if (msg && typeof msg === 'object' && (msg as Record<string, unknown>).type === 'flush') {
          queueMicrotask(() => currentOnMessage?.({ data: { type: 'flushed', seq: 0 } }))
        }
      },
    }
    disconnect() {}
  }
  class MockAudioContext {
    state = 'running'
    audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) }
    createMediaStreamSource() { return { connect: vi.fn() } }
    close() { this.state = 'closed'; return Promise.resolve() }
  }
  vi.stubGlobal('WebSocket', MockWebSocket)
  vi.stubGlobal('AudioContext', MockAudioContext)
  vi.stubGlobal('AudioWorkletNode', MockWorkletNode)
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({
        getTracks: () => [{ stop: vi.fn() }],
        getAudioTracks: () => [{ onended: null }],
      }),
    },
  })

  render(<App />)
  const startBtn = await screen.findByRole('button', { name: 'Start recording' })
  await waitFor(() => expect(startBtn).not.toBeDisabled())
  fireEvent.click(startBtn)
  await screen.findByRole('button', { name: 'Stop recording' })
  fireEvent.click(screen.getByRole('button', { name: 'Stop recording' }))
  await waitFor(() => expect(wsRef.current).not.toBeNull())

  wsRef.current?.onmessage?.({
    data: JSON.stringify({
      preview: true,
      transcript: 'Create a 15 seconds reel',
      asr_mode: 'en',
      parsed_command: {
        original_transcript: 'Create a 15 seconds reel',
        operations: [{ id: 'op1', type: 'create_reel', parameters: { duration_seconds: 15 } }],
        requires_clarification: false,
        clarification_question: null,
        warnings: [],
      },
    }),
  })

  // Apply button is shown, and /apply has NOT been called yet
  const applyBtn = await screen.findByRole('button', { name: 'Apply' })
  expect(fetchSpy).not.toHaveBeenCalledWith('/api/projects/project/apply', expect.anything())

  fireEvent.click(applyBtn)
  await waitFor(() =>
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/projects/project/apply',
      expect.objectContaining({ method: 'POST' }),
    ),
  )
})

test('Phase 8 MicrophoneSettings renders cleanly without Permissions API', () => {
  render(<MicrophoneSettings />)
  expect(screen.getByRole('region', { name: 'Microphone settings' })).toBeInTheDocument()
  expect(screen.getByText(/Using system default microphone/i)).toBeInTheDocument()
})
