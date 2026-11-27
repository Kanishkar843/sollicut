export type Asset = {
  id: string
  filename: string
  media_type: 'image' | 'video' | 'audio'
  width?: number | null
  height?: number | null
  duration_seconds?: number | null
  trim_start?: number
  trim_end?: number | null
}
export type Operation = { id: string; type: string; parameters: Record<string, unknown> }
export type ReelSettings = {
  duration_seconds: number
  width: number
  height: number
  fps: number
  zoom_style: 'none' | 'smooth'
  music_enabled: boolean
  music_volume: number
  keep_clip_audio: boolean
  clip_audio_volume: number
  fit_mode: 'contain' | 'cover'
  overlay_text: string | null
  overlay_position: 'end_card' | 'bottom' | 'center'
  overlay_color: 'lime' | 'white' | 'amber'
  brightness: number
}
export type Project = {
  id: string
  assets: Asset[]
  current_output: string | null
  current_render_revision: number
  undo_stack: unknown[]
  settings: ReelSettings
}
export type AsrMode = 'tanglish' | 'ta' | 'en'
export type Parsed = {
  original_transcript: string
  operations: Operation[]
  requires_clarification: boolean
  clarification_question: string | null
  warnings: string[]
  matched_sources?: Record<string, string>
}
export type Command = {
  parsed_command: Parsed
  job_id?: string
  project?: Project
  download_url?: string
  transcript?: string
  secondary_transcript?: string | null
  language_mode?: string
  asr_mode?: AsrMode
  engines_used?: string[]
  asr_elapsed_ms?: number
  requires_clarification?: boolean
  preview?: boolean
  /** V2 transport fields */
  session_id?: string
  command_id?: string
}
export type Capabilities = {
  generation?: { configured: boolean; status: string; label?: string; model: string }
  renderer: { available: boolean }
  speech: { engine?: string; status: string; error: string | null }
  asr_engines?: { indicconformer_ta: boolean; faster_whisper_small: boolean }
  supported_modes?: AsrMode[]
  streaming_ws?: boolean
  voice_profile?: {
    profile: 'lightweight' | 'balanced' | 'accuracy'
    asr_model: string
    vad: 'silero' | 'rms'
    resampler: 'linear' | 'fir_kaiser'
    threads: number
  }
  limits?: { media_items?: number; image_mb?: number; video_mb?: number; video_seconds?: number }
}

export function buildVoiceWsUrl(projectId: string, mode: AsrMode, sessionId?: string, autoApply = true): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const sid = sessionId ?? crypto.randomUUID()
  const applyParam = autoApply ? '' : '&auto_apply=false'
  return `${proto}//${window.location.host}/ws/voice/${projectId}?mode=${encodeURIComponent(mode)}&session_id=${encodeURIComponent(sid)}${applyParam}`
}

export function encodeWav16k(chunks: Int16Array[], sampleRate = 16000): Blob {
  const totalSamples = chunks.reduce((acc, c) => acc + c.length, 0)
  const buffer = new ArrayBuffer(44 + totalSamples * 2)
  const view = new DataView(buffer)
  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }
  writeStr(0, 'RIFF')
  view.setUint32(4, 36 + totalSamples * 2, true)
  writeStr(8, 'WAVE')
  writeStr(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeStr(36, 'data')
  view.setUint32(40, totalSamples * 2, true)
  let offset = 44
  for (const chunk of chunks) {
    for (let i = 0; i < chunk.length; i++) {
      view.setInt16(offset, chunk[i], true)
      offset += 2
    }
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'The server could not complete this request.' }))
    throw new Error(typeof error.detail === 'string' ? error.detail : 'Please check the submitted file and try again.')
  }
  return response.json()
}

export function operationLabel(op: Operation): string {
  const p = op.parameters
  switch (op.type) {
    case 'create_reel':
      return `${p.duration_seconds}-second vertical reel · all media`
    case 'set_duration':
      return `${p.duration_seconds}-second reel`
    case 'set_zoom_style':
      return p.style === 'smooth' ? 'Smooth photo zoom' : 'Zoom off'
    case 'set_music':
      return p.enabled ? 'Background music on' : 'Music off'
    case 'set_music_volume':
      return p.direction === 'decrease' ? 'Softer background music' : 'Louder background music'
    case 'set_clip_audio':
      return p.enabled ? 'Original video audio on' : 'Video audio muted'
    case 'set_fit_mode':
      return p.mode === 'cover' ? 'Fill 9:16 frame' : 'Fit inside 9:16 frame'
    case 'set_text_overlay':
      return p.text ? `“${p.text}” · ${p.placement === 'end_card' ? 'at the end' : p.placement === 'center' ? 'centered' : 'at the bottom'}` : 'Text overlay cleared'
    case 'set_overlay_style':
      return `Text style updated`
    case 'set_aspect_ratio':
      return 'Vertical 9:16 format'
    case 'set_brightness':
      return Number(p.value) > 0 ? 'Brighter look' : 'Darker look'
    case 'trim_clip':
      return `Trimmed clip ${p.clip_index ?? ''}`.trim()
    case 'reorder_assets':
      return 'Reordered timeline clips'
    case 'undo':
      return 'Restore the previous edit'
    case 'export':
      return 'Download your MP4'
    default:
      return op.type
  }
}
