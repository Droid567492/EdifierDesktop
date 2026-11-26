import { useEffect, useState } from 'react'
import { Keyboard, Lock, Minus, Plus, Usb, Volume2, VolumeX } from 'lucide-react'
import type { AppSettings, BleState, UsbState } from '../types'

interface VolumeCardProps {
  ble: BleState
  usb: UsbState
  settings: AppSettings
  onSetVolume: (level: number) => void
  onSetUsbVolume: (percent: number) => void
  onSetUsbMute: (muted: boolean) => void
  onLockBitPerfect: () => void
  onToggleHotkeys: (enabled: boolean, lockUsb100: boolean) => void
}

export function VolumeCard({
  ble,
  usb,
  settings,
  onSetVolume,
  onSetUsbVolume,
  onSetUsbMute,
  onLockBitPerfect,
  onToggleHotkeys,
}: VolumeCardProps) {
  const [draftVol, setDraftVol] = useState(ble.volume)
  const [draftUsbVol, setDraftUsbVol] = useState(usb.volume_percent ?? 100)
  const [prevNonZero, setPrevNonZero] = useState(8)

  useEffect(() => {
    setDraftVol(ble.volume)
    if (ble.volume > 0) setPrevNonZero(ble.volume)
  }, [ble.volume])

  useEffect(() => {
    if (usb.volume_percent !== null) setDraftUsbVol(usb.volume_percent)
  }, [usb.volume_percent])

  const disabled = !ble.connected

  return (
    <section className="card">
      <div className="card-header">
        <h2 className="card-title">
          <Volume2 size={15} color="#f59e0b" />
          Hardware Gain &amp; USB-C Audio
        </h2>
        <span className="badge mono">0 – {ble.max_volume} STEPS</span>
      </div>

      <div className="vol-hero">
        <div className="vol-readout">
          <span className="vol-num mono">{draftVol}</span>
          <span className="vol-max mono">/ {ble.max_volume}</span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            className="btn btn-icon"
            disabled={disabled}
            onClick={() =>
              onSetVolume(draftVol === 0 ? Math.max(1, prevNonZero) : 0)
            }
            title={draftVol === 0 ? 'Unmute speaker' : 'Mute speaker (step 0)'}
          >
            {draftVol === 0 ? <VolumeX size={16} color="#f43f5e" /> : <Volume2 size={16} />}
          </button>
          <button
            className="btn btn-icon"
            disabled={disabled || draftVol <= 0}
            onClick={() => onSetVolume(Math.max(0, draftVol - 1))}
            title="Volume -1"
          >
            <Minus size={16} />
          </button>
          <button
            className="btn btn-icon"
            disabled={disabled || draftVol >= ble.max_volume}
            onClick={() => onSetVolume(Math.min(ble.max_volume, draftVol + 1))}
            title="Volume +1"
          >
            <Plus size={16} />
          </button>
        </div>
      </div>

      <div className="vol-steps" aria-label="Hardware volume step meter">
        {Array.from({ length: ble.max_volume }, (_, idx) => {
          const step = idx + 1
          return (
            <div
              key={step}
              className={`vol-step-bar ${step <= draftVol ? 'active' : ''}`}
              onClick={() => {
                if (!disabled) {
                  setDraftVol(step)
                  onSetVolume(step)
                }
              }}
              title={`Set hardware volume to ${step}/${ble.max_volume}`}
            />
          )
        })}
      </div>

      <input
        type="range"
        className="studio-slider"
        min={0}
        max={ble.max_volume}
        step={1}
        disabled={disabled}
        value={draftVol}
        onChange={(e) => setDraftVol(Number(e.target.value))}
        onMouseUp={() => onSetVolume(draftVol)}
        onTouchEnd={() => onSetVolume(draftVol)}
        onKeyUp={() => onSetVolume(draftVol)}
      />

      {/* USB-C Bridge Panel */}
      <div className="usb-subpanel">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, fontWeight: 600 }}>
            <Usb size={14} color="#38bdf8" />
            <span>Windows USB-C Audio Endpoint</span>
            {usb.usb_vid_pid && (
              <span className="badge mono">{usb.usb_vid_pid}</span>
            )}
          </div>
          {usb.connected ? (
            <span className="badge ok">{usb.is_default ? 'Default Output' : 'Active'}</span>
          ) : (
            <span className="badge">Not Detected</span>
          )}
        </div>

        {usb.connected ? (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
              <button
                className="btn btn-icon"
                onClick={() => onSetUsbMute(!(usb.muted ?? false))}
                title="Toggle Windows USB Mute"
              >
                {usb.muted ? <VolumeX size={14} color="#f43f5e" /> : <Volume2 size={14} color="#38bdf8" />}
              </button>
              <input
                type="range"
                className="studio-slider cyan"
                style={{ flex: '1 1 130px', minWidth: 110 }}
                min={0}
                max={100}
                value={draftUsbVol}
                onChange={(e) => setDraftUsbVol(Number(e.target.value))}
                onMouseUp={() => onSetUsbVolume(draftUsbVol)}
                onTouchEnd={() => onSetUsbVolume(draftUsbVol)}
              />
              <span className="mono" style={{ width: 42, textAlign: 'right', fontSize: 12.5 }}>
                {draftUsbVol}%
              </span>
              <button
                className="btn btn-cyan"
                onClick={onLockBitPerfect}
                title="Set Windows USB output to 100% and unmuted while controlling loudness on the M60 hardware amp"
              >
                <Lock size={13} />
                100% Bit-Perfect
              </button>
            </div>
          </>
        ) : (
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Plug the M60 in via USB-C and switch input to USB-C to manage the Windows
            WASAPI mixer alongside BLE hardware volume.
          </div>
        )}

        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 8,
            paddingTop: 6,
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
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
              checked={settings.hotkey_sync_enabled}
              onChange={(e) =>
                onToggleHotkeys(e.target.checked, settings.lock_usb_volume_on_sync)
              }
            />
            <Keyboard size={13} />
            <span>Bind PC Volume Keys → M60 Hardware Volume</span>
          </label>
          {settings.hotkey_sync_enabled && (
            <span className={`badge ${settings.hotkey_active ? 'ok' : ''}`}>
              {settings.hotkey_active ? 'Hotkeys Active' : settings.hotkey_error || 'Inactive'}
            </span>
          )}
        </div>
      </div>
    </section>
  )
}
