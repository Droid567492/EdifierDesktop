import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Download, ExternalLink, Info, Search } from 'lucide-react'
import { api } from './api'
import { AlertBanner } from './components/AlertBanner'
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
  SpeakerModel,
  SubOutLevel,
  UpdateState,
  UsbState,
} from './types'

const INITIAL_BLE: BleState = {
  connected: false,
  connecting: false,
  demo_mode: false,
  model: 'm60',
  address: null,
  device_name: 'EDIFIER M60 / M90',
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
  sub_out_level: 'medium',
  multipoint: false,
  power_save: false,
  timed_off_minutes: 0,
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
  auto_check_updates: true,
  dismissed_alerts: [],
  app_version: '1.2.0',
  platform: 'win32',
}

const INITIAL_UPDATE: UpdateState = {
  status: 'idle',
  current_version: '1.2.0',
  latest_version: null,
  release_url: null,
  release_notes: null,
  asset_name: null,
  asset_url: null,
  asset_size: null,
  install_mode: 'source',
  message: null,
  repo_url: 'https://github.com/Droid567492/EdifierDesktop',
  repo_search_url: 'https://github.com/search?q=Edifier+M60+M90+Desktop+Control&type=repositories',
  checked_at: null,
}

export default function App() {
  const [ble, setBle] = useState<BleState>(INITIAL_BLE)
  const [usb, setUsb] = useState<UsbState>(INITIAL_USB)
  const [savedPresets, setSavedPresets] = useState<SavedEqPreset[]>([])
  const [settings, setSettings] = useState<AppSettings>(INITIAL_SETTINGS)
  const [updateState, setUpdateState] = useState<UpdateState>(INITIAL_UPDATE)
  const [logs, setLogs] = useState<FrameLogEntry[]>([])
  const [wsConnected, setWsConnected] = useState(false)
  const [showConnectModal, setShowConnectModal] = useState(false)
  const [showDiagnostics, setShowDiagnostics] = useState(false)
  const [toastError, setToastError] = useState<string | null>(null)
  const [manualUpdateCheck, setManualUpdateCheck] = useState(false)
  const [sessionHiddenAlerts, setSessionHiddenAlerts] = useState<string[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  const applySnapshot = useCallback((snap: AppSnapshot) => {
    setBle(snap.ble_state)
    setUsb(snap.usb_state)
    setSavedPresets(snap.saved_eq_presets)
    setSettings(snap.settings)
    if (snap.update_state) setUpdateState(snap.update_state)
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
          } else if (msg.type === 'update_state') {
            setUpdateState(msg.data as UpdateState)
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

  const dismissedForever = settings.dismissed_alerts ?? []
  const isAlertVisible = (id: string) =>
    !dismissedForever.includes(id) && !sessionHiddenAlerts.includes(id)

  const hideForSession = (id: string) => {
    setSessionHiddenAlerts((prev) => (prev.includes(id) ? prev : [...prev, id]))
  }

  const dontShowAgain = (id: string) => {
    void runAction(async () => {
      const res = await api.dismissAlert(id)
      setSettings(res.settings)
    })
  }

  const updateAvailableId = `update_available:${updateState.latest_version ?? 'new'}`

  return (
    <div className="app-shell">
      <TopBar
        ble={ble}
        usb={usb}
        settings={settings}
        updateState={updateState}
        wsConnected={wsConnected}
        onOpenConnect={() => setShowConnectModal(true)}
        onDisconnectBle={() => void runAction(() => api.disconnectBle())}
        onRefresh={() => void runAction(() => api.refreshBle())}
        onToggleDemo={(targetModel: SpeakerModel) =>
          void runAction(async () => {
            const disable = ble.demo_mode && ble.model === targetModel
            const res = await api.setDemoMode(!disable, targetModel)
            setBle(res.ble_state)
          })
        }
        onToggleDiagnostics={() => setShowDiagnostics((s) => !s)}
        onToggleAutoCheckUpdates={(enabled) =>
          void runAction(async () => {
            const res = await api.setAutoCheckUpdates(enabled)
            setSettings(res.settings)
          })
        }
        onCheckUpdatesNow={() => {
          setManualUpdateCheck(true)
          setSessionHiddenAlerts((prev) =>
            prev.filter(
              (id) =>
                id !== 'update_repo_missing' &&
                id !== 'update_error' &&
                id !== 'update_up_to_date',
            ),
          )
          void runAction(async () => {
            const res = await api.checkForUpdates()
            setUpdateState(res.update_state)
          })
        }}
        onResetDismissedAlerts={() => {
          setSessionHiddenAlerts([])
          void runAction(async () => {
            const res = await api.resetDismissedAlerts()
            setSettings(res.settings)
          })
        }}
        showDiagnostics={showDiagnostics}
      />

      {updateState.status === 'update_available' &&
        isAlertVisible(updateAvailableId) && (
          <AlertBanner
            alertId={updateAvailableId}
            variant="update"
            icon={<Download size={16} />}
            title={`Update available: v${updateState.latest_version}`}
            message={
              <span>
                {updateState.message}
                {updateState.asset_name ? ` (${updateState.asset_name})` : ''}
              </span>
            }
            actions={
              <>
                {updateState.install_mode !== 'source' && updateState.asset_url && (
                  <button
                    className="btn btn-primary"
                    style={{ padding: '4px 10px', fontSize: 12 }}
                    onClick={() =>
                      void runAction(async () => {
                        const res = await api.applyUpdate()
                        setUpdateState(res.update_state)
                      })
                    }
                  >
                    <Download size={13} />
                    Update Now
                  </button>
                )}
                {updateState.release_url && (
                  <a
                    className="btn"
                    style={{ padding: '4px 10px', fontSize: 12, textDecoration: 'none' }}
                    href={updateState.release_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink size={12} />
                    Release Notes
                  </a>
                )}
              </>
            }
            onDismiss={() => hideForSession(updateAvailableId)}
            onDontShowAgain={dontShowAgain}
          />
        )}

      {(updateState.status === 'repo_moved' ||
        updateState.status === 'repo_not_found') &&
        isAlertVisible('update_repo_missing') && (
          <AlertBanner
            alertId="update_repo_missing"
            variant="warning"
            icon={<AlertTriangle size={16} />}
            title="Auto-Update could not reach the GitHub repository"
            message={
              <span>
                {updateState.message ||
                  'The repository could not be found or appears to have changed name. Please look up the project on GitHub to confirm whether the repository was renamed.'}
              </span>
            }
            actions={
              <a
                className="btn btn-primary"
                style={{ padding: '4px 10px', fontSize: 12, textDecoration: 'none' }}
                href={updateState.repo_search_url}
                target="_blank"
                rel="noreferrer"
              >
                <Search size={12} />
                Look Up Project on GitHub
              </a>
            }
            onDismiss={() => hideForSession('update_repo_missing')}
            onDontShowAgain={dontShowAgain}
          />
        )}

      {(updateState.status === 'updating' || updateState.status === 'updated') &&
        updateState.message && (
          <AlertBanner
            alertId="update_progress"
            variant="info"
            icon={<Download size={15} />}
            message={updateState.message}
            onDismiss={() => hideForSession('update_progress')}
            onDontShowAgain={dontShowAgain}
          />
        )}

      {updateState.status === 'error' &&
        updateState.message &&
        isAlertVisible('update_error') && (
          <AlertBanner
            alertId="update_error"
            variant="error"
            icon={<AlertTriangle size={15} />}
            message={updateState.message}
            onDismiss={() => hideForSession('update_error')}
            onDontShowAgain={dontShowAgain}
          />
        )}

      {manualUpdateCheck &&
        updateState.status === 'up_to_date' &&
        updateState.message &&
        isAlertVisible('update_up_to_date') && (
          <AlertBanner
            alertId="update_up_to_date"
            variant="info"
            icon={<Info size={15} />}
            message={updateState.message}
            onDismiss={() => {
              setManualUpdateCheck(false)
              hideForSession('update_up_to_date')
            }}
            onDontShowAgain={(id) => {
              setManualUpdateCheck(false)
              dontShowAgain(id)
            }}
          />
        )}

      {toastError && isAlertVisible('toast_error') && (
        <AlertBanner
          alertId="toast_error"
          variant="error"
          icon={<AlertTriangle size={15} />}
          message={toastError}
          onDismiss={() => setToastError(null)}
          onDontShowAgain={(id) => {
            dontShowAgain(id)
            setToastError(null)
          }}
        />
      )}

      {ble.notice && isAlertVisible('ble_notice') && (
        <AlertBanner
          alertId="ble_notice"
          variant="warning"
          icon={<Info size={15} />}
          message={ble.notice}
          onDismiss={() => hideForSession('ble_notice')}
          onDontShowAgain={dontShowAgain}
        />
      )}

      {!ble.connected && !ble.connecting && isAlertVisible('welcome_connect') && (
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
              Ready to connect your Edifier M60 or M90
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>
              Connect over Bluetooth LE to control volume, inputs, 6/9-band EQ, LDAC,
              and hardware settings.
            </div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <button
              className="btn"
              onClick={() => dontShowAgain('welcome_connect')}
            >
              Don&apos;t show again
            </button>
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
          onSaveProfile={(name, gainsDb, freqs, model) =>
            void runAction(async () => {
              const res = await api.saveEqProfile(name, gainsDb, freqs, model)
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
          onSetSubOut={(level: SubOutLevel) =>
            void runAction(async () => {
              const res = await api.setSubOut(level)
              setBle(res.ble_state)
            })
          }
          onSetMultipoint={(enabled) =>
            void runAction(async () => {
              const res = await api.setMultipoint(enabled)
              setBle(res.ble_state)
            })
          }
          onSetPowerSave={(enabled) =>
            void runAction(async () => {
              const res = await api.setPowerSave(enabled)
              setBle(res.ble_state)
            })
          }
          onSetTimedOff={(minutes) =>
            void runAction(async () => {
              const res = await api.setTimedOff(minutes)
              setBle(res.ble_state)
            })
          }
          onPowerOff={() =>
            void runAction(async () => {
              const res = await api.powerOffDevice()
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
          onDontShowAgain={dontShowAgain}
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
        dismissedAlerts={dismissedForever}
        onDontShowAgain={dontShowAgain}
        onClose={() => setShowConnectModal(false)}
        onConnect={async (addr) => {
          const res = await api.connectBle(addr)
          setBle(res.ble_state)
        }}
      />

      <footer className="app-footer">
        <span>
          <strong className="mono">v{settings.app_version ?? '1.2.0'}</strong> •{' '}
          <a href={updateState.repo_url} target="_blank" rel="noreferrer">
            GitHub Repository
          </a>
        </span>
        <span>
          Unofficial Edifier M60 / M90 controller • Built using AI assistance • Provided as-is
        </span>
      </footer>
    </div>
  )
}
