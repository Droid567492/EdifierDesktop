import { useState } from 'react'
import { Send, Terminal, X } from 'lucide-react'
import { api } from '../api'
import type { BleState, FrameLogEntry, UsbState } from '../types'

interface DiagnosticsDrawerProps {
  open: boolean
  ble: BleState
  usb: UsbState
  logs: FrameLogEntry[]
  onClose: () => void
}

export function DiagnosticsDrawer({
  open,
  ble,
  usb,
  logs,
  onClose,
}: DiagnosticsDrawerProps) {
  const [rawHex, setRawHex] = useState('AA EC 66 00 00')
  const [autoCs, setAutoCs] = useState(true)
  const [expectReply, setExpectReply] = useState(true)
  const [rawResult, setRawResult] = useState<string | null>(null)

  if (!open) return null

  const handleSendRaw = async (e: React.FormEvent) => {
    e.preventDefault()
    setRawResult(null)
    try {
      const res = await api.sendRawHex(rawHex, expectReply, autoCs)
      setRawResult(
        `Sent: ${res.sent_hex}${res.reply_hex ? `  →  Reply: ${res.reply_hex}` : ' (no reply)'}`,
      )
    } catch (err) {
      setRawResult(`Error: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  return (
    <section className="card">
      <div className="card-header">
        <h2 className="card-title">
          <Terminal size={15} color="#38bdf8" />
          Hardware Telemetry &amp; BLE Frame Inspector
        </h2>
        <button className="btn btn-icon" onClick={onClose}>
          <X size={15} />
        </button>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 10,
          fontSize: 12,
        }}
      >
        <div className="usb-subpanel">
          <div style={{ color: 'var(--text-muted)' }}>BLE Address / Classic MAC</div>
          <div className="mono">{ble.address || '—'}</div>
          <div className="mono" style={{ color: 'var(--text-secondary)' }}>
            Classic: {ble.classic_mac || '—'}
          </div>
        </div>
        <div className="usb-subpanel">
          <div style={{ color: 'var(--text-muted)' }}>Capabilities (0xD8)</div>
          <div className="mono" style={{ wordBreak: 'break-all', fontSize: 11 }}>
            {ble.capabilities?.raw_hex || '—'}
          </div>
        </div>
        <div className="usb-subpanel">
          <div style={{ color: 'var(--text-muted)' }}>USB-C Hardware (VID:PID)</div>
          <div className="mono">{usb.usb_vid_pid || 'Not detected'}</div>
          <div style={{ color: 'var(--text-secondary)', fontSize: 11 }}>
            {usb.device_name || usb.usb_pnp_name || 'No WASAPI endpoint'}
          </div>
        </div>
      </div>

      <div className="log-box">
        {logs.length === 0 ? (
          <div style={{ color: 'var(--text-muted)' }}>No BLE frames logged yet.</div>
        ) : (
          logs
            .slice()
            .reverse()
            .map((entry, idx) => (
              <div key={`${entry.ts}-${idx}`} className="log-line">
                <span style={{ color: 'var(--text-muted)' }}>
                  {entry.ts.slice(11, 23)}
                </span>
                <span
                  style={{
                    color:
                      entry.direction === 'TX'
                        ? 'var(--accent-amber)'
                        : 'var(--accent-cyan)',
                    fontWeight: 700,
                  }}
                >
                  {entry.direction}
                </span>
                <span style={{ color: 'var(--text-secondary)' }}>{entry.summary}</span>
                <span style={{ color: 'var(--text-primary)', wordBreak: 'break-all' }}>
                  {entry.hex}
                </span>
              </div>
            ))
        )}
      </div>

      <form
        onSubmit={handleSendRaw}
        style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}
      >
        <input
          className="text-input mono"
          style={{ flex: 1, minWidth: 240 }}
          value={rawHex}
          onChange={(e) => setRawHex(e.target.value)}
          placeholder="AA EC 66 00 00"
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--text-secondary)' }}>
          <input
            type="checkbox"
            checked={autoCs}
            onChange={(e) => setAutoCs(e.target.checked)}
          />
          Auto checksum
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--text-secondary)' }}>
          <input
            type="checkbox"
            checked={expectReply}
            onChange={(e) => setExpectReply(e.target.checked)}
          />
          Wait reply
        </label>
        <button className="btn btn-cyan" type="submit" disabled={!ble.connected}>
          <Send size={13} />
          Send Frame
        </button>
      </form>
      {rawResult && (
        <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
          {rawResult}
        </div>
      )}
    </section>
  )
}
