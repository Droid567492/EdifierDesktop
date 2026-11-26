import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { DeviceModal } from './components/DeviceModal'
import { DiagnosticsDrawer } from './components/DiagnosticsDrawer'
import { EqualizerCard } from './components/EqualizerCard'
import { InputSourceCard } from './components/InputSourceCard'
import { SettingsCard } from './components/SettingsCard'
import { TopBar } from './components/TopBar'
import { VolumeCard } from './components/VolumeCard'
import type {
  AppSettings,
  AppSnapshot,
  BleState,
  EqPreset,
  FrameLogEntry,
  InputSource,
  LdacMode,
  SavedEqPreset,
  SmartLightSensitivity,
  SmartLightTimer,
  UsbState,
} from './types'

const INITIAL_BLE: BleState = {
  connected: false,
  connecting: false,
  demo_mode: false,
  address: null,
  device_name: 'EDIFIER M60',
  firmware: null,
  classic_mac: null,
  capabilities: null,
  input_source: 'bluetooth',
  input_settling: false,
  volume: 0,
  max_volume: 16,
  eq_preset: 'music',
  custom_eq: {
    format: 3,
    bands: [
      { index: 0, freq: 62, gain_code: 6, gain_db: 0, q_raw: 7, filter_raw: 0 },
      { index: 1, freq: 250, gain_code: 6, gain_db: 0, q_raw: 7, filter_raw: 0 },
      { index: 2, freq: 1000, gain_code: 6, gain_db: 0, q_raw: 7, filter_raw: 0 },
      { index: 3, freq: 4000, gain_code: 6, gain_db: 0, q_raw: 7, filter_raw: 0 },
      { index: 4, freq: 8000, gain_code: 6, gain_db: 0, q_raw: 7, filter_raw: 0 },
      { index: 5, freq: 16000, gain_code: 6, gain_db: 0, q_raw: 7, filter_raw: 0 },
    ],
    timestamp: null,
    name: '',
  },
  ldac_mode: 'disabled',
  prompt_tone: true,
  smart_light_timer: '10s',
  smart_light_sensitivity: 'general',
  a2dp_state_code: null,
  a2dp_state: 'unknown',
  audio_decoding_code: null,
  audio_decoding: 'Unknown',
  notice: null,
  last_error: null,
}

const INITIAL_USB: UsbState = {
  connected: false,
  device_name: null,
  device_id: null,
  is_default: false,
  volume_percent: null,
  muted: null,
  usb_hardware_present: false,
  usb_vid_pid: null,
  usb_pnp_name: null,
  hid_interfaces: [],
  protocol_note: '',
  error: null,
}

const INITIAL_SETTINGS: AppSettings = {
  last_device_address: null,
  last_device_name: null,
  hotkey_sync_enabled: false,
  lock_usb_volume_on_sync: true,
}

export default function App() {
  const [ble, setBle] = useState<BleState>(INITIAL_BLE)
  const [usb, setUsb] = useState<UsbState>(INITIAL_USB)
  const [savedPresets, setSavedPresets] = useState<SavedEqPreset[]>([])
  const [settings, setSettings] = useState<AppSettings>(INITIAL_SETTINGS)
  const [logs, setLogs] = useState<FrameLogEntry[]>([])
  const [wsConnected, setWsConnected] = useState(false)
  const [showConnectModal, setShowConnectModal] = useState(false)
  const [showDiagnostics, setShowDiagnostics] = useState(false)
  const [toastError, setToastError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const applySnapshot = useCallback((snap: AppSnapshot) => {
    setBle(snap.ble_state)
    setUsb(snap.usb_state)
    setSavedPresets(snap.saved_eq_presets)
    setSettings(snap.settings)
    setLogs(snap.recent_logs)
  }, [])

  useEffect(() => {
    let active = true
    let retryTimer: number | undefined

    api
      .getState()
      .then((snap) => {
        if (active) applySnapshot(snap)
      })
      .catch(() => {})

    const connectWs = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${proto}//${window.location.host}/ws`)
      wsRef.current = ws

      ws.onopen = () => {
        if (active) setWsConnected(true)
      }
      ws.onclose = () => {
        if (!active) return
        setWsConnected(false)
        retryTimer = window.setTimeout(connectWs, 2000)
      }
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data) as { type: string; data: unknown }
          if (msg.type === 'snapshot') {
            applySnapshot(msg.data as AppSnapshot)
          } else if (msg.type === 'ble_state') {
            setBle(msg.data as BleState)
          } else if (msg.type === 'usb_state') {
            setUsb(msg.data as UsbState)
          } else if (msg.type === 'settings') {
            setSettings(msg.data as AppSettings)
          } else if (msg.type === 'saved_eq_presets') {
            const d = msg.data as { presets: SavedEqPreset[] }
            setSavedPresets(d.presets)
          } else if (msg.type === 'frame_log') {
            setLogs((prev) => [...prev.slice(-199), msg.data as FrameLogEntry])
          }
        } catch {
          // ignore malformed event
        }
      }
    }

    connectWs()
    return () => {
      active = false
      window.clearTimeout(retryTimer)
      wsRef.current?.close()
    }
  }, [applySnapshot])

  const runAction = async (fn: () => Promise<unknown>) => {
    setToastError(null)
    try {
      await fn()
    } catch (err) {
      setToastError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div className="app-shell">
      <TopBar
        ble={ble}
        usb={usb}
        wsConnected={wsConnected}
        onOpenConnect={() => setShowConnectModal(true)}
        onDisconnectBle={() => void runAction(() => api.disconnectBle())}
        onRefresh={() => void runAction(() => api.refreshBle())}
        onToggleDemo={() =>
          void runAction(async () => {
            const res = await api.setDemoMode(!ble.demo_mode)
            setBle(res.ble_state)
          })
        }
        onToggleDiagnostics={() => setShowDiagnostics((s) => !s)}
        showDiagnostics={showDiagnostics}
      />

      {toastError && (
        <div className="notice-banner error">
          <span>{toastError}</span>
          <button className="btn" onClick={() => setToastError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {ble.notice && (
        <div className="notice-banner">
          <span>{ble.notice}</span>
        </div>
      )}

      {!ble.connected && !ble.connecting && (
        <div
          className="card"
          style={{
            flexDirection: 'row',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            background:
              'linear-gradient(90deg, rgba(245,158,11,0.09), rgba(56,189,248,0.05))',
          }}
        >
          <div style={{ minWidth: 0, flex: '1 1 240px' }}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>
              Ready to connect your Edifier M60
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>
              Connect over Bluetooth LE to control volume, inputs, 6-band EQ, smart
              light, and LDAC.
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn btn-primary"
              onClick={() => setShowConnectModal(true)}
            >
              Scan &amp; Connect BLE
            </button>
          </div>
        </div>
      )}

      <main className="main-grid">
        <VolumeCard
          ble={ble}
          usb={usb}
          settings={settings}
          onSetVolume={(lvl) =>
            void runAction(async () => {
              const res = await api.setVolume(lvl)
              setBle(res.ble_state)
            })
          }
          onSetUsbVolume={(pct) =>
            void runAction(async () => {
              const res = await api.setUsbVolume(pct)
              setUsb(res.usb_state)
            })
          }
          onSetUsbMute={(muted) =>
            void runAction(async () => {
              const res = await api.setUsbMute(muted)
              setUsb(res.usb_state)
            })
          }
          onLockBitPerfect={() =>
            void runAction(async () => {
              const res = await api.lockUsbBitPerfect()
              setUsb(res.usb_state)
            })
          }
          onToggleHotkeys={(enabled, lockUsb100) =>
            void runAction(async () => {
              const res = await api.setHotkeys(enabled, lockUsb100)
              setSettings(res.settings)
            })
          }
        />

        <InputSourceCard
          ble={ble}
          onSelectInput={(src: InputSource) =>
            void runAction(async () => {
              const res = await api.setInput(src)
              setBle(res.ble_state)
            })
          }
          onPlayback={(act) => void runAction(() => api.sendPlayback(act))}
        />

        <EqualizerCard
          ble={ble}
          savedPresets={savedPresets}
          onSelectPreset={(preset: EqPreset) =>
            void runAction(async () => {
              const res = await api.setEqPreset(preset)
              setBle(res.ble_state)
            })
          }
          onUpdateBand={(index, gainDb, freq, qRaw) =>
            void runAction(async () => {
              const res = await api.setCustomEqBand(index, gainDb, freq, qRaw)
              setBle(res.ble_state)
            })
          }
          onApplyAllBands={(bands, name) =>
            void runAction(async () => {
              const res = await api.applyCustomEqAll(bands, name)
              setBle(res.ble_state)
            })
          }
          onSaveProfile={(name, gainsDb, freqs) =>
            void runAction(async () => {
              const res = await api.saveEqProfile(name, gainsDb, freqs)
              setSavedPresets(res.presets)
            })
          }
          onDeleteProfile={(id) =>
            void runAction(async () => {
              const res = await api.deleteEqProfile(id)
              setSavedPresets(res.presets)
            })
          }
        />

        <SettingsCard
          ble={ble}
          settings={settings}
          onSetSmartLight={(timer: SmartLightTimer, sens: SmartLightSensitivity) =>
            void runAction(async () => {
              const res = await api.setSmartLight(timer, sens)
              setBle(res.ble_state)
            })
          }
          onSetPromptTone={(enabled) =>
            void runAction(async () => {
              const res = await api.setPromptTone(enabled)
              setBle(res.ble_state)
            })
          }
          onSetLdac={(mode: LdacMode) =>
            void runAction(async () => {
              const res = await api.setLdac(mode)
              setBle(res.ble_state)
            })
          }
          onRename={(name) =>
            void runAction(async () => {
              const res = await api.renameDevice(name)
              setBle(res.ble_state)
            })
          }
          onDisconnectBtAudio={() =>
            void runAction(async () => {
              const res = await api.disconnectBtAudio()
              setBle(res.ble_state)
            })
          }
          onToggleAutostart={(enabled) =>
            void runAction(async () => {
              const res = await api.setAutostart(enabled)
              setSettings(res.settings)
            })
          }
        />
      </main>

      <DiagnosticsDrawer
        open={showDiagnostics}
        ble={ble}
        usb={usb}
        logs={logs}
        onClose={() => setShowDiagnostics(false)}
      />

      <DeviceModal
        open={showConnectModal}
        lastAddress={settings.last_device_address}
        lastName={settings.last_device_name}
        onClose={() => setShowConnectModal(false)}
        onConnect={async (addr) => {
          const res = await api.connectBle(addr)
          setBle(res.ble_state)
        }}
      />
    </div>
  )
}
