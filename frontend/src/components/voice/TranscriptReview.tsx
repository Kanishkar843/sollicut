/**
 * frontend/src/components/voice/TranscriptReview.tsx — Phase 8
 *
 * Shows the transcript + proposed operation list received from the voice WS/REST.
 * Operations are NOT applied until the user explicitly clicks "Apply" / "Apply all".
 * Supports inline transcript editing before applying.
 */
import { useEffect, useState } from 'react'
import { Check, Pencil, X } from 'lucide-react'
import { type Command } from '../../api'
import { OperationPreview } from './OperationPreview'
import { Clarification } from './Clarification'

type TranscriptReviewProps = {
  result: Command
  /** Called when user clicks "Apply" / "Apply all"; receives optional edited transcript */
  onApply: (result: Command, editedTranscript?: string) => void
  /** Called when user clicks "Cancel" or dismiss */
  onCancel: () => void
  /** If true, the Apply button shows a spinner */
  applying?: boolean
}

export function TranscriptReview({ result, onApply, onCancel, applying = false }: TranscriptReviewProps) {
  const parsed = result.parsed_command
  const original = parsed.original_transcript
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(original)

  useEffect(() => {
    setDraft(parsed.original_transcript)
    setEditing(false)
  }, [parsed.original_transcript, result.command_id])

  const trimmedDraft = draft.trim()
  const isEdited = trimmedDraft !== original.trim()
  const hasClarification = parsed.requires_clarification && !editing && !isEdited
  const canApply = isEdited ? trimmedDraft.length > 0 : parsed.operations.length > 0 && !parsed.requires_clarification

  return (
    <div className="transcript-review" role="region" aria-label="Voice command review">
      <div className="transcript-review__header">
        <span className="eyebrow">{hasClarification ? "LET'S CLARIFY" : 'REVIEW COMMAND'}</span>
        <div className="transcript-review__header-actions">
          <button
            type="button"
            className="transcript-review__icon-btn"
            aria-label={editing ? 'Done editing transcript' : 'Edit transcript'}
            disabled={applying}
            onClick={() => setEditing((v) => !v)}
          >
            <Pencil size={13} />
          </button>
          <button
            type="button"
            className="transcript-review__dismiss"
            aria-label="Cancel voice command"
            disabled={applying}
            onClick={onCancel}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {editing ? (
        <textarea
          className="inspector-textarea transcript-review__editor"
          rows={2}
          maxLength={1000}
          aria-label="Edit voice command transcript"
          value={draft}
          disabled={applying}
          onChange={(e) => setDraft(e.target.value)}
        />
      ) : (
        <blockquote className="transcript-review__quote">
          {trimmedDraft || original}
        </blockquote>
      )}

      {!isEdited && result.secondary_transcript && (
        <details className="secondary-transcript">
          <summary>Dual-ASR Tamil pass</summary>
          <span>{result.secondary_transcript}</span>
        </details>
      )}

      {result.engines_used && result.engines_used.length > 0 && (
        <div className="transcript-review__engines">
          {result.engines_used.map((e) => (
            <span key={e} className="engine-badge">{e}</span>
          ))}
        </div>
      )}

      {hasClarification ? (
        <Clarification question={parsed.clarification_question} onCancel={onCancel} />
      ) : (
        <OperationPreview
          operations={parsed.operations}
          matchedSources={parsed.matched_sources}
          edited={isEdited}
        />
      )}

      {!isEdited && parsed.warnings.length > 0 && (
        <ul className="transcript-review__warnings">
          {parsed.warnings.map((w) => (
            <li key={w} className="muted">{w}</li>
          ))}
        </ul>
      )}

      {!hasClarification && (
        <div className="transcript-review__actions">
          <button
            type="button"
            className="transcript-review__cancel-btn"
            onClick={onCancel}
            disabled={applying}
          >
            Cancel
          </button>
          <button
            type="button"
            className="transcript-review__edit-btn"
            onClick={() => setEditing((v) => !v)}
            disabled={applying}
          >
            {editing ? 'Preview' : 'Edit'}
          </button>
          <button
            type="button"
            className="transcript-review__apply-btn"
            onClick={() => onApply(result, isEdited ? trimmedDraft : undefined)}
            disabled={applying || !canApply}
            aria-busy={applying}
          >
            {applying ? (
              <span className="spinner-xs" aria-hidden="true" />
            ) : (
              <Check size={14} />
            )}
            {isEdited
              ? 'Apply'
              : `Apply${parsed.operations.length > 1 ? ` all ${parsed.operations.length}` : ''}`}
          </button>
        </div>
      )}
    </div>
  )
}
