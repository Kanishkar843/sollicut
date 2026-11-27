export type Keyframe = {
  id: string
  time_seconds: number
  x: number
  y: number
  scale: number
  rotation: number
  opacity: number
  easing: 'linear' | 'ease_in' | 'ease_out' | 'ease_in_out'
}

export type TextPosition = 'end_card' | 'bottom' | 'center' | 'top'
export type TextColor = 'lime' | 'white' | 'amber' | 'cyan' | 'rose'
export type TextAnimation = 'none' | 'fade' | 'slide_up' | 'pop'

export type TextLayer = {
  id: string
  text: string
  position: TextPosition
  color: TextColor
  animation: TextAnimation
  start_time?: number | null
  end_time?: number | null
  clip_index?: number | null
  is_caption?: boolean
}

export type AspectRatio = '9:16' | '16:9' | '1:1' | '4:5'
export type FilterPreset = 'none' | 'cinematic' | 'warm' | 'cool' | 'bw' | 'vivid' | 'vintage' | 'high_contrast'
export type TransitionStyle = 'none' | 'fade' | 'dissolve' | 'slideleft' | 'slideright' | 'wipeleft' | 'circleopen'
export type SpeedCurve = 'normal' | 'slow_mo' | 'fast' | 'ramp_in' | 'ramp_out'
export type CutoutMode = 'none' | 'chroma_key' | 'auto_cutout'
export type VocalIsolation = 'none' | 'vocals_only' | 'music_only'
export type StickerBadge = 'none' | 'sale' | 'new' | 'top_pick' | 'tamil_special'

export type Asset = {
  id: string
  filename: string
  media_type: 'image' | 'video' | 'audio'
  width?: number | null
  height?: number | null
  duration_seconds?: number | null
  trim_start?: number
  trim_end?: number | null
  speed?: number
  volume?: number
  filter_preset?: FilterPreset
  cutout_mode?: CutoutMode
  chroma_color?: string
  chroma_similarity?: number
  stabilize?: boolean
  relight?: number
  keyframes?: Keyframe[]
}

export type Operation = { id: string; type: string; parameters: Record<string, unknown> }

export type ReelSettings = {
  duration_seconds: number
  aspect_ratio?: AspectRatio
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
  overlay_position: 'end_card' | 'bottom' | 'center' | 'top'
  overlay_color: 'lime' | 'white' | 'amber' | 'cyan' | 'rose'
  brightness: number
  text_layers?: TextLayer[]
  active_text_id?: string | null
  transition_style?: TransitionStyle
  transition_duration?: number
  filter_preset?: FilterPreset
  speed_curve?: SpeedCurve
  keyframes?: Keyframe[]
  audio_normalize?: boolean
  audio_denoise?: boolean
  voice_enhance?: boolean
  vocal_isolation?: VocalIsolation
  narration_enabled?: boolean
  narration_volume?: number
  narration_asset_id?: string | null
  sticker_badge?: StickerBadge
  template_id?: string | null
}

export type Project = {
  id: string
  assets: Asset[]
  current_output: string | null
  current_render_revision: number
  undo_stack: unknown[]
  redo_stack?: unknown[]
  settings: ReelSettings
}

export type Parsed = {
  original_transcript: string
  operations: Operation[]
  requires_clarification: boolean
  clarification_question: string | null
  warnings: string[]
}

export type Command = {
  parsed_command: Parsed
  job_id?: string
  project?: Project
  download_url?: string
  transcript?: string
}

export type Capabilities = {
  generation?: { configured: boolean; status: string; label?: string; model: string }
  renderer: { available: boolean; raqm?: boolean; tamil_shaping?: string }
  speech: { status: string; error: string | null }
  tts?: { available: boolean; backend: string; languages: string[] }
  cutout?: { backend: string; u2net_ready: boolean }
  limits?: { media_items?: number; image_mb?: number; video_mb?: number; video_seconds?: number }
}

export type AssetsCatalog = {
  aspect_ratios?: { id: AspectRatio; label: string; width: number; height: number; desc: string }[]
  templates: { id: string; name: string; description: string; badge: string; settings: Record<string, unknown> }[]
  audio_packs: { id: string; name: string; category: string; filename: string; folder?: string; duration_seconds: number; license: string }[]
  filters: { id: FilterPreset; label: string; category: string }[]
  transitions: { id: TransitionStyle; label: string; category: string }[]
  stickers: { id: StickerBadge; label: string }[]
  stock_video: { status: string; note: string; items: unknown[] }
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
    case 'update_text_layer':
      return p.text
        ? `“${p.text}” · ${p.placement === 'end_card' ? 'at the end' : p.placement === 'center' ? 'centered' : p.placement === 'top' ? 'at the top' : 'at the bottom'}`
        : 'Text overlay cleared'
    case 'remove_text_layer':
      return 'Removed text layer'
    case 'set_overlay_style':
      return 'Text style updated'
    case 'set_aspect_ratio':
      return `Format ${p.aspect_ratio ?? '9:16'}`
    case 'set_brightness':
      return Number(p.value) > 0 ? 'Brighter look' : 'Darker look'
    case 'set_transition':
      return p.style === 'none' ? 'Transitions cleared' : `Transition: ${p.style}`
    case 'set_filter':
      return p.preset === 'none' ? 'Filter cleared' : `Filter: ${p.preset}`
    case 'set_clip_speed':
      return `Clip speed ${p.speed}x`
    case 'split_clip':
      return `Split clip ${p.clip_index ?? ''} at ${p.split_at_seconds}s`.trim()
    case 'set_audio_processing':
      return 'Updated audio processing'
    case 'set_visual_effect':
      return 'Updated visual effects'
    case 'set_keyframes':
      return 'Updated keyframes'
    case 'set_sticker':
      return p.sticker_badge === 'none' ? 'Sticker removed' : `Sticker: ${p.sticker_badge}`
    case 'apply_template':
      return 'Applied template'
    case 'generate_tts':
      return 'Generated TTS narration'
    case 'trim_clip':
      return `Trimmed clip ${p.clip_index ?? ''}`.trim()
    case 'reorder_assets':
      return 'Reordered timeline clips'
    case 'undo':
      return 'Restore the previous edit'
    case 'redo':
      return 'Redo edit'
    case 'export':
      return 'Download your MP4'
    default:
      return op.type
  }
}
