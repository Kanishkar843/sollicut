import { useEffect, useRef, useState } from 'react'
import {
  AudioLines,
  ChevronLeft,
  ChevronRight,
  Download,
  Film,
  FolderOpen,
  ImagePlus,
  LoaderCircle,
  Maximize2,
  Mic,
  Music2,
  Pause,
  Play,
  Scissors,
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
  X,
} from 'lucide-react'
import GeneratePanel from './GeneratePanel'
import Timeline from './Timeline'
import VoiceButton from './VoiceButton'
import { TranscriptReview } from './components/voice/TranscriptReview'
import { MicrophoneSettings } from './components/voice/MicrophoneSettings'
import { api, type AsrMode, type Capabilities, type Command, type Project } from './api'

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

// Keep alias for compatibility with any existing imports.
export const validatePhotos = validateMedia

type InspectorTab = 'text' | 'audio' | 'look' | 'trim' | 'ai'

function formatTime(sec: number): string {
  const s = Math.max(0, sec)
  const mins = Math.floor(s / 60)
  const rem = (s % 60).toFixed(1).padStart(4, '0')
  return `${String(mins).padStart(2, '0')}:${rem}`
}

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [caps, setCaps] = useState<Capabilities | null>(null)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState('Ready')
  const [error, setError] = useState('')
  const [asrMode, setAsrMode] = useState<AsrMode>('tanglish')
  const [resetting, setResetting] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<InspectorTab>('text')
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null)
  const [showPrivacy, setShowPrivacy] = useState(false)
  // Phase 8: pending voice command awaiting explicit user approval
  const [pendingResult, setPendingResult] = useState<Command | null>(null)
  const [applyingResult, setApplyingResult] = useState(false)
  const [showMicSettings, setShowMicSettings] = useState(false)
  const [micDeviceId, setMicDeviceId] = useState('')

  // Video preview transport state
  const [playing, setPlaying] = useState(false)
  const [mutedPreview, setMutedPreview] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)

  // Inspector draft fields synced with project settings
  const [overlayDraft, setOverlayDraft] = useState('')
  const [overlayPosDraft, setOverlayPosDraft] = useState<'end_card' | 'bottom' | 'center'>('end_card')
  const [overlayColorDraft, setOverlayColorDraft] = useState<'lime' | 'white' | 'amber'>('lime')
  const [durationDraft, setDurationDraft] = useState(15)
  const [zoomDraft, setZoomDraft] = useState<'smooth' | 'none'>('smooth')
  const [brightnessDraft, setBrightnessDraft] = useState(0)
  const [fitDraft, setFitDraft] = useState<'contain' | 'cover'>('contain')
  const [musicEnabledDraft, setMusicEnabledDraft] = useState(true)
  const [musicVolDraft, setMusicVolDraft] = useState(0.2)
  const [clipAudioDraft, setClipAudioDraft] = useState(false)
  const [clipVolDraft, setClipVolDraft] = useState(0.7)
  const [trimStartDraft, setTrimStartDraft] = useState(0)
  const [trimEndDraft, setTrimEndDraft] = useState(0)

  const initial = useRef<Promise<Project> | null>(null)
  const upload = useRef<HTMLInputElement>(null)
  const music = useRef<HTMLInputElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const voicePanelRef = useRef<HTMLDivElement>(null)
  const mediaPanelRef = useRef<HTMLElement>(null)

  const mediaAssets = project?.assets.filter((a) => a.media_type !== 'audio') ?? []
  const selectedClip = mediaAssets.find((a) => a.id === selectedClipId) ?? mediaAssets[0] ?? null

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
    setOverlayDraft(s?.overlay_text ?? '')
    setOverlayPosDraft(s?.overlay_position ?? 'end_card')
    setOverlayColorDraft(s?.overlay_color ?? 'lime')
    setDurationDraft(s?.duration_seconds ?? 15)
    setZoomDraft(s?.zoom_style ?? 'smooth')
    setBrightnessDraft(s?.brightness ?? 0)
    setFitDraft(s?.fit_mode ?? 'contain')
    setMusicEnabledDraft(s?.music_enabled ?? true)
    setMusicVolDraft(s?.music_volume ?? 0.2)
    setClipAudioDraft(s?.keep_clip_audio ?? false)
    setClipVolDraft(s?.clip_audio_volume ?? 0.7)
    const firstMedia = project.assets.find((a) => a.media_type !== 'audio')
    if (!selectedClipId || !project.assets.some((a) => a.id === selectedClipId)) {
      setSelectedClipId(firstMedia?.id ?? null)
    }
  }, [project])

  useEffect(() => {
    if (!selectedClip || selectedClip.media_type !== 'video') return
    setTrimStartDraft(selectedClip.trim_start ?? 0)
    setTrimEndDraft(selectedClip.trim_end ?? selectedClip.duration_seconds ?? 5)
  }, [selectedClip?.id, selectedClip?.trim_start, selectedClip?.trim_end, selectedClip?.duration_seconds])

  useEffect(() => {
    if (!jobId || !project) return
    let live = true
    const poll = async () => {
      try {
        const job = await api<{ status: string; stage: string; error?: string }>(`/jobs/${jobId}`)
        if (!live) return
        setStage(job.stage)
        if (job.status === 'done') {
          const p = await api<Project>(`/projects/${project.id}`)
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
      }
    }
    void poll()
    const timer = setInterval(poll, 1000)
    return () => {
      live = false
      clearInterval(timer)
    }
  }, [jobId, project?.id])

  async function filesSelected(files: File[], audio = false) {
    if (!project || busy) return
    const validation = audio ? null : validateMedia(files, mediaAssets.length)
    if (validation) {
      setError(validation)
      return
    }
    setError('')
    setBusy(true)
    setStage('Uploading your media')
    try {
      let latest = project
      for (const file of files) {
        const form = new FormData()
        form.append('file', file)
        latest = await api<Project>(`/projects/${project.id}/assets`, { method: 'POST', body: form })
        setProject(latest)
      }
      setStage('Ready')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function handleVoiceResult(result: Command) {
    // Phase 8: Store result for user review; do NOT auto-apply operations.
    setBusy(false)
    if (result.parsed_command.requires_clarification) {
      setStage('A little more detail')
      setPendingResult(result)
    } else {
      setStage('Review and apply')
      setPendingResult(result)
    }
  }

  /**
   * Phase 8 — Called when user clicks "Apply" / "Apply all" in TranscriptReview.
   * Executes the previewed or edited transcript on the server.
   */
  async function applyPendingResult(result: Command, editedTranscript?: string) {
    if (!project) return
    setApplyingResult(true)
    setBusy(true)
    setError('')
    try {
      let executed = result
      if (editedTranscript || (!result.job_id && !result.project && !result.download_url)) {
        setStage('Applying voice command')
        const useDual = !editedTranscript && Boolean(result.secondary_transcript)
        executed = await api<Command>(`/projects/${project.id}/apply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            transcript: editedTranscript ?? result.parsed_command.original_transcript,
            ...(useDual
              ? {
                  secondary_transcript: result.secondary_transcript,
                  asr_mode: result.asr_mode ?? asrMode,
                }
              : {}),
          }),
        })
      }

      if (executed.parsed_command.requires_clarification) {
        setPendingResult(executed)
        setStage('A little more detail')
        setBusy(false)
        return
      }

      setPendingResult(null)
      if (executed.job_id) {
        setStage('Rendering reel')
        setJobId(executed.job_id)
      } else {
        if (executed.project) setProject(executed.project)
        if (executed.download_url) {
          const a = document.createElement('a')
          a.href = executed.download_url
          a.download = 'SolliCut-reel.mp4'
          a.click()
        }
        setStage(executed.download_url ? 'Ready to download' : 'Previous edit restored')
        setBusy(false)
      }
    } catch (e) {
      setError((e as Error).message)
      setStage('Review and apply')
      setBusy(false)
    } finally {
      setApplyingResult(false)
    }
  }

  async function handleAudio(blob: Blob, extension: string) {
    if (!project) return
    setBusy(true)
    setError('')
    setStage('Processing speech')
    setPendingResult(null)
    try {
      const form = new FormData()
      form.append('file', blob, `command.${extension}`)
      form.append('asr_mode', asrMode)
      form.append('auto_apply', 'false')
      if (asrMode !== 'tanglish') form.append('language_hint', asrMode)
      const result = await api<Command>(`/projects/${project.id}/voice-command`, { method: 'POST', body: form })
      handleVoiceResult(result)
    } catch (e) {
      setError((e as Error).message)
      setBusy(false)
      setStage('Ready')
    }
  }

  async function applyVisualEdit(payload: Record<string, unknown>, stageLabel = 'Applying studio edit') {
    if (!project || busy) return
    setBusy(true)
    setError('')
    setStage(stageLabel)
    try {
      const res = await api<{ job_id?: string; project?: Project }>(`/projects/${project.id}/edit`, {
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

  async function undo() {
    if (!project) return
    setBusy(true)
    setError('')
    try {
      setProject(await api<Project>(`/projects/${project.id}/undo`, { method: 'POST' }))
      setPendingResult(null)
      setStage('Previous edit restored')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function reset() {
    if (!project) return
    setBusy(true)
    try {
      await api(`/projects/${project.id}`, { method: 'DELETE' })
      const p = await api<Project>('/projects', { method: 'POST' })
      setProject(p)
      localStorage.setItem('sollicut-project', p.id)
      setPendingResult(null)
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
    if (!project) return
    setBusy(true)
    try {
      setProject(await api<Project>(`/projects/${project.id}/assets/${id}`, { method: 'DELETE' }))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
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
      voicePanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      return
    }
    if (tab === 'media') {
      mediaPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      return
    }
    setActiveTab(tab)
  }

  function requestPreviewFullscreen() {
    const el = videoRef.current
    if (!el || typeof el.requestFullscreen !== 'function') return
    void el.requestFullscreen()
  }

  const totalDur = project?.settings?.duration_seconds ?? 15
  const audioAsset = project?.assets.find((a) => a.media_type === 'audio')
  const speechReady = caps?.speech.status === 'ready'

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
          <span>
            <Film size={13} />
            9:16 · 720×1280
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
          <button
            type="button"
            className="rail-btn voice-rail"
            onClick={() => jumpTab('voice')}
            title="Voice Director"
            aria-label="Focus Voice Director"
          >
            <Mic size={18} />
            <span>Voice</span>
          </button>
          <button
            type="button"
            className="rail-btn"
            onClick={() => jumpTab('media')}
            title="Your media"
            aria-label="Focus media library"
          >
            <FolderOpen size={18} />
            <span>Media</span>
          </button>
          <button
            type="button"
            className={`rail-btn ${activeTab === 'text' ? 'active' : ''}`}
            onClick={() => setActiveTab('text')}
            aria-label="Text overlay tools"
          >
            <Type size={18} />
            <span>Text</span>
          </button>
          <button
            type="button"
            className={`rail-btn ${activeTab === 'audio' ? 'active' : ''}`}
            onClick={() => setActiveTab('audio')}
            aria-label="Audio and music tools"
          >
            <Music2 size={18} />
            <span>Audio</span>
          </button>
          <button
            type="button"
            className={`rail-btn ${activeTab === 'look' ? 'active' : ''}`}
            onClick={() => setActiveTab('look')}
            aria-label="Look and format tools"
          >
            <SlidersHorizontal size={18} />
            <span>Look</span>
          </button>
          <button
            type="button"
            className={`rail-btn ${activeTab === 'trim' ? 'active' : ''}`}
            onClick={() => setActiveTab('trim')}
            aria-label="Trim clip tools"
          >
            <Scissors size={18} />
            <span>Trim</span>
          </button>
          <button
            type="button"
            className={`rail-btn ${activeTab === 'ai' ? 'active' : ''}`}
            onClick={() => setActiveTab('ai')}
            aria-label="Optional Gemini ad generator"
          >
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
                              <button
                                type="button"
                                aria-label={`Move ${asset.filename} left`}
                                disabled={busy || i === 0}
                                onClick={() => void moveClip(i, -1)}
                              >
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
                          <button
                            type="button"
                            aria-label={`Remove ${asset.filename}`}
                            disabled={busy}
                            onClick={() => void remove(asset.id)}
                          >
                            <X size={12} />
                          </button>
                        </div>
                      </div>
                    ))}
                    {mediaAssets.length < 5 && (
                      <button
                        type="button"
                        className="add-photo"
                        disabled={busy}
                        onClick={() => upload.current?.click()}
                        aria-label="Add more photos or videos"
                      >
                        <ImagePlus size={20} />
                        <span>Add media</span>
                      </button>
                    )}
                  </div>
                ) : (
                  <button
                    type="button"
                    className="dropzone"
                    disabled={busy || !project}
                    onClick={() => upload.current?.click()}
                  >
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
                  <span>{audioAsset?.filename ?? 'Original demo music'}</span>
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
                  <span className="preview-label">
                    {project?.current_output ? `READY · REV ${project.current_render_revision}` : 'NO RENDER YET'}
                  </span>
                </div>

                <div className="preview-canvas">
                  <div className="video-frame">
                    {project?.current_output ? (
                      <video
                        ref={videoRef}
                        key={project.current_render_revision}
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
                        <p>Upload photos or video clips on the left, then tap the microphone to direct your reel.</p>
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
                  <button
                    type="button"
                    className="transport-btn"
                    disabled={!project?.current_output}
                    onClick={toggleMutePreview}
                    aria-label={mutedPreview ? 'Unmute preview' : 'Mute preview'}
                  >
                    {mutedPreview ? <VolumeX size={14} /> : <Volume2 size={14} />}
                  </button>
                  <button
                    type="button"
                    className="transport-btn"
                    disabled={!project?.current_output}
                    onClick={() => seekTo(0)}
                    aria-label="Jump to start"
                  >
                    <SkipBack size={14} />
                  </button>
                  <button
                    type="button"
                    className="transport-btn primary-play"
                    disabled={!project?.current_output}
                    onClick={togglePlay}
                    aria-label={playing ? 'Pause preview' : 'Play preview'}
                  >
                    {playing ? <Pause size={15} /> : <Play size={15} />}
                  </button>
                  <button
                    type="button"
                    className="transport-btn"
                    disabled={!project?.current_output}
                    onClick={() => seekTo(Math.max(0, totalDur - 4))}
                    aria-label="Jump to offer end card"
                  >
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
                  <button
                    type="button"
                    className="transport-btn"
                    disabled={!project?.current_output}
                    onClick={requestPreviewFullscreen}
                    aria-label="Fullscreen preview"
                  >
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
                  <button
                    type="button"
                    className="transcript-review__icon-btn"
                    aria-label="Microphone settings"
                    aria-expanded={showMicSettings}
                    onClick={() => setShowMicSettings((v) => !v)}
                  >
                    <Mic size={14} />
                  </button>
                </div>

                <VoiceButton
                  disabled={busy || mediaAssets.length < 1 || !speechReady}
                  projectId={project?.id}
                  mode={asrMode}
                  previewOnly={true}
                  resampler={caps?.voice_profile?.resampler ?? 'fir_kaiser'}
                  deviceId={micDeviceId}
                  onModeChange={setAsrMode}
                  onProcessing={() => {
                    setBusy(true)
                    setError('')
                    setStage('Processing speech')
                    setPendingResult(null)
                  }}
                  onStreamResult={handleVoiceResult}
                  onAudio={(b, e) => void handleAudio(b, e)}
                  onError={(msg) => {
                    setError(msg)
                    setBusy(false)
                    setStage('Ready')
                  }}
                />

                {showMicSettings && (
                  <MicrophoneSettings deviceId={micDeviceId} onDeviceChange={setMicDeviceId} />
                )}

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
                      ? '“Offer ah 25 percent nu maathu. Background music konjam kammi pannu.”'
                      : '“Indha photos use panni 15 seconds reel create pannu. Smooth zoom, music, last la 20 percent offer podu.”'}
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

                {/* Phase 8: TranscriptReview — operations NOT applied until user clicks Apply */}
                {pendingResult && (
                  <TranscriptReview
                    result={pendingResult}
                    applying={applyingResult}
                    onApply={(r, edited) => void applyPendingResult(r, edited)}
                    onCancel={() => {
                      setPendingResult(null)
                      setStage('Ready')
                    }}
                  />
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
                      <label className="field-label" htmlFor="overlay-text-input">
                        Promotional offer text
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
                              ['end_card', 'End card (last 4s)'],
                              ['bottom', 'Bottom'],
                              ['center', 'Center'],
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
                        <span className="field-label">Accent bar</span>
                        <div className="swatch-row">
                          {(
                            [
                              ['lime', '#d7ef41', 'Electric Lime'],
                              ['white', '#f5f7f4', 'Crisp White'],
                              ['amber', '#fbbf24', 'Warm Amber'],
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
                          disabled={busy || !project?.settings?.overlay_text}
                          onClick={() => {
                            setOverlayDraft('')
                            void applyVisualEdit({ clear_overlay: true, render: mediaAssets.length > 0 }, 'Removing text overlay')
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
                                render: true,
                              },
                              'Updating text overlay',
                            )
                          }
                        >
                          Apply text
                        </button>
                      </div>
                    </div>
                  )}

                  {activeTab === 'audio' && (
                    <div className="panel-fields">
                      <div className="toggle-row">
                        <div>
                          <strong>Background music</strong>
                          <span>{audioAsset?.filename ?? 'Original demo music'}</span>
                        </div>
                        <input
                          type="checkbox"
                          aria-label="Enable background music"
                          checked={musicEnabledDraft}
                          disabled={busy}
                          onChange={(e) => setMusicEnabledDraft(e.target.checked)}
                        />
                      </div>
                      <div className="control-group">
                        <label className="field-label" htmlFor="bgm-vol">
                          Music volume: {Math.round(musicVolDraft * 100)}%
                        </label>
                        <input
                          id="bgm-vol"
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={musicVolDraft}
                          disabled={busy || !musicEnabledDraft}
                          onChange={(e) => setMusicVolDraft(Number(e.target.value))}
                        />
                      </div>
                      <div className="music-row">
                        <Music2 size={15} />
                        <span>{audioAsset?.filename ?? 'Original demo music included'}</span>
                        {audioAsset ? (
                          <button type="button" className="text-button" disabled={busy} onClick={() => void remove(audioAsset.id)}>
                            Remove
                          </button>
                        ) : (
                          <button type="button" className="text-button" disabled={busy || !project} onClick={() => music.current?.click()}>
                            Use my music
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
                      <div className="toggle-row">
                        <div>
                          <strong>Original video clip audio</strong>
                          <span>Keep audio from uploaded video clips</span>
                        </div>
                        <input
                          type="checkbox"
                          aria-label="Keep original video clip audio"
                          checked={clipAudioDraft}
                          disabled={busy}
                          onChange={(e) => setClipAudioDraft(e.target.checked)}
                        />
                      </div>
                      {clipAudioDraft && (
                        <div className="control-group">
                          <label className="field-label" htmlFor="clip-vol">
                            Clip audio volume: {Math.round(clipVolDraft * 100)}%
                          </label>
                          <input
                            id="clip-vol"
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={clipVolDraft}
                            disabled={busy}
                            onChange={(e) => setClipVolDraft(Number(e.target.value))}
                          />
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
                        <label className="field-label" htmlFor="reel-dur">
                          Reel duration: {durationDraft}s
                        </label>
                        <input
                          id="reel-dur"
                          type="range"
                          min={3}
                          max={30}
                          step={1}
                          value={durationDraft}
                          disabled={busy}
                          onChange={(e) => setDurationDraft(Number(e.target.value))}
                        />
                      </div>
                      <div className="toggle-row">
                        <div>
                          <strong>Smooth photo zoom</strong>
                          <span>Gentle Ken Burns motion on still photos</span>
                        </div>
                        <input
                          type="checkbox"
                          aria-label="Smooth photo zoom"
                          checked={zoomDraft === 'smooth'}
                          disabled={busy}
                          onChange={(e) => setZoomDraft(e.target.checked ? 'smooth' : 'none')}
                        />
                      </div>
                      <div className="control-group">
                        <label className="field-label" htmlFor="look-bright">
                          Brightness: {brightnessDraft > 0 ? `+${Math.round(brightnessDraft * 100)}%` : `${Math.round(brightnessDraft * 100)}%`}
                        </label>
                        <input
                          id="look-bright"
                          type="range"
                          min={-0.3}
                          max={0.3}
                          step={0.05}
                          value={brightnessDraft}
                          disabled={busy}
                          onChange={(e) => setBrightnessDraft(Number(e.target.value))}
                        />
                      </div>
                      <div className="control-group">
                        <span className="field-label">Framing</span>
                        <div className="pill-row">
                          <button
                            type="button"
                            className={`pill-btn ${fitDraft === 'contain' ? 'active' : ''}`}
                            disabled={busy}
                            onClick={() => setFitDraft('contain')}
                          >
                            Fit frame
                          </button>
                          <button
                            type="button"
                            className={`pill-btn ${fitDraft === 'cover' ? 'active' : ''}`}
                            disabled={busy}
                            onClick={() => setFitDraft('cover')}
                          >
                            Fill 9:16
                          </button>
                        </div>
                      </div>
                      <button
                        type="button"
                        className="lime-button full-btn"
                        disabled={busy || mediaAssets.length < 1}
                        onClick={() =>
                          void applyVisualEdit(
                            {
                              duration_seconds: durationDraft,
                              zoom_style: zoomDraft,
                              brightness: brightnessDraft,
                              fit_mode: fitDraft,
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
                      {selectedClip && selectedClip.media_type === 'video' ? (
                        <>
                          <div className="selected-clip-summary">
                            <strong>{selectedClip.filename}</strong>
                            <span>Source length: {(selectedClip.duration_seconds ?? 0).toFixed(1)}s</span>
                          </div>
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
                                    render: true,
                                  },
                                  'Trimming video clip',
                                )
                              }
                            >
                              Apply trim
                            </button>
                          </div>
                        </>
                      ) : (
                        <p className="muted-box">
                          Select an uploaded video clip in <strong>Your media</strong> or on the timeline to trim its start and end points. Photos automatically animate across their timeline slot.
                        </p>
                      )}
                    </div>
                  )}

                  {activeTab === 'ai' && project && (
                    <GeneratePanel
                      project={project}
                      caps={caps}
                      busy={busy}
                      languageHint={asrMode === 'tanglish' ? '' : asrMode}
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
                Your uploaded media and voice commands are processed locally by this SolliCut server. No cloud AI API is required for core editing.
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
