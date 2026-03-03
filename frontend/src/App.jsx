import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import AuthScreen from './components/AuthScreen'
import PortalHeader from './components/PortalHeader'
import CreateProfilePage from './pages/CreateProfilePage'

const API_BASE_ENV = String(import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '')
const IS_LOCAL_DEV_HOST = typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location.hostname)
const LIVE_ECG_REFRESH_MS = 700

const DEFAULT_ECG_PROMPT = {
  durationSec: 10,
  samplingRate: 500,
  lead: 'II',
  noiseLevel: 0.02,
  arrhythmiaMode: 'auto',
  outputFormat: 'waveform',
}

const ECG_PRESETS = {
  normal: {
    label: 'Normal',
    form: { age: 25, sex: 1, thalach: 72, trestbps: 120, chol: 180, restecg: 0, exang: 0, oldpeak: 0.1 },
    prompt: { durationSec: 10, samplingRate: 500, lead: 'II', noiseLevel: 0.01, arrhythmiaMode: 'none' },
  },
  arrhythmia: {
    label: 'Arrhythmia',
    form: { age: 60, sex: 0, thalach: 120, restecg: 1, exang: 1, oldpeak: 2.2 },
    prompt: { durationSec: 15, samplingRate: 500, lead: 'II', noiseLevel: 0.03, arrhythmiaMode: 'high' },
  },
  cad: {
    label: 'CAD',
    form: { age: 55, sex: 1, thalach: 98, trestbps: 150, chol: 280, restecg: 1, exang: 1, oldpeak: 2.0 },
    prompt: { durationSec: 12, samplingRate: 500, lead: 'V5', noiseLevel: 0.02, arrhythmiaMode: 'mild' },
  },
  mi: {
    label: 'MI',
    form: { age: 62, sex: 1, thalach: 105, restecg: 1, exang: 1, oldpeak: 3.8, troponin: 1.2 },
    prompt: { durationSec: 10, samplingRate: 500, lead: 'III', noiseLevel: 0.02, arrhythmiaMode: 'high' },
  },
  hf: {
    label: 'Heart Failure',
    form: { age: 70, thalach: 88, trestbps: 155, restecg: 2, oldpeak: 1.6, bnp: 650, ejection_fraction: 35 },
    prompt: { durationSec: 12, samplingRate: 360, lead: 'V6', noiseLevel: 0.03, arrhythmiaMode: 'mild' },
  },
}

const FIELD_SECTIONS = [
  { title: 'Demographics & Symptoms', fields: ['age', 'sex', 'cp', 'exang', 'family_history'] },
  { title: 'Vitals & Functional Metrics', fields: ['trestbps', 'thalach', 'oldpeak', 'slope', 'ejection_fraction'] },
  { title: 'Lab & Imaging Indicators', fields: ['chol', 'fbs', 'restecg', 'ca', 'thal', 'creatinine', 'bnp', 'troponin'] },
  { title: 'Lifestyle & Comorbidity', fields: ['bmi', 'smoking', 'diabetes'] },
  { title: 'Advanced Clinical Inputs (Optional)', fields: ['dyspnea', 'edema', 'palpitations', 'syncope', 'heart_murmur', 'fever', 'crp', 'esr', 'oxygen_saturation', 'leg_pain_walking', 'abi_index', 'strep_history', 'cyanosis', 'growth_delay'] },
]

const PATIENT_FIELD_SECTIONS = [
  { title: 'Basic Health Inputs', fields: ['age', 'sex', 'cp', 'exang', 'family_history'] },
  { title: 'Lab & Imaging Indicators', fields: ['chol', 'fbs', 'restecg', 'ca', 'thal', 'creatinine', 'bnp', 'troponin'] },
  { title: 'Lifestyle & Comorbidity', fields: ['bmi', 'smoking', 'diabetes'] },
  { title: 'Optional Cardiac Vitals', fields: ['trestbps', 'thalach', 'oldpeak', 'slope', 'ejection_fraction'] },
  { title: 'Advanced Clinical Inputs (Optional)', fields: ['dyspnea', 'edema', 'palpitations', 'syncope', 'heart_murmur', 'fever', 'crp', 'esr', 'oxygen_saturation', 'leg_pain_walking', 'abi_index', 'strep_history', 'cyanosis', 'growth_delay'] },
]

const FIELD_CONFIG = {
  age: { label: 'Age (years)', type: 'number', min: 18, max: 95, step: 1 },
  sex: { label: 'Sex', type: 'select', options: [{ v: 0, t: 'Female' }, { v: 1, t: 'Male' }] },
  cp: { label: 'Chest Pain Type', type: 'select', options: [{ v: 0, t: 'Typical Angina' }, { v: 1, t: 'Atypical Angina' }, { v: 2, t: 'Non-Anginal Pain' }, { v: 3, t: 'Asymptomatic' }] },
  trestbps: { label: 'Resting BP (mmHg)', type: 'number', min: 80, max: 220, step: 1 },
  chol: { label: 'Cholesterol (mg/dL)', type: 'number', min: 100, max: 600, step: 1 },
  fbs: { label: 'Fasting Blood Sugar (mg/dL)', type: 'number', min: 60, max: 500, step: 1 },
  restecg: { label: 'Resting ECG', type: 'select', options: [{ v: 0, t: 'Normal' }, { v: 1, t: 'ST-T Abnormality' }, { v: 2, t: 'LV Hypertrophy' }] },
  thalach: { label: 'Max Heart Rate (bpm)', type: 'number', min: 60, max: 220, step: 1 },
  exang: { label: 'Exercise Angina', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  oldpeak: { label: 'ST Depression (mm)', type: 'number', min: 0, max: 7, step: 0.1 },
  slope: { label: 'ST Slope', type: 'select', options: [{ v: 0, t: 'Upsloping' }, { v: 1, t: 'Flat' }, { v: 2, t: 'Downsloping' }] },
  ca: { label: 'Blocked Vessels (0-3)', type: 'number', min: 0, max: 3, step: 1 },
  thal: { label: 'Thalassemia', type: 'select', options: [{ v: 1, t: 'Normal' }, { v: 2, t: 'Fixed Defect' }, { v: 3, t: 'Reversible Defect' }] },
  bmi: { label: 'BMI (kg/m2)', type: 'number', min: 15, max: 50, step: 0.1 },
  smoking: { label: 'Smoking', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  diabetes: { label: 'Diabetes', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  family_history: { label: 'Family History', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  creatinine: { label: 'Creatinine (mg/dL)', type: 'number', min: 0.3, max: 5, step: 0.1 },
  bnp: { label: 'BNP (pg/mL)', type: 'number', min: 0, max: 2000, step: 1 },
  troponin: { label: 'Troponin-I (ng/mL)', type: 'number', min: 0, max: 4, step: 0.01 },
  ejection_fraction: { label: 'Ejection Fraction (%)', type: 'number', min: 15, max: 80, step: 1 },
  dyspnea: { label: 'Shortness Of Breath', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  edema: { label: 'Swelling (Edema)', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  palpitations: { label: 'Palpitations', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  syncope: { label: 'Syncope / Dizziness', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  heart_murmur: { label: 'Heart Murmur', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  fever: { label: 'Fever', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  crp: { label: 'CRP (mg/L)', type: 'number', min: 0, max: 400, step: 0.1 },
  esr: { label: 'ESR (mm/hr)', type: 'number', min: 0, max: 150, step: 1 },
  oxygen_saturation: { label: 'Oxygen Saturation (%)', type: 'number', min: 50, max: 100, step: 1 },
  leg_pain_walking: { label: 'Leg Pain While Walking', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  abi_index: { label: 'ABI Index', type: 'number', min: 0.2, max: 2.0, step: 0.01 },
  strep_history: { label: 'Past Strep / Rheumatic History', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  cyanosis: { label: 'Cyanosis', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
  growth_delay: { label: 'Growth Delay (history)', type: 'select', options: [{ v: 0, t: 'No' }, { v: 1, t: 'Yes' }] },
}

const DEFAULT_FORM = {
  age: 56, sex: 1, cp: 2, trestbps: 142, chol: 245, fbs: 110, restecg: 1, thalach: 132,
  exang: 1, oldpeak: 2.1, slope: 1, ca: 1, thal: 2, bmi: 28.4, smoking: 1, diabetes: 0,
  family_history: 1, creatinine: 1.1, bnp: 178, troponin: 0.05, ejection_fraction: 51,
}

const OPTIONAL_FORM = {
  dyspnea: '', edema: '', palpitations: '', syncope: '', heart_murmur: '', fever: '',
  crp: '', esr: '', oxygen_saturation: '', leg_pain_walking: '', abi_index: '',
  strep_history: '', cyanosis: '', growth_delay: '',
}

const EMPTY_FORM = {
  ...Object.fromEntries(Object.keys(DEFAULT_FORM).map((k) => [k, ''])),
  ...OPTIONAL_FORM,
}

const DEFAULT_PROFILE_FORM = {
  full_name: '', age: '', sex: '', dob: '', phone: '', email: '', address: '', blood_group: '',
  emergency_contact: '', allergies: '', existing_conditions: '', notes: '',
}
const SUPPORTED_IMAGE_MIME = new Set(['image/png', 'image/jpeg', 'image/jpg'])
const SUPPORTED_IMAGE_EXT = new Set(['.png', '.jpg', '.jpeg'])

function toPayloadWithDefaults(form) {
  const out = {}
  for (const [k, defaultVal] of Object.entries(DEFAULT_FORM)) {
    const v = form[k]
    const resolved = (v === '' || v === null || v === undefined) ? Number(defaultVal) : Number(v)
    if (k === 'fbs') {
      // Model expects binary FBS flag: 1 when fasting blood sugar is above 120 mg/dL.
      out[k] = resolved > 120 ? 1 : 0
      continue
    }
    out[k] = resolved
  }
  for (const k of Object.keys(OPTIONAL_FORM)) {
    const v = form[k]
    if (v === '' || v === null || v === undefined) continue
    const n = Number(v)
    if (Number.isFinite(n)) out[k] = n
  }
  return out
}

function formatPct(value) {
  if (value === null || value === undefined) return '--'
  return `${Number(value).toFixed(1)}%`
}

function formatDateTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getPatientRiskCaption(level) {
  if (level === 'CRITICAL') return 'High-alert risk. Immediate hospital-level care is recommended.'
  if (level === 'HIGH') return 'High risk. Consult cardiology quickly and follow treatment closely.'
  if (level === 'MODERATE') return 'Moderate risk. Medication adherence and follow-up are important.'
  if (level === 'MINIMAL' || level === 'LOW') return 'Lower current risk. Keep prevention and routine follow-up.'
  return 'Risk level available after diagnosis.'
}

function getLifestylePlan(result) {
  const lines = []
  const risk = result?.risk_tier?.level || 'UNKNOWN'
  const hasCad = (result?.diseases || []).some((d) => d.id === 'cad')
  const hasHf = (result?.diseases || []).some((d) => d.id === 'hf')
  const hasMi = (result?.diseases || []).some((d) => d.id === 'mi')
  const hasArr = (result?.diseases || []).some((d) => d.id === 'arr')

  lines.push('Diet: low-sodium, high-fiber, low trans-fat, and balanced hydration.')
  lines.push('Exercise: begin with 30 minutes of walking most days unless clinician advises restrictions.')
  lines.push('Stress: daily sleep routine, breathing exercises, and reduced stimulants.')
  if (hasCad || hasMi) lines.push('Cardio protection: prioritize LDL reduction plan and omega-3 rich foods.')
  if (hasHf) lines.push('Heart failure care: monitor weight/fluid trend and avoid excess salt intake.')
  if (hasArr) lines.push('Rhythm care: reduce caffeine/energy drinks and track palpitation episodes.')
  if (risk === 'CRITICAL' || risk === 'HIGH') lines.push('Follow-up urgency: keep rapid cardiology review within 24-72 hours.')
  return lines
}

function getNextBestTests(result) {
  const tests = []
  const diseaseIds = (result?.diseases || []).map((d) => d.id)
  const recText = (result?.recommendations || []).map((r) => String(r.text || '').toLowerCase()).join(' ')
  const mentions = (token) => recText.includes(token)

  if (mentions('ecg') || diseaseIds.includes('arr')) tests.push('12-lead ECG and rhythm strip review')
  if (mentions('echo') || diseaseIds.includes('hf')) tests.push('2D Echo for chamber and ejection fraction assessment')
  if (mentions('troponin') || diseaseIds.includes('mi')) tests.push('Serial Troponin-I with acute coronary protocol')
  if (mentions('mri')) tests.push('Cardiac MRI tissue characterization')
  if (mentions('cath') || diseaseIds.includes('cad') || diseaseIds.includes('mi')) tests.push('Cath Lab / Coronary angiography planning')
  if (tests.length === 0) tests.push('Routine follow-up labs and repeat ECG at clinician discretion')
  return tests
}

function getEmergencyGuidance(result) {
  const risk = result?.risk_tier?.level || ''
  const score = Number(result?.master_probability || 0)
  const hasMi = (result?.diseases || []).some((d) => d.id === 'mi' && Number(d.probability || 0) > 80)
  const critical = risk === 'CRITICAL' || score >= 80 || hasMi
  if (!critical) {
    return ['No immediate emergency trigger from current AI score. If symptoms worsen, seek urgent care.']
  }
  return [
    'Emergency protocol: move patient to monitored emergency care / ICU pathway.',
    'Start acute chest pain protocol per hospital policy (aspirin/oxygen only when clinically indicated).',
    'Prepare advanced cardiac evaluation (urgent ECG, enzymes, and cath-lab readiness).',
  ]
}

function getSafetyStatusTitle(status) {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'blocked') return 'AI Safety Gate: Blocked'
  if (normalized === 'caution') return 'AI Safety Gate: Provisional'
  return 'AI Safety Gate: Clear'
}

function parseDoctorSummary(note) {
  const parts = String(note?.remarks || '')
    .split('|')
    .map((x) => x.trim())
    .filter(Boolean)
  const diseaseType = parts[0] || ''
  const severityLevel = parts[1] || ''
  const clinicalRemarks = parts.slice(2).join(' | ')
  const diseaseTypes = diseaseType
    ? diseaseType.split(/[,/;]+/).map((x) => x.trim()).filter(Boolean)
    : []
  const medications = String(note?.prescription || '')
    .split(/[,;]+/)
    .map((x) => x.trim())
    .filter(Boolean)
  return { diseaseType, severityLevel, clinicalRemarks, diseaseTypes, medications }
}

function normalizeEcgSignal(raw) {
  if (Array.isArray(raw)) {
    return raw
      .map((v) => Number(v))
      .filter((v) => Number.isFinite(v))
  }
  if (typeof raw === 'string' && raw.trim()) {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return normalizeEcgSignal(parsed)
    } catch {
      return []
    }
  }
  return []
}

function escHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function isSupportedDiagnosticImage(file) {
  if (!file) return false
  const mime = String(file.type || '').toLowerCase()
  if (SUPPORTED_IMAGE_MIME.has(mime)) return true
  const name = String(file.name || '').toLowerCase()
  const dot = name.lastIndexOf('.')
  const ext = dot >= 0 ? name.slice(dot) : ''
  return SUPPORTED_IMAGE_EXT.has(ext)
}

function isBlobLikeUpload(value) {
  return typeof Blob !== 'undefined' && value instanceof Blob
}

function resolveImageUploadFile(fileOverride, stateFile) {
  if (isBlobLikeUpload(fileOverride)) return fileOverride
  if (isBlobLikeUpload(stateFile)) return stateFile
  return null
}

async function fetchJsonSafe(url, options) {
  const response = await fetch(url, options)
  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { error: text?.slice(0, 220) || 'Non-JSON response from server' }
  }
  return { response, data }
}

async function authJsonWith405Fallback(url, payload) {
  const first = await fetchJsonSafe(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (first.response.status !== 405) return first
  const qs = new URLSearchParams()
  Object.entries(payload || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v) !== '') qs.set(k, String(v))
  })
  return fetchJsonSafe(`${url}?${qs.toString()}`)
}

async function postImageSummaryWithFieldFallback(url, file, fields, onApiBaseDetected) {
  let lastData = null
  let lastStatus = 0
  if (!isBlobLikeUpload(file)) {
    return {
      response: { ok: false, status: 400 },
      data: { error: 'Invalid image input. Please choose PNG/JPG/JPEG file again.' },
    }
  }
  const parseJson = async (response) => {
    try {
      return await response.json()
    } catch {
      return null
    }
  }
  const isMissingImageError = (response, data) => {
    if (response.status !== 400) return false
    const message = String(data?.error || '').toLowerCase()
    return message.includes('missing file field') || message.includes('no image received')
  }
  const inferUploadMimeType = (uploadedFile) => {
    const mime = String(uploadedFile?.type || '').toLowerCase()
    if (mime) return mime
    const name = String(uploadedFile?.name || '').toLowerCase()
    if (name.endsWith('.png')) return 'image/png'
    if (name.endsWith('.jpeg') || name.endsWith('.jpg')) return 'image/jpeg'
    return 'application/octet-stream'
  }

  const tryRawBodyUpload = async (targetUrl) => {
    const mime = inferUploadMimeType(file)
    const headers = mime ? { 'Content-Type': mime } : {}
    const response = await fetch(targetUrl, {
      method: 'POST',
      headers,
      body: file,
    })
    const data = await parseJson(response)
    lastData = data
    lastStatus = response.status
    return { response, data }
  }

  const tryUrl = async (targetUrl) => {
    for (const field of fields) {
      const formData = new FormData()
      formData.append(field, file, file?.name || `${field}.jpg`)
      const response = await fetch(targetUrl, { method: 'POST', body: formData })
      const data = await parseJson(response)
      if (response.ok) return { response, data, missingFieldError: false }
      lastData = data
      lastStatus = response.status
      if (!isMissingImageError(response, data)) {
        return { response, data, missingFieldError: false }
      }
    }
    const rawAttempt = await tryRawBodyUpload(targetUrl)
    if (rawAttempt.response.ok) return { ...rawAttempt, missingFieldError: false }
    return { ...rawAttempt, missingFieldError: isMissingImageError(rawAttempt.response, rawAttempt.data) }
  }

  const first = await tryUrl(url)
  if (first.response.ok || !first.missingFieldError) return first

  const altBase = await discoverBackendBase()
  if (typeof onApiBaseDetected === 'function') onApiBaseDetected(altBase)
  if (altBase && !url.startsWith(altBase)) {
    const endpoint = (() => {
      try {
        return new URL(url).pathname
      } catch {
        return '/api/ecg-image-summary'
      }
    })()
    const second = await tryUrl(`${altBase}${endpoint}`)
    if (second.response.ok) return second
  }
  return { response: { ok: false, status: lastStatus }, data: lastData }
}

async function discoverBackendBase() {
  const candidates = []
  if (API_BASE_ENV) candidates.push(API_BASE_ENV)
  if (!API_BASE_ENV) candidates.push('')
  if (IS_LOCAL_DEV_HOST) {
    for (let port = 5000; port <= 5040; port += 1) {
      const candidate = `http://127.0.0.1:${port}`
      if (!candidates.includes(candidate)) candidates.push(candidate)
    }
  }
  let fallbackBase = API_BASE_ENV || ''
  for (const base of candidates) {
    try {
      const { response, data } = await fetchJsonSafe(`${base}/api/health`)
      if (response.ok && data?.status === 'ok') {
        fallbackBase = base
        if (data?.image_upload_field_fallback) return base
      }
    } catch {
      // continue
    }
  }
  return fallbackBase
}

function App() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [viewerRole, setViewerRole] = useState('doctor')
  const [authMode, setAuthMode] = useState('login')
  const [authStage, setAuthStage] = useState('credentials')
  const [authToken, setAuthToken] = useState('')
  const [authUser, setAuthUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(false)
  const [otpCode, setOtpCode] = useState('')
  const [otpSession, setOtpSession] = useState(null)
  const [authForm, setAuthForm] = useState({
    name: '',
    email: '',
    mobile: '',
    password: '',
    role: 'patient',
    login: '',
  })
  const [profileForm, setProfileForm] = useState(DEFAULT_PROFILE_FORM)
  const [profiles, setProfiles] = useState([])
  const [activeProfileId, setActiveProfileId] = useState('')
  const [history, setHistory] = useState([])
  const [health, setHealth] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [loadingPredict, setLoadingPredict] = useState(false)
  const [creatingProfile, setCreatingProfile] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)
  const [chatText, setChatText] = useState('')
  const [chatLog, setChatLog] = useState([])
  const [ecgImageFile, setEcgImageFile] = useState(null)
  const [ecgImageSummary, setEcgImageSummary] = useState(null)
  const [ecgImageAnalyzing, setEcgImageAnalyzing] = useState(false)
  const [assistantEcgSignal, setAssistantEcgSignal] = useState([])
  const [assistantEcgMeta, setAssistantEcgMeta] = useState({ hr: null, sampleRate: null, durationSec: null })
  const [assistantEcgLoading, setAssistantEcgLoading] = useState(false)
  const [assistantEcgBootstrapped, setAssistantEcgBootstrapped] = useState(false)
  const [assistantEcgExpanded, setAssistantEcgExpanded] = useState(false)
  const [assistantEcgLive, setAssistantEcgLive] = useState(false)
  const [assistantEcgScroll, setAssistantEcgScroll] = useState(0)
  const [assistantEcgPrompt, setAssistantEcgPrompt] = useState(DEFAULT_ECG_PROMPT)
  const [mriImageFile, setMriImageFile] = useState(null)
  const [mriImageSummary, setMriImageSummary] = useState(null)
  const [mriImageAnalyzing, setMriImageAnalyzing] = useState(false)
  const [cathImageFile, setCathImageFile] = useState(null)
  const [cathImageSummary, setCathImageSummary] = useState(null)
  const [cathImageAnalyzing, setCathImageAnalyzing] = useState(false)
  const [defaultsAppliedFields, setDefaultsAppliedFields] = useState([])
  const [apiBase, setApiBase] = useState(API_BASE_ENV)
  const [patientUploadFile, setPatientUploadFile] = useState(null)
  const [patientUploadSummary, setPatientUploadSummary] = useState('')
  const [patientUploadType, setPatientUploadType] = useState('report')
  const [patientUploadLoading, setPatientUploadLoading] = useState(false)
  const [patientUploadResult, setPatientUploadResult] = useState(null)
  const [patientUploads, setPatientUploads] = useState([])
  const [patientDoctorSummaries, setPatientDoctorSummaries] = useState([])
  const [selectedDoctorSummaryId, setSelectedDoctorSummaryId] = useState('')
  const [patientDoctors, setPatientDoctors] = useState([])
  const [patientAppointments, setPatientAppointments] = useState([])
  const [patientSelectedDoctorId, setPatientSelectedDoctorId] = useState('')
  const [patientAppointmentDate, setPatientAppointmentDate] = useState('')
  const [patientAppointmentNotes, setPatientAppointmentNotes] = useState('')
  const [patientBookingLoading, setPatientBookingLoading] = useState(false)
  const [doctorPatientId, setDoctorPatientId] = useState('')
  const [doctorPatientData, setDoctorPatientData] = useState(null)
  const [doctorSearchResults, setDoctorSearchResults] = useState([])
  const [doctorUploadFile, setDoctorUploadFile] = useState(null)
  const [doctorUploadType, setDoctorUploadType] = useState('report')
  const [doctorUploadSummary, setDoctorUploadSummary] = useState('')
  const [doctorUploadLoading, setDoctorUploadLoading] = useState(false)
  const [doctorNotePrescription, setDoctorNotePrescription] = useState('')
  const [doctorNoteRemarks, setDoctorNoteRemarks] = useState('')
  const [doctorNoteSaving, setDoctorNoteSaving] = useState(false)
  const [doctorDashboard, setDoctorDashboard] = useState({
    overview: {
      total_patients: 0,
      today_appointments: 0,
      pending_reports: 0,
      uploaded_scans_to_review: 0,
      ai_alerts: 0,
    },
    charts: {
      disease_distribution: [],
      monthly_patient_count: [],
      diagnosis_success_rate: 0,
    },
  })
  const [doctorAppointments, setDoctorAppointments] = useState([])
  const [doctorAlerts, setDoctorAlerts] = useState([])
  const [_doctorMessages, setDoctorMessages] = useState([])
  const [doctorMessageText, setDoctorMessageText] = useState('')
  const [doctorFollowUpDate, setDoctorFollowUpDate] = useState('')
  const [doctorConsultLink, setDoctorConsultLink] = useState('')
  const [doctorDiseaseType, setDoctorDiseaseType] = useState('')
  const [doctorSeverityLevel, setDoctorSeverityLevel] = useState('')
  const [doctorImagePrimary, setDoctorImagePrimary] = useState('')
  const [doctorImageCompare, setDoctorImageCompare] = useState('')
  const [doctorImageZoom, setDoctorImageZoom] = useState(1)
  const [doctorAcceptedPatientUploads, setDoctorAcceptedPatientUploads] = useState([])
  const [analyzerDragTarget, setAnalyzerDragTarget] = useState('')
  const [patientView, setPatientView] = useState('workspace')
  const [portalPage, setPortalPage] = useState('workspace')
  const [diagnosisStage, setDiagnosisStage] = useState('inputs')
  const navigatePortalPage = useCallback((nextPage) => {
    setPortalPage(nextPage)
    if (nextPage === 'diagnosis') setDiagnosisStage('inputs')
    if (viewerRole === 'patient' && patientView === 'create-profile') {
      setPatientView('workspace')
    }
  }, [viewerRole, patientView])
  const navigateWorkflowStep = useCallback((step) => {
    if (step.page === 'diagnosis') {
      setPortalPage('diagnosis')
      setDiagnosisStage(step.stage || 'inputs')
      if (viewerRole === 'patient' && patientView === 'create-profile') setPatientView('workspace')
      return
    }
    navigatePortalPage(step.page)
  }, [navigatePortalPage, patientView, viewerRole])
  const navigateTopPage = useCallback((target) => {
    if (viewerRole === 'patient' && patientView === 'create-profile') setPatientView('workspace')
    if (target === 'workspace') {
      setPortalPage('workspace')
      return
    }
    if (target === 'inputs') {
      setPortalPage('diagnosis')
      setDiagnosisStage('inputs')
      return
    }
    if (target === 'diagnosis') {
      setPortalPage('diagnosis')
      setDiagnosisStage('diagnosis')
      return
    }
    if (target === 'report') {
      setPortalPage('assistant')
    }
  }, [patientView, viewerRole])

  const activeProfile = useMemo(
    () => profiles.find((p) => String(p.id) === String(activeProfileId)) || null,
    [profiles, activeProfileId],
  )

  const riskTone = useMemo(() => {
    const level = result?.risk_tier?.level || ''
    if (level === 'CRITICAL') return 'risk-critical'
    if (level === 'HIGH') return 'risk-high'
    if (level === 'MODERATE') return 'risk-moderate'
    return 'risk-low'
  }, [result])

  const selectedDoctorSummary = useMemo(
    () => patientDoctorSummaries.find((s) => String(s.id) === String(selectedDoctorSummaryId)) || null,
    [patientDoctorSummaries, selectedDoctorSummaryId],
  )
  const selectedDoctorSummaryEcg = useMemo(
    () => normalizeEcgSignal(selectedDoctorSummary?.ecg_signal),
    [selectedDoctorSummary],
  )
  const assistantVisibleEcg = useMemo(() => {
    const diagnosisSignal = normalizeEcgSignal(result?.ecg_signal)
    if (portalPage === 'assistant' && assistantEcgSignal.length > 0) {
      if (!assistantEcgLive || assistantEcgSignal.length < 2) return assistantEcgSignal
      const shift = Math.abs(assistantEcgScroll) % assistantEcgSignal.length
      if (!shift) return assistantEcgSignal
      return [...assistantEcgSignal.slice(shift), ...assistantEcgSignal.slice(0, shift)]
    }
    if (diagnosisSignal.length > 0) return diagnosisSignal
    if (assistantEcgSignal.length > 0) return assistantEcgSignal
    if (selectedDoctorSummaryEcg.length > 0) return selectedDoctorSummaryEcg
    return []
  }, [assistantEcgLive, assistantEcgScroll, assistantEcgSignal, portalPage, result?.ecg_signal, selectedDoctorSummaryEcg])
  const assistantDisplayHr = useMemo(() => {
    const fromResultForm = Number(form?.thalach)
    if (normalizeEcgSignal(result?.ecg_signal).length > 0 && Number.isFinite(fromResultForm)) return Math.round(fromResultForm)
    if (Number.isFinite(Number(assistantEcgMeta.hr))) return Math.round(Number(assistantEcgMeta.hr))
    return null
  }, [assistantEcgMeta.hr, form?.thalach, result?.ecg_signal])
  const doctorPendingAppointments = useMemo(
    () => (doctorAppointments || []).filter((a) => String(a?.status || '').toLowerCase() === 'pending'),
    [doctorAppointments],
  )
  const hasClinicalSubject = viewerRole === 'doctor'
    ? Boolean(doctorPatientData?.patient?.user_id)
    : Boolean(activeProfileId)
  const stepItems = useMemo(() => {
    const roleLabel = viewerRole === 'doctor' ? 'Patient' : 'Profile'
    const hasDiagnosis = Boolean(result)
    const activeStep = (() => {
      if (portalPage === 'workspace') return 1
      if (portalPage === 'diagnosis') return diagnosisStage === 'diagnosis' ? 3 : 2
      if (portalPage === 'assistant') return 4
      return 1
    })()
    return [
      { id: 1, label: roleLabel, done: hasClinicalSubject, active: activeStep === 1, page: 'workspace', stage: null },
      { id: 2, label: 'Inputs', done: hasClinicalSubject && (portalPage !== 'workspace' || hasDiagnosis), active: activeStep === 2, page: 'diagnosis', stage: 'inputs' },
      { id: 3, label: 'Diagnosis', done: hasDiagnosis, active: activeStep === 3, page: 'diagnosis', stage: 'diagnosis' },
      { id: 4, label: 'Report', done: hasDiagnosis && portalPage === 'assistant', active: activeStep === 4, page: 'assistant', stage: null },
    ]
  }, [viewerRole, hasClinicalSubject, portalPage, diagnosisStage, result])
  const metricCards = useMemo(() => {
    if (!result) return []
    const ef = Number(form?.ejection_fraction)
    const troponin = Number(form?.troponin)
    const bnp = Number(form?.bnp)
    const safe = (v, suffix = '') => (Number.isFinite(Number(v)) ? `${Number(v).toFixed(1)}${suffix}` : '--')
    const asPct = (v) => safe(v, '%')
    const efTone = Number.isFinite(ef) ? (ef < 40 ? 'critical' : ef < 55 ? 'caution' : 'normal') : 'info'
    const trTone = Number.isFinite(troponin) ? (troponin > 0.5 ? 'critical' : troponin > 0.04 ? 'caution' : 'normal') : 'info'
    const bnpTone = Number.isFinite(bnp) ? (bnp > 400 ? 'critical' : bnp > 100 ? 'caution' : 'normal') : 'info'
    return [
      { label: 'Overall Risk', value: asPct(result.master_probability), tone: 'info' },
      { label: 'Raw Model', value: asPct(result.raw_model_probability), tone: 'info' },
      { label: 'Clinical Severity', value: asPct(result.clinical_severity_score), tone: 'info' },
      { label: 'Ejection Fraction', value: Number.isFinite(ef) ? `${ef.toFixed(0)}%` : '--', tone: efTone },
      { label: 'Troponin-I', value: Number.isFinite(troponin) ? `${troponin.toFixed(2)} ng/mL` : '--', tone: trTone },
      { label: 'BNP', value: Number.isFinite(bnp) ? `${bnp.toFixed(0)} pg/mL` : '--', tone: bnpTone },
    ]
  }, [result, form])
  const safetyAssessment = useMemo(() => {
    const safety = result?.safety_assessment
    if (!safety || typeof safety !== 'object') return null
    const status = String(safety.status || 'ok').toLowerCase()
    const tone = status === 'blocked' ? 'blocked' : status === 'caution' ? 'caution' : 'ok'
    return {
      status,
      tone,
      title: getSafetyStatusTitle(status),
      summary: String(safety.summary || ''),
      clinicalJustification: String(safety.clinical_justification || ''),
      reasons: Array.isArray(safety.reasons) ? safety.reasons : [],
      confidenceScore: Number.isFinite(Number(safety.confidence_score)) ? Number(safety.confidence_score) : null,
      boundaryDistance: Number.isFinite(Number(safety?.uncertainty?.boundary_distance_pct))
        ? Number(safety.uncertainty.boundary_distance_pct)
        : null,
      oodCount: Number.isFinite(Number(safety?.uncertainty?.ood_feature_count))
        ? Number(safety.uncertainty.ood_feature_count)
        : null,
    }
  }, [result])

  const loadProfiles = useCallback(async (base, tokenOverride) => {
    const token = tokenOverride || authToken
    if (!token) {
      setProfiles([])
      return
    }
    const { response, data } = await fetchJsonSafe(`${base}/api/profiles`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load profiles')
    setProfiles(Array.isArray(data) ? data : [])
  }, [authToken])

  const loadHistory = useCallback(async (base, profileId, tokenOverride) => {
    const token = tokenOverride || authToken
    if (!profileId) {
      setHistory([])
      return
    }
    if (!token) {
      setHistory([])
      return
    }
    const { response, data } = await fetchJsonSafe(`${base}/api/profiles/${profileId}/diagnoses`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load profile history')
    setHistory(Array.isArray(data) ? data : [])
  }, [authToken])

  const bootstrap = useCallback(async (baseArg) => {
    setError('')
    const base = baseArg || (await discoverBackendBase())
    setApiBase(base)
    try {
      const { response, data } = await fetchJsonSafe(`${base}/api/health`)
      if (!response.ok) throw new Error(data?.error || `Health check failed (${response.status})`)
      setHealth(data)
      if (authToken) {
        await loadProfiles(base)
        if (activeProfileId) await loadHistory(base, activeProfileId)
      } else {
        setProfiles([])
        setHistory([])
      }
    } catch (e) {
      setHealth(null)
      setProfiles([])
      setHistory([])
      const target = base || '(same origin)'
      const deploymentHint = (!IS_LOCAL_DEV_HOST && !API_BASE_ENV)
        ? ' Set VITE_API_BASE in Netlify to your backend URL.'
        : ''
      setError(`Cannot connect to API at ${target}. ${e.message}${deploymentHint}`)
    }
  }, [activeProfileId, authToken, loadHistory, loadProfiles])

  useEffect(() => {
    bootstrap()
  }, [bootstrap])

  useEffect(() => {
    if (!authToken) {
      setProfiles([])
      setHistory([])
      setActiveProfileId('')
      return
    }
    loadProfiles(apiBase).catch((e) => setError(e.message))
  }, [apiBase, authToken, loadProfiles])

  const loadPatientUploads = useCallback(async (tokenOverride) => {
    const token = tokenOverride || authToken
    if (!token) return
    const { response, data } = await fetchJsonSafe(`${apiBase}/api/patient-records`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load uploaded records')
    const rows = Array.isArray(data) ? data : []
    const seen = new Set()
    const deduped = []
    for (const row of rows) {
      const key = String(row?.id ?? `${row?.file_url || ''}|${row?.upload_date || ''}`)
      if (seen.has(key)) continue
      seen.add(key)
      deduped.push(row)
    }
    setPatientUploads(deduped)
  }, [apiBase, authToken])

  const loadPatientDoctorSummaries = useCallback(async (tokenOverride) => {
    const token = tokenOverride || authToken
    if (!token) return
    const { response, data } = await fetchJsonSafe(`${apiBase}/api/patient/doctor-summaries`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load doctor summaries')
    setPatientDoctorSummaries(Array.isArray(data) ? data : [])
  }, [apiBase, authToken])

  const loadDoctorsForPatient = useCallback(async (tokenOverride) => {
    const token = tokenOverride || authToken
    if (!token) return
    const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctors`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load doctors')
    setPatientDoctors(Array.isArray(data) ? data : [])
  }, [apiBase, authToken])

  const loadPatientAppointments = useCallback(async (tokenOverride) => {
    const token = tokenOverride || authToken
    if (!token) return
    const { response, data } = await fetchJsonSafe(`${apiBase}/api/patient/appointments`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load appointments')
    setPatientAppointments(Array.isArray(data) ? data : [])
  }, [apiBase, authToken])

  const loadDoctorDashboard = useCallback(async (tokenOverride) => {
    const token = tokenOverride || authToken
    if (!token) return
    const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/dashboard`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load doctor dashboard')
    setDoctorDashboard(data || {})
  }, [apiBase, authToken])

  const loadDoctorAppointments = useCallback(async (tokenOverride) => {
    const token = tokenOverride || authToken
    if (!token) return
    const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/appointments`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load appointments')
    setDoctorAppointments(Array.isArray(data) ? data : [])
  }, [apiBase, authToken])

  const loadDoctorAlerts = useCallback(async (tokenOverride) => {
    const token = tokenOverride || authToken
    if (!token) return
    const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/alerts`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load alerts')
    setDoctorAlerts(Array.isArray(data) ? data : [])
  }, [apiBase, authToken])

  const loadDoctorMessages = useCallback(async (patientUserId, tokenOverride) => {
    const token = tokenOverride || authToken
    if (!token || !patientUserId) return
    const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/messages/${encodeURIComponent(patientUserId)}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error(data?.error || 'Failed to load messages')
    setDoctorMessages(Array.isArray(data) ? data : [])
  }, [apiBase, authToken])

  useEffect(() => {
    if (authUser?.role === 'doctor' && authToken) {
      loadDoctorDashboard().catch(() => {})
      loadDoctorAppointments().catch(() => {})
      loadDoctorAlerts().catch(() => {})
    }
    if (authUser?.role === 'patient' && authToken) {
      loadPatientUploads().catch(() => {})
      loadPatientDoctorSummaries().catch(() => {})
      loadDoctorsForPatient().catch(() => {})
      loadPatientAppointments().catch(() => {})
    }
  }, [authUser, authToken, loadDoctorAlerts, loadDoctorAppointments, loadDoctorDashboard, loadDoctorsForPatient, loadPatientAppointments, loadPatientDoctorSummaries, loadPatientUploads])

  useEffect(() => {
    if (selectedDoctorSummaryId && !selectedDoctorSummary) {
      setSelectedDoctorSummaryId('')
    }
  }, [selectedDoctorSummary, selectedDoctorSummaryId])

  useEffect(() => {
    if (!patientSelectedDoctorId && patientDoctors.length > 0) {
      setPatientSelectedDoctorId(patientDoctors[0].user_id)
      return
    }
    if (patientSelectedDoctorId && !patientDoctors.find((d) => d.user_id === patientSelectedDoctorId)) {
      setPatientSelectedDoctorId(patientDoctors[0]?.user_id || '')
    }
  }, [patientDoctors, patientSelectedDoctorId])

  useEffect(() => {
    setPortalPage('workspace')
    setDiagnosisStage('inputs')
    setAssistantEcgSignal([])
    setAssistantEcgMeta({ hr: null, sampleRate: null, durationSec: null })
    setAssistantEcgBootstrapped(false)
    setAssistantEcgLive(false)
    setAssistantEcgPrompt(DEFAULT_ECG_PROMPT)
  }, [viewerRole, authUser?.user_id])

  useEffect(() => {
    if (!successMessage) return undefined
    const timer = setTimeout(() => setSuccessMessage(''), 2600)
    return () => clearTimeout(timer)
  }, [successMessage])

  useEffect(() => {
    if (!assistantEcgExpanded) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setAssistantEcgExpanded(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [assistantEcgExpanded])

  useEffect(() => {
    if (portalPage !== 'assistant') return
    if (assistantEcgBootstrapped) return
    if (assistantVisibleEcg.length > 1) return
    generateAssistantEcgSignal('auto')
  }, [assistantEcgBootstrapped, assistantVisibleEcg.length, portalPage])

  useEffect(() => {
    if (portalPage === 'assistant') return
    if (assistantEcgLive) setAssistantEcgLive(false)
  }, [assistantEcgLive, portalPage])

  useEffect(() => {
    if (!assistantEcgLive) return undefined
    if (portalPage !== 'assistant') return undefined
    const timer = setInterval(() => {
      generateAssistantEcgSignal('live')
    }, LIVE_ECG_REFRESH_MS)
    return () => clearInterval(timer)
  }, [assistantEcgLive, portalPage, form, result?.master_probability, apiBase, assistantEcgPrompt])

  useEffect(() => {
    if (!assistantEcgLive) {
      setAssistantEcgScroll(0)
      return undefined
    }
    if (portalPage !== 'assistant') return undefined
    if (assistantEcgSignal.length < 2) return undefined
    const timer = setInterval(() => {
      const sampleRate = Number(assistantEcgMeta.sampleRate || assistantEcgPrompt.samplingRate || 300)
      const step = Math.max(1, Math.round(Math.max(120, sampleRate) * 0.01))
      setAssistantEcgScroll((prev) => {
        const next = prev - step
        return next < 0 ? (assistantEcgSignal.length + next) : next
      })
    }, 120)
    return () => clearInterval(timer)
  }, [assistantEcgLive, portalPage, assistantEcgSignal.length, assistantEcgMeta.sampleRate, assistantEcgPrompt.samplingRate])

  function authHeaders(extra = {}) {
    const headers = { ...extra }
    if (authToken) headers.Authorization = `Bearer ${authToken}`
    return headers
  }

  function showSuccess(message) {
    setSuccessMessage(String(message || '').trim())
  }

  function switchAuthMode(mode) {
    setAuthMode(mode)
    setAuthStage('credentials')
    setOtpCode('')
    setOtpSession(null)
    setAuthForm((prev) => ({ ...prev, password: '' }))
    setError('')
  }

  async function signUp() {
    setAuthLoading(true)
    setError('')
    try {
      const email = authForm.email.trim()
      const mobile = authForm.mobile.trim()
      if (!email && !mobile) {
        throw new Error('Enter email or mobile to sign up.')
      }
      const payload = {
        name: authForm.name.trim(),
        email,
        mobile,
        password: authForm.password,
        role: authForm.role,
      }
      const { response, data } = await authJsonWith405Fallback(`${apiBase}/api/auth/signup/initiate`, payload)
      if (!response.ok) throw new Error(data?.error || 'Signup OTP initiation failed')
      const preview = data?.otp_preview ? ` OTP: ${data.otp_preview}` : ''
      const deliveryLabel = data?.delivery || 'channel'
      const statusText = data?.delivery_status === 'sent' ? 'OTP sent' : 'OTP not delivered'
      const note = data?.delivery_note ? ` ${data.delivery_note}` : ''
      const canProceedToVerify = data?.delivery_status === 'sent' || Boolean(data?.otp_preview)
      if (canProceedToVerify) {
        setOtpSession({
          purpose: 'signup',
          otp_id: data.otp_id,
          expires_at: data.expires_at,
        })
        setAuthForm((prev) => ({ ...prev, password: '' }))
        setAuthStage('otp')
        setError(`${statusText} via ${deliveryLabel}. Enter OTP to complete registration.${preview}${note}`)
      } else {
        setAuthStage('credentials')
        setError(`OTP not delivered via ${deliveryLabel}.${note} Configure provider settings and try again.`)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setAuthLoading(false)
    }
  }

  async function login() {
    setAuthLoading(true)
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login: authForm.login.trim(),
          password: authForm.password,
        }),
      })
      if (!response.ok) throw new Error(data?.error || 'Login failed')
      setAuthToken(data.token)
      setAuthUser(data.user)
      setViewerRole(data?.user?.role === 'patient' ? 'patient' : 'doctor')
      setPortalPage('workspace')
      setAuthStage('credentials')
      setOtpSession(null)
      setOtpCode('')
      if (data?.user?.role === 'doctor') {
        setActiveProfileId('')
        setHistory([])
        await loadDoctorDashboard(data.token)
        await loadDoctorAppointments(data.token)
        await loadDoctorAlerts(data.token)
      }
      await loadProfiles(apiBase, data.token)
      if (data?.user?.role === 'patient') {
        await loadPatientUploads(data.token)
        await loadPatientDoctorSummaries(data.token)
        await loadDoctorsForPatient(data.token)
        await loadPatientAppointments(data.token)
      }
    } catch (e) {
      setError(e.message)
      setAuthToken('')
      setAuthUser(null)
    } finally {
      setAuthLoading(false)
    }
  }

  async function verifyOtp() {
    if (!otpSession?.otp_id) {
      setError('OTP session missing. Start login/signup again.')
      return
    }
    if (otpSession.purpose !== 'signup') {
      setError('OTP verification is only required for signup.')
      return
    }
    if (!otpCode.trim()) {
      setError('Enter OTP code.')
      return
    }
    setAuthLoading(true)
    setError('')
    try {
      const route = '/api/auth/signup/verify'
      const { response, data } = await authJsonWith405Fallback(`${apiBase}${route}`, {
        otp_id: otpSession.otp_id,
        otp_code: otpCode.trim(),
      })
      if (!response.ok) throw new Error(data?.error || 'OTP verification failed')

      const loginHint = data?.user?.email || data?.user?.mobile || ''
      setAuthStage('credentials')
      setAuthMode('login')
      setOtpCode('')
      setOtpSession(null)
      setAuthForm((prev) => ({ ...prev, login: loginHint, password: '' }))
      setError(`Signup complete. User ID: ${data?.user?.user_id}. Please login with password.`)
    } catch (e) {
      setError(e.message)
    } finally {
      setAuthLoading(false)
    }
  }

  async function resendOtp() {
    if (authMode === 'signup' || otpSession?.purpose === 'signup') {
      await signUp()
    }
  }

  function logoutAuth() {
    setAuthToken('')
    setAuthUser(null)
    setAuthStage('credentials')
    setOtpCode('')
    setOtpSession(null)
    setDoctorPatientData(null)
    setDoctorAppointments([])
    setDoctorAlerts([])
    setDoctorMessages([])
    setDoctorAcceptedPatientUploads([])
    setPatientUploads([])
    setPatientDoctorSummaries([])
    setPatientDoctors([])
    setPatientAppointments([])
    setPatientSelectedDoctorId('')
    setPatientAppointmentDate('')
    setPatientAppointmentNotes('')
    setSelectedDoctorSummaryId('')
    setDoctorPatientId('')
    setPatientUploadResult(null)
    setPortalPage('workspace')
    setError('')
  }

  async function searchPatientById() {
    if (!doctorPatientId.trim()) {
      setError('Enter Patient ID like PAT-10458')
      return
    }
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/patient/${encodeURIComponent(doctorPatientId.trim())}`, {
        headers: authHeaders(),
      })
      if (!response.ok) throw new Error(data?.error || 'Patient search failed')
      setDoctorPatientData(data)
      setDoctorSearchResults(data?.patient ? [data.patient] : [])
      setDoctorImagePrimary('')
      setDoctorImageCompare('')
      await loadDoctorMessages(data?.patient?.user_id || '')
    } catch (e) {
      setError(e.message)
      setDoctorPatientData(null)
      setDoctorMessages([])
      setDoctorSearchResults([])
    }
  }

  async function searchPatients() {
    const q = doctorPatientId.trim()
    if (!q) {
      setError('Enter Patient ID / name / phone')
      return
    }
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/patients?q=${encodeURIComponent(q)}`, {
        headers: authHeaders(),
      })
      if (!response.ok) throw new Error(data?.error || 'Patient search failed')
      const rows = Array.isArray(data) ? data : []
      setDoctorSearchResults(rows)
      if (rows.length === 1) {
        await openDoctorPatient(rows[0].user_id)
      }
    } catch (e) {
      setError(e.message)
      setDoctorSearchResults([])
    }
  }

  async function addDoctorNote() {
    if (!doctorPatientData?.patient?.user_id) {
      setError('Search and open a patient first.')
      return
    }
    setDoctorNoteSaving(true)
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/notes`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          patient_user_id: doctorPatientData.patient.user_id,
          prescription: doctorNotePrescription.trim(),
          remarks: [doctorDiseaseType.trim(), doctorSeverityLevel.trim(), doctorNoteRemarks.trim()]
            .filter(Boolean)
            .join(' | '),
          ecg_signal: normalizeEcgSignal(result?.ecg_signal).slice(0, 1200),
        }),
      })
      if (!response.ok) throw new Error(data?.error || 'Failed to save doctor note')
      setDoctorNotePrescription('')
      setDoctorNoteRemarks('')
      setDoctorDiseaseType('')
      setDoctorSeverityLevel('')

      // Close the active appointment queue item for this patient after summary submission.
      const queueItemForPatient = (doctorAppointments || []).find(
        (a) =>
          String(a?.patient_user_id || '') === String(doctorPatientData.patient.user_id) &&
          String(a?.status || '').toLowerCase() === 'accepted',
      ) || (doctorAppointments || []).find(
        (a) =>
          String(a?.patient_user_id || '') === String(doctorPatientData.patient.user_id) &&
          String(a?.status || '').toLowerCase() === 'pending',
      )
      if (queueItemForPatient?.id) {
        await fetchJsonSafe(`${apiBase}/api/doctor/appointments/${queueItemForPatient.id}`, {
          method: 'PUT',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ status: 'completed' }),
        })
      }

      await loadDoctorDashboard()
      await loadDoctorAppointments()
      setForm(EMPTY_FORM)
      setDefaultsAppliedFields([])
      setResult(null)
      setDoctorPatientData(null)
      setDoctorPatientId('')
    } catch (e) {
      setError(e.message)
    } finally {
      setDoctorNoteSaving(false)
    }
  }

  async function openDoctorPatient(patientUserId) {
    const pid = String(patientUserId || '').trim()
    if (!pid) return
    setDoctorPatientId(pid)
    setDoctorPatientData((prev) => ({
      ...(prev || {}),
      patient: {
        ...(prev?.patient || {}),
        user_id: pid,
        name: prev?.patient?.name || 'Loading...',
      },
    }))
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/patient/${encodeURIComponent(pid)}`, {
        headers: authHeaders(),
      })
      if (!response.ok) throw new Error(data?.error || 'Patient open failed')
      setDoctorPatientData(data)
      setDoctorImagePrimary('')
      setDoctorImageCompare('')
      loadDoctorMessages(pid).catch(() => {})
      return data
    } catch (e) {
      setError(e.message)
      setDoctorPatientData(null)
      return null
    }
  }

  function prefillDoctorSummaryFromPatient(patientData) {
    const latestDiag = (patientData?.diagnoses || [])[0]
    if (latestDiag?.diagnosis_summary) setDoctorDiseaseType(latestDiag.diagnosis_summary)
    if (latestDiag?.risk_level) setDoctorSeverityLevel(latestDiag.risk_level)

    const latestNote = (patientData?.notes || [])[0]
    if (latestNote?.prescription) setDoctorNotePrescription(latestNote.prescription)
    if (latestNote?.remarks) setDoctorNoteRemarks(latestNote.remarks)
  }

  async function createFollowUpAppointment() {
    if (!doctorPatientData?.patient?.user_id) {
      setError('Open a patient first.')
      return
    }
    if (!doctorFollowUpDate) {
      setError('Set follow-up date and time.')
      return
    }
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/appointments`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          patient_user_id: doctorPatientData.patient.user_id,
          scheduled_at: new Date(doctorFollowUpDate).toISOString(),
          status: 'pending',
          consult_link: doctorConsultLink.trim(),
          notes: 'Follow-up from diagnosis module',
        }),
      })
      if (!response.ok) throw new Error(data?.error || 'Appointment create failed')
      await loadDoctorAppointments()
      setDoctorFollowUpDate('')
      setDoctorConsultLink('')
    } catch (e) {
      setError(e.message)
    }
  }

  async function updateAppointment(appointmentId, status) {
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/appointments/${appointmentId}`, {
        method: 'PUT',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ status }),
      })
      if (!response.ok) throw new Error(data?.error || 'Appointment update failed')
      await loadDoctorAppointments()
    } catch (e) {
      setError(e.message)
    }
  }

  async function acceptAppointmentAndOpenPatient(appointment) {
    if (!appointment?.id) return
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/appointments/${appointment.id}`, {
        method: 'PUT',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ status: 'accepted' }),
      })
      if (!response.ok) throw new Error(data?.error || 'Appointment accept failed')
      await loadDoctorAppointments()
      const patientData = await openDoctorPatient(appointment.patient_user_id)
      if (patientData) {
        prefillDoctorSummaryFromPatient(patientData)
        const uploads = Array.isArray(patientData.records) ? patientData.records : []
        setDoctorAcceptedPatientUploads(uploads)
      } else {
        setDoctorAcceptedPatientUploads([])
      }
    } catch (e) {
      setError(e.message)
    }
  }

  async function _sendDoctorMessage() {
    if (!doctorPatientData?.patient?.user_id) {
      setError('Open a patient first.')
      return
    }
    if (!doctorMessageText.trim()) return
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/messages/${encodeURIComponent(doctorPatientData.patient.user_id)}`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ message_text: doctorMessageText.trim() }),
      })
      if (!response.ok) throw new Error(data?.error || 'Message send failed')
      setDoctorMessageText('')
      await loadDoctorMessages(doctorPatientData.patient.user_id)
    } catch (e) {
      setError(e.message)
    }
  }

  async function deleteDoctorNote(noteId) {
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/doctor/notes/${noteId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      if (!response.ok) throw new Error(data?.error || 'Delete note failed')
      await searchPatientById()
    } catch (e) {
      setError(e.message)
    }
  }

  async function uploadDoctorRecordForPatient() {
    if (!doctorPatientData?.patient?.user_id) {
      setError('Select a patient first.')
      return
    }
    if (!doctorUploadFile) {
      setError('Choose a file to upload for patient.')
      return
    }
    setDoctorUploadLoading(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('file', doctorUploadFile)
      fd.append('record_type', doctorUploadType)
      fd.append('diagnosis_summary', doctorUploadSummary.trim())
      const response = await fetch(`${apiBase}/api/doctor/patient/${encodeURIComponent(doctorPatientData.patient.user_id)}/records/upload`, {
        method: 'POST',
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
        body: fd,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data?.error || 'Doctor upload failed')
      setDoctorUploadFile(null)
      setDoctorUploadSummary('')
      await openDoctorPatient(doctorPatientData.patient.user_id)
      await loadDoctorDashboard()
    } catch (e) {
      setError(e.message)
    } finally {
      setDoctorUploadLoading(false)
    }
  }

  async function uploadPatientRecord() {
    if (!patientUploadFile) {
      setError('Choose a file to upload.')
      return
    }
    setPatientUploadLoading(true)
    setError('')
    setPatientUploadResult(null)
    try {
      const fd = new FormData()
      fd.append('file', patientUploadFile)
      fd.append('diagnosis_summary', patientUploadSummary.trim())
      fd.append('record_type', patientUploadType)
      if (patientSelectedDoctorId) fd.append('doctor_user_id', patientSelectedDoctorId)
      const response = await fetch(`${apiBase}/api/patient-records/upload`, {
        method: 'POST',
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
        body: fd,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data?.error || 'Upload failed')
      setPatientUploadResult(data)
      setPatientUploadSummary('')
      setPatientUploadFile(null)
      await loadPatientUploads()
      await loadPatientAppointments()
    } catch (e) {
      setError(e.message)
    } finally {
      setPatientUploadLoading(false)
    }
  }

  async function bookPatientAppointment() {
    if (!patientSelectedDoctorId) {
      setError('Select doctor to book appointment.')
      return
    }
    setPatientBookingLoading(true)
    setError('')
    try {
      const scheduledAt = patientAppointmentDate
        ? new Date(patientAppointmentDate).toISOString()
        : new Date().toISOString()
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/patient/appointments`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          doctor_user_id: patientSelectedDoctorId,
          scheduled_at: scheduledAt,
          notes: patientAppointmentNotes.trim() || 'Patient requested appointment',
        }),
      })
      if (!response.ok) throw new Error(data?.error || 'Appointment booking failed')
      setPatientAppointmentDate('')
      setPatientAppointmentNotes('')
      await loadPatientAppointments()
    } catch (e) {
      setError(e.message)
    } finally {
      setPatientBookingLoading(false)
    }
  }

  async function createCompleteProfile() {
    setCreatingProfile(true)
    setError('')
    try {
      if (!profileForm.full_name.trim()) {
        throw new Error('Full name is required')
      }
      const details = {
        dob: profileForm.dob,
        phone: profileForm.phone,
        email: profileForm.email,
        address: profileForm.address,
        blood_group: profileForm.blood_group,
        emergency_contact: profileForm.emergency_contact,
        allergies: profileForm.allergies,
        existing_conditions: profileForm.existing_conditions,
      }
      const payload = {
        full_name: profileForm.full_name.trim(),
        age: profileForm.age === '' ? null : Number(profileForm.age),
        sex: profileForm.sex === '' ? null : Number(profileForm.sex),
        notes: profileForm.notes.trim(),
        details,
      }
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/profiles`, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
      })
      if (!response.ok) throw new Error(data?.error || 'Profile creation failed')
      setProfiles((prev) => {
        if (prev.some((p) => String(p.id) === String(data.id))) return prev
        return [{
          id: data.id,
          full_name: payload.full_name,
          age: payload.age,
          sex: payload.sex,
          notes: payload.notes,
        }, ...prev]
      })
      await loadProfiles(apiBase)
      setActiveProfileId(String(data.id))
      setPatientView('workspace')
      setProfileForm(DEFAULT_PROFILE_FORM)
      setForm(EMPTY_FORM)
      setResult(null)
      await loadHistory(apiBase, data.id)
    } catch (e) {
      setError(e.message)
    } finally {
      setCreatingProfile(false)
    }
  }

  function handleAnalyzerDragOver(e, target) {
    e.preventDefault()
    e.stopPropagation()
    if (analyzerDragTarget !== target) setAnalyzerDragTarget(target)
  }

  function handleAnalyzerDragLeave(e, target) {
    e.preventDefault()
    e.stopPropagation()
    const related = e.relatedTarget
    if (!related || !e.currentTarget.contains(related)) {
      if (analyzerDragTarget === target) setAnalyzerDragTarget('')
    }
  }

  async function handleAnalyzerDrop(e, target, setter, label, analyzeFn) {
    e.preventDefault()
    e.stopPropagation()
    setAnalyzerDragTarget('')
    const file = e.dataTransfer?.files?.[0] || null
    if (!file) return
    if (!isSupportedDiagnosticImage(file)) {
      setError(`Use PNG/JPG/JPEG image for ${label}.`)
      return
    }
    setter(file)
    setError('')
    if (typeof analyzeFn === 'function') {
      await analyzeFn(file)
    }
  }

  async function switchProfile(profileId) {
    setActiveProfileId(profileId)
    setResult(null)
    setError('')
    await loadHistory(apiBase, profileId)
  }

  function logoutProfile() {
    setActiveProfileId('')
    setHistory([])
    setResult(null)
    setError('')
  }

  function openCreateProfile() {
    setError('')
    setPatientView('create-profile')
  }

  function applyEcgPreset(presetId) {
    const preset = ECG_PRESETS[presetId]
    if (!preset) return
    setForm((prev) => ({ ...prev, ...preset.form }))
    setAssistantEcgPrompt((prev) => ({ ...prev, ...preset.prompt }))
    setError('')
  }

  function exportAssistantEcgCsv() {
    const signal = normalizeEcgSignal(assistantVisibleEcg)
    if (signal.length < 2) {
      setError('Generate ECG signal first, then export CSV.')
      return
    }
    const duration = Number(assistantEcgMeta.durationSec || assistantEcgPrompt.durationSec || 10)
    const sampleRate = Number(assistantEcgMeta.sampleRate || assistantEcgPrompt.samplingRate || 500)
    const lines = ['index,time_sec,value_mv']
    for (let i = 0; i < signal.length; i += 1) {
      const t = (duration > 0 && signal.length > 1) ? (i * duration / (signal.length - 1)) : (i / Math.max(sampleRate, 1))
      lines.push(`${i},${t.toFixed(6)},${Number(signal[i]).toFixed(6)}`)
    }
    const blob = new Blob([`${lines.join('\n')}\n`], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ecg_signal_${Date.now()}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  async function generateAssistantEcgSignal(reason = 'manual') {
    if (assistantEcgLoading) return
    setAssistantEcgLoading(true)
    if (reason === 'manual' || reason === 'image-analysis') setError('')
    try {
      const payload = toPayloadWithDefaults(form)
      const riskSource = Number(result?.master_probability)
      const normalizedRisk = Number.isFinite(riskSource) ? riskSource : 42
      const durationSec = Math.max(3, Math.min(30, Number(assistantEcgPrompt.durationSec || 10)))
      const samplingRate = Math.max(120, Math.min(1000, Number(assistantEcgPrompt.samplingRate || 500)))
      const lead = String(assistantEcgPrompt.lead || 'II').trim().toUpperCase()
      const noiseLevel = Math.max(0, Math.min(0.2, Number(assistantEcgPrompt.noiseLevel || 0)))
      const arrhythmiaMode = String(assistantEcgPrompt.arrhythmiaMode || 'auto')
      const qs = new URLSearchParams({
        age: String(Number(payload?.age ?? DEFAULT_FORM.age)),
        hr: String(Number(payload?.thalach ?? DEFAULT_FORM.thalach)),
        restecg: String(Number(payload?.restecg ?? DEFAULT_FORM.restecg)),
        oldpeak: String(Number(payload?.oldpeak ?? DEFAULT_FORM.oldpeak)),
        exang: String(Number(payload?.exang ?? DEFAULT_FORM.exang)),
        risk: String(Math.max(5, Math.min(95, normalizedRisk))),
        seconds: String(durationSec),
        sample_rate: String(samplingRate),
        lead,
        noise_level: String(noiseLevel),
        arrhythmia: arrhythmiaMode,
        points: '920',
      })
      if (reason === 'live') qs.set('tick', String(Date.now()))
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/ecg-realtime?${qs.toString()}`)
      if (!response.ok) throw new Error(data?.error || `ECG generation failed (${response.status})`)
      const signal = normalizeEcgSignal(data?.signal)
      if (signal.length > 0) {
        setAssistantEcgSignal(signal)
        setAssistantEcgMeta({
          hr: Number.isFinite(Number(data?.hr)) ? Number(data.hr) : null,
          sampleRate: Number.isFinite(Number(data?.sample_rate)) ? Number(data.sample_rate) : null,
          durationSec: Number.isFinite(Number(data?.duration_sec)) ? Number(data.duration_sec) : null,
        })
      }
      else throw new Error('ECG generation returned empty signal.')
    } catch (e) {
      if (reason === 'manual' || reason === 'image-analysis') setError(e.message)
    } finally {
      setAssistantEcgLoading(false)
      if (reason === 'auto') setAssistantEcgBootstrapped(true)
    }
  }

  async function runPrediction() {
    if (viewerRole === 'doctor' && !doctorPatientData?.patient?.user_id) {
      setError('Search and open patient ID first, then run diagnosis.')
      return
    }
    if (viewerRole === 'patient' && !activeProfileId) {
      setError('Create/select a user profile before running diagnosis.')
      return
    }
    if (ecgImageFile && !isSupportedDiagnosticImage(ecgImageFile)) {
      setError('ECG analyzer supports only PNG/JPG/JPEG files.')
      return
    }
    setLoadingPredict(true)
    setError('')
    const blankFields = Object.keys(DEFAULT_FORM).filter((k) => form[k] === '' || form[k] === null || form[k] === undefined)
    setDefaultsAppliedFields(blankFields)
    try {
      const endpoint = viewerRole === 'doctor'
        ? `${apiBase}/api/doctor/patient/${encodeURIComponent(doctorPatientData.patient.user_id)}/diagnose`
        : `${apiBase}/api/profiles/${activeProfileId}/diagnose`
      const { response, data } = await fetchJsonSafe(endpoint, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(toPayloadWithDefaults(form)),
      })
      if (viewerRole === 'doctor' && response.status === 405) {
        throw new Error('Doctor diagnose endpoint is not active on current backend. Restart backend and try again.')
      }
      if (!response.ok) {
        setError(data?.error || `Diagnosis failed (${response.status})`)
        setResult(null)
      } else {
        setResult(data)
        const safetyStatus = String(data?.safety_assessment?.status || 'ok').toLowerCase()
        if (safetyStatus === 'blocked') {
          setSuccessMessage('AI safety gate blocked autonomous interpretation. Clinician confirmation is required.')
        } else if (safetyStatus === 'caution') {
          setSuccessMessage('Diagnosis marked provisional by AI safety gate. Please confirm clinically.')
        } else {
          setSuccessMessage('')
        }
        setDiagnosisStage('diagnosis')
        setAssistantEcgSignal([])
        setAssistantEcgMeta({ hr: null, sampleRate: null, durationSec: null })
        setAssistantEcgBootstrapped(false)
        if (ecgImageFile) {
          setEcgImageAnalyzing(true)
          try {
            const { response: responseEcg, data: dataEcg } = await postImageSummaryWithFieldFallback(
              `${apiBase}/api/ecg-image-summary`,
              ecgImageFile,
              ['ecg_image', 'file'],
              setApiBase,
            )
            if (responseEcg.ok) setEcgImageSummary(dataEcg)
          } catch {
            // Ignore ECG interpretation failure; diagnosis result is still valid.
          } finally {
            setEcgImageAnalyzing(false)
          }
        }
        if (viewerRole === 'patient') {
          await loadHistory(apiBase, activeProfileId)
        } else {
          await searchPatientById()
          await loadDoctorDashboard()
          await loadDoctorAlerts()
        }
      }
    } catch (e) {
      setError(`Diagnosis request failed. ${e.message}`)
    } finally {
      setLoadingPredict(false)
    }
  }

  async function sendChat(e) {
    e.preventDefault()
    const message = chatText.trim()
    if (!message) return

    setChatLoading(true)
    setError('')
    setChatLog((prev) => [...prev, { role: 'user', text: message }])
    setChatText('')

    try {
      const currentSummary = result
        ? {
            report_id: result.report_id,
            master_probability: result.master_probability,
            risk_tier: result?.risk_tier?.level,
            top_diseases: (result?.diseases || []).slice(0, 3).map((d) => ({ name: d.name, probability: d.probability })),
            recommendations: (result?.recommendations || []).slice(0, 3),
          }
        : null
      const historySummary = (history || []).slice(0, 3).map((h) => ({
        report_id: h.report_id,
        risk_level: h.risk_level,
        master_probability: h.master_probability,
        created_at: h.created_at,
      }))
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          role: viewerRole,
          include_precautions: true,
          context: {
            active_profile_name: activeProfile?.full_name || null,
            current_summary: currentSummary,
            history_summary: historySummary,
          },
        }),
      })
      if (!response.ok) {
        setChatLog((prev) => [...prev, { role: 'assistant', text: data?.error || `Chat failed (${response.status})` }])
      } else {
        setChatLog((prev) => [...prev, { role: 'assistant', text: data.reply }])
      }
    } catch (e) {
      setChatLog((prev) => [...prev, { role: 'assistant', text: `Network error: ${e.message}` }])
    } finally {
      setChatLoading(false)
    }
  }

  async function analyzeEcgImage(fileOverride = null) {
    const selectedFile = resolveImageUploadFile(fileOverride, ecgImageFile)
    if (!selectedFile) {
      setError('Please choose an ECG image first.')
      return
    }
    setEcgImageAnalyzing(true)
    setError('')
    try {
      const { response, data } = await postImageSummaryWithFieldFallback(
        `${apiBase}/api/ecg-image-summary`,
        selectedFile,
        ['ecg_image', 'file'],
        setApiBase,
      )
      if (!response.ok) throw new Error(data?.error || `ECG image analysis failed (${response.status})`)
      setEcgImageSummary(data)
      setAssistantEcgBootstrapped(false)
      await generateAssistantEcgSignal('image-analysis')
    } catch (e) {
      setError(e.message)
      setEcgImageSummary(null)
    } finally {
      setEcgImageAnalyzing(false)
    }
  }

  async function analyzeMriImage(fileOverride = null) {
    const selectedFile = resolveImageUploadFile(fileOverride, mriImageFile)
    if (!selectedFile) {
      setError('Please choose an MRI image first.')
      return
    }
    setMriImageAnalyzing(true)
    setError('')
    try {
      const { response, data } = await postImageSummaryWithFieldFallback(
        `${apiBase}/api/mri-image-summary`,
        selectedFile,
        ['mri_image', 'file'],
        setApiBase,
      )
      if (!response.ok) throw new Error(data?.error || `MRI image analysis failed (${response.status})`)
      setMriImageSummary(data)
    } catch (e) {
      setError(e.message)
      setMriImageSummary(null)
    } finally {
      setMriImageAnalyzing(false)
    }
  }

  async function analyzeCathlabImage(fileOverride = null) {
    const selectedFile = resolveImageUploadFile(fileOverride, cathImageFile)
    if (!selectedFile) {
      setError('Please choose a Cath Lab image first.')
      return
    }
    setCathImageAnalyzing(true)
    setError('')
    try {
      const { response, data } = await postImageSummaryWithFieldFallback(
        `${apiBase}/api/cathlab-image-summary`,
        selectedFile,
        ['cathlab_image', 'file'],
        setApiBase,
      )
      if (!response.ok) throw new Error(data?.error || `Cath Lab image analysis failed (${response.status})`)
      setCathImageSummary(data)
    } catch (e) {
      setError(e.message)
      setCathImageSummary(null)
    } finally {
      setCathImageAnalyzing(false)
    }
  }

  async function _deleteDiagnosisHistoryItem(diagnosisId) {
    if (!activeProfileId) return
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/profiles/${activeProfileId}/diagnoses/${diagnosisId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      if (!response.ok) throw new Error(data?.error || `Delete failed (${response.status})`)
      await loadHistory(apiBase, activeProfileId)
      if (result?.report_id && history.find((h) => h.id === diagnosisId)?.report_id === result.report_id) {
        setResult(null)
      }
    } catch (e) {
      setError(e.message)
    }
  }

  async function _clearProfileHistory() {
    if (!activeProfileId) return
    setError('')
    try {
      const { response, data } = await fetchJsonSafe(`${apiBase}/api/profiles/${activeProfileId}/diagnoses`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      if (!response.ok) throw new Error(data?.error || `Clear history failed (${response.status})`)
      await loadHistory(apiBase, activeProfileId)
      setResult(null)
    } catch (e) {
      setError(e.message)
    }
  }

  function ecgPoints(values) {
    if (!values || values.length === 0) return ''
    const width = 920
    const height = 140
    const min = Math.min(...values)
    const max = Math.max(...values)
    const span = max - min || 1
    return values
      .map((v, i) => {
        const x = (i / (values.length - 1)) * width
        const y = height - ((v - min) / span) * height
        return `${x},${y}`
      })
      .join(' ')
  }

  function downloadCurrentReport() {
    const hasImageAnalysis = Boolean(ecgImageSummary || mriImageSummary || cathImageSummary)
    if (!result && !hasImageAnalysis) {
      setError('Run diagnosis or analyze at least one image, then download report.')
      return
    }
    const createdAt = new Date().toISOString()
    const profileName = activeProfile?.full_name || 'Unknown User'
    const reportId = result?.report_id || `IMG-${createdAt.replace(/[-:.TZ]/g, '').slice(0, 14)}`
    const diseaseRows = (result?.diseases || [])
      .map((d) => `<li><b>${escHtml(d.name)}</b> - ${Number(d.probability).toFixed(1)}% (ICD: ${escHtml(d.icd)})</li>`)
      .join('') || '<li>No high-probability disease cards.</li>'
    const recRows = (result?.recommendations || [])
      .map((r) => `<li>[${escHtml(r.priority)}] ${escHtml(r.text)}</li>`)
      .join('') || '<li>No recommendations returned.</li>'
    const reasoningRows = (result?.reasoning_chain || [])
      .map((s) => `<li><b>${escHtml(s.category)}:</b> ${escHtml(s.finding)} (${escHtml(s.weight)})</li>`)
      .join('') || '<li>No reasoning chain available.</li>'
    const imageSummaryRows = ecgImageSummary
      ? `
  <div class="card">
    <h2>ECG Image Summary</h2>
    <p>${escHtml(ecgImageSummary.summary || 'No ECG image summary.')}</p>
    <ul>${(ecgImageSummary.quality_flags || []).map((q) => `<li>${escHtml(q)}</li>`).join('') || '<li>No quality flags.</li>'}</ul>
  </div>`
      : ''
    const mriSummaryRows = mriImageSummary
      ? `
  <div class="card">
    <h2>MRI Image Summary</h2>
    <p>${escHtml(mriImageSummary.summary || 'No MRI image summary.')}</p>
    <ul>${(mriImageSummary.quality_flags || []).map((q) => `<li>${escHtml(q)}</li>`).join('') || '<li>No quality flags.</li>'}</ul>
  </div>`
      : ''
    const cathSummaryRows = cathImageSummary
      ? `
  <div class="card">
    <h2>Cath Lab Image Summary</h2>
    <p>${escHtml(cathImageSummary.summary || 'No Cath Lab image summary.')}</p>
    <ul>${(cathImageSummary.quality_flags || []).map((q) => `<li>${escHtml(q)}</li>`).join('') || '<li>No quality flags.</li>'}</ul>
  </div>`
      : ''
    const ecg = Array.isArray(result?.ecg_signal) ? result.ecg_signal : []
    let ecgPoints = ''
    if (ecg.length > 1) {
      const width = 860
      const height = 150
      const min = Math.min(...ecg)
      const max = Math.max(...ecg)
      const span = max - min || 1
      ecgPoints = ecg
        .map((v, i) => {
          const x = (i / (ecg.length - 1)) * width
          const y = height - ((v - min) / span) * height
          return `${x},${y}`
        })
        .join(' ')
    }

    const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>AGI CardioSense Report</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 900px; margin: 24px auto; color: #111827; line-height: 1.4; }
    .badge { display: inline-block; padding: 6px 10px; border-radius: 999px; background: #e6f7f3; color: #0f766e; font-weight: 700; font-size: 12px; }
    .card { border: 1px solid #dbe3ef; border-radius: 10px; padding: 12px; margin-top: 12px; }
    h1 { margin: 0 0 4px 0; }
    h2 { margin: 0 0 8px 0; font-size: 18px; }
    ul { margin: 0; padding-left: 18px; }
    .meta { color: #4b5563; font-size: 13px; margin-bottom: 8px; }
  </style>
</head>
<body>
  <span class="badge">Generated by AGI CardioSense AI</span>
  <h1>${result ? 'Cardiovascular Diagnosis Report' : 'Cardiac Image Analysis Report'}</h1>
  <p class="meta">User: <b>${escHtml(profileName)}</b> | Report ID: <b>${escHtml(reportId)}</b> | Created: ${escHtml(createdAt)}</p>
  ${
    result
      ? `
  <div class="card">
    <h2>Risk Summary</h2>
    <p><b>Overall Risk:</b> ${Number(result.master_probability || 0).toFixed(1)}%</p>
    <p><b>Risk Tier:</b> ${escHtml(result?.risk_tier?.level || 'UNKNOWN')}</p>
    <p><b>Recommended Action:</b> ${escHtml(result?.risk_tier?.action || 'N/A')}</p>
  </div>

  <div class="card">
    <h2>AI Safety Assessment</h2>
    <p><b>Status:</b> ${escHtml(getSafetyStatusTitle(result?.safety_assessment?.status || 'ok'))}</p>
    <p><b>Summary:</b> ${escHtml(result?.safety_assessment?.summary || 'Use as decision support, not as standalone diagnosis.')}</p>
    <p><b>Clinician Review Required:</b> ${result?.requires_clinician_review ? 'Yes' : 'No'}</p>
    ${
      Array.isArray(result?.safety_assessment?.reasons) && result.safety_assessment.reasons.length > 0
        ? `<ul>${result.safety_assessment.reasons.map((reason) => `<li>${escHtml(reason)}</li>`).join('')}</ul>`
        : '<p>No additional uncertainty reasons flagged.</p>'
    }
  </div>

  <div class="card">
    <h2>Disease Breakdown</h2>
    <ul>${diseaseRows}</ul>
  </div>

  <div class="card">
    <h2>Recommendations</h2>
    <ul>${recRows}</ul>
  </div>

  <div class="card">
    <h2>Reasoning Chain</h2>
    <ul>${reasoningRows}</ul>
  </div>

  <div class="card">
    <h2>ECG Signal</h2>
    ${ecgPoints ? `<svg viewBox="0 0 860 150" width="100%" height="170" style="border:1px solid #dbe3ef;border-radius:8px;background:#fcfdff;"><polyline points="${ecgPoints}" fill="none" stroke="#d3394a" stroke-width="2"/></svg>` : '<p>No ECG signal available.</p>'}
  </div>`
      : `
  <div class="card">
    <h2>Summary</h2>
    <p>This report was generated from uploaded image analysis only. Run full diagnosis to include risk score and disease probabilities.</p>
  </div>`
  }
  ${imageSummaryRows}
  ${mriSummaryRows}
  ${cathSummaryRows}
</body>
</html>`

    const blob = new Blob([html], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `AGI_CardioSense_Report_${(reportId || 'REPORT').replace(/[^a-zA-Z0-9_-]/g, '_')}.html`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    showSuccess('Report exported successfully.')
  }

  if (!authUser) {
    return (
      <AuthScreen
        health={health}
        error={error}
        authMode={authMode}
        authStage={authStage}
        authForm={authForm}
        setAuthForm={setAuthForm}
        authLoading={authLoading}
        otpCode={otpCode}
        setOtpCode={setOtpCode}
        switchAuthMode={switchAuthMode}
        signUp={signUp}
        login={login}
        verifyOtp={verifyOtp}
        resendOtp={resendOtp}
        setAuthStage={setAuthStage}
      />
    )
  }

  return (
    <main className="app-shell">
      <PortalHeader
        viewerRole={viewerRole}
        authUser={authUser}
        logoutAuth={logoutAuth}
        portalPage={portalPage}
        diagnosisStage={diagnosisStage}
        setPortalPage={navigateTopPage}
        health={health}
      />

      {error && <div className="alert">{error}</div>}
      {successMessage && <div className="alert success">{successMessage}</div>}
      <section className="workflow-stepper" aria-label="Clinical workflow">
        {stepItems.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`step-chip step-chip-button ${s.done ? 'done' : ''} ${s.active ? 'active' : ''}`}
            onClick={() => navigateWorkflowStep(s)}
          >
            <span>{s.id}</span>
            <strong>{s.label}</strong>
          </button>
        ))}
      </section>

      {viewerRole === 'patient' && patientView === 'create-profile' ? (
        <CreateProfilePage
          profileForm={profileForm}
          setProfileForm={setProfileForm}
          creatingProfile={creatingProfile}
          createCompleteProfile={createCompleteProfile}
          setPatientView={setPatientView}
        />
      ) : (
      <>
      {portalPage === 'workspace' && (
      <section className="layout single-column">
        <aside className="panel profile-panel">
          <h2>{viewerRole === 'doctor' ? 'Doctor Workspace' : 'Patient Workspace'}</h2>
          <p>
            {viewerRole === 'doctor'
              ? 'Manage profiles, run diagnosis, review and maintain longitudinal records.'
              : 'Create/select your profile and manage appointments and records.'}
          </p>

          {viewerRole === 'patient' && (
            <>
              <section className="workspace-block">
                <h3>Patient Workspace</h3>
                <p className="muted">Create/select your profile and manage appointments and records.</p>
                <label><span>Select Profile</span>
                  <select value={activeProfileId} onChange={(e) => switchProfile(e.target.value)}>
                    <option value="">No active profile</option>
                    {profiles.map((p) => (
                      <option key={p.id} value={p.id}>{p.full_name}</option>
                    ))}
                  </select>
                </label>
                <div className="actions">
                  <button className="btn" onClick={() => bootstrap(apiBase)}>Refresh Profiles</button>
                  <button className="btn primary" onClick={openCreateProfile}>Create New Profile</button>
                  <button className="btn" onClick={logoutProfile}>Logout Profile</button>
                </div>
              </section>

              <section className="workspace-block">
                <h3>Book Appointment For Doctor</h3>
                <div className="profile-create-grid">
                  <label><span>Doctor</span>
                    <select value={patientSelectedDoctorId} onChange={(e) => setPatientSelectedDoctorId(e.target.value)}>
                      <option value="">Select doctor</option>
                      {patientDoctors.map((d) => (
                        <option key={d.user_id} value={d.user_id}>{d.name} ({d.user_id})</option>
                      ))}
                    </select>
                  </label>
                  <label><span>Preferred Date/Time</span><input type="datetime-local" value={patientAppointmentDate} onChange={(e) => setPatientAppointmentDate(e.target.value)} /></label>
                  <label><span>Notes</span><input value={patientAppointmentNotes} onChange={(e) => setPatientAppointmentNotes(e.target.value)} placeholder="Reason for visit (optional)" /></label>
                </div>
                <div className="actions">
                  <button className="btn primary" onClick={bookPatientAppointment} disabled={patientBookingLoading}>
                    {patientBookingLoading ? 'Booking...' : 'Book Appointment'}
                  </button>
                </div>
                <div className="appointment-history-wrap">
                  <h4 className="appointment-top-heading">Previous Appointments</h4>
                  <div className="history-scroll appointment-history-scroll">
                    {patientAppointments.length === 0 && <p className="muted">No appointments booked yet.</p>}
                    {patientAppointments.slice(0, 20).map((a) => (
                      <div key={`pa-${a.id}`} className="history-item">
                        <button className="history-view-btn">
                          <strong>{a.doctor_name || a.doctor_user_id}</strong>
                          <small>{formatDateTime(a.scheduled_at)} · {a.status}</small>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              <section className="workspace-block">
                <h3>Upload Medical Record</h3>
                <div className="profile-create-grid">
                  <label><span>Record Type</span>
                    <select value={patientUploadType} onChange={(e) => setPatientUploadType(e.target.value)}>
                      <option value="ecg">ECG</option>
                      <option value="mri">MRI</option>
                      <option value="cathlab">Cath Lab</option>
                      <option value="report">Report</option>
                      <option value="lab">Lab</option>
                      <option value="imaging">Imaging</option>
                      <option value="other">Other</option>
                    </select>
                  </label>
                  <label><span>Queue Doctor (optional)</span>
                    <select value={patientSelectedDoctorId} onChange={(e) => setPatientSelectedDoctorId(e.target.value)}>
                      <option value="">No doctor selected</option>
                      {patientDoctors.map((d) => (
                        <option key={`up-${d.user_id}`} value={d.user_id}>{d.name} ({d.user_id})</option>
                      ))}
                    </select>
                  </label>
                  <label><span>Select File</span><input type="file" onChange={(e) => setPatientUploadFile(e.target.files?.[0] || null)} /></label>
                  <label><span>Short Summary</span><input value={patientUploadSummary} onChange={(e) => setPatientUploadSummary(e.target.value)} placeholder="Optional summary" /></label>
                </div>
                <div className="actions">
                  <button className="btn primary" onClick={uploadPatientRecord} disabled={patientUploadLoading}>
                    {patientUploadLoading ? 'Uploading...' : 'Upload to Doctor Dashboard'}
                  </button>
                </div>
                {patientUploadResult && (
                  <p className="active-user">
                    Uploaded: <b>{patientUploadResult.file_name}</b> [{patientUploadResult.record_type}] ({patientUploadResult.patient_user_id})
                  </p>
                )}
              </section>

              <section className="workspace-block">
                <h3>My Uploaded Records</h3>
                <div className="history-scroll">
                  {patientUploads.length === 0 && <p className="muted">No uploads yet.</p>}
                  {patientUploads.map((u) => (
                    <div key={`my-up-${u.id}`} className="history-item">
                      <button className="history-view-btn">
                        <strong>{u.file_name}</strong>
                        <small>{u.record_type} · {formatDateTime(u.upload_date)}</small>
                      </button>
                      <a className="btn" href={`${apiBase}${u.file_url}`} target="_blank" rel="noreferrer">Open</a>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}

          {viewerRole === 'doctor' && (
            <>
              <h3>Doctor Dashboard</h3>
              <div className="status-grid doctor-mini-grid">
                <div className="status-card"><span>Total Patients</span><strong>{doctorDashboard?.overview?.total_patients ?? 0}</strong></div>
                <div className="status-card"><span>Today Appointments</span><strong>{doctorDashboard?.overview?.today_appointments ?? 0}</strong></div>
                <div className="status-card"><span>Pending Reports</span><strong>{doctorDashboard?.overview?.pending_reports ?? 0}</strong></div>
                <div className="status-card"><span>Scans To Review</span><strong>{doctorDashboard?.overview?.uploaded_scans_to_review ?? 0}</strong></div>
                <div className="status-card"><span>AI Alerts</span><strong>{doctorDashboard?.overview?.ai_alerts ?? 0}</strong></div>
              </div>

              <h3>Doctor Search (Patient ID)</h3>
              <div className="actions">
                <input value={doctorPatientId} onChange={(e) => setDoctorPatientId(e.target.value)} placeholder="PAT-10458 / name / phone" />
                <button type="button" className="btn primary" onClick={searchPatients}>Search</button>
              </div>
              <div className="history-scroll">
                {doctorSearchResults.length === 0 && <p className="muted">Search to list patients and select one.</p>}
                {doctorSearchResults.map((p) => (
                  <div key={`s-${p.user_id}`} className="history-item">
                    <button type="button" className="history-view-btn" onClick={() => openDoctorPatient(p.user_id)}>
                      <strong>{p.name}</strong>
                      <small>{p.user_id} · {p.mobile || p.email || '-'}</small>
                    </button>
                    <button type="button" className="btn" onClick={() => openDoctorPatient(p.user_id)}>Select</button>
                  </div>
                ))}
              </div>
              {doctorPatientData?.patient && (
                <p className="active-user">
                  Selected Patient: <b>{doctorPatientData.patient.name}</b> ({doctorPatientData.patient.user_id})
                </p>
              )}

              <h3>Appointments To Accept</h3>
              <div className="history-scroll">
                {doctorPendingAppointments.length === 0 && <p className="muted">No pending appointments.</p>}
                {doctorPendingAppointments.slice(0, 20).map((a) => (
                  <div key={`ap-${a.id}`} className="history-item">
                    <button className="history-view-btn">
                      <strong>{a.patient_name || a.patient_user_id}</strong>
                      <small>{formatDateTime(a.scheduled_at)} · pending</small>
                    </button>
                    <div className="actions">
                      <button className="btn" onClick={() => acceptAppointmentAndOpenPatient(a)}>Accept</button>
                      <button className="btn" onClick={() => updateAppointment(a.id, 'rejected')}>Reject</button>
                    </div>
                  </div>
                ))}
              </div>

              <h3>New Patient Uploads</h3>
              <div className="history-scroll">
                {doctorAcceptedPatientUploads.length === 0 && <p className="muted">No uploads for accepted patient yet.</p>}
                {doctorAcceptedPatientUploads.slice(0, 20).map((u) => (
                  <div key={`au-${u.id}`} className="history-item">
                    <button className="history-view-btn">
                      <strong>{u.file_name}</strong>
                      <small>{u.record_type || 'file'} · {formatDateTime(u.upload_date)}</small>
                    </button>
                    <a className="btn" href={`${apiBase}${u.file_url}`} target="_blank" rel="noreferrer">Open</a>
                  </div>
                ))}
              </div>

              <h3>AI Alerts</h3>
              <div className="history-scroll alerts-scroll">
                {doctorAlerts.length === 0 && <p className="muted">No active alerts.</p>}
                {doctorAlerts.slice(0, 20).map((a, idx) => (
                  <div key={`al-${idx}`} className="history-item">
                    <button className="history-view-btn" onClick={() => openDoctorPatient(a.patient_user_id)}>
                      <strong>{a.patient_user_id}</strong>
                      <small>{a.risk_level} · {formatPct(a.master_probability)} · {formatDateTime(a.created_at)}</small>
                    </button>
                  </div>
                ))}
              </div>

              {doctorAcceptedPatientUploads.length > 0 && (
                <>
                  <p className="muted">Accepted patient uploads are now visible above and also in Patient Uploaded Records.</p>
                </>
              )}
            </>
          )}

        </aside>
      </section>
      )}

      {portalPage === 'diagnosis' && diagnosisStage === 'inputs' && (
      <section className="layout single-column">
        <section className="panel form-panel">
          <h2>{viewerRole === 'doctor' ? 'Clinical Input' : 'Patient Input'}</h2>
          {viewerRole === 'patient'
            ? (activeProfile
              ? <p className="active-user">Active Profile: <b>{activeProfile.full_name}</b></p>
              : <p className="active-user">No active profile. Create/select one first.</p>)
            : (
              doctorPatientData?.patient?.user_id
                ? <p className="active-user">Selected Patient: <b>{doctorPatientData.patient.name}</b> ({doctorPatientData.patient.user_id})</p>
                : <p className="active-user">No patient selected. Search and select patient first.</p>
            )}
          {defaultsAppliedFields.length > 0 && (
            <p className="active-user">
              Auto-default applied for: <b>{defaultsAppliedFields.join(', ')}</b>
            </p>
          )}
          {(viewerRole === 'doctor' ? FIELD_SECTIONS : PATIENT_FIELD_SECTIONS).map((section) => (
            <div className="field-section" key={section.title}>
              <h3>{section.title}</h3>
              <div className="form-grid">
                {section.fields.map((field) => {
                  const config = FIELD_CONFIG[field]
                  return (
                    <label key={field}>
                      <span>{config.label}</span>
                      {config.type === 'select' ? (
                        <select value={form[field]} onChange={(e) => setForm((prev) => ({ ...prev, [field]: e.target.value === '' ? '' : Number(e.target.value) }))}>
                          <option value=""></option>
                          {config.options.map((opt) => <option key={opt.v} value={opt.v}>{opt.t}</option>)}
                        </select>
                      ) : (
                        <input type="number" min={config.min} max={config.max} step={config.step} value={form[field]} onChange={(e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))} />
                      )}
                    </label>
                  )
                })}
              </div>
            </div>
          ))}

          {viewerRole === 'doctor' && (
            <div className="field-section">
              <h3>ECG Upload / Selection</h3>
              <div className="actions">
                <input
                  type="file"
                  accept=".png,.jpg,.jpeg,image/png,image/jpeg"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null
                    if (file && !isSupportedDiagnosticImage(file)) {
                      setError('ECG upload supports only PNG/JPG/JPEG.')
                      setEcgImageFile(null)
                      e.target.value = ''
                      return
                    }
                    setError('')
                    setEcgImageFile(file)
                    if (file) generateAssistantEcgSignal('manual')
                  }}
                />
                {ecgImageFile && <span className="active-user">Selected: <b>{ecgImageFile.name}</b></span>}
              </div>
            </div>
          )}

          <div className="actions">
            <button className="btn primary" onClick={runPrediction} disabled={loadingPredict || (viewerRole === 'patient' && !activeProfileId)}>
              {loadingPredict ? 'Running model...' : (viewerRole === 'doctor' ? 'Run AGI Diagnosis' : 'Run My Diagnosis')}
            </button>
            <button className="btn" onClick={() => { setForm({ ...DEFAULT_FORM, ...OPTIONAL_FORM }); setDefaultsAppliedFields([]) }}>
              Apply Defaults
            </button>
            <button className="btn" onClick={() => { setForm(EMPTY_FORM); setResult(null); setDiagnosisStage('inputs'); setError('') }}>Reset</button>
          </div>

          {viewerRole === 'patient' && (
            <div className="field-section">
              <h3>Doctor Saved Summaries</h3>
              <div className="history-scroll">
                {patientDoctorSummaries.length === 0 && <p className="muted">No doctor summaries yet.</p>}
                {patientDoctorSummaries.map((s) => (
                  <div key={`ds-${s.id}`} className="history-item">
                    <button className="history-view-btn">
                      <strong>{s.doctor_user_id}</strong>
                      <small>{s.prescription || 'No prescription'} · {s.remarks || 'No remarks'} · {normalizeEcgSignal(s.ecg_signal).length > 0 ? 'ECG saved' : 'No ECG'} · {formatDateTime(s.created_at)}</small>
                    </button>
                    <button className="btn" onClick={() => setSelectedDoctorSummaryId(String(s.id))}>View</button>
                  </div>
                ))}
              </div>
            </div>
          )}

        </section>
      </section>
      )}

      {((portalPage === 'diagnosis' && diagnosisStage === 'diagnosis') || portalPage === 'assistant') && (
      <section className={`layout ${(portalPage === 'diagnosis' || portalPage === 'assistant') ? 'single-column' : ''} results-zone`}>
        {portalPage === 'diagnosis' && (
        <section className="panel diagnosis-panel">
          <h2>Diagnosis Summary</h2>
          {viewerRole === 'patient' && (
            <>
              <h3>Profile Diagnosis History</h3>
              <div className="history-scroll diagnosis-history-scroll">
                {history.length === 0 && <p className="muted">No saved diagnoses for selected profile.</p>}
                {history.map((h) => (
                  <div key={h.id} className="history-item">
                    <button
                      className="history-view-btn"
                      onClick={() => {
                        setSelectedDoctorSummaryId('')
                        setResult(h.result_payload)
                      }}
                    >
                      <strong>{h.report_id}</strong>
                      <small>{h.risk_level} · {formatPct(h.master_probability)} · {formatDateTime(h.created_at)}</small>
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
          {viewerRole === 'patient' && selectedDoctorSummary && (
            <div className="doctor-summary-card">
              <h3>Selected Doctor Summary</h3>
              {(() => {
                const details = parseDoctorSummary(selectedDoctorSummary)
                return (
                  <>
                    <p><strong>Doctor:</strong> {selectedDoctorSummary.doctor_user_id}</p>
                    <p><strong>Date:</strong> {formatDateTime(selectedDoctorSummary.created_at)}</p>
                    <p><strong>Diagnosis Summary:</strong> {details.clinicalRemarks || selectedDoctorSummary.remarks || 'No diagnosis summary provided.'}</p>
                    <p><strong>Disease Type:</strong> {details.diseaseType || 'Not specified'}</p>
                    <p><strong>Severity:</strong> {details.severityLevel || 'Not specified'}</p>
                    <p><strong>Medications / Prescription:</strong> {selectedDoctorSummary.prescription || 'Not specified'}</p>
                    {selectedDoctorSummaryEcg.length > 0 && (
                      <>
                        <strong>ECG Signal</strong>
                        <div className="ecg-box">
                          <svg viewBox="0 0 920 140" preserveAspectRatio="none">
                            <polyline points={ecgPoints(selectedDoctorSummaryEcg)} />
                          </svg>
                        </div>
                      </>
                    )}
                    {details.diseaseTypes.length > 0 && (
                      <>
                        <strong>Disease Types</strong>
                        <ul className="list">{details.diseaseTypes.map((d, idx) => <li key={`dt-${idx}`}>{d}</li>)}</ul>
                      </>
                    )}
                    {details.medications.length > 0 && (
                      <>
                        <strong>Medication List</strong>
                        <ul className="list">{details.medications.map((m, idx) => <li key={`med-${idx}`}>{m}</li>)}</ul>
                      </>
                    )}
                  </>
                )
              })()}
            </div>
          )}
          {!result && !selectedDoctorSummary && (
            <>
              <p>No report yet. Complete the flow and run diagnosis.</p>
              <div className="actions">
                <button className="btn" onClick={() => setDiagnosisStage('inputs')}>Back To Inputs</button>
              </div>
            </>
          )}
          {result && (
            <>
              <div className={`risk-banner ${riskTone}`}>
                <div><span>Overall Risk</span><h3>{formatPct(result.master_probability)}</h3></div>
                <div><span>Tier</span><h3>{result.risk_tier.level}</h3></div>
                <div><span>Report ID</span><h3>{result.report_id}</h3></div>
              </div>
              {safetyAssessment && (
                <article className={`safety-banner ${safetyAssessment.tone}`}>
                  <header>
                    <strong>{safetyAssessment.title}</strong>
                    <span>{result?.requires_clinician_review ? 'Clinician review required' : 'Safety gate clear'}</span>
                  </header>
                  <p>{safetyAssessment.summary || 'Use this output only as decision support.'}</p>
                  {safetyAssessment.clinicalJustification && (
                    <p className="muted">Clinical justification: {safetyAssessment.clinicalJustification}</p>
                  )}
                  {safetyAssessment.reasons.length > 0 && (
                    <ul className="list">
                      {safetyAssessment.reasons.map((reason, idx) => <li key={`safety-reason-${idx}`}>{reason}</li>)}
                    </ul>
                  )}
                  <p className="muted">
                    Confidence score: {safetyAssessment.confidenceScore != null ? `${safetyAssessment.confidenceScore.toFixed(1)} / 100` : '--'}
                    {' | '}Boundary distance: {safetyAssessment.boundaryDistance != null ? `${safetyAssessment.boundaryDistance.toFixed(1)}%` : '--'}
                    {' | '}OOD features: {safetyAssessment.oodCount != null ? safetyAssessment.oodCount : '--'}
                  </p>
                </article>
              )}
              <div className="clinical-metrics">
                {metricCards.map((m) => (
                  <article key={m.label} className={`metric-card ${m.tone}`}>
                    <span>{m.label}</span>
                    <strong>{m.value}</strong>
                  </article>
                ))}
              </div>
              {(result.raw_model_probability != null || result.clinical_severity_score != null) && (
                <p className="muted">
                  Calibrated risk is shown above. Raw model disease probability: {formatPct(result.raw_model_probability)} | Clinical severity score: {formatPct(result.clinical_severity_score)}
                </p>
              )}
              {result.primary_condition && (
                <>
                  <h3>Most Likely Primary Condition</h3>
                  <article className="disease-card">
                    <header>
                      <strong>{result.primary_condition.name}</strong>
                      <span>{formatPct(result.primary_condition.probability)} - {result.primary_condition.confidence} Confidence</span>
                    </header>
                    {result.primary_condition.co_primary && result.primary_condition.secondary_condition && (
                      <p className="muted">
                        Co-primary condition: {result.primary_condition.secondary_condition.name} ({formatPct(result.primary_condition.secondary_condition.probability)}), difference {formatPct(result.primary_condition.secondary_condition.delta_from_primary)}.
                      </p>
                    )}
                    {result.primary_condition.acs_overlap && result.primary_condition.acs_overlap_note && (
                      <p className="muted">{result.primary_condition.acs_overlap_note}</p>
                    )}
                    <p>{result.primary_condition.summary}</p>
                    <small>ICD: {result.primary_condition.icd || 'N/A'}</small>
                    {(result.primary_condition.reasons || []).length > 0 && (
                      <>
                        <h4>Why this is primary</h4>
                        <ul className="list">
                          {(result.primary_condition.reasons || []).map((line, idx) => <li key={`pc-reason-${idx}`}>{line}</li>)}
                        </ul>
                      </>
                    )}
                    {(result.primary_condition.next_steps || []).length > 0 && (
                      <>
                        <h4>Recommended next steps</h4>
                        <ul className="list">
                          {(result.primary_condition.next_steps || []).map((line, idx) => <li key={`pc-next-${idx}`}>{line}</li>)}
                        </ul>
                      </>
                    )}
                  </article>
                </>
              )}
              {viewerRole === 'doctor' ? (
                <>
                  <h3>Disease Breakdown</h3>
                  <div className="disease-grid">
                    {(result.diseases || []).map((disease) => (
                      <article key={disease.id} className="disease-card">
                        <header><strong>{disease.name}</strong><span>{formatPct(disease.probability)}</span></header>
                        <p>{disease.description}</p>
                        <small>ICD: {disease.icd}</small>
                      </article>
                    ))}
                  </div>

                  <h3>Recommendations</h3>
                  <ul className="list">{(result.recommendations || []).map((rec, idx) => <li key={`${rec.priority}-${idx}`}>[{rec.priority}] {rec.text}</li>)}</ul>
                </>
              ) : (
                <div className="diag-sections">
                  <section className="diag-section">
                    <h3 className="diag-side-heading">Easy Summary</h3>
                    <div className="diag-side-content">
                      <p className="muted">{getPatientRiskCaption(result?.risk_tier?.level)}</p>
                    </div>
                  </section>

                  <section className="diag-section">
                    <h3 className="diag-side-heading">Main Concerns</h3>
                    <div className="diag-side-content">
                      <ul className="list">
                        {(result.diseases || []).slice(0, 3).map((d) => <li key={`patient-${d.id}`}>{d.name} ({formatPct(d.probability)})</li>)}
                        {(result.diseases || []).length === 0 && <li>No major disease signal detected by this model run.</li>}
                      </ul>
                    </div>
                  </section>

                  <section className="diag-section">
                    <h3 className="diag-side-heading">Lifestyle Plan</h3>
                    <div className="diag-side-content">
                      <ul className="list">{getLifestylePlan(result).map((line, idx) => <li key={`life-${idx}`}>{line}</li>)}</ul>
                    </div>
                  </section>

                  <section className="diag-section">
                    <h3 className="diag-side-heading">Next Best Tests</h3>
                    <div className="diag-side-content">
                      <ul className="list">{getNextBestTests(result).map((line, idx) => <li key={`test-${idx}`}>{line}</li>)}</ul>
                    </div>
                  </section>

                  <section className="diag-section">
                    <h3 className="diag-side-heading">Emergency Guidance</h3>
                    <div className="diag-side-content">
                      <ul className="list">{getEmergencyGuidance(result).map((line, idx) => <li key={`emer-${idx}`}>{line}</li>)}</ul>
                    </div>
                  </section>
                </div>
              )}

              {(result.input_requirements || []).length > 0 && (
                <>
                  <h3>Additional Inputs Recommended</h3>
                  <ul className="list">
                    {(result.input_requirements || []).map((req, idx) => {
                      const disease = req?.disease || 'Disease'
                      const fields = Array.isArray(req?.needed_inputs) ? req.needed_inputs.join(', ') : ''
                      const reason = req?.reason ? ` (${req.reason})` : ''
                      return <li key={`req-${idx}`}>{disease}: {fields || 'Provide more clinical details'}{reason}</li>
                    })}
                  </ul>
                </>
              )}

              <div className="actions">
                <button className="btn primary" onClick={downloadCurrentReport}>Export Report (PDF/HTML)</button>
              </div>

              {viewerRole === 'doctor' && doctorPatientData?.patient && (
                <>
                  <h3>Patient Profile</h3>
                  <div className="disease-grid">
                    <article className="disease-card">
                      <header><strong>Demographics</strong></header>
                      <p>Name: {doctorPatientData?.patient_profile?.demographics?.full_name || doctorPatientData.patient.name}</p>
                      <p>Age: {doctorPatientData?.patient_profile?.demographics?.age ?? '-'}</p>
                      <p>Sex: {doctorPatientData?.patient_profile?.demographics?.sex === 1 ? 'Male' : doctorPatientData?.patient_profile?.demographics?.sex === 0 ? 'Female' : '-'}</p>
                    </article>
                    <article className="disease-card">
                      <header><strong>Vitals / Conditions</strong></header>
                      <p>Past heart conditions: {doctorPatientData?.patient_profile?.past_heart_conditions || '-'}</p>
                      <p>Symptoms: {Array.isArray(doctorPatientData?.patient_profile?.symptoms) ? doctorPatientData.patient_profile.symptoms.join(', ') : '-'}</p>
                      <p>Medications: {Array.isArray(doctorPatientData?.patient_profile?.medications) ? doctorPatientData.patient_profile.medications.join(', ') : '-'}</p>
                    </article>
                  </div>

                  <h3>Doctor Notes & Prescription</h3>
                  <div className="profile-create-grid">
                    <label><span>Final Diagnosis</span><input value={doctorDiseaseType} onChange={(e) => setDoctorDiseaseType(e.target.value)} placeholder="Disease type / diagnosis" /></label>
                    <label><span>Severity Level</span><input value={doctorSeverityLevel} onChange={(e) => setDoctorSeverityLevel(e.target.value)} placeholder="Mild / Moderate / Severe" /></label>
                    <label><span>Prescription</span><input value={doctorNotePrescription} onChange={(e) => setDoctorNotePrescription(e.target.value)} placeholder="Medication / treatment plan" /></label>
                    <label><span>Clinical Remarks</span><textarea rows={3} value={doctorNoteRemarks} onChange={(e) => setDoctorNoteRemarks(e.target.value)} placeholder="Doctor notes / observations" /></label>
                    <label><span>Follow-up Date</span><input type="datetime-local" value={doctorFollowUpDate} onChange={(e) => setDoctorFollowUpDate(e.target.value)} /></label>
                    <label><span>Consult Link</span><input value={doctorConsultLink} onChange={(e) => setDoctorConsultLink(e.target.value)} placeholder="Video consult link (optional)" /></label>
                  </div>
                  <div className="actions">
                    <button className="btn primary" onClick={addDoctorNote} disabled={doctorNoteSaving}>
                      {doctorNoteSaving ? 'Submitting...' : 'Submit Diagnosis Summary'}
                    </button>
                    <button className="btn" onClick={createFollowUpAppointment}>Create Follow-up</button>
                  </div>
                  <div className="history-scroll">
                    {(doctorPatientData.notes || []).length === 0 && <p className="muted">No doctor notes yet.</p>}
                    {(doctorPatientData.notes || []).map((n) => (
                      <div className="history-item" key={`note-${n.id}`}>
                        <button className="history-view-btn">
                          <strong>{n.doctor_user_id}</strong>
                          <small>{n.prescription || 'No prescription'} · {n.remarks || 'No remarks'} · {normalizeEcgSignal(n.ecg_signal).length > 0 ? 'ECG saved' : 'No ECG'} · {formatDateTime(n.created_at)}</small>
                        </button>
                        <button className="btn" onClick={() => deleteDoctorNote(n.id)}>Delete</button>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </section>
        )}

        {portalPage === 'assistant' && (
        <section className="panel">
          <h2>{viewerRole === 'doctor' ? 'Monitoring & Medical Assistant' : 'My Monitoring & Care Assistant'}</h2>
          <h3>ECG Prompt Builder</h3>
          <div className="profile-create-grid">
            <label><span>Duration (sec)</span>
              <input
                type="number"
                min="3"
                max="30"
                step="1"
                value={assistantEcgPrompt.durationSec}
                onChange={(e) => setAssistantEcgPrompt((prev) => ({ ...prev, durationSec: e.target.value }))}
              />
            </label>
            <label><span>Sampling Rate (Hz)</span>
              <input
                type="number"
                min="120"
                max="1000"
                step="10"
                value={assistantEcgPrompt.samplingRate}
                onChange={(e) => setAssistantEcgPrompt((prev) => ({ ...prev, samplingRate: e.target.value }))}
              />
            </label>
            <label><span>Lead Type</span>
              <select value={assistantEcgPrompt.lead} onChange={(e) => setAssistantEcgPrompt((prev) => ({ ...prev, lead: e.target.value }))}>
                <option value="I">Lead I</option>
                <option value="II">Lead II</option>
                <option value="III">Lead III</option>
                <option value="V1">Lead V1</option>
                <option value="V2">Lead V2</option>
                <option value="V3">Lead V3</option>
                <option value="V4">Lead V4</option>
                <option value="V5">Lead V5</option>
                <option value="V6">Lead V6</option>
              </select>
            </label>
            <label><span>Noise Level (0-0.20)</span>
              <input
                type="number"
                min="0"
                max="0.2"
                step="0.005"
                value={assistantEcgPrompt.noiseLevel}
                onChange={(e) => setAssistantEcgPrompt((prev) => ({ ...prev, noiseLevel: e.target.value }))}
              />
            </label>
            <label><span>Arrhythmia</span>
              <select value={assistantEcgPrompt.arrhythmiaMode} onChange={(e) => setAssistantEcgPrompt((prev) => ({ ...prev, arrhythmiaMode: e.target.value }))}>
                <option value="auto">Auto</option>
                <option value="none">None</option>
                <option value="mild">Mild</option>
                <option value="high">High</option>
              </select>
            </label>
            <label><span>Output Format</span>
              <select value={assistantEcgPrompt.outputFormat} onChange={(e) => setAssistantEcgPrompt((prev) => ({ ...prev, outputFormat: e.target.value }))}>
                <option value="waveform">Waveform Image</option>
                <option value="timeseries">Time-Series Data (CSV)</option>
                <option value="animation">Animation (coming soon)</option>
              </select>
            </label>
          </div>
          <div className="actions">
            {Object.entries(ECG_PRESETS).map(([key, preset]) => (
              <button key={key} className="btn" onClick={() => applyEcgPreset(key)}>{preset.label}</button>
            ))}
          </div>
          <h3>ECG Signal</h3>
          <div className="ecg-meta-row">
            <span className="ecg-meta-chip">{assistantDisplayHr != null ? `BPM ${assistantDisplayHr}` : 'BPM --'}</span>
            <span className="ecg-meta-chip">
              {Number.isFinite(Number(assistantEcgMeta.sampleRate))
                ? `Sample ${Number(assistantEcgMeta.sampleRate).toFixed(0)} Hz`
                : 'Sample --'}
            </span>
            <span className="ecg-meta-chip">
              {Number.isFinite(Number(assistantEcgMeta.durationSec))
                ? `Duration ${Number(assistantEcgMeta.durationSec).toFixed(1)}s`
                : 'Duration --'}
            </span>
            <span className={`ecg-meta-chip ${assistantEcgLive ? 'live' : ''}`}>{assistantEcgLive ? 'Live ON' : 'Live OFF'}</span>
          </div>
          <div className="ecg-box ecg-box--assistant">
            {assistantVisibleEcg.length > 1 ? (
              <svg viewBox="0 0 920 140" preserveAspectRatio="none"><polyline points={ecgPoints(assistantVisibleEcg)} /></svg>
            ) : (
              <div className="ecg-placeholder">{assistantEcgLoading ? 'Generating ECG signal...' : 'Analyze ECG photo or click Generate ECG Signal.'}</div>
            )}
          </div>
          <div className="actions">
            <button className="btn" onClick={() => generateAssistantEcgSignal('manual')} disabled={assistantEcgLoading}>
              {assistantEcgLoading ? 'Generating...' : 'Generate ECG Signal'}
            </button>
            <button
              className={`btn ${assistantEcgLive ? 'primary' : ''}`}
              onClick={() => {
                const next = !assistantEcgLive
                setAssistantEcgLive(next)
                if (next) generateAssistantEcgSignal('live')
              }}
            >
              {assistantEcgLive ? 'Stop Live ECG' : 'Start Live ECG'}
            </button>
            <button className="btn" onClick={() => setAssistantEcgExpanded(true)} disabled={assistantVisibleEcg.length < 2}>
              Expand ECG
            </button>
            {assistantEcgPrompt.outputFormat === 'timeseries' && (
              <button className="btn" onClick={exportAssistantEcgCsv} disabled={assistantVisibleEcg.length < 2}>
                Download ECG CSV
              </button>
            )}
          </div>

          {viewerRole === 'doctor' && (
            <>
              <h3>Upload Record For Selected Patient</h3>
              <div className="profile-create-grid">
                <label><span>Record Type</span>
                  <select value={doctorUploadType} onChange={(e) => setDoctorUploadType(e.target.value)}>
                    <option value="ecg">ECG</option>
                    <option value="mri">MRI</option>
                    <option value="cathlab">Cath Lab</option>
                    <option value="report">Report</option>
                    <option value="lab">Lab</option>
                    <option value="imaging">Imaging</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <label><span>Select File</span><input type="file" onChange={(e) => setDoctorUploadFile(e.target.files?.[0] || null)} /></label>
                <label><span>Summary</span><input value={doctorUploadSummary} onChange={(e) => setDoctorUploadSummary(e.target.value)} placeholder="Optional summary for patient history" /></label>
              </div>
              <div className="actions">
                <button className="btn primary" onClick={uploadDoctorRecordForPatient} disabled={doctorUploadLoading || !doctorPatientData?.patient?.user_id}>
                  {doctorUploadLoading ? 'Uploading...' : 'Upload To Selected Patient'}
                </button>
              </div>

              <h3>Patient Uploaded Records</h3>
              <div className="history-scroll">
                {(doctorPatientData?.records || []).length === 0 && <p className="muted">Search a patient ID to see linked uploads.</p>}
                {(doctorPatientData?.records || []).map((r) => (
                  <div key={`rec-${r.id}`} className="history-item">
                    <button className="history-view-btn">
                      <strong>{r.file_name}</strong>
                      <small>
                        {(r.file_type || 'file')} · {formatDateTime(r.upload_date)}
                        {r.diagnosis_summary ? ` · ${r.diagnosis_summary}` : ''}
                      </small>
                    </button>
                    <div className="actions">
                      {(r.file_type || '').startsWith('image/') && (
                        <button className="btn" onClick={() => setDoctorImagePrimary(`${apiBase}${r.file_url}`)}>View</button>
                      )}
                      <a className="btn" href={`${apiBase}${r.file_url}`} target="_blank" rel="noreferrer">Open</a>
                    </div>
                  </div>
                ))}
              </div>

              {doctorImagePrimary && (
                <>
                  <h3>Medical Image Viewer</h3>
                  <div className="actions">
                    <label><span>Zoom</span><input type="range" min="1" max="3" step="0.1" value={doctorImageZoom} onChange={(e) => setDoctorImageZoom(Number(e.target.value))} /></label>
                    <select value={doctorImageCompare} onChange={(e) => setDoctorImageCompare(e.target.value)}>
                      <option value="">Compare with old image (optional)</option>
                      {(doctorPatientData?.records || [])
                        .filter((r) => (r.file_type || '').startsWith('image/'))
                        .map((r) => <option key={`cmp-${r.id}`} value={`${apiBase}${r.file_url}`}>{r.file_name}</option>)}
                    </select>
                  </div>
                  <div className="image-compare">
                    <img src={doctorImagePrimary} alt="Primary medical scan" style={{ transform: `scale(${doctorImageZoom})` }} />
                    {doctorImageCompare && <img src={doctorImageCompare} alt="Comparison medical scan" style={{ transform: `scale(${doctorImageZoom})` }} />}
                  </div>
                </>
              )}

              <h3>Patient AI Diagnosis Timeline</h3>
              <div className="history-scroll">
                {(doctorPatientData?.diagnoses || []).length === 0 && <p className="muted">No linked diagnosis history found for this patient name.</p>}
                {(doctorPatientData?.diagnoses || []).map((d) => (
                  <div key={`diag-${d.id}`} className="history-item">
                    <button className="history-view-btn">
                      <strong>{d.report_id}</strong>
                      <small>{d.risk_level} · {formatPct(d.master_probability)} · {d.diagnosis_summary || 'No summary'} · {formatDateTime(d.created_at)}</small>
                    </button>
                  </div>
                ))}
              </div>

            </>
          )}

          <h3>{viewerRole === 'doctor' ? 'ECG Image Analyzer' : 'Upload ECG Photo'}</h3>
          <div
            className={`image-dropzone ${analyzerDragTarget === 'ecg' ? 'active' : ''}`}
            onDragOver={(e) => handleAnalyzerDragOver(e, 'ecg')}
            onDragLeave={(e) => handleAnalyzerDragLeave(e, 'ecg')}
            onDrop={(e) => handleAnalyzerDrop(e, 'ecg', setEcgImageFile, 'ECG Analyzer', analyzeEcgImage)}
          >
            <p className="muted">Drag and drop ECG image here, or choose file.</p>
            <div className="actions">
              <input
                type="file"
                accept=".png,.jpg,.jpeg,image/png,image/jpeg"
                onChange={(e) => {
                  const file = e.target.files?.[0] || null
                  if (file && !isSupportedDiagnosticImage(file)) {
                    setError('ECG analyzer supports only PNG/JPG/JPEG.')
                    setEcgImageFile(null)
                    e.target.value = ''
                    return
                  }
                  setError('')
                  setEcgImageFile(file)
                  if (file) generateAssistantEcgSignal('manual')
                }}
              />
              <button className="btn primary" onClick={() => analyzeEcgImage()} disabled={ecgImageAnalyzing}>
                {ecgImageAnalyzing ? 'Analyzing...' : (viewerRole === 'doctor' ? 'Analyze ECG Image' : 'Analyze ECG Photo')}
              </button>
            </div>
            {ecgImageFile && <p className="active-user">Selected: <b>{ecgImageFile.name}</b></p>}
          </div>
          {ecgImageSummary && (
            <div className="chat-log">
              <div className="chat-row assistant">
                <strong>Summary:</strong> {ecgImageSummary.summary}
              </div>
              {(ecgImageSummary.quality_flags || []).map((flag, idx) => (
                <div key={idx} className="chat-row user">
                  <strong>Quality Flag:</strong> {flag}
                </div>
              ))}
              {(ecgImageSummary.precautions || []).map((item, idx) => (
                <div key={`p-${idx}`} className="chat-row assistant">
                  <strong>Precaution:</strong> {item}
                </div>
              ))}
            </div>
          )}

          <h3>{viewerRole === 'doctor' ? 'MRI Image Analyzer' : 'Upload MRI Photo'}</h3>
          <div
            className={`image-dropzone ${analyzerDragTarget === 'mri' ? 'active' : ''}`}
            onDragOver={(e) => handleAnalyzerDragOver(e, 'mri')}
            onDragLeave={(e) => handleAnalyzerDragLeave(e, 'mri')}
            onDrop={(e) => handleAnalyzerDrop(e, 'mri', setMriImageFile, 'MRI Analyzer', analyzeMriImage)}
          >
            <p className="muted">Drag and drop MRI image here, or choose file.</p>
            <div className="actions">
              <input
                type="file"
                accept=".png,.jpg,.jpeg,image/png,image/jpeg"
                onChange={(e) => {
                  const file = e.target.files?.[0] || null
                  if (file && !isSupportedDiagnosticImage(file)) {
                    setError('MRI analyzer supports only PNG/JPG/JPEG.')
                    setMriImageFile(null)
                    e.target.value = ''
                    return
                  }
                  setError('')
                  setMriImageFile(file)
                }}
              />
              <button className="btn primary" onClick={() => analyzeMriImage()} disabled={mriImageAnalyzing}>
                {mriImageAnalyzing ? 'Analyzing...' : (viewerRole === 'doctor' ? 'Analyze MRI Image' : 'Analyze MRI Photo')}
              </button>
            </div>
            {mriImageFile && <p className="active-user">Selected: <b>{mriImageFile.name}</b></p>}
          </div>
          {mriImageSummary && (
            <div className="chat-log">
              <div className="chat-row assistant">
                <strong>Summary:</strong> {mriImageSummary.summary}
              </div>
              {(mriImageSummary.quality_flags || []).map((flag, idx) => (
                <div key={`mri-f-${idx}`} className="chat-row user">
                  <strong>Quality Flag:</strong> {flag}
                </div>
              ))}
              {(mriImageSummary.precautions || []).map((item, idx) => (
                <div key={`mri-p-${idx}`} className="chat-row assistant">
                  <strong>Precaution:</strong> {item}
                </div>
              ))}
            </div>
          )}

          <h3>{viewerRole === 'doctor' ? 'Cath Lab Image Analyzer' : 'Upload Cath Lab Photo'}</h3>
          <div
            className={`image-dropzone ${analyzerDragTarget === 'cath' ? 'active' : ''}`}
            onDragOver={(e) => handleAnalyzerDragOver(e, 'cath')}
            onDragLeave={(e) => handleAnalyzerDragLeave(e, 'cath')}
            onDrop={(e) => handleAnalyzerDrop(e, 'cath', setCathImageFile, 'Cath Lab Analyzer', analyzeCathlabImage)}
          >
            <p className="muted">Drag and drop Cath Lab image here, or choose file.</p>
            <div className="actions">
              <input
                type="file"
                accept=".png,.jpg,.jpeg,image/png,image/jpeg"
                onChange={(e) => {
                  const file = e.target.files?.[0] || null
                  if (file && !isSupportedDiagnosticImage(file)) {
                    setError('Cath Lab analyzer supports only PNG/JPG/JPEG.')
                    setCathImageFile(null)
                    e.target.value = ''
                    return
                  }
                  setError('')
                  setCathImageFile(file)
                }}
              />
              <button className="btn primary" onClick={() => analyzeCathlabImage()} disabled={cathImageAnalyzing}>
                {cathImageAnalyzing ? 'Analyzing...' : (viewerRole === 'doctor' ? 'Analyze Cath Lab Image' : 'Analyze Cath Lab Photo')}
              </button>
            </div>
            {cathImageFile && <p className="active-user">Selected: <b>{cathImageFile.name}</b></p>}
          </div>
          {cathImageSummary && (
            <div className="chat-log">
              <div className="chat-row assistant">
                <strong>Summary:</strong> {cathImageSummary.summary}
              </div>
              {(cathImageSummary.quality_flags || []).map((flag, idx) => (
                <div key={`cath-f-${idx}`} className="chat-row user">
                  <strong>Quality Flag:</strong> {flag}
                </div>
              ))}
              {(cathImageSummary.precautions || []).map((item, idx) => (
                <div key={`cath-p-${idx}`} className="chat-row assistant">
                  <strong>Precaution:</strong> {item}
                </div>
              ))}
            </div>
          )}

          {viewerRole === 'patient' && (
            <>
              <h3>Care Assistant (Simple Guidance + Precautions)</h3>
              <div className="chat-log">
                {chatLog.length === 0 && <p className="muted">Ask any question; response includes precautions automatically.</p>}
                {chatLog.map((entry, idx) => <div key={idx} className={`chat-row ${entry.role}`}><strong>{entry.role === 'user' ? 'You' : 'Assistant'}:</strong> {entry.text}</div>)}
              </div>
              <form className="chat-form" onSubmit={sendChat}>
                <input
                  value={chatText}
                  onChange={(e) => setChatText(e.target.value)}
                  placeholder="Ask about your report, medicines, diet, or precautions..."
                />
                <button className="btn primary" disabled={chatLoading} type="submit">{chatLoading ? 'Sending...' : 'Send'}</button>
              </form>
            </>
          )}
        </section>
        )}
      </section>
      )}
      </>
      )}
      {assistantEcgExpanded && (
        <div className="ecg-modal-overlay" role="dialog" aria-modal="true" onClick={() => setAssistantEcgExpanded(false)}>
          <div className="ecg-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ecg-modal-head">
              <h3>Expanded ECG Signal</h3>
              <button className="btn" onClick={() => setAssistantEcgExpanded(false)}>Close</button>
            </div>
            <div className="ecg-box ecg-box--expanded">
              <svg viewBox="0 0 920 140" preserveAspectRatio="none"><polyline points={ecgPoints(assistantVisibleEcg)} /></svg>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

export default App
