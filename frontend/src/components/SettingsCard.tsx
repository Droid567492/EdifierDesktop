import { useEffect, useState } from 'react'
import {
  Bell,
  BluetoothOff,
  Clock,
  Cpu,
  Lightbulb,
  Pencil,
  Power,
  ShieldAlert,
  Speaker,
  Users,
  Zap,
} from 'lucide-react'
import type {
  AppSettings,
  BleState,
  LdacMode,
  SmartLightSensitivity,
  SmartLightTimer,
  SubOutLevel,
} from '../types'

interface SettingsCardProps {
  ble: BleState
  settings: AppSettings
  onSetSmartLight: (timer: SmartLightTimer, sensitivity: SmartLightSensitivity) => void
  onSetSubOut: (level: SubOutLevel) => void
  onSetMultipoint: (enabled: boolean) => void
  onSetPowerSave: (enabled: boolean) => void
  onSetTimedOff: (minutes: number) => void
  onPowerOff: () => void
  onSetPromptTone: (enabled: boolean) => void
  onSetLdac: (mode: LdacMode) => void
  onRename: (name: string) => void
  onDisconnectBtAudio: () => void
  onToggleAutostart: (enabled: boolean) => void
  onDontShowAgain: (alertId: string) => void
}

const TIMERS: { id: SmartLightTimer; label: string }[] = [
  { id: '5s', label: '5s' },
  { id: '10s', label: '10s' },
  { id: '20s', label: '20s' },
  { id: 'always_on', label: 'Always' },
]

const SENSITIVITIES: { id: SmartLightSensitivity; label: string }[] = [
  { id: 'high', label: 'High' },
  { id: 'general', label: 'General' },
  { id: 'low', label: 'Low' },
]

const LDAC_MODES: { id: LdacMode; label: string }[] = [
  { id: 'disabled', label: 'Off (SBC/AAC)' },
  { id: '48khz', label: 'LDAC 48k' },
  { id: '96khz', label: 'LDAC 96k' },
]

const SUB_OUT_LEVELS: { id: SubOutLevel; label: string }[] = [
  { id: 'low', label: 'Low' },
  { id: 'medium', label: 'Medium' },
  { id: 'high', label: 'High' },
]

const TIMED_OFF_PRESETS: { mins: number; label: string }[] = [
  { mins: 0, label: 'Off' },
  { mins: 15, label: '15m' },
  { mins: 30, label: '30m' },
  { mins: 60, label: '60m' },
  { mins: 90, label: '90m' },
]

export function SettingsCard({
  ble,
  settings,
  onSetSmartLight,
  onSetSubOut,
  onSetMultipoint,
  onSetPowerSave,
  onSetTimedOff,
  onPowerOff,
  onSetPromptTone,
  onSetLdac,
  onRename,
  onDisconnectBtAudio,
  onToggleAutostart,
  onDontShowAgain,
}: SettingsCardProps) {
  const [nameInput, setNameInput] = useState(ble.device_name)
  const [confirmAction, setConfirmAction] = useState<
    | { kind: 'ldac'; mode: LdacMode }
    | { kind: 'disconnect_bt' }
    | { kind: 'power_off' }
    | null
  >(null)
  const [dontAskAgainChecked, setDontAskAgainChecked] = useState(false)

  useEffect(() => {
    setNameInput(ble.device_name)
  }, [ble.device_name])

  const disabled = !ble.connected
  const isM90 = ble.model === 'm90'
  const dismissed = settings.dismissed_alerts ?? []
  const isLinux = Boolean(settings.platform && settings.platform !== 'win32')
  const utf8Bytes = new TextEncoder().encode(nameInput).length
  const nameValid = utf8Bytes >= 1 && utf8Bytes <= 35

  return (
    <section className="card" style={{ gridColumn: '1 / -1' }}>
      <div className="card-header">
        <h2 className="card-title">
          <Lightbulb size={15} color="#f59e0b" />
          {isM90
            ? 'M90 Hardware, Power, Codec & Device Preferences'
            : 'Hardware Lighting, Codec & Device Preferences'}
        </h2>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(300px, 100%), 1fr))',
          gap: '4px 24px',
        }}
      >
        <div>
          {!isM90 ? (
            <>
              <div className="setting-row">
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>Smart Light Timeout</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                    Top capacitive touch panel backlight duration
                  </div>
                </div>
                <div className="seg-group">
                  {TIMERS.map((t) => (
                    <button
                      key={t.id}
                      className={`seg-btn ${ble.smart_light_timer === t.id ? 'active' : ''}`}
                      disabled={disabled}
                      onClick={() =>
                        onSetSmartLight(t.id, ble.smart_light_sensitivity)
                      }
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="setting-row">
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>Proximity Sensitivity</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                    Hand-approach wake sensor (resets on power cycle)
                  </div>
                </div>
                <div className="seg-group">
                  {SENSITIVITIES.map((s) => (
                    <button
                      key={s.id}
                      className={`seg-btn ${ble.smart_light_sensitivity === s.id ? 'active' : ''}`}
                      disabled={disabled}
                      onClick={() => onSetSmartLight(ble.smart_light_timer, s.id)}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="setting-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Speaker size={15} color="#94a3b8" />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>Subwoofer Output (Sub Out)</div>
                    <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                      External subwoofer output gain trim (AA ED 14)
                    </div>
                  </div>
                </div>
                <div className="seg-group">
                  {SUB_OUT_LEVELS.map((lvl) => (
                    <button
                      key={lvl.id}
                      className={`seg-btn ${ble.sub_out_level === lvl.id ? 'active' : ''}`}
                      disabled={disabled}
                      onClick={() => onSetSubOut(lvl.id)}
                    >
                      {lvl.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="setting-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Users size={15} color="#94a3b8" />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>Bluetooth Multipoint</div>
                    <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                      Dual-device simultaneous Bluetooth standby
                    </div>
                  </div>
                </div>
                <div className="seg-group">
                  <button
                    className={`seg-btn ${ble.multipoint ? 'active' : ''}`}
                    disabled={disabled}
                    onClick={() => onSetMultipoint(true)}
                  >
                    On
                  </button>
                  <button
                    className={`seg-btn ${!ble.multipoint ? 'active' : ''}`}
                    disabled={disabled}
                    onClick={() => onSetMultipoint(false)}
                  >
                    Off
                  </button>
                </div>
              </div>

              <div className="setting-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Zap size={15} color="#94a3b8" />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>Auto Power-Save Mode</div>
                    <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                      Speaker low-power standby behavior
                    </div>
                  </div>
                </div>
                <div className="seg-group">
                  <button
                    className={`seg-btn ${ble.power_save ? 'active' : ''}`}
                    disabled={disabled}
                    onClick={() => onSetPowerSave(true)}
                  >
                    On
                  </button>
                  <button
                    className={`seg-btn ${!ble.power_save ? 'active' : ''}`}
                    disabled={disabled}
                    onClick={() => onSetPowerSave(false)}
                  >
                    Off
                  </button>
                </div>
              </div>

              <div className="setting-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Clock size={15} color="#94a3b8" />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>Timed Power-Off</div>
                    <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                      {ble.timed_off_minutes > 0
                        ? `Scheduled shutdown in ${ble.timed_off_minutes} min`
                        : 'Automatic sleep timer disabled'}
                    </div>
                  </div>
                </div>
                <div className="seg-group">
                  {TIMED_OFF_PRESETS.map((t) => (
                    <button
                      key={t.mins}
                      className={`seg-btn ${ble.timed_off_minutes === t.mins ? 'active' : ''}`}
                      disabled={disabled}
                      onClick={() => onSetTimedOff(t.mins)}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          <div className="setting-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Bell size={15} color="#94a3b8" />
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>Bluetooth Prompt Tone</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                  Audible chime on BT connect/disconnect
                </div>
              </div>
            </div>
            <div className="seg-group">
              <button
                className={`seg-btn ${ble.prompt_tone ? 'active' : ''}`}
                disabled={disabled}
                onClick={() => onSetPromptTone(true)}
              >
                On
              </button>
              <button
                className={`seg-btn ${!ble.prompt_tone ? 'active' : ''}`}
                disabled={disabled}
                onClick={() => onSetPromptTone(false)}
              >
                Off
              </button>
            </div>
          </div>
        </div>

        <div>
          <div className="setting-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Cpu size={15} color="#94a3b8" />
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>LDAC Codec Preference</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                  May drop BT briefly when changed
                </div>
              </div>
            </div>
            <div className="seg-group">
              {LDAC_MODES.map((m) => (
                <button
                  key={m.id}
                  className={`seg-btn ${ble.ldac_mode === m.id ? 'active' : ''}`}
                  disabled={disabled}
                  onClick={() => {
                    if (ble.demo_mode || dismissed.includes('confirm_ldac')) {
                      onSetLdac(m.id)
                    } else {
                      setDontAskAgainChecked(false)
                      setConfirmAction({ kind: 'ldac', mode: m.id })
                    }
                  }}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          <div className="setting-row">
            <div>
              <div style={{ fontWeight: 600, fontSize: 13 }}>Device Name</div>
              <div className="mono" style={{ fontSize: 11, color: nameValid ? 'var(--text-secondary)' : '#fda4af' }}>
                {utf8Bytes} / 35 UTF-8 bytes
              </div>
            </div>
            <form
              style={{ display: 'flex', gap: 6, flex: '0 1 240px', minWidth: 0 }}
              onSubmit={(e) => {
                e.preventDefault()
                if (nameValid && !disabled) onRename(nameInput)
              }}
            >
              <input
                className="text-input"
                style={{ flex: '1 1 130px', minWidth: 0 }}
                value={nameInput}
                disabled={disabled}
                onChange={(e) => setNameInput(e.target.value)}
              />
              <button className="btn" type="submit" disabled={disabled || !nameValid}>
                <Pencil size={13} />
                Apply
              </button>
            </form>
          </div>

          {!isM90 ? (
            <div className="setting-row">
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>Bluetooth Audio Link</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                  Send 0xCD disconnect (drops active BT/BLE link)
                </div>
              </div>
              <button
                className="btn btn-danger"
                disabled={disabled}
                onClick={() => {
                  if (dismissed.includes('confirm_disconnect_bt')) {
                    onDisconnectBtAudio()
                  } else {
                    setDontAskAgainChecked(false)
                    setConfirmAction({ kind: 'disconnect_bt' })
                  }
                }}
              >
                <BluetoothOff size={14} />
                Disconnect BT Audio
              </button>
            </div>
          ) : (
            <div className="setting-row">
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>Speaker Power</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                  Send M90 remote shutdown command (0xCE)
                </div>
              </div>
              <button
                className="btn btn-danger"
                disabled={disabled}
                onClick={() => {
                  if (dismissed.includes('confirm_power_off')) {
                    onPowerOff()
                  } else {
                    setDontAskAgainChecked(false)
                    setConfirmAction({ kind: 'power_off' })
                  }
                }}
              >
                <Power size={14} />
                Power Off M90
              </button>
            </div>
          )}

          <div className="setting-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Power size={15} color="#94a3b8" />
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>
                  {isLinux ? 'Start at Login' : 'Start with Windows'}
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                  Launch quietly in the system tray at login
                  {settings.autostart_error ? ` (${settings.autostart_error})` : ''}
                </div>
              </div>
            </div>
            <div className="seg-group">
              <button
                className={`seg-btn ${settings.autostart_enabled ? 'active' : ''}`}
                onClick={() => onToggleAutostart(true)}
              >
                On
              </button>
              <button
                className={`seg-btn ${!settings.autostart_enabled ? 'active' : ''}`}
                onClick={() => onToggleAutostart(false)}
              >
                Off
              </button>
            </div>
          </div>
        </div>
      </div>

      {confirmAction && (
        <div className="modal-backdrop" onClick={() => setConfirmAction(null)}>
          <div
            className="modal-card"
            style={{ maxWidth: 440 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="card-header">
              <h3 className="card-title">
                <ShieldAlert size={16} color="#f59e0b" />
                {confirmAction.kind === 'ldac'
                  ? 'Confirm LDAC Codec Change'
                  : confirmAction.kind === 'power_off'
                    ? 'Power Off Edifier M90?'
                    : 'Disconnect Bluetooth Audio?'}
              </h3>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>
              {confirmAction.kind === 'ldac'
                ? isM90
                  ? `Changing M90 LDAC preference to "${confirmAction.mode}" may restart the speaker's Bluetooth link while applying the codec. Continue?`
                  : `Changing LDAC preference to "${confirmAction.mode}" can cause the Edifier M60 to drop both Bluetooth audio and BLE control connections while applying the setting, and may reset smart-light sensitivity. Continue?`
                : confirmAction.kind === 'power_off'
                  ? 'Sending 0xCE immediately powers off your Edifier M90 over BLE. You will need to wake the speaker manually before reconnecting.'
                  : 'Sending 0xCD disconnects the Bluetooth A2DP audio link (and may drop BLE as well). You may need to reconnect from system Bluetooth settings afterward.'}
            </p>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                fontSize: 12,
                color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={dontAskAgainChecked}
                onChange={(e) => setDontAskAgainChecked(e.target.checked)}
              />
              Don&apos;t show this alert again
            </label>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => setConfirmAction(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  if (dontAskAgainChecked) {
                    onDontShowAgain(
                      confirmAction.kind === 'ldac'
                        ? 'confirm_ldac'
                        : confirmAction.kind === 'power_off'
                          ? 'confirm_power_off'
                          : 'confirm_disconnect_bt',
                    )
                  }
                  if (confirmAction.kind === 'ldac') {
                    onSetLdac(confirmAction.mode)
                  } else if (confirmAction.kind === 'power_off') {
                    onPowerOff()
                  } else {
                    onDisconnectBtAudio()
                  }
                  setConfirmAction(null)
                }}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
