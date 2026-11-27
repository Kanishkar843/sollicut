import { ChevronLeft, ChevronRight, Film, Image as ImageIcon, Music2, Type } from 'lucide-react'
import type { Asset, Project } from './api'

type Tab = 'voice' | 'text' | 'audio' | 'look' | 'trim' | 'ai'

type Props = {
  project: Project
  mediaAssets: Asset[]
  selectedClipId: string | null
  currentTime: number
  busy: boolean
  onSelectClip: (id: string) => void
  onMoveClip: (index: number, delta: -1 | 1) => void
  onJumpTab: (tab: Tab) => void
  onSeek: (seconds: number) => void
}

function fmt(sec: number): string {
  const s = Math.max(0, sec)
  const mins = Math.floor(s / 60)
  const rem = (s % 60).toFixed(1).padStart(4, '0')
  return `${String(mins).padStart(2, '0')}:${rem}`
}

const WAVE = [28, 52, 74, 44, 86, 62, 35, 92, 58, 70, 40, 82, 65, 30, 78, 54, 88, 46, 66, 38, 75, 50, 84, 42, 68, 34, 72, 58]

export default function Timeline({
  project,
  mediaAssets,
  selectedClipId,
  currentTime,
  busy,
  onSelectClip,
  onMoveClip,
  onJumpTab,
  onSeek,
}: Props) {
  const total = project.settings?.duration_seconds ?? 15
  const zoomStyle = project.settings?.zoom_style ?? 'smooth'
  const musicEnabled = project.settings?.music_enabled ?? true
  const musicVolume = project.settings?.music_volume ?? 0.2
  const keepClipAudio = project.settings?.keep_clip_audio ?? false
  const playheadPct = Math.min(100, Math.max(0, (currentTime / total) * 100))
  const overlayText = project.settings?.overlay_text ?? null
  const overlayPos = project.settings?.overlay_position ?? 'end_card'
  const endCardStart = Math.max(0, total - 4)
  const overlayLeftPct = overlayPos === 'end_card' ? (endCardStart / total) * 100 : 0
  const overlayWidthPct = overlayPos === 'end_card' ? ((total - endCardStart) / total) * 100 : 100
  const audioAsset = project.assets.find((a) => a.media_type === 'audio')
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(total * f * 10) / 10)
  const slotSec = mediaAssets.length ? total / mediaAssets.length : total

  function handleRulerClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!project.current_output) return
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    onSeek(ratio * total)
  }

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
          <span>{musicEnabled ? `Music ${Math.round(musicVolume * 100)}%` : 'Music muted'}</span>
        </div>
      </div>

      <div className="timeline-body">
        <div className="track-labels" aria-hidden="true">
          <div className="ruler-spacer" />
          <div className="track-label"><Film size={13} />Media</div>
          <div className="track-label"><Type size={13} />Text</div>
          <div className="track-label"><Music2 size={13} />Audio</div>
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

          <div className="track-row media-track">
            {mediaAssets.length === 0 ? (
              <div className="track-empty">Upload photos or video clips above to build your reel timeline</div>
            ) : (
              mediaAssets.map((asset, index) => {
                const selected = asset.id === selectedClipId
                const trimmed = asset.media_type === 'video' && ((asset.trim_start ?? 0) > 0 || asset.trim_end != null)
                return (
                  <div
                    key={asset.id}
                    className={`tl-clip ${selected ? 'selected' : ''}`}
                    style={{ flex: 1 }}
                    onClick={() => onSelectClip(asset.id)}
                  >
                    <div className="tl-clip-thumb">
                      {asset.media_type === 'video' ? <Film size={12} /> : <ImageIcon size={12} />}
                    </div>
                    <div className="tl-clip-info">
                      <strong>#{index + 1} {asset.filename}</strong>
                      <span>
                        {slotSec.toFixed(1)}s{trimmed ? ` · trim ${(asset.trim_start ?? 0).toFixed(1)}–${(asset.trim_end ?? asset.duration_seconds ?? slotSec).toFixed(1)}s` : ''}
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
                )
              })
            )}
          </div>

          <div className="track-row overlay-track">
            {overlayText ? (
              <button
                type="button"
                className="tl-overlay-pill"
                style={{ left: `${overlayLeftPct}%`, width: `${overlayWidthPct}%` }}
                onClick={() => onJumpTab('text')}
              >
                <span>{overlayText}</span>
                <small>{overlayPos === 'end_card' ? 'End card' : overlayPos}</small>
              </button>
            ) : (
              <button type="button" className="track-add-hint" onClick={() => onJumpTab('text')}>
                + Add promotional text overlay (or say “Last la 20 percent offer nu text podu”)
              </button>
            )}
          </div>

          <div className="track-row audio-track">
            <button type="button" className="tl-audio-bar" onClick={() => onJumpTab('audio')}>
              <div className="tl-audio-meta">
                <span>
                  {musicEnabled
                    ? audioAsset?.filename ?? 'Original demo music'
                    : 'Background music muted'}
                  {keepClipAudio ? ' + Clip audio' : ''}
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
