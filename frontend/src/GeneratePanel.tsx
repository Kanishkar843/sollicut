import { useState } from 'react'
import { KeyRound, Sparkles } from 'lucide-react'
import VoiceButton from './VoiceButton'
import { api, type Capabilities, type Project } from './api'

type Props = {
  project: Project
  caps: Capabilities | null
  busy: boolean
  onJobStarted: (jobId: string, stage: string) => void
}

export default function GeneratePanel({ project, caps, busy, onJobStarted }: Props) {
  const [prompt, setPrompt] = useState('')
  const [duration, setDuration] = useState(10)
  const [refs, setRefs] = useState<string[]>([])
  const [transcribing, setTranscribing] = useState(false)
  const [error, setError] = useState('')

  const configured = Boolean(caps?.generation?.configured)
  const modelName = caps?.generation?.model ?? 'gemini-omni-1.2-flash'
  const photos = project.assets.filter((a) => a.media_type === 'image')
  const disabled = busy || transcribing

  async function record(blob: Blob, ext: string) {
    setTranscribing(true)
    setError('')
    try {
      const data = new FormData()
      data.append('file', blob, `idea.${ext}`)
      data.append('mode', 'generate')
      const result = await api<{ generation_prompt: string }>(`/projects/${project.id}/voice-command`, {
        method: 'POST',
        body: data,
      })
      setPrompt(result.generation_prompt)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setTranscribing(false)
    }
  }

  function toggleRef(id: string) {
    setRefs((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : prev.length < 2 ? [...prev, id] : prev))
  }

  async function generate() {
    if (!configured || !prompt.trim()) return
    setError('')
    try {
      const res = await api<{ job_id: string; stage: string }>(`/projects/${project.id}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript: prompt.trim(),
          duration_seconds: duration,
          aspect_ratio: '9:16',
          reference_asset_ids: refs,
        }),
      })
      onJobStarted(res.job_id, res.stage || 'Submitting prompt to Gemini')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <section className="generation-panel" aria-label="Optional cloud advertisement generator">
      <div className="gen-header">
        <div>
          <span className="eyebrow">OPTIONAL CLOUD CREATION</span>
          <h3>Speak a new advertisement</h3>
        </div>
        <span className={`key-badge ${configured ? 'ready' : 'missing'}`}>
          <KeyRound size={12} />
          {configured ? `Configured · ${modelName}` : 'Key not set'}
        </span>
      </div>
      <p className="gen-desc">
        Record an ad idea, review or edit the prompt below, and optionally send it to Gemini ({modelName}). Ordinary voice and timeline editing needs no API key.
      </p>
      {!configured && (
        <div className="notice">
          <strong>Key not set:</strong> Set <code>GEMINI_API_KEY</code> on the server to enable cloud video generation. Core editing stays keyless.
        </div>
      )}
      <VoiceButton disabled={disabled || caps?.speech.status !== 'ready'} onAudio={(b, e) => void record(b, e)} onError={setError} />
      <label className="field-label" htmlFor="gen-prompt-input">
        Spoken prompt (review before sending)
      </label>
      <textarea
        id="gen-prompt-input"
        className="inspector-textarea"
        rows={3}
        placeholder="Speak an advertisement idea or type a prompt to review..."
        value={prompt}
        disabled={disabled}
        onChange={(e) => setPrompt(e.target.value)}
      />
      <div className="gen-controls">
        <div className="control-group">
          <label htmlFor="gen-duration">Duration: {duration}s (9:16)</label>
          <input
            id="gen-duration"
            type="range"
            min={3}
            max={15}
            step={1}
            value={duration}
            disabled={disabled}
            onChange={(e) => setDuration(Number(e.target.value))}
          />
        </div>
      </div>
      {photos.length > 0 && (
        <div className="ref-picker">
          <span className="field-label">Reference product photos (optional, up to 2)</span>
          <div className="ref-chips">
            {photos.map((photo, idx) => (
              <button
                key={photo.id}
                type="button"
                className={`ref-chip ${refs.includes(photo.id) ? 'active' : ''}`}
                disabled={disabled}
                onClick={() => toggleRef(photo.id)}
              >
                <img src={`/api/projects/${project.id}/assets/${photo.id}`} alt={photo.filename} />
                <span>#{idx + 1}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <button
        type="button"
        className="lime-button full-btn"
        disabled={disabled || !configured || !prompt.trim()}
        onClick={() => void generate()}
      >
        <Sparkles size={16} />
        {configured ? 'Generate with Gemini' : 'Key not set'}
      </button>
      {transcribing && (
        <p role="status" className="status">
          Transcribing ad idea locally…
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  )
}
