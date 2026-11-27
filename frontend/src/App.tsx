import { useEffect, useRef, useState } from 'react'
import {
  AudioLines,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Film,
  FolderOpen,
  ImagePlus,
  Layers,
  LoaderCircle,
  Maximize2,
  Mic,
  Music2,
  Package,
  Pause,
  Play,
  Plus,
  Redo2,
  Scissors,
  Send,
  ShieldCheck,
  SkipBack,
  SkipForward,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Type,
  Undo2,
  Volume2,
  VolumeX,
  Wand2,
  X,
} from 'lucide-react'
import GeneratePanel from './GeneratePanel'
import Timeline from './Timeline'
import VoiceButton from './VoiceButton'
import {
  api,
  operationLabel,
  type AspectRatio,
  type AssetsCatalog,
  type Capabilities,
  type Command,
  type FilterPreset,
  type Keyframe,
  type Parsed,
  type Project,
  type SpeedCurve,
  type StickerBadge,
  type TextAnimation,
  type TextColor,
  type TextLayer,
  type TextPosition,
  type TransitionStyle,
  type VocalIsolation,
} from './api'

export function validateMedia(files: File[], count: number): string | null {
  if (files.length + count > 5) return 'Choose up to 5 photos or video clips in total.'
  if (files.some((f) => !['image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/quicktime', 'video/webm'].includes(f.type))) {
    return 'Use JPEG, PNG, WebP, MP4, MOV or WebM.'
  }
  if (files.some((f) => f.size > (f.type.startsWith('video/') ? 100 : 15) * 1024 * 1024)) {
    return 'Photos must be under 15 MB; videos under 100 MB.'
  }
  return null
}

export const validatePhotos = validateMedia

type InspectorTab = 'text' | 'audio' | 'look' | 'trim' | 'fx' | 'assets' | 'ai'

const ASPECT_RATIO_OPTIONS: { id: AspectRatio; label: string; width: number; height: number; desc: string }[] = [
  { id: '9:16', label: '9:16 Vertical', width: 720, height: 1280, desc: 'Reels / Shorts' },
  { id: '16:9', label: '16:9 Landscape', width: 1280, height: 720, desc: 'YouTube / Wide' },
  { id: '1:1', label: '1:1 Square', width: 1080, height: 1080, desc: 'Feed Post' },
  { id: '4:5', label: '4:5 Portrait', width: 864, height: 1080, desc: 'Social Portrait' },
]

const DEFAULT_FILTERS: { id: FilterPreset; label: string; category: string }[] = [
  { id: 'none', label: 'Original', category: 'Basic' },
  { id: 'vivid', label: 'Vivid', category: 'Pop' },
  { id: 'high_contrast', label: 'High Contrast', category: 'Basic' },
  { id: 'cinematic', label: 'Cinematic', category: 'Cinematic' },
  { id: 'warm', label: 'Warm', category: 'Mood' },
  { id: 'cool', label: 'Cool', category: 'Mood' },
  { id: 'vintage', label: 'Vintage', category: 'Cinematic' },
  { id: 'bw', label: 'B&W', category: 'Mood' },
]

const DEFAULT_TRANSITIONS: { id: TransitionStyle; label: string; category: string }[] = [
  { id: 'none', label: 'Cut (None)', category: 'Basic' },
  { id: 'fade', label: 'Fade', category: 'Basic' },
  { id: 'dissolve', label: 'Dissolve', category: 'Basic' },
  { id: 'slideleft', label: 'Slide Left', category: 'Motion' },
  { id: 'slideright', label: 'Slide Right', category: 'Motion' },
  { id: 'wipeleft', label: 'Wipe', category: 'Motion' },
  { id: 'circleopen', label: 'Circle Reveal', category: 'Shape' },
]

function formatTime(sec: number): string {
  const s = Math.max(0, sec)
  const mins = Math.floor(s / 60)
  const rem = (s % 60).toFixed(1).padStart(4, '0')
  return `${String(mins).padStart(2, '0')}:${rem}`
}

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [caps, setCaps] = useState<Capabilities | null>(null)
  const [catalog, setCatalog] = useState<AssetsCatalog | null>(null)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState('Ready')
  const [error, setError] = useState('')
  const [parsed, setParsed] = useState<Parsed | null>(null)
  const [language, setLanguage] = useState('')
  const [manualCommand, setManualCommand] = useState('')
  const [resetting, setResetting] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<InspectorTab>('text')
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null)
  const [showPrivacy, setShowPrivacy] = useState(false)

  // Video preview transport state
  const [playing, setPlaying] = useState(false)
  const [mutedPreview, setMutedPreview] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)

  // Text, Captions & TTS drafts
  const [activeTextIdDraft, setActiveTextIdDraft] = useState<string | null>(null)
  const [overlayDraft, setOverlayDraft] = useState('')
  const [overlayPosDraft, setOverlayPosDraft] = useState<TextPosition>('end_card')
  const [overlayColorDraft, setOverlayColorDraft] = useState<TextColor>('lime')
  const [overlayAnimDraft, setOverlayAnimDraft] = useState<TextAnimation>('none')
  const [ttsText, setTtsText] = useState('')
  const [ttsLang, setTtsLang] = useState<'en' | 'ta'>('en')

  // Look, Transition, Audio, Trim & FX drafts
  const [aspectRatioDraft, setAspectRatioDraft] = useState<AspectRatio>('9:16')
  const [durationDraft, setDurationDraft] = useState(15)
  const [selectedInbuiltAudioId, setSelectedInbuiltAudioId] = useState('soft_calm')
  const [previewingAudioId, setPreviewingAudioId] = useState<string | null>(null)
  const inbuiltPreviewRef = useRef<HTMLAudioElement | null>(null)
  const [zoomDraft, setZoomDraft] = useState<'smooth' | 'none'>('smooth')
  const [brightnessDraft, setBrightnessDraft] = useState(0)
  const [fitDraft, setFitDraft] = useState<'contain' | 'cover'>('contain')
  const [filterDraft, setFilterDraft] = useState<FilterPreset>('none')
  const [transitionDraft, setTransitionDraft] = useState<TransitionStyle>('none')
  const [transitionDurDraft, setTransitionDurDraft] = useState(0.5)
  const [speedCurveDraft, setSpeedCurveDraft] = useState<SpeedCurve>('normal')

  const [musicEnabledDraft, setMusicEnabledDraft] = useState(true)
  const [musicVolDraft, setMusicVolDraft] = useState(0.2)
  const [clipAudioDraft, setClipAudioDraft] = useState(false)
  const [clipVolDraft, setClipVolDraft] = useState(0.7)
  const [denoiseDraft, setDenoiseDraft] = useState(false)
  const [normalizeDraft, setNormalizeDraft] = useState(false)
  const [voiceEnhanceDraft, setVoiceEnhanceDraft] = useState(false)
  const [vocalIsoDraft, setVocalIsoDraft] = useState<VocalIsolation>('none')
  const [narrationEnabledDraft, setNarrationEnabledDraft] = useState(false)
  const [narrationVolDraft, setNarrationVolDraft] = useState(0.9)

  const [trimStartDraft, setTrimStartDraft] = useState(0)
  const [trimEndDraft, setTrimEndDraft] = useState(0)
  const [splitAtDraft, setSplitAtDraft] = useState(1.0)
  const [clipSpeedDraft, setClipSpeedDraft] = useState(1.0)
  const [clipOwnVolDraft, setClipOwnVolDraft] = useState(1.0)

  const [cutoutDraft, setCutoutDraft] = useState<'none' | 'chroma_key' | 'auto_cutout'>('none')
  const [chromaColorDraft, setChromaColorDraft] = useState('0x00ff00')
  const [chromaSimDraft, setChromaSimDraft] = useState(0.25)
  const [stabilizeDraft, setStabilizeDraft] = useState(false)
  const [relightDraft, setRelightDraft] = useState(0)
  const [keyframesDraft, setKeyframesDraft] = useState<Keyframe[]>([])

  const initial = useRef<Promise<Project> | null>(null)
  const pollingRef = useRef(false)
  const projectIdRef = useRef<string | null>(null)
  const upload = useRef<HTMLInputElement>(null)
  const music = useRef<HTMLInputElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const voicePanelRef = useRef<HTMLDivElement>(null)
  const mediaPanelRef = useRef<HTMLElement>(null)
  const manualCmdInputRef = useRef<HTMLInputElement>(null)

  const mediaAssets = project?.assets.filter((a) => a.media_type !== 'audio') ?? []
  const selectedClip = mediaAssets.find((a) => a.id === selectedClipId) ?? mediaAssets[0] ?? null
  const promoLayers = (project?.settings?.text_layers ?? []).filter((l) => !l.is_caption)
  const captionLayers = (project?.settings?.text_layers ?? []).filter((l) => l.is_caption)

  useEffect(() => {
    projectIdRef.current = project?.id ?? null
  }, [project?.id])

  useEffect(() => {
    let live = true
    const saved = localStorage.getItem('sollicut-project')
    if (!initial.current) {
      initial.current = saved
        ? api<Project>(`/projects/${saved}`).catch(() => api<Project>('/projects', { method: 'POST' }))
        : api<Project>('/projects', { method: 'POST' })
    }
    initial.current
      .then((p) => {
        if (live) {
          setProject(p)
          localStorage.setItem('sollicut-project', p.id)
        }
      })
      .catch((e) => live && setError(e.message))

    const refresh = () => api<Capabilities>('/capabilities').then((c) => live && setCaps(c)).catch((e) => live && setError(e.message))
    void refresh()
    api<AssetsCatalog>('/assets-catalog').then((cat) => live && setCatalog(cat)).catch(() => {})
    const timer = setInterval(refresh, 5000)
    return () => {
      live = false
      clearInterval(timer)
    }
  }, [])

  // Sync inspector controls whenever project updates
  useEffect(() => {
    if (!project) return
    const s = project.settings
    const activeLayer =
      (s?.text_layers ?? []).find((l) => l.id === s?.active_text_id) ??
      (s?.text_layers ?? []).find((l) => !l.is_caption) ??
      null
    setActiveTextIdDraft(activeLayer?.id ?? s?.active_text_id ?? null)
    setOverlayDraft(activeLayer?.text ?? s?.overlay_text ?? '')
    setOverlayPosDraft(activeLayer?.position ?? s?.overlay_position ?? 'end_card')
    setOverlayColorDraft(activeLayer?.color ?? s?.overlay_color ?? 'lime')
    setOverlayAnimDraft(activeLayer?.animation ?? 'none')

    setAspectRatioDraft((s?.aspect_ratio as AspectRatio | undefined) ?? '9:16')
    setDurationDraft(s?.duration_seconds ?? 15)
    setZoomDraft(s?.zoom_style ?? 'smooth')
    setBrightnessDraft(s?.brightness ?? 0)
    setFitDraft(s?.fit_mode ?? 'contain')
    setFilterDraft(s?.filter_preset ?? 'none')
    setTransitionDraft(s?.transition_style ?? 'none')
    setTransitionDurDraft(s?.transition_duration ?? 0.5)
    setSpeedCurveDraft(s?.speed_curve ?? 'normal')

    setMusicEnabledDraft(s?.music_enabled ?? true)
    setMusicVolDraft(s?.music_volume ?? 0.2)
    setClipAudioDraft(s?.keep_clip_audio ?? false)
    setClipVolDraft(s?.clip_audio_volume ?? 0.7)
    setDenoiseDraft(s?.audio_denoise ?? false)
    setNormalizeDraft(s?.audio_normalize ?? false)
    setVoiceEnhanceDraft(s?.voice_enhance ?? false)
    setVocalIsoDraft(s?.vocal_isolation ?? 'none')
    setNarrationEnabledDraft(s?.narration_enabled ?? false)
    setNarrationVolDraft(s?.narration_volume ?? 0.9)

    const firstMedia = project.assets.find((a) => a.media_type !== 'audio')
    if (!selectedClipId || !project.assets.some((a) => a.id === selectedClipId)) {
      setSelectedClipId(firstMedia?.id ?? null)
    }
  }, [project])

  useEffect(() => {
    if (!selectedClip) return
    if (selectedClip.media_type === 'video') {
      const start = selectedClip.trim_start ?? 0
      const end = selectedClip.trim_end ?? selectedClip.duration_seconds ?? 5
      setTrimStartDraft(start)
      setTrimEndDraft(end)
      setSplitAtDraft(Number(((start + end) / 2).toFixed(1)))
    }
    setClipSpeedDraft(selectedClip.speed ?? 1.0)
    setClipOwnVolDraft(selectedClip.volume ?? 1.0)
    setCutoutDraft(selectedClip.cutout_mode ?? 'none')
    setChromaColorDraft(selectedClip.chroma_color ?? '0x00ff00')
    setChromaSimDraft(selectedClip.chroma_similarity ?? 0.25)
    setStabilizeDraft(selectedClip.stabilize ?? false)
    setRelightDraft(selectedClip.relight ?? 0)
    setKeyframesDraft(selectedClip.keyframes ?? [])
  }, [
    selectedClip?.id,
    selectedClip?.trim_start,
    selectedClip?.trim_end,
    selectedClip?.duration_seconds,
    selectedClip?.speed,
    selectedClip?.volume,
    selectedClip?.cutout_mode,
    selectedClip?.chroma_color,
    selectedClip?.chroma_similarity,
    selectedClip?.stabilize,
    selectedClip?.relight,
  ])

  useEffect(() => {
    if (!jobId || !project?.id) return
    let live = true
    const pid = project.id
    const poll = async () => {
      if (pollingRef.current) return
      pollingRef.current = true
      try {
        const job = await api<{ status: string; stage: string; error?: string }>(`/jobs/${jobId}`)
        if (!live) return
        setStage(job.stage)
        if (job.status === 'done') {
          const p = await api<Project>(`/projects/${pid}`)
          if (live) {
            setProject(p)
            setBusy(false)
            setJobId(null)
            setCurrentTime(0)
            setPlaying(false)
          }
        }
        if (job.status === 'failed') {
          setError(job.error || 'Rendering failed')
          setBusy(false)
          setJobId(null)
        }
      } catch (e) {
        if (live) {
          setError((e as Error).message)
          setBusy(false)
          setJobId(null)
        }
      } finally {
        pollingRef.current = false
      }
    }
    void poll()
    const timer = setInterval(poll, 900)
    return () => {
      live = false
      pollingRef.current = false
      clearInterval(timer)
    }
  }, [jobId, project?.id])

  async function filesSelected(files: File[], audio = false) {
    const pid = projectIdRef.current
    if (!project || !pid || busy) return
    const validation = audio ? null : validateMedia(files, mediaAssets.length)
    if (validation) {
      setError(validation)
      return
    }
    setError('')
    setBusy(true)
    setStage(audio ? 'Uploading your music' : 'Uploading your media')
    try {
      let latest = project
      if (audio) {
        const existingAudio = project.assets.find((a) => a.media_type === 'audio')
        if (existingAudio) {
          latest = await api<Project>(`/projects/${pid}/assets/${existingAudio.id}`, { method: 'DELETE' })
        }
      }
      for (const file of files) {
        const form = new FormData()
        form.append('file', file)
        latest = await api<Project>(`/projects/${pid}/assets`, { method: 'POST', body: form })
        setProject(latest)
      }
      setStage('Ready')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function handleCommandResult(result: Command) {
    setParsed(result.parsed_command)
    if (result.parsed_command.requires_clarification) {
      setStage('A little more detail')
      setBusy(false)
    } else if (result.job_id) {
      setStage('Rendering reel')
      setJobId(result.job_id)
    } else {
      if (result.project) setProject(result.project)
      if (result.download_url) {
        const a = document.createElement('a')
        a.href = result.download_url
        a.download = 'SolliCut-reel.mp4'
        a.click()
      }
      setStage(result.download_url ? 'Ready to download' : 'Updated project')
      setBusy(false)
    }
  }

  async function handleAudio(blob: Blob, extension: string) {
    const pid = projectIdRef.current
    if (!pid) return
    setBusy(true)
    setError('')
    setStage('Processing speech')
    setParsed(null)
    try {
      const form = new FormData()
      form.append('file', blob, `command.${extension}`)
      if (language) form.append('language_hint', language)
      const result = await api<Command>(`/projects/${pid}/voice-command`, { method: 'POST', body: form })
      handleCommandResult(result)
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
      setStage('Ready')
    }
  }

  async function applyTypedCommand(e: React.FormEvent) {
    e.preventDefault()
    const pid = projectIdRef.current
    const cmd = manualCommand.trim()
    if (!pid || !cmd || busy) return
    setBusy(true)
    setError('')
    setStage('Applying command')
    setParsed(null)
    try {
      const result = await api<Command>(`/projects/${pid}/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: cmd }),
      })
      setManualCommand('')
      handleCommandResult(result)
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
      setStage('Ready')
    }
  }

  async function applyVisualEdit(payload: Record<string, unknown>, stageLabel = 'Applying studio edit') {
    const pid = projectIdRef.current
    if (!pid || busy) return
    setBusy(true)
    setError('')
    setStage(stageLabel)
    try {
      const res = await api<{ job_id?: string; project?: Project }>(`/projects/${pid}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (res.job_id) {
        setJobId(res.job_id)
      } else if (res.project) {
        setProject(res.project)
        setStage('Ready')
        setBusy(false)
      }
    } catch (e) {
      setError((e as Error).message)
      setStage('Ready')
      setBusy(false)
    }
  }

  async function moveClip(index: number, delta: -1 | 1) {
    const target = index + delta
    if (target < 0 || target >= mediaAssets.length) return
    const ordered = [...mediaAssets]
    const [item] = ordered.splice(index, 1)
    ordered.splice(target, 0, item)
    await applyVisualEdit({ reorder_asset_ids: ordered.map((a) => a.id), render: Boolean(project?.current_output) }, 'Reordering clips')
  }

  async function reorderClipIds(orderedIds: string[]) {
    await applyVisualEdit({ reorder_asset_ids: orderedIds, render: Boolean(project?.current_output) }, 'Reordering clips')
  }

  async function undo() {
    const pid = projectIdRef.current
    if (!pid) return
    setBusy(true)
    setError('')
    try {
      setProject(await api<Project>(`/projects/${pid}/undo`, { method: 'POST' }))
      setParsed(null)
      setStage('Previous edit restored')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function redo() {
    const pid = projectIdRef.current
    if (!pid) return
    setBusy(true)
    setError('')
    try {
      setProject(await api<Project>(`/projects/${pid}/redo`, { method: 'POST' }))
      setParsed(null)
      setStage('Edit re-applied')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function reset() {
    const pid = projectIdRef.current
    if (!pid) return
    setBusy(true)
    try {
      await api(`/projects/${pid}`, { method: 'DELETE' })
      const p = await api<Project>('/projects', { method: 'POST' })
      setProject(p)
      localStorage.setItem('sollicut-project', p.id)
      setParsed(null)
      setSelectedClipId(null)
      setError('')
      setStage('Ready')
      setResetting(false)
      setCurrentTime(0)
      setPlaying(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: string) {
    const pid = projectIdRef.current
    if (!pid) return
    setBusy(true)
    try {
      setProject(await api<Project>(`/projects/${pid}/assets/${id}`, { method: 'DELETE' }))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function runAutoCaptions() {
    const pid = projectIdRef.current
    if (!pid || busy) return
    setBusy(true)
    setError('')
    setStage('Transcribing clip captions')
    try {
      const res = await api<{ job_id?: string; project?: Project }>(`/projects/${pid}/auto-captions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language_hint: language || null, render: mediaAssets.length > 0 }),
      })
      if (res.job_id) setJobId(res.job_id)
      else if (res.project) {
        setProject(res.project)
        setStage('Captions generated')
        setBusy(false)
      }
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
      setStage('Ready')
    }
  }

  async function runTTS() {
    const pid = projectIdRef.current
    if (!pid || !ttsText.trim() || busy) return
    setBusy(true)
    setError('')
    setStage('Synthesizing offline TTS')
    try {
      const res = await api<{ job_id?: string; project?: Project }>(`/projects/${pid}/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: ttsText.trim(), language: ttsLang, render: mediaAssets.length > 0 }),
      })
      if (res.job_id) setJobId(res.job_id)
      else if (res.project) {
        setProject(res.project)
        setStage('Narration attached')
        setBusy(false)
      }
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
      setStage('Ready')
    }
  }

  async function applyTemplate(templateId: string) {
    const pid = projectIdRef.current
    if (!pid || busy) return
    setBusy(true)
    setError('')
    setStage('Applying template')
    try {
      const res = await api<{ job_id?: string; project?: Project }>(`/projects/${pid}/apply-template`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: templateId, render: mediaAssets.length > 0 }),
      })
      if (res.job_id) setJobId(res.job_id)
      else if (res.project) {
        setProject(res.project)
        setStage('Template applied')
        setBusy(false)
      }
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
      setStage('Ready')
    }
  }

  async function attachCatalogAudio(audioId: string) {
    const pid = projectIdRef.current
    if (!pid || busy) return
    setBusy(true)
    setError('')
    setStage('Attaching audio pack')
    try {
      const res = await api<{ job_id?: string; project?: Project }>(`/projects/${pid}/attach-catalog-audio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_id: audioId, render: Boolean(project?.current_output) }),
      })
      if (res.job_id) setJobId(res.job_id)
      else if (res.project) {
        setProject(res.project)
        setStage('Audio pack attached')
        setBusy(false)
      }
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
      setStage('Ready')
    }
  }

  function selectTextLayer(layerId: string) {
    const layer = promoLayers.find((l) => l.id === layerId)
    if (!layer) return
    setActiveTextIdDraft(layer.id)
    setOverlayDraft(layer.text)
    setOverlayPosDraft(layer.position)
    setOverlayColorDraft(layer.color)
    setOverlayAnimDraft(layer.animation)
  }

  function startNewTextLayer() {
    setActiveTextIdDraft('__new__')
    setOverlayDraft('')
    setOverlayPosDraft('bottom')
    setOverlayColorDraft('lime')
    setOverlayAnimDraft('none')
  }

  function addKeyframe() {
    const t = Number(Math.min(durationDraft, keyframesDraft.length ? keyframesDraft[keyframesDraft.length - 1].time_seconds + 1.5 : 0).toFixed(1))
    setKeyframesDraft((prev) => [
      ...prev,
      {
        id: `kf-${Date.now()}-${prev.length}`,
        time_seconds: t,
        x: 0,
        y: 0,
        scale: prev.length ? 1.12 : 1.0,
        rotation: 0,
        opacity: 1.0,
        easing: 'ease_in_out',
      },
    ])
  }

  function togglePlay() {
    const el = videoRef.current
    if (!el) return
    if (el.paused) {
      void el.play()
    } else {
      el.pause()
    }
  }

  function seekTo(seconds: number) {
    const el = videoRef.current
    if (!el) return
    const clamped = Math.max(0, Math.min(project?.settings?.duration_seconds ?? 15, seconds))
    el.currentTime = clamped
    setCurrentTime(clamped)
  }

  function toggleMutePreview() {
    const el = videoRef.current
    const next = !mutedPreview
    setMutedPreview(next)
    if (el) el.muted = next
  }

  function jumpTab(tab: 'voice' | 'media' | InspectorTab) {
    if (tab === 'voice') {
      manualCmdInputRef.current?.focus()
      voicePanelRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
      return
    }
    if (tab === 'media') {
      if (!busy && project && mediaAssets.length < 5) {
        upload.current?.click()
      }
      mediaPanelRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
      return
    }
    setActiveTab(tab)
  }

  function requestPreviewFullscreen() {
    const el = videoRef.current
    if (!el || typeof el.requestFullscreen !== 'function') return
    void el.requestFullscreen()
  }

  function toggleAudioPreview(audioId: string) {
    const el = inbuiltPreviewRef.current
    if (previewingAudioId === audioId) {
      el?.pause()
      setPreviewingAudioId(null)
      return
    }
    if (el) {
      el.src = `/api/assets-catalog/audio/${audioId}`
      void el.play().catch(() => {})
    }
    setPreviewingAudioId(audioId)
  }

  const totalDur = project?.settings?.duration_seconds ?? 15
  const audioAsset = project?.assets.find((a) => a.media_type === 'audio')
  const speechReady = caps?.speech.status === 'ready'
  const aspectChoices = Array.isArray(catalog?.aspect_ratios) && catalog.aspect_ratios.length > 0 ? catalog.aspect_ratios : ASPECT_RATIO_OPTIONS
  const currentAspectRatio = ((project?.settings?.aspect_ratio as AspectRatio | undefined) ?? aspectRatioDraft ?? '9:16') as AspectRatio
  const activeAspectInfo = aspectChoices.find((a) => a.id === currentAspectRatio) ?? ASPECT_RATIO_OPTIONS[0]
  const isLandscape = activeAspectInfo.width > activeAspectInfo.height
  const catalogAudioPacks = Array.isArray(catalog?.audio_packs) ? catalog.audio_packs : []
  const soothingPacks = catalogAudioPacks.filter((p) => p.category !== 'SFX')
  const filterChoices = Array.isArray(catalog?.filters) && catalog.filters.length > 0 ? catalog.filters : DEFAULT_FILTERS
  const transitionChoices = Array.isArray(catalog?.transitions) && catalog.transitions.length > 0 ? catalog.transitions : DEFAULT_TRANSITIONS

  return (
    <div className="studio-shell">
      <header className="studio-topbar">
        <a className="brand" href="#">
          <span className="brand-icon">
            <AudioLines size={20} />
          </span>
          SolliCut
          <span className="beta">STUDIO</span>
        </a>

        <div className="topbar-meta" aria-label="Project summary">
          <span className="topbar-aspect">
            <Film size={13} />
            <select
              aria-label="Aspect ratio"
              value={currentAspectRatio}
              disabled={busy || !project}
              onChange={(e) => {
                const next = e.target.value as AspectRatio
                setAspectRatioDraft(next)
                void applyVisualEdit({ aspect_ratio: next, render: mediaAssets.length > 0 }, `Switching format to ${next}`)
              }}
            >
              {aspectChoices.map((ar) => (
                <option key={ar.id} value={ar.id}>
                  {ar.id} · {ar.width}×{ar.height}
                </option>
              ))}
            </select>
          </span>
          <span>{totalDur}s</span>
          <span>{mediaAssets.length}/5 media</span>
          <span className={`speech-pill ${speechReady ? 'ok' : ''}`}>
            <i />
            {speechReady ? 'Local ASR ready' : caps?.speech.status === 'loading' ? 'Loading ASR…' : 'ASR unavailable'}
          </span>
        </div>

        <div className="topbar-actions">
          <button type="button" className="quiet" disabled={busy || !project?.undo_stack.length} onClick={() => void undo()}>
            <Undo2 size={15} />
            Undo
          </button>
          <button
            type="button"
            className="quiet"
            disabled={busy || !(project?.redo_stack?.length)}
            onClick={() => void redo()}
            aria-label="Redo"
          >
            <Redo2 size={15} />
            Redo
          </button>
          <button type="button" className="quiet" disabled={!project || busy} onClick={() => setResetting(true)}>
            New reel
          </button>
          <a
            className={`download ${busy || !project?.current_output ? 'disabled' : ''}`}
            aria-disabled={busy || !project?.current_output}
            href={!busy && project?.current_output ? `/api/projects/${project.id}/download` : undefined}
            download
          >
            <Download size={15} />
            Download MP4
          </a>
        </div>
      </header>

      <div className="studio-body">
        <aside className="tool-rail" aria-label="Editor tools">
          <button type="button" className="rail-btn voice-rail" onClick={() => jumpTab('voice')} title="Voice Director" aria-label="Focus Voice Director">
            <Mic size={18} />
            <span>Voice</span>
          </button>
          <button type="button" className="rail-btn" onClick={() => jumpTab('media')} title="Your media" aria-label="Focus media library">
            <FolderOpen size={18} />
            <span>Media</span>
          </button>
          <button type="button" className={`rail-btn ${activeTab === 'text' ? 'active' : ''}`} onClick={() => setActiveTab('text')} aria-label="Text overlay tools">
            <Type size={18} />
            <span>Text</span>
          </button>
          <button type="button" className={`rail-btn ${activeTab === 'audio' ? 'active' : ''}`} onClick={() => setActiveTab('audio')} aria-label="Audio and music tools">
            <Music2 size={18} />
            <span>Audio</span>
          </button>
          <button type="button" className={`rail-btn ${activeTab === 'look' ? 'active' : ''}`} onClick={() => setActiveTab('look')} aria-label="Look and format tools">
            <SlidersHorizontal size={18} />
            <span>Look</span>
          </button>
          <button type="button" className={`rail-btn ${activeTab === 'trim' ? 'active' : ''}`} onClick={() => setActiveTab('trim')} aria-label="Trim clip tools">
            <Scissors size={18} />
            <span>Trim</span>
          </button>
          <button type="button" className={`rail-btn ${activeTab === 'fx' ? 'active' : ''}`} onClick={() => setActiveTab('fx')} aria-label="Visual effects and keyframes">
            <Wand2 size={18} />
            <span>FX</span>
          </button>
          <button type="button" className={`rail-btn ${activeTab === 'assets' ? 'active' : ''}`} onClick={() => setActiveTab('assets')} aria-label="Templates and asset packs">
            <Package size={18} />
            <span>Assets</span>
          </button>
          <button type="button" className={`rail-btn ${activeTab === 'ai' ? 'active' : ''}`} onClick={() => setActiveTab('ai')} aria-label="Optional Gemini ad generator">
            <Sparkles size={18} />
            <span>AI Ad</span>
          </button>
          <button
            type="button"
            className={`rail-btn rail-bottom ${showPrivacy ? 'active' : ''}`}
            onClick={() => setShowPrivacy((v) => !v)}
            aria-label="Local processing privacy info"
          >
            <ShieldCheck size={18} />
            <span>Local</span>
          </button>
        </aside>

        <main className="studio-main">
          <div className="studio-workspace">
            <section ref={mediaPanelRef} className="media-library media-column" aria-label="Your media">
              <div className="section-heading">
                <div>
                  <h2>Your media</h2>
                  <p>1–5 photos or video clips</p>
                </div>
                <span className="count">{mediaAssets.length}/5 clips</span>
              </div>
              <input
                ref={upload}
                className="sr-only"
                type="file"
                accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
                multiple
                aria-label="Upload photos or videos"
                onChange={(e) => {
                  void filesSelected(Array.from(e.target.files ?? []))
                  e.target.value = ''
                }}
              />
              <div
                className={`photo-area ${mediaAssets.length ? 'filled' : ''}`}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault()
                  void filesSelected(Array.from(e.dataTransfer.files))
                }}
              >
                {mediaAssets.length ? (
                  <div className="photo-grid">
                    {mediaAssets.map((asset, i) => (
                      <div
                        className={`photo ${selectedClip?.id === asset.id ? 'selected' : ''}`}
                        key={asset.id}
                        onClick={() => {
                          setSelectedClipId(asset.id)
                          if (asset.media_type === 'video') setActiveTab('trim')
                        }}
                      >
                        {asset.media_type === 'video' ? (
                          <video muted preload="metadata" src={`/api/projects/${project!.id}/assets/${asset.id}`} />
                        ) : (
                          <img src={`/api/projects/${project!.id}/assets/${asset.id}`} alt={asset.filename} />
                        )}
                        <span className="clip-badge">
                          #{i + 1} · {asset.media_type === 'video' ? `${(asset.duration_seconds ?? 0).toFixed(1)}s` : 'PHOTO'}
                        </span>
                        <div className="clip-actions" onClick={(e) => e.stopPropagation()}>
                          {mediaAssets.length > 1 && (
                            <>
                              <button type="button" aria-label={`Move ${asset.filename} left`} disabled={busy || i === 0} onClick={() => void moveClip(i, -1)}>
                                <ChevronLeft size={12} />
                              </button>
                              <button
                                type="button"
                                aria-label={`Move ${asset.filename} right`}
                                disabled={busy || i === mediaAssets.length - 1}
                                onClick={() => void moveClip(i, 1)}
                              >
                                <ChevronRight size={12} />
                              </button>
                            </>
                          )}
                          <button type="button" aria-label={`Remove ${asset.filename}`} disabled={busy} onClick={() => void remove(asset.id)}>
                            <X size={12} />
                          </button>
                        </div>
                      </div>
                    ))}
                    {mediaAssets.length < 5 && (
                      <button type="button" className="add-photo" disabled={busy} onClick={() => upload.current?.click()} aria-label="Add more photos or videos">
                        <ImagePlus size={20} />
                        <span>Add media</span>
                      </button>
                    )}
                  </div>
                ) : (
                  <button type="button" className="dropzone" disabled={busy || !project} onClick={() => upload.current?.click()}>
                    <div className="upload-symbol">
                      <ImagePlus size={24} />
                    </div>
                    <strong>Drop photos or video clips here</strong>
                    <span>or click to choose from your device</span>
                    <small>Photos: JPG, PNG, WebP (up to 15 MB) · Videos: MP4, MOV, WebM (up to 100 MB)</small>
                  </button>
                )}
              </div>
              <div className="media-bin-footer">
                <div className="bin-audio-pill">
                  <Music2 size={14} />
                  <span>{audioAsset?.filename ?? 'Inbuilt music'}</span>
                  <button type="button" className="text-button" disabled={busy || !project} onClick={() => music.current?.click()}>
                    Your music
                  </button>
                  <button type="button" className="text-button" onClick={() => setActiveTab('audio')}>
                    Mix
                  </button>
                </div>
              </div>
            </section>

            <section className="stage-column" aria-label="Video preview">
              <div className="preview-stage">
                <div className="stage-header">
                  <span className="eyebrow">REEL PREVIEW</span>
                  <span className="preview-label">{project?.current_output ? `READY · REV ${project.current_render_revision}` : 'NO RENDER YET'}</span>
                </div>

                <div className="preview-canvas">
                  <div
                    className={`video-frame ${isLandscape ? 'landscape' : ''}`}
                    style={{ aspectRatio: `${activeAspectInfo.width} / ${activeAspectInfo.height}` }}
                  >
                    {project?.current_output ? (
                      <video
                        ref={videoRef}
                        key={`${project.current_render_revision}-${project.current_output}`}
                        controls
                        playsInline
                        src={`/api/projects/${project.id}/video?revision=${project.current_render_revision}`}
                        aria-label="Rendered reel preview"
                        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                        onPlay={() => setPlaying(true)}
                        onPause={() => setPlaying(false)}
                        onEnded={() => setPlaying(false)}
                      />
                    ) : (
                      <div className="empty-preview">
                        <div className="preview-art">
                          <div />
                          <div />
                          <div>
                            <Sparkles size={28} />
                          </div>
                        </div>
                        <h3>Speak it. Cut it. Sell it.</h3>
                        <p>Upload photos or video clips on the left, then speak or type your edit command.</p>
                        <span>720 × 1280 · 9:16 VERTICAL MP4</span>
                      </div>
                    )}
                    {busy && jobId && (
                      <div className="render-cover">
                        <LoaderCircle className="spin" size={32} />
                        <strong>{stage}</strong>
                        <span>Building your vertical reel on the server.</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="transport-bar" aria-label="Preview playback controls">
                  <button type="button" className="transport-btn" disabled={!project?.current_output} onClick={toggleMutePreview} aria-label={mutedPreview ? 'Unmute preview' : 'Mute preview'}>
                    {mutedPreview ? <VolumeX size={14} /> : <Volume2 size={14} />}
                  </button>
                  <button type="button" className="transport-btn" disabled={!project?.current_output} onClick={() => seekTo(0)} aria-label="Jump to start">
                    <SkipBack size={14} />
                  </button>
                  <button type="button" className="transport-btn primary-play" disabled={!project?.current_output} onClick={togglePlay} aria-label={playing ? 'Pause preview' : 'Play preview'}>
                    {playing ? <Pause size={15} /> : <Play size={15} />}
                  </button>
                  <button type="button" className="transport-btn" disabled={!project?.current_output} onClick={() => seekTo(Math.max(0, totalDur - 4))} aria-label="Jump to offer end card">
                    <SkipForward size={14} />
                  </button>
                  <input
                    type="range"
                    className="transport-scrub"
                    aria-label="Seek reel time"
                    min={0}
                    max={totalDur}
                    step={0.1}
                    value={Math.min(currentTime, totalDur)}
                    disabled={!project?.current_output}
                    onChange={(e) => seekTo(Number(e.target.value))}
                  />
                  <span className="timecode">
                    {formatTime(currentTime)} / {formatTime(totalDur)}
                  </span>
                  <button type="button" className="transport-btn" disabled={!project?.current_output} onClick={requestPreviewFullscreen} aria-label="Fullscreen preview">
                    <Maximize2 size={14} />
                  </button>
                </div>
              </div>
            </section>

            <aside className="inspector-column" aria-label="Voice director and editing inspector">
              <div ref={voicePanelRef} className="voice-card">
                <div className="section-heading">
                  <div>
                    <span className="eyebrow">VOICE DIRECTOR</span>
                    <h2>{project?.current_output ? 'What would you change?' : 'What should we create?'}</h2>
                  </div>
                  <div className="select-wrap">
                    <select aria-label="Speech language" value={language} disabled={busy} onChange={(e) => setLanguage(e.target.value)}>
                      <option value="">Auto language</option>
                      <option value="ta">Tamil / Tanglish</option>
                      <option value="en">English</option>
                    </select>
                    <ChevronDown size={14} />
                  </div>
                </div>

                <VoiceButton disabled={busy || mediaAssets.length < 1 || !speechReady} onAudio={(b, e) => void handleAudio(b, e)} onError={setError} />

                <form className="command-form" onSubmit={(e) => void applyTypedCommand(e)}>
                  <input
                    ref={manualCmdInputRef}
                    type="text"
                    className="inspector-input"
                    aria-label="Manual command input"
                    placeholder="Or type Tamil / Tanglish / English command..."
                    value={manualCommand}
                    disabled={busy || !project}
                    onChange={(e) => setManualCommand(e.target.value)}
                  />
                  <button type="submit" className="lime-button" disabled={busy || !manualCommand.trim() || !project} aria-label="Run command">
                    <Send size={14} />
                  </button>
                </form>

                <div className="status" role="status">
                  {busy ? <LoaderCircle className="spin" size={14} /> : <span className="status-dot" />}
                  {stage}
                  {mediaAssets.length < 1 && !busy ? ' · Add a photo or clip to begin' : ''}
                </div>

                {caps && caps.speech.status !== 'ready' && (
                  <div className="notice">{caps.speech.status === 'loading' ? 'Loading the local speech model…' : caps.speech.error}</div>
                )}
                {caps && !caps.renderer.available && (
                  <div className="notice">The media renderer is unavailable. Check the server setup before creating a reel.</div>
                )}

                <div className="try-saying">
                  <span>TRY SAYING</span>
                  <p>
                    {project?.current_output
                      ? '“Offer ah 25 percent nu maathu. Fade transition add pannu.”'
                      : '“Indha photos use panni 15 seconds reel create pannu. Last la 20 percent offer podu.”'}
                  </p>
                </div>

                {error && (
                  <div className="error" role="alert">
                    <span>{error}</span>
                    <button type="button" aria-label="Dismiss error" onClick={() => setError('')}>
                      <X size={16} />
                    </button>
                  </div>
                )}

                {parsed && (
                  <div className="interpretation">
                    <span className="eyebrow">{parsed.requires_clarification ? 'LET’S CLARIFY' : 'I UNDERSTOOD'}</span>
                    <blockquote>{parsed.original_transcript}</blockquote>
                    {parsed.requires_clarification ? (
                      <p>{parsed.clarification_question}</p>
                    ) : (
                      <div className="operation-list">
                        {parsed.operations.map((op) => (
                          <span key={op.id}>
                            <Check size={13} />
                            {operationLabel(op)}
                          </span>
                        ))}
                      </div>
                    )}
                    {parsed.warnings.map((w) => (
                      <p key={w} className="muted">
                        {w}
                      </p>
                    ))}
                  </div>
                )}
              </div>

              <div className="inspector-card">
                <div className="inspector-tabs" role="tablist" aria-label="Editing panels">
                  {(
                    [
                      ['text', 'A · Text'],
                      ['audio', 'Audio'],
                      ['look', 'Look'],
                      ['trim', 'Trim'],
                      ['fx', 'FX'],
                      ['assets', 'Assets'],
                      ['ai', 'AI Ad'],
                    ] as const
                  ).map(([tabId, label]) => (
                    <button
                      key={tabId}
                      type="button"
                      role="tab"
                      aria-selected={activeTab === tabId}
                      className={`inspector-tab ${activeTab === tabId ? 'active' : ''}`}
                      onClick={() => setActiveTab(tabId)}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <div className="inspector-body">
                  {activeTab === 'text' && (
                    <div className="panel-fields">
                      <div className="layer-header">
                        <span className="field-label">Text layers ({promoLayers.length})</span>
                        <button type="button" className="text-button" disabled={busy} onClick={startNewTextLayer}>
                          + New layer
                        </button>
                      </div>
                      {promoLayers.length > 0 && (
                        <div className="pill-row">
                          {promoLayers.map((layer, idx) => (
                            <button
                              key={layer.id}
                              type="button"
                              className={`pill-btn ${activeTextIdDraft === layer.id ? 'active' : ''}`}
                              onClick={() => selectTextLayer(layer.id)}
                            >
                              #{idx + 1} {layer.text.slice(0, 14)}
                            </button>
                          ))}
                        </div>
                      )}

                      <label className="field-label" htmlFor="overlay-text-input">
                        Promotional offer / title text
                      </label>
                      <input
                        id="overlay-text-input"
                        type="text"
                        maxLength={100}
                        className="inspector-input"
                        placeholder="e.g. 20 percent offer or இன்று 20% ஆஃபர்"
                        value={overlayDraft}
                        disabled={busy}
                        onChange={(e) => setOverlayDraft(e.target.value)}
                      />

                      <div className="control-group">
                        <span className="field-label">Placement</span>
                        <div className="pill-row">
                          {(
                            [
                              ['end_card', 'End card'],
                              ['bottom', 'Bottom'],
                              ['center', 'Center'],
                              ['top', 'Top'],
                            ] as const
                          ).map(([pos, label]) => (
                            <button
                              key={pos}
                              type="button"
                              className={`pill-btn ${overlayPosDraft === pos ? 'active' : ''}`}
                              disabled={busy}
                              onClick={() => setOverlayPosDraft(pos)}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="control-group">
                        <span className="field-label">Animation preset</span>
                        <div className="pill-row">
                          {(
                            [
                              ['none', 'None'],
                              ['fade', 'Fade'],
                              ['slide_up', 'Slide Up'],
                              ['pop', 'Pop'],
                            ] as const
                          ).map(([anim, label]) => (
                            <button
                              key={anim}
                              type="button"
                              className={`pill-btn ${overlayAnimDraft === anim ? 'active' : ''}`}
                              disabled={busy}
                              onClick={() => setOverlayAnimDraft(anim)}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="control-group">
                        <span className="field-label">Accent bar</span>
                        <div className="swatch-row">
                          {(
                            [
                              ['lime', '#d7ef41', 'Electric Lime'],
                              ['white', '#f5f7f4', 'Crisp White'],
                              ['amber', '#fbbf24', 'Warm Amber'],
                              ['cyan', '#3fd0e3', 'Studio Cyan'],
                              ['rose', '#f472b6', 'Festive Rose'],
                            ] as const
                          ).map(([colorKey, hex, title]) => (
                            <button
                              key={colorKey}
                              type="button"
                              aria-label={title}
                              className={`swatch ${overlayColorDraft === colorKey ? 'active' : ''}`}
                              style={{ background: hex }}
                              disabled={busy}
                              onClick={() => setOverlayColorDraft(colorKey)}
                            />
                          ))}
                        </div>
                      </div>

                      <div className="panel-actions">
                        <button
                          type="button"
                          className="quiet"
                          disabled={busy || (!project?.settings?.overlay_text && promoLayers.length === 0)}
                          onClick={() => {
                            setOverlayDraft('')
                            void applyVisualEdit(
                              { clear_overlay: true, active_text_id: activeTextIdDraft === '__new__' ? undefined : activeTextIdDraft, render: mediaAssets.length > 0 },
                              'Removing text overlay',
                            )
                          }}
                        >
                          Clear
                        </button>
                        <button
                          type="button"
                          className="lime-button flex-1"
                          disabled={busy || mediaAssets.length < 1 || !overlayDraft.trim()}
                          onClick={() =>
                            void applyVisualEdit(
                              {
                                overlay_text: overlayDraft.trim(),
                                overlay_position: overlayPosDraft,
                                overlay_color: overlayColorDraft,
                                overlay_animation: overlayAnimDraft,
                                active_text_id: activeTextIdDraft === '__new__' ? `txt-${Date.now()}` : activeTextIdDraft,
                                render: true,
                              },
                              'Updating text overlay',
                            )
                          }
                        >
                          Apply text
                        </button>
                      </div>

                      <div className="subpanel-divider" />

                      <div className="layer-header">
                        <span className="field-label">Auto-Captions (Local ASR)</span>
                        <button type="button" className="quiet" disabled={busy || !speechReady || mediaAssets.length < 1} onClick={() => void runAutoCaptions()}>
                          Auto-captions
                        </button>
                      </div>
                      {captionLayers.length > 0 && (
                        <div className="caption-list">
                          {captionLayers.map((cap) => (
                            <div key={cap.id} className="caption-item">
                              <input
                                type="text"
                                className="inspector-input"
                                value={cap.text}
                                disabled={busy}
                                onChange={(e) => {
                                  const nextText = e.target.value
                                  const updated = (project?.settings?.text_layers ?? []).map((l) =>
                                    l.id === cap.id ? { ...l, text: nextText } : l,
                                  )
                                  setProject((prev) => (prev ? { ...prev, settings: { ...prev.settings, text_layers: updated } } : prev))
                                }}
                              />
                              <button
                                type="button"
                                className="quiet"
                                disabled={busy}
                                onClick={() => void applyVisualEdit({ text_layers: project?.settings?.text_layers ?? [], render: mediaAssets.length > 0 }, 'Updating captions')}
                              >
                                Save
                              </button>
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="subpanel-divider" />

                      <span className="field-label">Offline TTS Narration ({caps?.tts?.backend ?? 'local'})</span>
                      <div className="caption-item">
                        <input
                          type="text"
                          className="inspector-input"
                          placeholder="Speak text aloud in Tamil or English..."
                          value={ttsText}
                          disabled={busy}
                          onChange={(e) => setTtsText(e.target.value)}
                        />
                        <select className="compact-select" aria-label="TTS language" value={ttsLang} onChange={(e) => setTtsLang(e.target.value as 'en' | 'ta')}>
                          <option value="en">EN</option>
                          <option value="ta">TA</option>
                        </select>
                      </div>
                      <button
                        type="button"
                        className="quiet full-btn"
                        disabled={busy || !ttsText.trim() || !caps?.tts?.available}
                        onClick={() => void runTTS()}
                      >
                        Generate &amp; attach voiceover
                      </button>
                    </div>
                  )}

                  {activeTab === 'audio' && (
                    <div className="panel-fields">
                      <div className="toggle-row">
                        <div>
                          <strong>Background music</strong>
                          <span>{audioAsset?.filename ?? 'Inbuilt music'}</span>
                        </div>
                        <input type="checkbox" aria-label="Enable background music" checked={musicEnabledDraft} disabled={busy} onChange={(e) => setMusicEnabledDraft(e.target.checked)} />
                      </div>
                      <div className="control-group">
                        <label className="field-label" htmlFor="bgm-vol">
                          Music volume: {Math.round(musicVolDraft * 100)}%
                        </label>
                        <input id="bgm-vol" type="range" min={0} max={1} step={0.05} value={musicVolDraft} disabled={busy || !musicEnabledDraft} onChange={(e) => setMusicVolDraft(Number(e.target.value))} />
                      </div>
                      <div className="music-row">
                        <Music2 size={15} />
                        <span>{audioAsset?.filename ?? 'Inbuilt music included'}</span>
                        <button type="button" className="text-button" disabled={busy || !project} onClick={() => music.current?.click()}>
                          Your music
                        </button>
                        {audioAsset && (
                          <button type="button" className="text-button" disabled={busy} onClick={() => void remove(audioAsset.id)}>
                            Remove
                          </button>
                        )}
                        <input
                          className="sr-only"
                          ref={music}
                          type="file"
                          accept="audio/mpeg,audio/wav,audio/mp4,audio/ogg"
                          aria-label="Upload background music"
                          onChange={(e) => {
                            void filesSelected(Array.from(e.target.files ?? []), true)
                            e.target.value = ''
                          }}
                        />
                      </div>
                      {soothingPacks.length > 0 && (
                        <div className="control-group">
                          <span className="field-label">Inbuilt soothing music ({soothingPacks.filter((p) => p.category === 'Soothing').length} CC0 tracks)</span>
                          <div className="caption-item">
                            <select
                              className="compact-select inbuilt-select"
                              aria-label="Inbuilt soothing music"
                              value={selectedInbuiltAudioId}
                              disabled={busy}
                              onChange={(e) => setSelectedInbuiltAudioId(e.target.value)}
                            >
                              {soothingPacks.map((pack) => (
                                <option key={pack.id} value={pack.id}>
                                  {pack.name} · {Math.round(pack.duration_seconds)}s
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              className="quiet"
                              aria-label={previewingAudioId === selectedInbuiltAudioId ? 'Stop preview track' : 'Preview soothing track'}
                              onClick={() => toggleAudioPreview(selectedInbuiltAudioId)}
                            >
                              {previewingAudioId === selectedInbuiltAudioId ? <Pause size={13} /> : <Play size={13} />}
                            </button>
                            <button
                              type="button"
                              className="quiet"
                              disabled={busy || !project}
                              onClick={() => {
                                inbuiltPreviewRef.current?.pause()
                                setPreviewingAudioId(null)
                                void attachCatalogAudio(selectedInbuiltAudioId)
                              }}
                            >
                              Use track
                            </button>
                          </div>
                        </div>
                      )}
                      <div className="toggle-row">
                        <div>
                          <strong>Original video clip audio</strong>
                          <span>Keep audio from uploaded video clips</span>
                        </div>
                        <input type="checkbox" aria-label="Keep original video clip audio" checked={clipAudioDraft} disabled={busy} onChange={(e) => setClipAudioDraft(e.target.checked)} />
                      </div>
                      {clipAudioDraft && (
                        <div className="control-group">
                          <label className="field-label" htmlFor="clip-vol">
                            Clip audio volume: {Math.round(clipVolDraft * 100)}%
                          </label>
                          <input id="clip-vol" type="range" min={0} max={1} step={0.05} value={clipVolDraft} disabled={busy} onChange={(e) => setClipVolDraft(Number(e.target.value))} />
                        </div>
                      )}

                      <div className="subpanel-divider" />
                      <span className="field-label">Audio Enhancement &amp; Isolation</span>
                      <div className="toggle-row">
                        <div>
                          <strong>Noise reduction</strong>
                          <span>FFmpeg FFT denoise filter</span>
                        </div>
                        <input type="checkbox" aria-label="Noise reduction" checked={denoiseDraft} disabled={busy} onChange={(e) => setDenoiseDraft(e.target.checked)} />
                      </div>
                      <div className="toggle-row">
                        <div>
                          <strong>Loudness normalize</strong>
                          <span>EBU R128 (-16 LUFS) auto-gain</span>
                        </div>
                        <input type="checkbox" aria-label="Loudness normalize" checked={normalizeDraft} disabled={busy} onChange={(e) => setNormalizeDraft(e.target.checked)} />
                      </div>
                      <div className="toggle-row">
                        <div>
                          <strong>Voice enhance</strong>
                          <span>Speech presence EQ + compressor</span>
                        </div>
                        <input type="checkbox" aria-label="Voice enhance" checked={voiceEnhanceDraft} disabled={busy} onChange={(e) => setVoiceEnhanceDraft(e.target.checked)} />
                      </div>
                      <div className="control-group">
                        <span className="field-label">Vocal isolation</span>
                        <div className="pill-row">
                          {(
                            [
                              ['none', 'Full Mix'],
                              ['vocals_only', 'Vocals Only'],
                              ['music_only', 'Music Bed'],
                            ] as const
                          ).map(([mode, label]) => (
                            <button key={mode} type="button" className={`pill-btn ${vocalIsoDraft === mode ? 'active' : ''}`} disabled={busy} onClick={() => setVocalIsoDraft(mode)}>
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                      {project?.settings?.narration_asset_id && (
                        <div className="toggle-row">
                          <div>
                            <strong>TTS Narration ({Math.round(narrationVolDraft * 100)}%)</strong>
                            <span>Include generated voiceover</span>
                          </div>
                          <input type="checkbox" aria-label="Enable TTS narration" checked={narrationEnabledDraft} disabled={busy} onChange={(e) => setNarrationEnabledDraft(e.target.checked)} />
                        </div>
                      )}

                      <button
                        type="button"
                        className="lime-button full-btn"
                        disabled={busy || mediaAssets.length < 1}
                        onClick={() =>
                          void applyVisualEdit(
                            {
                              music_enabled: musicEnabledDraft,
                              music_volume: musicVolDraft,
                              keep_clip_audio: clipAudioDraft,
                              clip_audio_volume: clipVolDraft,
                              audio_denoise: denoiseDraft,
                              audio_normalize: normalizeDraft,
                              voice_enhance: voiceEnhanceDraft,
                              vocal_isolation: vocalIsoDraft,
                              narration_enabled: narrationEnabledDraft,
                              narration_volume: narrationVolDraft,
                              render: true,
                            },
                            'Updating audio mix',
                          )
                        }
                      >
                        Apply audio
                      </button>
                    </div>
                  )}

                  {activeTab === 'look' && (
                    <div className="panel-fields">
                      <div className="control-group">
                        <span className="field-label">Aspect ratio &amp; resolution</span>
                        <div className="pill-row">
                          {aspectChoices.map((ar) => (
                            <button
                              key={ar.id}
                              type="button"
                              className={`pill-btn ${aspectRatioDraft === ar.id ? 'active' : ''}`}
                              disabled={busy}
                              onClick={() => setAspectRatioDraft(ar.id)}
                            >
                              {ar.id} ({ar.width}×{ar.height})
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="control-group">
                        <label className="field-label" htmlFor="reel-dur">
                          Reel duration: {durationDraft}s
                        </label>
                        <input id="reel-dur" type="range" min={3} max={30} step={1} value={durationDraft} disabled={busy} onChange={(e) => setDurationDraft(Number(e.target.value))} />
                      </div>
                      <div className="toggle-row">
                        <div>
                          <strong>Smooth photo zoom</strong>
                          <span>Gentle Ken Burns motion on still photos</span>
                        </div>
                        <input type="checkbox" aria-label="Smooth photo zoom" checked={zoomDraft === 'smooth'} disabled={busy} onChange={(e) => setZoomDraft(e.target.checked ? 'smooth' : 'none')} />
                      </div>
                      <div className="control-group">
                        <label className="field-label" htmlFor="look-bright">
                          Brightness: {brightnessDraft > 0 ? `+${Math.round(brightnessDraft * 100)}%` : `${Math.round(brightnessDraft * 100)}%`}
                        </label>
                        <input id="look-bright" type="range" min={-0.3} max={0.3} step={0.05} value={brightnessDraft} disabled={busy} onChange={(e) => setBrightnessDraft(Number(e.target.value))} />
                      </div>
                      <div className="control-group">
                        <span className="field-label">Framing</span>
                        <div className="pill-row">
                          <button type="button" className={`pill-btn ${fitDraft === 'contain' ? 'active' : ''}`} disabled={busy} onClick={() => setFitDraft('contain')}>
                            Fit frame
                          </button>
                          <button type="button" className={`pill-btn ${fitDraft === 'cover' ? 'active' : ''}`} disabled={busy} onClick={() => setFitDraft('cover')}>
                            Fill {aspectRatioDraft}
                          </button>
                        </div>
                      </div>
                      <div className="control-group">
                        <span className="field-label">Color Filter</span>
                        <div className="pill-row">
                          {filterChoices.map((f) => (
                            <button key={f.id} type="button" className={`pill-btn ${filterDraft === f.id ? 'active' : ''}`} disabled={busy} onClick={() => setFilterDraft(f.id)}>
                              {f.label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="control-group">
                        <span className="field-label">Clip Transition</span>
                        <div className="pill-row">
                          {transitionChoices.map((t) => (
                            <button key={t.id} type="button" className={`pill-btn ${transitionDraft === t.id ? 'active' : ''}`} disabled={busy} onClick={() => setTransitionDraft(t.id)}>
                              {t.label}
                            </button>
                          ))}
                        </div>
                      </div>
                      {transitionDraft !== 'none' && (
                        <div className="control-group">
                          <label className="field-label" htmlFor="trans-dur">
                            Transition duration: {transitionDurDraft.toFixed(1)}s
                          </label>
                          <input id="trans-dur" type="range" min={0.2} max={1.5} step={0.1} value={transitionDurDraft} disabled={busy} onChange={(e) => setTransitionDurDraft(Number(e.target.value))} />
                        </div>
                      )}
                      <div className="control-group">
                        <span className="field-label">Global Speed Curve</span>
                        <div className="pill-row">
                          {(
                            [
                              ['normal', '1.0x Normal'],
                              ['slow_mo', '0.5x Slow Mo'],
                              ['fast', '2.0x Fast'],
                            ] as const
                          ).map(([sc, label]) => (
                            <button key={sc} type="button" className={`pill-btn ${speedCurveDraft === sc ? 'active' : ''}`} disabled={busy} onClick={() => setSpeedCurveDraft(sc)}>
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="lime-button full-btn"
                        disabled={busy || mediaAssets.length < 1}
                        onClick={() =>
                          void applyVisualEdit(
                            {
                              aspect_ratio: aspectRatioDraft,
                              duration_seconds: durationDraft,
                              zoom_style: zoomDraft,
                              brightness: brightnessDraft,
                              fit_mode: fitDraft,
                              filter_preset: filterDraft,
                              transition_style: transitionDraft,
                              transition_duration: transitionDurDraft,
                              speed_curve: speedCurveDraft,
                              render: true,
                            },
                            'Rendering updated look',
                          )
                        }
                      >
                        Apply look
                      </button>
                    </div>
                  )}

                  {activeTab === 'trim' && (
                    <div className="panel-fields">
                      {selectedClip ? (
                        <>
                          <div className="selected-clip-summary">
                            <strong>{selectedClip.filename}</strong>
                            <span>{selectedClip.media_type === 'video' ? `Length: ${(selectedClip.duration_seconds ?? 0).toFixed(1)}s` : 'Photo clip'}</span>
                          </div>
                          {selectedClip.media_type === 'video' ? (
                            <>
                              <div className="control-group">
                                <label className="field-label" htmlFor="trim-start">
                                  Start trim: {trimStartDraft.toFixed(1)}s
                                </label>
                                <input
                                  id="trim-start"
                                  type="range"
                                  min={0}
                                  max={Math.max(0, (selectedClip.duration_seconds ?? 1) - 0.3)}
                                  step={0.1}
                                  value={trimStartDraft}
                                  disabled={busy}
                                  onChange={(e) => {
                                    const val = Number(e.target.value)
                                    setTrimStartDraft(val)
                                    if (trimEndDraft <= val + 0.2) {
                                      setTrimEndDraft(Math.min(selectedClip.duration_seconds ?? val + 0.5, val + 0.3))
                                    }
                                  }}
                                />
                              </div>
                              <div className="control-group">
                                <label className="field-label" htmlFor="trim-end">
                                  End trim: {trimEndDraft.toFixed(1)}s
                                </label>
                                <input
                                  id="trim-end"
                                  type="range"
                                  min={Math.min(selectedClip.duration_seconds ?? 1, trimStartDraft + 0.2)}
                                  max={selectedClip.duration_seconds ?? 10}
                                  step={0.1}
                                  value={trimEndDraft}
                                  disabled={busy}
                                  onChange={(e) => setTrimEndDraft(Number(e.target.value))}
                                />
                              </div>
                              <div className="panel-actions">
                                <button
                                  type="button"
                                  className="quiet"
                                  disabled={busy}
                                  onClick={() => {
                                    setTrimStartDraft(0)
                                    setTrimEndDraft(selectedClip.duration_seconds ?? 5)
                                    void applyVisualEdit(
                                      {
                                        trim_asset_id: selectedClip.id,
                                        trim_start: 0,
                                        trim_end: selectedClip.duration_seconds ?? 5,
                                        render: Boolean(project?.current_output),
                                      },
                                      'Resetting clip trim',
                                    )
                                  }}
                                >
                                  Reset
                                </button>
                                <button
                                  type="button"
                                  className="lime-button flex-1"
                                  disabled={busy}
                                  onClick={() =>
                                    void applyVisualEdit(
                                      {
                                        trim_asset_id: selectedClip.id,
                                        trim_start: trimStartDraft,
                                        trim_end: trimEndDraft,
                                        clip_asset_id: selectedClip.id,
                                        clip_speed: clipSpeedDraft,
                                        clip_volume: clipOwnVolDraft,
                                        render: true,
                                      },
                                      'Trimming video clip',
                                    )
                                  }
                                >
                                  Apply trim
                                </button>
                              </div>

                              <div className="subpanel-divider" />
                              <div className="control-group">
                                <label className="field-label" htmlFor="split-at">
                                  Split clip at ({splitAtDraft.toFixed(1)}s)
                                </label>
                                <div className="caption-item">
                                  <input
                                    id="split-at"
                                    type="number"
                                    step={0.1}
                                    min={0.2}
                                    max={Math.max(0.4, (selectedClip.duration_seconds ?? 2) - 0.2)}
                                    className="inspector-input"
                                    value={splitAtDraft}
                                    disabled={busy || mediaAssets.length >= 5}
                                    onChange={(e) => setSplitAtDraft(Number(e.target.value))}
                                  />
                                  <button
                                    type="button"
                                    className="quiet"
                                    disabled={busy || mediaAssets.length >= 5}
                                    onClick={() =>
                                      void applyVisualEdit(
                                        { split_asset_id: selectedClip.id, split_at_seconds: splitAtDraft, render: Boolean(project?.current_output) },
                                        'Splitting clip',
                                      )
                                    }
                                  >
                                    Split
                                  </button>
                                </div>
                              </div>
                            </>
                          ) : (
                            <p className="muted-box">Photos animate across their timeline slot. Adjust speed or switch to FX for keyframes &amp; cutouts.</p>
                          )}

                          <div className="control-group">
                            <label className="field-label" htmlFor="clip-speed">
                              Clip speed: {clipSpeedDraft.toFixed(2)}x
                            </label>
                            <input id="clip-speed" type="range" min={0.25} max={4.0} step={0.25} value={clipSpeedDraft} disabled={busy} onChange={(e) => setClipSpeedDraft(Number(e.target.value))} />
                          </div>
                          {selectedClip.media_type === 'video' && (
                            <div className="control-group">
                              <label className="field-label" htmlFor="clip-own-vol">
                                Clip volume: {Math.round(clipOwnVolDraft * 100)}%
                              </label>
                              <input id="clip-own-vol" type="range" min={0} max={2.0} step={0.1} value={clipOwnVolDraft} disabled={busy} onChange={(e) => setClipOwnVolDraft(Number(e.target.value))} />
                            </div>
                          )}
                          {selectedClip.media_type === 'image' && (
                            <button
                              type="button"
                              className="lime-button full-btn"
                              disabled={busy}
                              onClick={() =>
                                void applyVisualEdit({ clip_asset_id: selectedClip.id, clip_speed: clipSpeedDraft, render: true }, 'Updating clip speed')
                              }
                            >
                              Apply clip speed
                            </button>
                          )}
                        </>
                      ) : (
                        <p className="muted-box">Upload and select a photo or video clip in Your media to trim, split, or adjust speed.</p>
                      )}
                    </div>
                  )}

                  {activeTab === 'fx' && (
                    <div className="panel-fields">
                      {selectedClip ? (
                        <>
                          <div className="selected-clip-summary">
                            <strong>{selectedClip.filename}</strong>
                            <span>Cutout: {caps?.cutout?.backend ?? 'opencv_grabcut'}</span>
                          </div>
                          <div className="control-group">
                            <span className="field-label">Background Cutout / Chroma Key</span>
                            <div className="pill-row">
                              {(
                                [
                                  ['none', 'None'],
                                  ['auto_cutout', 'Auto Cutout'],
                                  ['chroma_key', 'Chroma Key'],
                                ] as const
                              ).map(([mode, label]) => (
                                <button key={mode} type="button" className={`pill-btn ${cutoutDraft === mode ? 'active' : ''}`} disabled={busy} onClick={() => setCutoutDraft(mode)}>
                                  {label}
                                </button>
                              ))}
                            </div>
                          </div>
                          {cutoutDraft === 'chroma_key' && (
                            <div className="panel-fields">
                              <div className="caption-item">
                                <input type="text" className="inspector-input" aria-label="Chroma key color" value={chromaColorDraft} disabled={busy} onChange={(e) => setChromaColorDraft(e.target.value)} />
                                <input type="range" min={0.05} max={0.55} step={0.05} value={chromaSimDraft} disabled={busy} onChange={(e) => setChromaSimDraft(Number(e.target.value))} />
                              </div>
                            </div>
                          )}
                          {selectedClip.media_type === 'video' && (
                            <div className="toggle-row">
                              <div>
                                <strong>Video stabilize</strong>
                                <span>FFmpeg deshake motion smoothing</span>
                              </div>
                              <input type="checkbox" aria-label="Video stabilize" checked={stabilizeDraft} disabled={busy} onChange={(e) => setStabilizeDraft(e.target.checked)} />
                            </div>
                          )}
                          <div className="control-group">
                            <label className="field-label" htmlFor="relight-slider">
                              Relight exposure: {relightDraft > 0 ? `+${Math.round(relightDraft * 100)}%` : `${Math.round(relightDraft * 100)}%`}
                            </label>
                            <input id="relight-slider" type="range" min={-0.5} max={0.5} step={0.05} value={relightDraft} disabled={busy} onChange={(e) => setRelightDraft(Number(e.target.value))} />
                          </div>

                          <div className="subpanel-divider" />
                          <div className="layer-header">
                            <span className="field-label">Keyframes ({keyframesDraft.length})</span>
                            <button type="button" className="text-button" disabled={busy} onClick={addKeyframe}>
                              <Plus size={12} /> Add keyframe
                            </button>
                          </div>
                          {keyframesDraft.map((kfItem, idx) => (
                            <div key={kfItem.id} className="kf-row">
                              <span>@{kfItem.time_seconds}s</span>
                              <label>
                                Scale
                                <input
                                  type="number"
                                  step={0.1}
                                  min={0.3}
                                  max={2.5}
                                  value={kfItem.scale}
                                  onChange={(e) =>
                                    setKeyframesDraft((prev) => prev.map((k, kIdx) => (kIdx === idx ? { ...k, scale: Number(e.target.value) } : k)))
                                  }
                                />
                              </label>
                              <label>
                                Rot°
                                <input
                                  type="number"
                                  step={5}
                                  min={-180}
                                  max={180}
                                  value={kfItem.rotation}
                                  onChange={(e) =>
                                    setKeyframesDraft((prev) => prev.map((k, kIdx) => (kIdx === idx ? { ...k, rotation: Number(e.target.value) } : k)))
                                  }
                                />
                              </label>
                              <button type="button" className="quiet" onClick={() => setKeyframesDraft((prev) => prev.filter((_, kIdx) => kIdx !== idx))}>
                                <X size={12} />
                              </button>
                            </div>
                          ))}

                          <button
                            type="button"
                            className="lime-button full-btn"
                            disabled={busy}
                            onClick={() =>
                              void applyVisualEdit(
                                {
                                  clip_asset_id: selectedClip.id,
                                  clip_cutout_mode: cutoutDraft,
                                  clip_chroma_color: chromaColorDraft,
                                  clip_chroma_similarity: chromaSimDraft,
                                  clip_stabilize: stabilizeDraft,
                                  clip_relight: relightDraft,
                                  clip_keyframes: keyframesDraft,
                                  render: true,
                                },
                                'Applying visual FX',
                              )
                            }
                          >
                            Apply FX &amp; keyframes
                          </button>
                        </>
                      ) : (
                        <p className="muted-box">Upload and select a photo or video clip to apply cutout, chroma key, stabilization, relight, or keyframes.</p>
                      )}
                    </div>
                  )}

                  {activeTab === 'assets' && (
                    <div className="panel-fields">
                      <span className="field-label">Sticker Badge Overlay</span>
                      <div className="pill-row">
                        {(catalog?.stickers ?? [
                          { id: 'none', label: 'None' },
                          { id: 'sale', label: 'SALE' },
                          { id: 'new', label: 'NEW' },
                          { id: 'top_pick', label: 'TOP PICK' },
                          { id: 'tamil_special', label: 'சிறப்பு' },
                        ]).map((st) => (
                          <button
                            key={st.id}
                            type="button"
                            className={`pill-btn ${(project?.settings?.sticker_badge ?? 'none') === st.id ? 'active' : ''}`}
                            disabled={busy || mediaAssets.length < 1}
                            onClick={() =>
                              void applyVisualEdit({ sticker_badge: st.id as StickerBadge, render: Boolean(project?.current_output) }, 'Updating sticker')
                            }
                          >
                            {st.label}
                          </button>
                        ))}
                      </div>

                      <div className="subpanel-divider" />
                      <span className="field-label">Editable Reel Templates</span>
                      <div className="catalog-list">
                        {(catalog?.templates ?? []).map((tpl) => (
                          <div key={tpl.id} className="catalog-card">
                            <div>
                              <strong>{tpl.name}</strong>
                              <span>{tpl.description}</span>
                            </div>
                            <button type="button" className="quiet" disabled={busy || mediaAssets.length < 1} onClick={() => void applyTemplate(tpl.id)}>
                              Apply
                            </button>
                          </div>
                        ))}
                      </div>

                      <div className="subpanel-divider" />
                      <span className="field-label">Inbuilt Soothing Music &amp; SFX (CC0 / Local)</span>
                      <div className="catalog-list">
                        {catalogAudioPacks.map((pack) => (
                          <div key={pack.id} className="catalog-card">
                            <div>
                              <strong>{pack.name}</strong>
                              <span>{pack.category} · {pack.duration_seconds}s · {pack.license}</span>
                            </div>
                            <div className="catalog-actions">
                              <button
                                type="button"
                                className="quiet"
                                aria-label={previewingAudioId === pack.id ? `Stop ${pack.name}` : `Preview ${pack.name}`}
                                onClick={() => toggleAudioPreview(pack.id)}
                              >
                                {previewingAudioId === pack.id ? <Pause size={12} /> : <Play size={12} />}
                              </button>
                              <button
                                type="button"
                                className="quiet"
                                disabled={busy || !project}
                                onClick={() => {
                                  inbuiltPreviewRef.current?.pause()
                                  setPreviewingAudioId(null)
                                  void attachCatalogAudio(pack.id)
                                }}
                              >
                                Use
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="notice">
                        <Layers size={13} /> <strong>Stock Video:</strong> {catalog?.stock_video?.note ?? 'Deferred (P2+) for 100% offline/no-copyright editing.'}
                      </div>
                    </div>
                  )}

                  {activeTab === 'ai' && project && (
                    <GeneratePanel
                      project={project}
                      caps={caps}
                      busy={busy}
                      languageHint={language}
                      onJobStarted={(id, st) => {
                        setBusy(true)
                        setStage(st)
                        setJobId(id)
                      }}
                    />
                  )}
                </div>
              </div>
            </aside>
          </div>

          {project && (
            <Timeline
              project={project}
              mediaAssets={mediaAssets}
              selectedClipId={selectedClip?.id ?? null}
              currentTime={currentTime}
              busy={busy}
              onSelectClip={(id) => {
                setSelectedClipId(id)
                const item = mediaAssets.find((a) => a.id === id)
                if (item?.media_type === 'video') setActiveTab('trim')
              }}
              onMoveClip={(i, delta) => void moveClip(i, delta)}
              onReorderIds={(ids) => void reorderClipIds(ids)}
              onSelectTextLayer={(id) => selectTextLayer(id)}
              onAddMedia={() => upload.current?.click()}
              onToggleMusicMute={() =>
                void applyVisualEdit(
                  { music_enabled: !project.settings.music_enabled, render: Boolean(project.current_output) },
                  project.settings.music_enabled ? 'Muting background music' : 'Enabling background music',
                )
              }
              onJumpTab={jumpTab}
              onSeek={seekTo}
            />
          )}

          {showPrivacy && (
            <div className="local-note-banner">
              <ShieldCheck size={16} />
              <span>
                Your uploaded media, voice commands, TTS, and visual effects run locally on this SolliCut server. No cloud AI API is required for core editing.
              </span>
            </div>
          )}

          <footer>
            <span>Processed by this SolliCut server · Keyless core editing</span>
            <span>Tamil · Tanglish · English</span>
            <span>Livelihoods &amp; small business</span>
          </footer>
        </main>
      </div>

      <audio ref={inbuiltPreviewRef} className="sr-only" onEnded={() => setPreviewingAudioId(null)} />
      {resetting && (
        <div className="modal-backdrop">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="reset-title">
            <Trash2 size={26} />
            <h2 id="reset-title">Start a fresh reel?</h2>
            <p>
              This deletes this project’s photos, videos, recordings and rendered videos from the server. Download your reel first if you want to keep it.
            </p>
            <div>
              <button type="button" className="quiet" onClick={() => setResetting(false)}>
                Keep editing
              </button>
              <button type="button" className="danger" disabled={busy} onClick={() => void reset()}>
                Delete and start fresh
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
