/**
 * frontend/src/components/voice/Clarification.tsx — Phase 8
 *
 * Renders a clarification_question from the server when the parsed command
 * is ambiguous. Prompts the user to retry speaking with more detail.
 * No form submission — user must re-trigger the voice button.
 */
import { HelpCircle } from 'lucide-react'

type ClarificationProps = {
  question: string | null
  /** Called when user dismisses the panel without retrying */
  onCancel: () => void
}

export function Clarification({ question, onCancel }: ClarificationProps) {
  const text = question ?? 'Could you give a bit more detail?'

  return (
    <div className="clarification" role="alert" aria-live="polite">
      <div className="clarification__question">
        <HelpCircle size={15} aria-hidden="true" />
        <p>{text}</p>
      </div>
      <div className="clarification__actions">
        <button
          type="button"
          className="transcript-review__cancel-btn"
          onClick={onCancel}
        >
          Dismiss
        </button>
        <span className="clarification__hint">
          Tap the mic and try again with more detail.
        </span>
      </div>
    </div>
  )
}
