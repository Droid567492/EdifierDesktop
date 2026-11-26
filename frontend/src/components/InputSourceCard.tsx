import {
  Bluetooth,
  Cable,
  Disc,
  Pause,
  Play,
  Radio,
  SkipBack,
  SkipForward,
  Sparkles,
  Tv,
  Usb,
} from 'lucide-react'
import type { BleState, InputSource } from '../types'

interface InputSourceCardProps {
  ble: BleState
  onSelectInput: (source: InputSource) => void
  onPlayback: (action: 'play' | 'pause' | 'next' | 'previous') => void
}

const M60_SOURCES: { id: InputSource; label: string; sub: string; icon: typeof Bluetooth }[] = [
  { id: 'bluetooth', label: 'Bluetooth', sub: 'A2DP / LDAC', icon: Bluetooth },
  { id: 'usb', label: 'USB-C', sub: 'UAC PCM 48/96k', icon: Usb },
  { id: 'aux', label: 'AUX In', sub: '3.5mm Analog', icon: Cable },
]

const M90_SOURCES: { id: InputSource; label: string; sub: string; icon: typeof Bluetooth }[] = [
  { id: 'bluetooth', label: 'Bluetooth', sub: 'A2DP / LDAC', icon: Bluetooth },
  { id: 'usb', label: 'USB-C', sub: 'UAC PCM', icon: Usb },
  { id: 'hdmi', label: 'HDMI', sub: 'ARC Audio', icon: Tv },
  { id: 'optical', label: 'Optical', sub: 'S/PDIF Toslink', icon: Disc },
  { id: 'aux', label: 'AUX In', sub: '3.5mm Analog', icon: Cable },
]

export function InputSourceCard({
  ble,
  onSelectInput,
  onPlayback,
}: InputSourceCardProps) {
  const disabled = !ble.connected
  const sources = ble.model === 'm90' ? M90_SOURCES : M60_SOURCES
  const isHiRes =
    ble.audio_decoding_code === 0x04 ||
    ble.audio_decoding_code === 0x05 ||
    ble.audio_decoding_code === 0x09

  return (
    <section className="card">
      <div className="card-header">
        <h2 className="card-title">
          <Radio size={15} color="#f59e0b" />
          Input Source &amp; Transport
        </h2>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {ble.input_settling && <span className="badge">Settling…</span>}
          <span className={`badge ${isHiRes ? 'hires' : ''}`}>
            {isHiRes && <Sparkles size={11} />}
            {ble.audio_decoding}
          </span>
        </div>
      </div>

      <div className={`source-grid ${ble.model === 'm90' ? 'five-col' : ''}`}>
        {sources.map(({ id, label, sub, icon: Icon }) => {
          const active = ble.input_source === id
          return (
            <button
              key={id}
              className={`source-tile ${active ? 'active' : ''} ${id === 'usb' ? 'usb' : ''}`}
              disabled={disabled}
              onClick={() => onSelectInput(id)}
            >
              <Icon size={20} />
              <span>{label}</span>
              <span style={{ fontSize: 11, opacity: 0.72, fontWeight: 500 }}>
                {sub}
              </span>
            </button>
          )
        })}
      </div>

      <div className="playback-bar">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 12, fontWeight: 600 }}>AVRCP Media Transport</span>
          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            A2DP Link: <strong className="mono">{ble.a2dp_state}</strong>
          </span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            className="btn btn-icon"
            disabled={disabled}
            onClick={() => onPlayback('previous')}
            title="Previous Track"
          >
            <SkipBack size={15} />
          </button>
          <button
            className="btn btn-icon"
            disabled={disabled}
            onClick={() => onPlayback('play')}
            title="Play"
          >
            <Play size={15} />
          </button>
          <button
            className="btn btn-icon"
            disabled={disabled}
            onClick={() => onPlayback('pause')}
            title="Pause"
          >
            <Pause size={15} />
          </button>
          <button
            className="btn btn-icon"
            disabled={disabled}
            onClick={() => onPlayback('next')}
            title="Next Track"
          >
            <SkipForward size={15} />
          </button>
        </div>
      </div>

      <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
        Note: The Edifier M60 / M90 USB-C port carries UAC audio only; all DSP, EQ,
        and input commands travel over BLE concurrently even while listening over USB-C.
      </div>
    </section>
  )
}
