import { useState } from 'react'
import { Mic, Square } from 'lucide-react'
import { type AsrMode, type Command } from './api'
import { microphoneError, useRecorder, type RecorderState } from './hooks/useRecorder'

export { microphoneError }

const MODE_OPTIONS: readonly { id: AsrMode; label: string }[] = [
  { id: 'tanglish', label: 'Tanglish' },
  { id: 'ta', label: 'தமிழ்' },
  { id: 'en', label: 'English' },
]

const BAR_WEIGHTS = [0.65, 0.95, 1.2, 0.9, 0.7]

/** Human-readable label for each recorder lifecycle state */
const STATE_LABEL: Record<RecorderState, string> = {
  idle:         'Tap to speak',
  initializing: 'Starting microphone…',
  recording:    'Listening',
  stopping:     'Finishing…',
  flushing:     'Flushing audio…',
  processing:   'Transcribing…',
  completed:    'Done',
  failed:       'Error — tap to retry',
  cancelled:    'Cancelled',
}

const STATE_HINT: Record<RecorderState, string> = {
  idle:         'Tamil, Tanglish or English · up to 30 seconds',
  initializing: 'Allow microphone access if prompted',
  recording:    "Tap again when you're done",
  stopping:     'Please wait',
  flushing:     'Please wait',
  processing:   'Please wait',
  completed:    '',
  failed:       '',
  cancelled:    '',
}

type VoiceButtonProps = {
  disabled: boolean
  projectId?: string
  mode?: AsrMode
  previewOnly?: boolean
  resampler?: 'linear' | 'fir_kaiser'
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
  previewOnly = false,
  resampler = 'fir_kaiser',
  onModeChange,
  onStreamResult,
  onProcessing,
  onAudio,
  onError,
  showModeSelector = true,
}: VoiceButtonProps) {
  const [internalMode, setInternalMode] = useState<AsrMode>('tanglish')
  const activeMode = mode ?? internalMode
  const { recording, recorderState, seconds, rmsLevel, start, stop } = useRecorder()

  function selectMode(next: AsrMode) {
    setInternalMode(next)
    onModeChange?.(next)
  }

  function handleToggle() {
    if (recording || recorderState === 'stopping' || recorderState === 'flushing') {
      stop()
    } else if (recorderState === 'idle' || recorderState === 'completed' || recorderState === 'failed' || recorderState === 'cancelled') {
      void start({
        projectId,
        mode: activeMode,
        previewOnly,
        resampler,
        onStreamResult,
        onProcessing,
        onAudio,
        onError,
      })
    }
  }

  const isActive = recording || recorderState === 'stopping' || recorderState === 'flushing'
  const isBusy = recorderState === 'processing' || recorderState === 'initializing'
  const label = STATE_LABEL[recorderState]
  const hint = STATE_HINT[recorderState]

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
              disabled={disabled || isActive || isBusy}
              onClick={() => selectMode(opt.id)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
      <div className="voice-control">
        <button
          className={`mic-button ${isActive ? 'recording' : ''} ${isBusy ? 'processing' : ''}`}
          disabled={(disabled && !isActive) || isBusy}
          onClick={handleToggle}
          aria-label={isActive ? 'Stop recording' : 'Start recording'}
          aria-busy={isBusy}
        >
          {isActive ? <Square size={26} fill="currentColor" /> : <Mic size={28} />}
        </button>
        <div>
          <strong>
            {recorderState === 'recording' ? `${label} · ${seconds}s` : label}
          </strong>
          {hint && <span>{hint}</span>}
        </div>
        {isActive && (
          <div className="sound-bars" aria-hidden="true" data-rms={rmsLevel.toFixed(4)} data-state={recorderState}>
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
