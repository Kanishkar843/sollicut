import { useState } from 'react'
import { Mic, Square } from 'lucide-react'
import { type AsrMode, type Command } from './api'
import { microphoneError, useRecorder } from './hooks/useRecorder'

export { microphoneError }

const MODE_OPTIONS: readonly { id: AsrMode; label: string }[] = [
  { id: 'tanglish', label: 'Tanglish' },
  { id: 'ta', label: 'தமிழ்' },
  { id: 'en', label: 'English' },
]

const BAR_WEIGHTS = [0.65, 0.95, 1.2, 0.9, 0.7]

type VoiceButtonProps = {
  disabled: boolean
  projectId?: string
  mode?: AsrMode
  onModeChange?: (mode: AsrMode) => void
  onStreamResult?: (command: Command) => void
  onProcessing?: () => void
  onAudio: (blob: Blob, extension: string) => void
  onError: (message: string) => void
  showModeSelector?: boolean
}

export default function VoiceButton({
  disabled,
  projectId,
  mode,
  onModeChange,
  onStreamResult,
  onProcessing,
  onAudio,
  onError,
  showModeSelector = true,
}: VoiceButtonProps) {
  const [internalMode, setInternalMode] = useState<AsrMode>('tanglish')
  const activeMode = mode ?? internalMode
  const { recording, seconds, rmsLevel, start, stop } = useRecorder()

  function selectMode(next: AsrMode) {
    setInternalMode(next)
    onModeChange?.(next)
  }

  function handleToggle() {
    if (recording) {
      stop()
    } else {
      void start({
        projectId,
        mode: activeMode,
        onStreamResult,
        onProcessing,
        onAudio,
        onError,
      })
    }
  }

  return (
    <div className="voice-control-wrap">
      {showModeSelector && (
        <div className="asr-mode-pills" role="group" aria-label="Speech language mode">
          {MODE_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className={`asr-mode-pill ${activeMode === opt.id ? 'active' : ''}`}
              aria-pressed={activeMode === opt.id}
              disabled={disabled || recording}
              onClick={() => selectMode(opt.id)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
      <div className="voice-control">
        <button
          className={`mic-button ${recording ? 'recording' : ''}`}
          disabled={disabled && !recording}
          onClick={handleToggle}
          aria-label={recording ? 'Stop recording' : 'Start recording'}
        >
          {recording ? <Square size={26} fill="currentColor" /> : <Mic size={28} />}
        </button>
        <div>
          <strong>{recording ? `Listening · ${seconds}s` : 'Tap to speak'}</strong>
          <span>{recording ? 'Tap again when you’re done' : 'Tamil, Tanglish or English · up to 30 seconds'}</span>
        </div>
        {recording && (
          <div className="sound-bars" aria-hidden="true" data-rms={rmsLevel.toFixed(4)}>
            {BAR_WEIGHTS.map((w, i) => (
              <i
                key={i}
                style={{
                  height: `${Math.round(Math.max(4, Math.min(22, 4 + rmsLevel * 180 * w)))}px`,
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
