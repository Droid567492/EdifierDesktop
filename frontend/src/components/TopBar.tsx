import { useEffect, useRef, useState } from 'react'
import {
  Activity,
  BellOff,
  Bluetooth,
  BluetoothConnected,
  Cpu,
  Download,
  MoreVertical,
  RefreshCw,
  Speaker,
  Usb,
} from 'lucide-react'
import type { AppSettings, BleState, UpdateState, UsbState } from '../types'

interface TopBarProps {
  ble: BleState
  usb: UsbState
  settings: AppSettings
  updateState: UpdateState
  wsConnected: boolean
  onOpenConnect: () => void
  onDisconnectBle: () => void
  onRefresh: () => void
  onToggleDemo: () => void
  onToggleDiagnostics: () => void
  onToggleAutoCheckUpdates: (enabled: boolean) => void
  onCheckUpdatesNow: () => void
  onResetDismissedAlerts: () => void
  showDiagnostics: boolean
}

export function TopBar({
  ble,
  usb,
  settings,
  updateState,
  wsConnected,
  onOpenConnect,
  onDisconnectBle,
  onRefresh,
  onToggleDemo,
  onToggleDiagnostics,
  onToggleAutoCheckUpdates,
  onCheckUpdatesNow,
  onResetDismissedAlerts,
  showDiagnostics,
}: TopBarProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!menuOpen) return

    const onMouseDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [menuOpen])

  const autoUpdatesOn = settings.auto_check_updates !== false
  const hasDismissedAlerts = (settings.dismissed_alerts?.length ?? 0) > 0
  const hasMenuBadge =
    ble.demo_mode ||
    showDiagnostics ||
    updateState.status === 'update_available' ||
    updateState.status === 'repo_moved' ||
    updateState.status === 'repo_not_found'

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-icon">
          <Speaker size={20} />
        </div>
        <div style={{ minWidth: 0 }}>
          <h1 className="brand-title">Edifier M60 // Studio Control</h1>
          <div className="brand-sub">
            <span className="mono">{ble.device_name || 'EDIFIER M60'}</span>
            {ble.firmware && <span className="badge mono">FW {ble.firmware}</span>}
            {!wsConnected && <span className="badge">Reconnecting UI…</span>}
          </div>
        </div>
      </div>

      <div className="topbar-controls">
        <button
          className={`status-pill ${ble.connected ? 'ble-on' : ''}`}
          onClick={ble.connected && !ble.demo_mode ? onDisconnectBle : onOpenConnect}
          title={
            ble.connected
              ? 'Click to manage or disconnect BLE link'
              : 'Scan and connect to Edifier M60 via Bluetooth LE'
          }
        >
          {ble.connected ? <BluetoothConnected size={14} /> : <Bluetooth size={14} />}
          <span>
            {ble.connecting
              ? 'BLE Connecting…'
              : ble.connected
                ? ble.demo_mode
                  ? 'BLE: Demo Link'
                  : 'BLE: Connected'
                : 'BLE: Disconnected'}
          </span>
        </button>

        {!ble.connected && (
          <button className="btn btn-primary" onClick={onOpenConnect}>
            <Bluetooth size={14} />
            Connect Speaker
          </button>
        )}

        <div
          className={`status-pill ${usb.connected || usb.usb_hardware_present ? 'usb-on' : ''}`}
          title={usb.protocol_note}
        >
          <Usb size={14} />
          <span>
            {usb.connected
              ? `USB-C: ${usb.volume_percent ?? '--'}%`
              : usb.usb_hardware_present
                ? 'USB-C: Attached'
                : 'USB-C: Not Detected'}
          </span>
        </div>

        <button
          className="btn btn-icon"
          onClick={onRefresh}
          disabled={!ble.connected}
          title="Refresh all speaker settings from BLE"
        >
          <RefreshCw size={15} />
        </button>

        <div className="menu-anchor" ref={menuRef}>
          <button
            className={`btn btn-icon ${menuOpen ? 'btn-cyan' : ''}`}
            onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label="More options"
            title="More options"
          >
            <MoreVertical size={15} />
            {hasMenuBadge && <span className="menu-dot-indicator" />}
          </button>

          {menuOpen && (
            <div className="dropdown-menu" role="menu">
              <button
                className={`dropdown-item ${autoUpdatesOn ? 'active-cyan' : ''}`}
                role="menuitemcheckbox"
                aria-checked={autoUpdatesOn}
                onClick={() => onToggleAutoCheckUpdates(!autoUpdatesOn)}
              >
                <span className="dropdown-item-label">
                  <Download size={14} />
                  <span>Check for Updates</span>
                </span>
                <span className={`badge ${autoUpdatesOn ? 'ok' : ''}`}>
                  {autoUpdatesOn ? 'ON' : 'OFF'}
                </span>
              </button>

              <button
                className="dropdown-item"
                role="menuitem"
                disabled={updateState.status === 'checking'}
                onClick={() => {
                  onCheckUpdatesNow()
                  setMenuOpen(false)
                }}
              >
                <span className="dropdown-item-label">
                  <RefreshCw size={14} />
                  <span>
                    {updateState.status === 'checking'
                      ? 'Checking Updates…'
                      : 'Check for Updates Now'}
                  </span>
                </span>
              </button>

              <div className="dropdown-divider" />

              <button
                className={`dropdown-item ${ble.demo_mode ? 'active-amber' : ''}`}
                role="menuitemcheckbox"
                aria-checked={ble.demo_mode}
                onClick={() => {
                  onToggleDemo()
                  setMenuOpen(false)
                }}
              >
                <span className="dropdown-item-label">
                  <Cpu size={14} />
                  <span>Demo Mode</span>
                </span>
                <span className={`badge ${ble.demo_mode ? 'hires' : ''}`}>
                  {ble.demo_mode ? 'ON' : 'OFF'}
                </span>
              </button>

              <button
                className={`dropdown-item ${showDiagnostics ? 'active-cyan' : ''}`}
                role="menuitemcheckbox"
                aria-checked={showDiagnostics}
                onClick={() => {
                  onToggleDiagnostics()
                  setMenuOpen(false)
                }}
              >
                <span className="dropdown-item-label">
                  <Activity size={14} />
                  <span>Diagnostics</span>
                </span>
                <span className={`badge ${showDiagnostics ? 'ok' : ''}`}>
                  {showDiagnostics ? 'Shown' : 'Hidden'}
                </span>
              </button>

              {hasDismissedAlerts && (
                <>
                  <div className="dropdown-divider" />
                  <button
                    className="dropdown-item"
                    role="menuitem"
                    onClick={() => {
                      onResetDismissedAlerts()
                      setMenuOpen(false)
                    }}
                  >
                    <span className="dropdown-item-label">
                      <BellOff size={14} />
                      <span>Restore Hidden Alerts</span>
                    </span>
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
