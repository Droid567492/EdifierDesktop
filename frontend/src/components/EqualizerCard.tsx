import { useEffect, useRef, useState } from 'react'
import { BookmarkPlus, RotateCcw, Sliders, Trash2 } from 'lucide-react'
import type { BleState, EqBand, EqPreset, SavedEqPreset, SpeakerModel } from '../types'

interface EqualizerCardProps {
  ble: BleState
  savedPresets: SavedEqPreset[]
  onSelectPreset: (preset: EqPreset) => void
  onUpdateBand: (index: number, gainDb: number, freq?: number, qRaw?: number) => void
  onApplyAllBands: (
    bands: { index: number; gain_db: number; freq?: number; q_raw?: number }[],
    name?: string,
  ) => void
  onSaveProfile: (
    name: string,
    gainsDb: number[],
    freqs: number[],
    model: SpeakerModel,
  ) => void
  onDeleteProfile: (id: string) => void
}

const M60_PRESETS: { id: EqPreset; label: string }[] = [
  { id: 'music', label: 'Music' },
  { id: 'monitor', label: 'Monitor' },
  { id: 'game', label: 'Game' },
  { id: 'movie', label: 'Movie' },
  { id: 'customized', label: 'Customized' },
]

const M90_PRESETS: { id: EqPreset; label: string }[] = [
  { id: 'classic', label: 'Classic' },
  { id: 'monitor', label: 'Monitor' },
  { id: 'dynamic', label: 'Dynamic' },
  { id: 'custom', label: 'Custom' },
]

function formatFreq(hz: number): string {
  return hz >= 1000 ? `${hz / 1000} kHz` : `${hz} Hz`
}

export function EqualizerCard({
  ble,
  savedPresets,
  onSelectPreset,
  onUpdateBand,
  onApplyAllBands,
  onSaveProfile,
  onDeleteProfile,
}: EqualizerCardProps) {
  const [draftBands, setDraftBands] = useState<EqBand[]>(ble.custom_eq.bands)
  const [profileName, setProfileName] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const debounceRefs = useRef<Record<number, number>>({})

  useEffect(() => {
    if (ble.custom_eq.bands.length >= 6) {
      setDraftBands(ble.custom_eq.bands)
    }
  }, [ble.custom_eq.bands])

  const disabled = !ble.connected
  const isM90 = ble.model === 'm90'
  const presets = isM90 ? M90_PRESETS : M60_PRESETS
  const isCustomActive = ble.eq_preset === 'customized' || ble.eq_preset === 'custom'
  const visibleSavedPresets = savedPresets.filter(
    (p) => (p.model ?? (p.freqs.length === 9 ? 'm90' : 'm60')) === ble.model,
  )

  const handleSliderChange = (idx: number, gainDb: number) => {
    setDraftBands((prev) =>
      prev.map((b) => (b.index === idx ? { ...b, gain_db: gainDb } : b)),
    )
    window.clearTimeout(debounceRefs.current[idx])
    debounceRefs.current[idx] = window.setTimeout(() => {
      onUpdateBand(idx, gainDb)
    }, 90)
  }

  const handleFlatten = () => {
    const flat = draftBands.map((b) => ({ ...b, gain_db: 0 }))
    setDraftBands(flat)
    onApplyAllBands(
      flat.map((b) => ({ index: b.index, gain_db: 0, freq: b.freq, q_raw: b.q_raw })),
      'Flat',
    )
  }

  const handleLoadProfile = (p: SavedEqPreset) => {
    const updated = draftBands.map((b, i) => ({
      ...b,
      gain_db: p.gains_db[i] ?? 0,
      freq: p.freqs[i] ?? b.freq,
    }))
    setDraftBands(updated)
    onApplyAllBands(
      updated.map((b) => ({
        index: b.index,
        gain_db: b.gain_db,
        freq: b.freq,
        q_raw: b.q_raw,
      })),
      p.name,
    )
  }

  // SVG frequency response curve coordinates (600 x 110)
  const width = 600
  const height = 108
  const padX = 34
  const padY = 14
  const points = draftBands.map((b, idx) => {
    const x = padX + (idx / Math.max(1, draftBands.length - 1)) * (width - padX * 2)
    const norm = (3.0 - b.gain_db) / 6.0
    const y = padY + norm * (height - padY * 2)
    return { x, y, b }
  })

  const linePath = points
    .map((pt, i) => {
      if (i === 0) return `M ${pt.x} ${pt.y}`
      const prev = points[i - 1]
      const cx = (prev.x + pt.x) / 2
      return `C ${cx} ${prev.y}, ${cx} ${pt.y}, ${pt.x} ${pt.y}`
    })
    .join(' ')

  const areaPath = points.length
    ? `${linePath} L ${points[points.length - 1].x} ${height - padY} L ${points[0].x} ${height - padY} Z`
    : ''

  return (
    <section className="card" style={{ gridColumn: '1 / -1' }}>
      <div className="card-header" style={{ flexWrap: 'wrap' }}>
        <h2 className="card-title">
          <Sliders size={15} color="#f59e0b" />
          {isM90 ? '9-Band DSP Equalizer' : '6-Band DSP Equalizer'}
        </h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          {ble.custom_eq.name && isCustomActive && (
            <span className="badge hires">Profile: {ble.custom_eq.name}</span>
          )}
          <button
            className="btn"
            disabled={disabled}
            onClick={handleFlatten}
            title={`Reset all ${draftBands.length} bands to 0.0 dB`}
          >
            <RotateCcw size={13} />
            Flatten 0 dB
          </button>
          <button
            className="btn"
            onClick={() => setShowAdvanced((s) => !s)}
          >
            {showAdvanced ? (isM90 ? 'Hide Freq' : 'Hide Freq/Q') : isM90 ? 'Freq (Hz)' : 'Freq / Q'}
          </button>
        </div>
      </div>

      <div className="preset-pills">
        {presets.map((p) => (
          <button
            key={p.id}
            className={`preset-pill ${ble.eq_preset === p.id ? 'active' : ''}`}
            disabled={disabled}
            onClick={() => onSelectPreset(p.id)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Interactive Curve */}
      <div className="eq-curve-box">
        <svg viewBox={`0 0 ${width} ${height}`} className="eq-curve-svg" preserveAspectRatio="none">
          <defs>
            <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.34" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          {/* +3, 0, -3 dB gridlines */}
          {[
            { db: '+3', y: padY },
            { db: '0', y: height / 2 },
            { db: '-3', y: height - padY },
          ].map((g) => (
            <g key={g.db}>
              <line
                x1={padX}
                x2={width - padX}
                y1={g.y}
                y2={g.y}
                stroke={g.db === '0' ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.06)'}
                strokeDasharray={g.db === '0' ? undefined : '4 4'}
              />
              <text
                x={8}
                y={g.y + 3}
                fill="#64748b"
                fontSize="10"
                fontFamily="JetBrains Mono, monospace"
              >
                {g.db}
              </text>
            </g>
          ))}
          {areaPath && <path d={areaPath} fill="url(#eqFill)" />}
          {linePath && (
            <path d={linePath} fill="none" stroke="#f59e0b" strokeWidth="2.5" />
          )}
          {points.map((pt) => (
            <circle
              key={pt.b.index}
              cx={pt.x}
              cy={pt.y}
              r={4.5}
              fill="#f59e0b"
              stroke="#0f1219"
              strokeWidth={2}
            />
          ))}
        </svg>
      </div>

      {/* Band Faders */}
      <div className={`eq-bands-grid ${isM90 ? 'nine-band' : ''}`}>
        {draftBands.map((band) => (
          <div key={band.index} className="eq-band-col">
            <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: band.gain_db === 0 ? 'var(--text-secondary)' : 'var(--accent-amber)' }}>
              {band.gain_db > 0 ? `+${band.gain_db.toFixed(1)}` : band.gain_db.toFixed(1)} dB
            </span>
            <div className="eq-slider-wrap">
              <input
                type="range"
                className="eq-vertical"
                min={-3}
                max={3}
                step={0.5}
                disabled={disabled}
                value={band.gain_db}
                onChange={(e) => handleSliderChange(band.index, Number(e.target.value))}
                aria-label={`${formatFreq(band.freq)} EQ gain`}
              />
            </div>
            <span className="mono" style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
              {formatFreq(band.freq)}
            </span>
            {showAdvanced && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: '100%' }}>
                <input
                  type="number"
                  className="text-input mono"
                  style={{ width: '100%', padding: '3px 5px', fontSize: 11 }}
                  value={band.freq}
                  min={20}
                  max={20000}
                  disabled={disabled}
                  onChange={(e) => {
                    const nextFreq = Number(e.target.value)
                    setDraftBands((prev) =>
                      prev.map((b) =>
                        b.index === band.index ? { ...b, freq: nextFreq } : b,
                      ),
                    )
                  }}
                  onBlur={(e) =>
                    onUpdateBand(band.index, band.gain_db, Number(e.target.value), band.q_raw)
                  }
                  title="Center Frequency (Hz)"
                />
                {!isM90 && (
                  <input
                    type="number"
                    className="text-input mono"
                    style={{ width: '100%', padding: '3px 5px', fontSize: 11 }}
                    value={band.q_raw}
                    min={1}
                    max={255}
                    disabled={disabled}
                    onChange={(e) => {
                      const nextQ = Number(e.target.value)
                      setDraftBands((prev) =>
                        prev.map((b) =>
                          b.index === band.index ? { ...b, q_raw: nextQ } : b,
                        ),
                      )
                    }}
                    onBlur={(e) =>
                      onUpdateBand(band.index, band.gain_db, band.freq, Number(e.target.value))
                    }
                    title="Q-Factor raw register"
                  />
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Saved Local Profiles */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 10,
          paddingTop: 8,
          borderTop: '1px solid var(--border-subtle)',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginRight: 4 }}>
            Local Profiles:
          </span>
          {visibleSavedPresets.map((p) => (
            <div
              key={p.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                background: 'var(--bg-surface-2)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 8,
                padding: '3px 6px',
              }}
            >
              <button
                className="seg-btn"
                style={{ padding: '3px 6px' }}
                disabled={disabled}
                onClick={() => handleLoadProfile(p)}
              >
                {p.name}
              </button>
              {!p.builtin && (
                <button
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: 2,
                    display: 'grid',
                  }}
                  onClick={() => onDeleteProfile(p.id)}
                  title="Delete saved profile"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          ))}
        </div>

        <form
          style={{ display: 'flex', flexWrap: 'wrap', gap: 6, flex: '1 1 220px', justifyContent: 'flex-end' }}
          onSubmit={(e) => {
            e.preventDefault()
            if (!profileName.trim()) return
            onSaveProfile(
              profileName.trim(),
              draftBands.map((b) => b.gain_db),
              draftBands.map((b) => b.freq),
              ble.model,
            )
            setProfileName('')
          }}
        >
          <input
            className="text-input"
            style={{ flex: '1 1 150px', minWidth: 0 }}
            placeholder="Save current curve as…"
            value={profileName}
            maxLength={32}
            onChange={(e) => setProfileName(e.target.value)}
          />
          <button className="btn" type="submit" disabled={!profileName.trim()}>
            <BookmarkPlus size={14} />
            Save
          </button>
        </form>
      </div>
    </section>
  )
}
