/**
 * frontend/src/components/voice/MicrophoneSettings.tsx — Phase 8
 *
 * Shows microphone permission status and available audio input devices.
 * Gracefully degrades when MediaDevices.enumerateDevices or Permissions API is unavailable.
 */
import { useEffect, useState } from 'react'
import { Mic } from 'lucide-react'

type MicrophoneSettingsProps = {
  /** Currently selected device ID */
  deviceId?: string
  /** Callback when user picks a device */
  onDeviceChange?: (deviceId: string) => void
}

type AudioDeviceOption = {
  deviceId: string
  label: string
}

export function MicrophoneSettings({ deviceId = '', onDeviceChange }: MicrophoneSettingsProps) {
  const [devices, setDevices] = useState<AudioDeviceOption[]>([])
  const [permState, setPermState] = useState<string>('prompt')

  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        if (navigator.permissions?.query) {
          const status = await navigator.permissions.query({ name: 'microphone' as PermissionName })
          if (mounted) setPermState(status.state)
        }
      } catch {
        // Permissions API for microphone is unsupported in some browsers
      }
      try {
        if (navigator.mediaDevices?.enumerateDevices) {
          const list = await navigator.mediaDevices.enumerateDevices()
          const mics = list
            .filter((d) => d.kind === 'audioinput')
            .map((d, idx) => ({
              deviceId: d.deviceId || `mic-${idx}`,
              label: d.label || `Microphone ${idx + 1}`,
            }))
          if (mounted) setDevices(mics)
        }
      } catch {
        // Ignore in restricted environments
      }
    }
    void load()
    return () => {
      mounted = false
    }
  }, [])

  return (
    <div className="mic-settings" role="region" aria-label="Microphone settings">
      <div className="mic-settings__header">
        <Mic size={13} aria-hidden="true" />
        <span>Microphone</span>
        <span className="mic-settings__perm" data-state={permState}>
          {permState === 'granted' ? 'Allowed' : permState === 'denied' ? 'Blocked' : 'Ready'}
        </span>
      </div>
      {devices.length > 0 ? (
        <div className="select-wrap">
          <select
            aria-label="Audio input device"
            value={deviceId}
            onChange={(e) => onDeviceChange?.(e.target.value)}
          >
            <option value="">System default microphone</option>
            {devices.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <p className="mic-settings__stub muted">
          Using system default microphone. Tap the mic button to grant access if prompted.
        </p>
      )}
    </div>
  )
}
