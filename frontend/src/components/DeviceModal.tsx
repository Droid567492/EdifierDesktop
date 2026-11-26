import { useEffect, useState } from 'react'
import { Bluetooth, Info, Loader2, Radio, Search, X } from 'lucide-react'
import { api } from '../api'
import type { ScannedDevice } from '../types'
import { AlertBanner } from './AlertBanner'

interface DeviceModalProps {
  open: boolean
  lastAddress: string | null
  lastName: string | null
  dismissedAlerts: string[]
  onDontShowAgain: (alertId: string) => void
  onClose: () => void
  onConnect: (address: string) => Promise<void>
}

export function DeviceModal({
  open,
  lastAddress,
  lastName,
  dismissedAlerts,
  onDontShowAgain,
  onClose,
  onConnect,
}: DeviceModalProps) {
  const [devices, setDevices] = useState<ScannedDevice[]>([])
  const [scanning, setScanning] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [manualAddr, setManualAddr] = useState(lastAddress ?? '')
  const [connectingAddr, setConnectingAddr] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runScan = async (includeAll = showAll) => {
    setScanning(true)
    setError(null)
    try {
      const res = await api.scanBle(6, includeAll)
      setDevices(res.devices)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'BLE scan failed')
    } finally {
      setScanning(false)
    }
  }

  useEffect(() => {
    if (open) {
      setManualAddr(lastAddress ?? '')
      void runScan(showAll)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  if (!open) return null

  const handleConnect = async (addr: string) => {
    setConnectingAddr(addr)
    setError(null)
    try {
      await onConnect(addr)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed')
    } finally {
      setConnectingAddr(null)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="card-header">
          <h2 className="card-title">
            <Bluetooth size={16} color="#f59e0b" />
            Connect Edifier M60 (BLE)
          </h2>
          <button className="btn btn-icon" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {!dismissedAlerts.includes('ble_connect_tips') && (
          <AlertBanner
            alertId="ble_connect_tips"
            variant="warning"
            icon={<Info size={15} />}
            message={
              <span style={{ fontSize: 12 }}>
                <strong>Connection tips:</strong> The M60 allows only{' '}
                <strong>one BLE connection at a time</strong> — close the EDIFIER
                ConneX phone app first. If the speaker isn&apos;t advertising while
                idle, wake it by playing audio or toggling Bluetooth/power.
              </span>
            }
            onDontShowAgain={onDontShowAgain}
          />
        )}

        {lastAddress && (
          <div className="device-row edifier">
            <div>
              <div style={{ fontWeight: 600 }}>
                Last Device: {lastName || 'Edifier M60'}
              </div>
              <div className="mono" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                {lastAddress}
              </div>
            </div>
            <button
              className="btn btn-primary"
              disabled={connectingAddr !== null}
              onClick={() => void handleConnect(lastAddress)}
            >
              {connectingAddr === lastAddress ? (
                <Loader2 size={14} className="spin" />
              ) : (
                'Reconnect'
              )}
            </button>
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showAll}
              onChange={(e) => {
                const next = e.target.checked
                setShowAll(next)
                void runScan(next)
              }}
            />
            Show unnamed / all BLE devices
          </label>
          <button
            className="btn"
            onClick={() => void runScan(showAll)}
            disabled={scanning}
          >
            {scanning ? <Loader2 size={14} /> : <Search size={14} />}
            {scanning ? 'Scanning…' : 'Rescan'}
          </button>
        </div>

        {error && !dismissedAlerts.includes('ble_modal_error') && (
          <AlertBanner
            alertId="ble_modal_error"
            variant="error"
            message={error}
            onDismiss={() => setError(null)}
            onDontShowAgain={(id) => {
              onDontShowAgain(id)
              setError(null)
            }}
          />
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {devices.length === 0 && !scanning && (
            <div style={{ padding: 18, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              No matching BLE peripherals found. Enable &quot;Show unnamed / all BLE
              devices&quot; or enter the speaker address manually below.
            </div>
          )}

          {devices.map((dev) => (
            <div
              key={dev.address}
              className={`device-row ${dev.is_edifier ? 'edifier' : ''}`}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
                  <span>{dev.name}</span>
                  {dev.is_edifier && <span className="badge hires">EDIFIER</span>}
                </div>
                <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                  {dev.address} {dev.rssi !== null ? `• ${dev.rssi} dBm` : ''}
                </div>
              </div>
              <button
                className="btn btn-primary"
                disabled={connectingAddr !== null}
                onClick={() => void handleConnect(dev.address)}
              >
                {connectingAddr === dev.address ? 'Connecting…' : 'Connect'}
              </button>
            </div>
          ))}
        </div>

        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
            Manual BLE MAC / Device ID
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              className="text-input mono"
              style={{ flex: 1 }}
              placeholder="e.g. AA:BB:CC:DD:EE:FF"
              value={manualAddr}
              onChange={(e) => setManualAddr(e.target.value)}
            />
            <button
              className="btn"
              disabled={!manualAddr.trim() || connectingAddr !== null}
              onClick={() => void handleConnect(manualAddr)}
            >
              <Radio size={14} />
              Connect
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
