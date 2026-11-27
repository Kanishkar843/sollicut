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
