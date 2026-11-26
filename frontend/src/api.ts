import type {
  AppSettings,
  AppSnapshot,
  BleState,
  EqPreset,
  InputSource,
  LdacMode,
  SavedEqPreset,
  ScannedDevice,
  SmartLightSensitivity,
  SmartLightTimer,
  SpeakerModel,
  SubOutLevel,
  UpdateState,
  UsbState,
} from './types'

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const err = await res.json()
      if (err?.detail) detail = String(err.detail)
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  getState: async (): Promise<AppSnapshot> => {
    const res = await fetch('/api/state')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json() as Promise<AppSnapshot>
  },

  scanBle: (timeout = 6, show_all = false) =>
    postJson<{ devices: ScannedDevice[] }>('/api/ble/scan', { timeout, show_all }),

  connectBle: (address: string) =>
    postJson<{ ble_state: BleState }>('/api/ble/connect', { address }),

  disconnectBle: () => postJson<{ ble_state: BleState }>('/api/ble/disconnect'),

  refreshBle: () => postJson<{ ble_state: BleState }>('/api/ble/refresh'),

  setDemoMode: (enabled: boolean, model: SpeakerModel = 'm60') =>
    postJson<{ ble_state: BleState }>('/api/demo', { enabled, model }),

  setVolume: (level: number) =>
    postJson<{ ble_state: BleState }>('/api/volume', { level }),

  setInput: (source: InputSource) =>
    postJson<{ ble_state: BleState }>('/api/input', { source }),

  sendPlayback: (action: 'play' | 'pause' | 'next' | 'previous') =>
    postJson<{ ble_state: BleState }>('/api/playback', { action }),

  setEqPreset: (preset: EqPreset) =>
    postJson<{ ble_state: BleState }>('/api/eq/preset', { preset }),

  setCustomEqBand: (
    index: number,
    gain_db: number,
    freq?: number,
    q_raw?: number,
  ) =>
    postJson<{ ble_state: BleState }>('/api/eq/custom/band', {
      index,
      gain_db,
      freq,
      q_raw,
    }),

  applyCustomEqAll: (
    bands: { index: number; gain_db: number; freq?: number; q_raw?: number }[],
    name?: string,
  ) => postJson<{ ble_state: BleState }>('/api/eq/custom/all', { bands, name }),

  saveEqProfile: (
    name: string,
    gains_db: number[],
    freqs: number[],
    model?: SpeakerModel,
  ) =>
    postJson<{ preset: SavedEqPreset; presets: SavedEqPreset[] }>('/api/eq/saved', {
      name,
      gains_db,
      freqs,
      model,
    }),

  deleteEqProfile: async (id: string) => {
    const res = await fetch(`/api/eq/saved/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
    if (!res.ok) throw new Error(`Delete failed (${res.status})`)
    return res.json() as Promise<{ presets: SavedEqPreset[] }>
  },

  setSmartLight: (timer: SmartLightTimer, sensitivity: SmartLightSensitivity) =>
    postJson<{ ble_state: BleState }>('/api/smart-light', { timer, sensitivity }),

  setSubOut: (level: SubOutLevel) =>
    postJson<{ ble_state: BleState }>('/api/sub-out', { level }),

  setMultipoint: (enabled: boolean) =>
    postJson<{ ble_state: BleState }>('/api/multipoint', { enabled }),

  setPowerSave: (enabled: boolean) =>
    postJson<{ ble_state: BleState }>('/api/power-save', { enabled }),

  setTimedOff: (minutes: number) =>
    postJson<{ ble_state: BleState }>('/api/timed-off', { minutes }),

  powerOffDevice: () =>
    postJson<{ ble_state: BleState }>('/api/device/power-off'),

  setPromptTone: (enabled: boolean) =>
    postJson<{ ble_state: BleState }>('/api/prompt-tone', { enabled }),

  setLdac: (mode: LdacMode) =>
    postJson<{ ble_state: BleState }>('/api/ldac', { mode }),

  renameDevice: (name: string) =>
    postJson<{ ble_state: BleState }>('/api/device/name', { name }),

  disconnectBtAudio: () =>
    postJson<{ ble_state: BleState }>('/api/device/disconnect-bt'),

  sendRawHex: (hex: string, expect_reply = true, auto_checksum = true) =>
    postJson<{ sent_hex: string; reply_hex: string | null }>('/api/raw', {
      hex,
      expect_reply,
      auto_checksum,
    }),

  refreshUsb: async (): Promise<{ usb_state: UsbState }> => {
    const res = await fetch('/api/usb/status')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json() as Promise<{ usb_state: UsbState }>
  },

  setUsbVolume: (percent: number) =>
    postJson<{ usb_state: UsbState }>('/api/usb/volume', { percent }),

  setUsbMute: (muted: boolean) =>
    postJson<{ usb_state: UsbState }>('/api/usb/mute', { muted }),

  lockUsbBitPerfect: () =>
    postJson<{ usb_state: UsbState }>('/api/usb/bit-perfect'),

  setHotkeys: (enabled: boolean, lock_usb_100: boolean) =>
    postJson<{ settings: AppSettings }>('/api/settings/hotkeys', {
      enabled,
      lock_usb_100,
    }),

  setAutostart: (enabled: boolean) =>
    postJson<{ settings: AppSettings }>('/api/settings/autostart', {
      enabled,
    }),

  setAutoCheckUpdates: (auto_check_updates: boolean) =>
    postJson<{ settings: AppSettings }>('/api/settings/updates', {
      auto_check_updates,
    }),

  checkForUpdates: () =>
    postJson<{ update_state: UpdateState }>('/api/updates/check'),

  applyUpdate: () =>
    postJson<{ update_state: UpdateState }>('/api/updates/apply'),

  dismissAlert: (alert_id: string) =>
    postJson<{ settings: AppSettings }>('/api/settings/alerts/dismiss', {
      alert_id,
    }),

  resetDismissedAlerts: () =>
    postJson<{ settings: AppSettings }>('/api/settings/alerts/reset'),
}
