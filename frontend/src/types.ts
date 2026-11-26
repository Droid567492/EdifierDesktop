export interface EqBand {
  index: number
  freq: number
  gain_code: number
  gain_db: number
  q_raw: number
  filter_raw: number
}

export interface CustomEqState {
  format: number
  bands: EqBand[]
  timestamp: number | null
  name: string
}

export interface Capabilities {
  raw_hex: string
  eq_profile: number | null
  ldac_flag: number | null
  length: number
}

export type InputSource = 'bluetooth' | 'usb' | 'aux'
export type EqPreset = 'music' | 'monitor' | 'game' | 'movie' | 'customized'
export type LdacMode = 'disabled' | '48khz' | '96khz'
export type SmartLightTimer = '5s' | '10s' | '20s' | 'always_on'
export type SmartLightSensitivity = 'high' | 'general' | 'low'

export interface BleState {
  connected: boolean
  connecting: boolean
  demo_mode: boolean
  address: string | null
  device_name: string
  firmware: string | null
  classic_mac: string | null
  capabilities: Capabilities | null
  input_source: InputSource
  input_settling: boolean
  volume: number
  max_volume: number
  eq_preset: EqPreset
  custom_eq: CustomEqState
  ldac_mode: LdacMode
  prompt_tone: boolean
  smart_light_timer: SmartLightTimer
  smart_light_sensitivity: SmartLightSensitivity
  a2dp_state_code: number | null
  a2dp_state: string
  audio_decoding_code: number | null
  audio_decoding: string
  notice: string | null
  last_error: string | null
}

export interface UsbInterfaceInfo {
  class: string
  name: string
  instance_id: string
  status: string
}

export interface UsbState {
  connected: boolean
  device_name: string | null
  device_id: string | null
  is_default: boolean
  volume_percent: number | null
  muted: boolean | null
  usb_hardware_present: boolean
  usb_vid_pid: string | null
  usb_pnp_name: string | null
  hid_interfaces: UsbInterfaceInfo[]
  protocol_note: string
  error: string | null
}

export interface SavedEqPreset {
  id: string
  name: string
  gains_db: number[]
  freqs: number[]
  builtin: boolean
}

export interface AppSettings {
  last_device_address: string | null
  last_device_name: string | null
  hotkey_sync_enabled: boolean
  lock_usb_volume_on_sync: boolean
  hotkey_active?: boolean
  hotkey_error?: string | null
  autostart_enabled?: boolean
  autostart_error?: string | null
}

export interface FrameLogEntry {
  ts: string
  direction: 'TX' | 'RX'
  hex: string
  summary: string
}

export interface ScannedDevice {
  address: string
  name: string
  rssi: number | null
  service_uuids: string[]
  is_edifier: boolean
}

export interface AppSnapshot {
  ble_state: BleState
  usb_state: UsbState
  saved_eq_presets: SavedEqPreset[]
  settings: AppSettings
  recent_logs: FrameLogEntry[]
}
