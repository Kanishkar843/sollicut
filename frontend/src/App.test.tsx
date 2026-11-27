import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App, { validateMedia } from './App'
import Landing from './Landing'
import VoiceButton, { microphoneError } from './VoiceButton'
import { operationLabel } from './api'

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

test('manual typed follow-up command updates text overlay and enables redo', async () => {
  let stateText: string | null = 'Sale 20%'
  let redoLen = 0
  const makeProject = () => ({
    id: 'project',
    assets: [{ id: 'p1', filename: 'one.png', media_type: 'image' }],
    current_output: 'renders/revision-1.mp4',
    current_render_revision: 1,
    undo_stack: [{}],
    redo_stack: redoLen ? [{}] : [],
    settings: {
      duration_seconds: 15,
      zoom_style: 'smooth',
      music_enabled: true,
      music_volume: 0.2,
      keep_clip_audio: false,
      clip_audio_volume: 0.7,
      fit_mode: 'contain',
      overlay_text: stateText,
      overlay_position: 'bottom',
      overlay_color: 'lime',
      brightness: 0,
      text_layers: stateText
        ? [{ id: 'txt-1', text: stateText, position: 'bottom', color: 'lime', animation: 'none', is_caption: false }]
        : [],
      active_text_id: stateText ? 'txt-1' : null,
      transition_style: 'none',
      filter_preset: 'none',
    },
  })

  const fetchSpy = vi.fn(async (input: string) => {
    const url = String(input)
    if (url.includes('capabilities')) {
      return {
        ok: true,
        json: async () => ({
          generation: { configured: false, status: 'key_not_set', model: 'gemini-omni-1.2-flash' },
          renderer: { available: true },
          speech: { status: 'ready', error: null },
          tts: { available: true, backend: 'pyttsx3', languages: ['en', 'ta'] },
          cutout: { backend: 'opencv_grabcut', u2net_ready: false, chroma_key: true },
        }),
      }
    }
    if (url.includes('assets-catalog')) {
      return { ok: true, json: async () => ({ templates: [], audio_packs: [], filters: [], transitions: [], stickers: [], stock_video: { status: 'deferred', note: 'Deferred', items: [] } }) }
    }
    if (url.endsWith('/apply')) {
      stateText = 'Sale 25%'
      return {
        ok: true,
        json: async () => ({
          parsed_command: {
            original_transcript: 'Change text to 25%',
            operations: [{ id: 'op-1', type: 'set_text_overlay', parameters: { text: 'Sale 25%', placement: 'bottom' } }],
            requires_clarification: false,
            clarification_question: null,
            warnings: [],
          },
          job_id: 'job-2',
        }),
      }
    }
    if (url.includes('/jobs/job-2')) {
      return { ok: true, json: async () => ({ status: 'done', stage: 'Ready to preview' }) }
    }
    if (url.endsWith('/undo')) {
      stateText = 'Sale 20%'
      redoLen = 1
      return { ok: true, json: async () => makeProject() }
    }
    if (url.endsWith('/redo')) {
      stateText = 'Sale 25%'
      redoLen = 0
      return { ok: true, json: async () => makeProject() }
    }
    return { ok: true, json: async () => makeProject() }
  })
  vi.stubGlobal('fetch', fetchSpy)
  render(<App />)

  const cmdInput = await screen.findByLabelText('Manual command input')
  fireEvent.change(cmdInput, { target: { value: 'Change text to 25%' } })
  fireEvent.click(screen.getByRole('button', { name: 'Run command' }))

  await waitFor(() => expect(screen.getByText('Sale 25%')).toBeInTheDocument())
  expect(screen.getByRole('tab', { name: 'FX' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Assets' })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
  await waitFor(() => expect(screen.getByText('Sale 20%')).toBeInTheDocument())

  fireEvent.click(screen.getByRole('button', { name: 'Redo' }))
  await waitFor(() => expect(screen.getByText('Sale 25%')).toBeInTheDocument())
})

