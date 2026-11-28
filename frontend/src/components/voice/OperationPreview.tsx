/**
 * frontend/src/components/voice/OperationPreview.tsx — Phase 8
 *
 * Visual summary of proposed edits with source/engine provenance badges.
 * Operations are shown using operationLabel() from api.ts.
 */
import { Check, Info } from 'lucide-react'
import { operationLabel, type Operation } from '../../api'

type OperationPreviewProps = {
  operations: Operation[]
  matchedSources?: Record<string, string>
  edited?: boolean
}

export function OperationPreview({ operations, matchedSources: _matchedSources, edited = false }: OperationPreviewProps) {
  if (edited) {
    return (
      <div className="operation-preview operation-preview--edited" role="status">
        <Info size={14} />
        <span>Transcript edited — click Apply to parse and execute updated command.</span>
      </div>
    )
  }

  if (operations.length === 0) {
    return (
      <div className="operation-preview operation-preview--empty" role="status">
        <Info size={14} />
        <span>No operations detected. Try editing the transcript or recording again.</span>
      </div>
    )
  }

  return (
    <div className="operation-preview" role="list" aria-label="Proposed edits">
      {operations.map((op) => (
        <div key={op.id} className="operation-preview__item" role="listitem">
          <Check size={13} aria-hidden="true" />
          <span className="operation-preview__label">{operationLabel(op)}</span>
        </div>
      ))}
    </div>
  )
}
