import { useState } from 'react'
import { Captions, ChevronLeft, ChevronRight, Film, Music2, Plus, Scissors, Sparkles, Type, Volume2, VolumeX } from 'lucide-react'
import type { Asset, Project, TextLayer } from './api'

type Tab = 'voice' | 'media' | 'text' | 'audio' | 'look' | 'trim' | 'fx' | 'assets' | 'ai'

type Props = {
  project: Project
  mediaAssets: Asset[]
  selectedClipId: string | null
  currentTime: number
  busy: boolean
  onSelectClip: (id: string) => void
  onMoveClip: (index: number, delta: -1 | 1) => void
  onReorderIds?: (orderedIds: string[]) => void
  onSelectTextLayer?: (layerId: string) => void
  onAddMedia: () => void
  onToggleMusicMute: () => void
  onJumpTab: (tab: Tab) => void
  onSeek: (seconds: number) => void
}

function fmt(sec: number): string {
  const s = Math.max(0, sec)
  const mins = Math.floor(s / 60)
  const rem = (s % 60).toFixed(1).padStart(4, '0')
  return `${String(mins).padStart(2, '0')}:${rem}`
}

const WAVE = [28, 52, 74, 44, 86, 62, 35, 92, 58, 70, 40, 82, 65, 30, 78, 54, 88, 46, 66, 38, 75, 50, 84, 42, 68, 34, 72, 58, 48, 76, 39, 64]

export default function Timeline({
  project,
  mediaAssets,
  selectedClipId,
  currentTime,
  busy,
  onSelectClip,
  onMoveClip,
  onReorderIds,
  onSelectTextLayer,
  onAddMedia,
  onToggleMusicMute,
  onJumpTab,
  onSeek,
}: Props) {
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const total = project.settings?.duration_seconds ?? 15
  const zoomStyle = project.settings?.zoom_style ?? 'smooth'
  const musicEnabled = project.settings?.music_enabled ?? true
  const musicVolume = project.settings?.music_volume ?? 0.2
  const keepClipAudio = project.settings?.keep_clip_audio ?? false
  const transitionStyle = project.settings?.transition_style ?? 'none'
  const filterPreset = project.settings?.filter_preset ?? 'none'
  const playheadPct = Math.min(100, Math.max(0, (currentTime / total) * 100))

  const allLayers: TextLayer[] = project.settings?.text_layers?.length
    ? project.settings.text_layers
    : project.settings?.overlay_text
      ? [
          {
            id: project.settings?.active_text_id ?? 'legacy-overlay',
            text: project.settings.overlay_text,
            position: project.settings.overlay_position ?? 'end_card',
            color: project.settings.overlay_color ?? 'lime',
            animation: 'none',
            is_caption: false,
          },
        ]
      : []

  const promoLayers = allLayers.filter((l) => !l.is_caption)
  const captionLayers = allLayers.filter((l) => l.is_caption)
  const audioAsset = project.assets.find((a) => a.media_type === 'audio')
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(total * f * 10) / 10)
  const slotSec = mediaAssets.length ? total / mediaAssets.length : total

  function handleRulerClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!project.current_output) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    onSeek(ratio * total)
  }

  function layerSpanPct(layer: TextLayer): { left: number; width: number } {
    if (layer.start_time != null || layer.end_time != null) {
      const s = Math.max(0, layer.start_time ?? 0)
      const e = Math.min(total, layer.end_time ?? total)
      return { left: (s / total) * 100, width: Math.max(10, ((e - s) / total) * 100) }
    }
    if (layer.clip_index != null && mediaAssets.length > 0) {
      const idx = Math.min(mediaAssets.length - 1, Math.max(0, layer.clip_index - 1))
      const w = 100 / mediaAssets.length
      return { left: idx * w, width: w }
    }
    if (layer.position === 'end_card' && !layer.is_caption) {
      const endCardStart = Math.max(0, total - 4)
      return { left: (endCardStart / total) * 100, width: ((total - endCardStart) / total) * 100 }
    }
    return { left: 0, width: 100 }
  }

  function handleDrop(targetIndex: number) {
    if (dragIndex === null || dragIndex === targetIndex || !onReorderIds || busy) {
      setDragIndex(null)
      return
    }
    const ordered = [...mediaAssets]
    const [moved] = ordered.splice(dragIndex, 1)
    ordered.splice(targetIndex, 0, moved)
    setDragIndex(null)
    onReorderIds(ordered.map((a) => a.id))
  }

  const audioFlags = [
    project.settings?.audio_denoise ? 'Denoise' : null,
    project.settings?.audio_normalize ? 'Norm' : null,
    project.settings?.voice_enhance ? 'Voice+' : null,
    project.settings?.vocal_isolation && project.settings.vocal_isolation !== 'none'
      ? project.settings.vocal_isolation === 'vocals_only'
        ? 'Vocals'
        : 'Instr'
      : null,
  ].filter(Boolean)

  return (
    <section className="timeline-dock" aria-label="Reel timeline">
      <div className="timeline-header">
        <div className="timeline-title">
          <strong>Timeline</strong>
          <span>{fmt(currentTime)} / {fmt(total)}</span>
        </div>
        <div className="timeline-legend">
          <span>{mediaAssets.length} clip{mediaAssets.length === 1 ? '' : 's'}</span>
          <span>{zoomStyle === 'smooth' ? 'Smooth zoom' : 'Static'}</span>
          {transitionStyle !== 'none' && <span>Transition: {transitionStyle}</span>}
          {filterPreset !== 'none' && <span>Filter: {filterPreset}</span>}
          <span>{musicEnabled ? `Music ${Math.round(musicVolume * 100)}%` : 'Music muted'}</span>
          {keepClipAudio && <span>Clip audio on</span>}
          {project.settings?.narration_enabled && <span>TTS on</span>}
        </div>
      </div>

      <div className="timeline-body">
        <div className="track-labels">
          <div className="ruler-spacer" />
          <div className="track-label">
            <span className="track-name"><Film size={13} />Media</span>
            <button
              type="button"
              className="track-ctrl"
              disabled={busy || mediaAssets.length >= 5}
              onClick={onAddMedia}
              title="Add photo or video clip"
              aria-label="Add media to timeline"
            >
              <Plus size={12} />
            </button>
          </div>
          <div className="track-label">
            <span className="track-name"><Type size={13} />Text</span>
            <button
              type="button"
              className="track-ctrl"
              onClick={() => onJumpTab('text')}
              title="Edit overlay text"
              aria-label="Edit text track"
            >
              <Type size={11} />
            </button>
          </div>
          <div className="track-label">
            <span className="track-name"><Captions size={13} />Captions</span>
            <button
              type="button"
              className="track-ctrl"
              onClick={() => onJumpTab('text')}
              title="Auto-captions & TTS"
              aria-label="Edit captions and TTS track"
            >
              <Sparkles size={11} />
            </button>
          </div>
          <div className="track-label">
            <span className="track-name"><Music2 size={13} />Audio</span>
            <button
              type="button"
              className={`track-ctrl ${!musicEnabled ? 'muted' : ''}`}
              disabled={busy}
              onClick={onToggleMusicMute}
              title={musicEnabled ? 'Mute background music' : 'Unmute background music'}
              aria-label={musicEnabled ? 'Mute background music' : 'Unmute background music'}
            >
              {musicEnabled ? <Volume2 size={12} /> : <VolumeX size={12} />}
            </button>
          </div>
        </div>

        <div className="tracks-canvas">
          <div
            className={`time-ruler ${project.current_output ? 'interactive' : ''}`}
            onClick={handleRulerClick}
            title={project.current_output ? 'Click anywhere to seek preview' : 'Render a reel to scrub preview'}
          >
            {ticks.map((tick) => (
              <span key={tick}>{fmt(tick)}</span>
            ))}
          </div>

          {project.current_output && (
            <div className="playhead" style={{ left: `${playheadPct}%` }} aria-hidden="true">
              <i />
            </div>
          )}

          {/* Track 1: Multi-clip Media track with drag/drop + transition badges */}
          <div className="track-row media-track">
            {mediaAssets.length === 0 ? (
              <div className="track-empty">Upload photos or video clips in Your media to populate the timeline</div>
            ) : (
              mediaAssets.map((asset, index) => {
                const selected = asset.id === selectedClipId
                const trimmed = asset.media_type === 'video' && ((asset.trim_start ?? 0) > 0 || asset.trim_end != null)
                const assetUrl = `/api/projects/${project.id}/assets/${asset.id}`
                const hasFx =
                  (asset.cutout_mode && asset.cutout_mode !== 'none') ||
                  asset.stabilize ||
                  (asset.keyframes && asset.keyframes.length > 0) ||
                  (asset.speed && Math.abs(asset.speed - 1) > 0.01)
                return (
                  <div key={asset.id} className="tl-clip-slot">
                    <div
                      draggable={!busy && mediaAssets.length > 1}
                      onDragStart={() => setDragIndex(index)}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => handleDrop(index)}
                      className={`tl-clip ${selected ? 'selected' : ''}`}
                      onClick={() => onSelectClip(asset.id)}
                    >
                      <div className="tl-clip-thumb" aria-hidden="true">
                        {asset.media_type === 'video' ? (
                          <video muted preload="metadata" src={assetUrl} />
                        ) : (
                          <img src={assetUrl} alt="" />
                        )}
                      </div>
                      <div className="tl-clip-info">
                        <strong>#{index + 1} {asset.filename}</strong>
                        <span>
                          {slotSec.toFixed(1)}s
                          {trimmed ? ` · ${(asset.trim_start ?? 0).toFixed(1)}–${(asset.trim_end ?? asset.duration_seconds ?? slotSec).toFixed(1)}s` : ''}
                          {hasFx ? ' · FX' : ''}
                        </span>
                      </div>
                      {mediaAssets.length > 1 && (
                        <div className="tl-clip-move" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            aria-label={`Move ${asset.filename} earlier`}
                            disabled={busy || index === 0}
                            onClick={() => onMoveClip(index, -1)}
                          >
                            <ChevronLeft size={12} />
                          </button>
                          <button
                            type="button"
                            aria-label={`Move ${asset.filename} later`}
                            disabled={busy || index === mediaAssets.length - 1}
                            onClick={() => onMoveClip(index, 1)}
                          >
                            <ChevronRight size={12} />
                          </button>
                        </div>
                      )}
                    </div>
                    {transitionStyle !== 'none' && index < mediaAssets.length - 1 && (
                      <button
                        type="button"
                        className="tl-transition-chip"
                        title={`Transition: ${transitionStyle}`}
                        onClick={() => onJumpTab('look')}
                      >
                        <Scissors size={10} />
                      </button>
                    )}
                  </div>
                )
              })
            )}
          </div>

          {/* Track 2: Persistent Multi-Layer Text track */}
          <div className="track-row overlay-track">
            {promoLayers.length > 0 ? (
              promoLayers.map((layer) => {
                const { left, width } = layerSpanPct(layer)
                const isActive = layer.id === project.settings?.active_text_id
                return (
                  <button
                    key={layer.id}
                    type="button"
                    className={`tl-overlay-pill ${isActive ? 'active' : ''}`}
                    style={{ left: `${left}%`, width: `${Math.min(100 - left, width)}%` }}
                    onClick={() => {
                      onSelectTextLayer?.(layer.id)
                      onJumpTab('text')
                    }}
                  >
                    <span>{layer.text}</span>
                    <small>{layer.clip_index ? `Clip ${layer.clip_index}` : layer.position === 'end_card' ? 'End card' : layer.position}</small>
                  </button>
                )
              })
            ) : (
              <button type="button" className="track-add-hint" onClick={() => onJumpTab('text')}>
                + Add promotional text overlay (or say “Last la 20 percent offer nu text podu”)
              </button>
            )}
          </div>

          {/* Track 3: Captions & Offline TTS Narration track */}
          <div className="track-row captions-track">
            {captionLayers.length > 0 ? (
              captionLayers.map((cap) => {
                const { left, width } = layerSpanPct(cap)
                return (
                  <button
                    key={cap.id}
                    type="button"
                    className="tl-caption-pill"
                    style={{ left: `${left}%`, width: `${Math.min(100 - left, Math.max(12, width))}%` }}
                    onClick={() => onJumpTab('text')}
                  >
                    <span>{cap.text}</span>
                  </button>
                )
              })
            ) : (
              <button type="button" className="track-add-hint" onClick={() => onJumpTab('text')}>
                {project.settings?.narration_enabled
                  ? 'TTS Narration active · Click to edit captions or voiceover'
                  : '+ Auto-captions & offline Tamil/English TTS narration'}
              </button>
            )}
          </div>

          {/* Track 4: Audio & DSP track */}
          <div className="track-row audio-track">
            <button type="button" className={`tl-audio-bar ${!musicEnabled ? 'muted' : ''}`} onClick={() => onJumpTab('audio')}>
              <div className="tl-audio-meta">
                <span>
                  {musicEnabled ? audioAsset?.filename ?? 'Original demo music' : 'Background music muted'}
                  {keepClipAudio ? ' + Clip audio' : ''}
                  {audioFlags.length ? ` · ${audioFlags.join(' · ')}` : ''}
                </span>
              </div>
              <div className="tl-waveform" aria-hidden="true">
                {WAVE.map((h, i) => (
                  <i
                    key={i}
                    style={{
                      height: `${musicEnabled ? Math.max(18, Math.round(h * Math.max(0.25, musicVolume * 2.4))) : 12}%`,
                      opacity: musicEnabled ? 0.9 : 0.25,
                    }}
                  />
                ))}
              </div>
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
