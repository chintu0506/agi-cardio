"""
AGI-Driven Intelligent Cardiovascular Diagnostic System
Flask API — v2.0 (Multimodal | Explainable | Conversational)
"""

import json, os, sys, math, re, random, subprocess, threading
from datetime import datetime, timedelta
import joblib, numpy as np, pandas as pd
from flask import Flask, request, jsonify, Response, render_template_string
import logging
from io import BytesIO
from storage import get_db, init_db, UPLOAD_DIR
from auth_access import install_auth_access_routes, SESSIONS

try:
    from PIL import Image
except Exception:
    Image = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)
app = Flask(__name__)
init_db()

# ── CORS ─────────────────────────────────────────────────────────────────────
def cors(data, status=200):
    body = json.dumps(data) if not isinstance(data, str) else data
    r = Response(body, status=status, mimetype='application/json')
    r.headers['Access-Control-Allow-Origin']  = '*'
    r.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return r

@app.after_request
def _cors(resp):
    resp.headers['Access-Control-Allow-Origin']  = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return resp

@app.route('/', defaults={'path':''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def _opt(path): return cors({})

install_auth_access_routes(app, get_db, cors, UPLOAD_DIR)


def _current_user_optional():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    sess = SESSIONS.get(token)
    if not sess:
        return None
    if datetime.fromisoformat(sess["expires_at"]) < datetime.now():
        SESSIONS.pop(token, None)
        return None
    return sess.get("user")


def _profile_is_accessible(profile_row, user):
    if not user:
        return False
    return str(profile_row.get("owner_user_id") or "") == str(user.get("user_id") or "")

@app.route('/', methods=['GET'])
def root():
    return cors({
        'name': 'AGI CardioSense API',
        'status': 'ok',
        'message': 'Backend is running. Use /diagnose for browser input form or call /api/predict directly.',
        'endpoints': [
            '/diagnose', '/db-view', '/api/health', '/api/model-info', '/api/eval-report', '/api/predict', '/api/chat',
            '/api/sample-cases', '/api/default-patient', '/api/profiles', '/api/profiles/<id>/diagnose',
            '/api/profiles/<id>/diagnoses', '/api/ecg-realtime', '/api/ecg-image-summary',
            '/api/mri-image-summary', '/api/cathlab-image-summary', '/api/auth/signup/initiate',
            '/api/auth/signup/verify', '/api/auth/login', '/api/auth/me', '/api/patient-records',
            '/api/patient-records/upload', '/api/patient/doctor-summaries',
            '/api/doctors', '/api/patient/appointments',
            '/api/doctor/dashboard', '/api/doctor/patients',
            '/api/doctor/patient/<patient_id>', '/api/doctor/patient/<patient_id>/diagnose',
            '/api/doctor/patient/<patient_id>/records/upload',
            '/api/doctor/appointments', '/api/doctor/alerts',
            '/api/doctor/messages/<patient_id>', '/api/doctor/notes'
        ]
    })

@app.route('/diagnose', methods=['GET'])
def diagnose_page():
    fields = []
    for f in FEATURES:
        info = FEAT_INFO.get(f, {})
        if info.get('cat'):
            options = CAT_VALUES.get(f, {})
            fields.append({
                'name': f,
                'label': info.get('label', f),
                'type': 'select',
                'options': sorted(options.items(), key=lambda x: int(x[0])),
                'unit': info.get('unit', ''),
                'value': DEFAULT_PATIENT.get(f, 0)
            })
        else:
            fields.append({
                'name': f,
                'label': info.get('label', f),
                'type': 'number',
                'min': info.get('low', 0),
                'max': info.get('high', 9999),
                'step': 0.1 if f in ['oldpeak', 'bmi', 'creatinine', 'troponin'] else 1,
                'unit': info.get('unit', ''),
                'value': DEFAULT_PATIENT.get(f, '')
            })

    html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AGI CardioSense - Patient Diagnosis</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; background: #f4f7fb; color: #111827; }
    .wrap { max-width: 1100px; margin: 24px auto; padding: 0 16px; }
    .card { background: #fff; border: 1px solid #dbe3ef; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    h1 { margin: 0 0 6px; font-size: 24px; }
    p { margin: 0; color: #4b5563; }
    .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
    label { display: grid; gap: 6px; font-size: 13px; color: #374151; }
    input, select { border: 1px solid #cfd8e6; border-radius: 8px; padding: 8px; font-size: 14px; }
    button { background: #0f766e; color: #fff; border: 1px solid #0b625c; border-radius: 8px; padding: 10px 14px; font-weight: 600; cursor: pointer; min-height: 38px; min-width: 120px; display: inline-flex; align-items: center; justify-content: center; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .muted { color: #6b7280; font-size: 13px; margin: 0; }
    .risk { border-radius: 10px; padding: 12px; border: 1px solid #e4ebf7; margin: 10px 0; display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; }
    .risk div { background: #fff; border: 1px solid #edf1f8; border-radius: 8px; padding: 8px; }
    .risk small { display: block; color: #6b7280; margin-bottom: 4px; }
    .risk strong { font-size: 18px; }
    .risk-low { background: #eafaf3; }
    .risk-mid { background: #fff4dd; }
    .risk-high { background: #ffe8d6; }
    .risk-critical { background: #ffe6eb; }
    .section { margin-top: 12px; }
    .section h3 { margin: 0 0 8px; font-size: 16px; }
    .dgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .dcard { border: 1px solid #dfe7f2; border-radius: 10px; padding: 10px; background: #fff; }
    .dhead { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
    .dcard p { margin: 6px 0; font-size: 13px; color: #4b5563; }
    ul, ol { margin: 0; padding-left: 18px; }
    li { margin-bottom: 6px; font-size: 14px; }
    details { margin-top: 12px; }
    pre { background: #0b1020; color: #d8e2ff; border-radius: 8px; padding: 12px; overflow: auto; min-height: 120px; }
    .row { display: flex; gap: 10px; align-items: center; margin-top: 12px; }
    .row-wrap { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 12px; }
    .hint { color: #6b7280; font-size: 12px; }
    .upload-box { margin-top: 12px; border: 1px dashed #cfd8e6; border-radius: 10px; padding: 10px; background: #fbfcff; }
    .profile-box { margin-top: 12px; border: 1px solid #d8e3f2; border-radius: 10px; padding: 10px; background: #f8fbff; }
    .profile-grid { display: grid; grid-template-columns: 2fr 1fr 1fr 2fr auto; gap: 8px; margin-top: 8px; align-items: stretch; }
    .profile-grid button { width: 100%; }
    .history-item button { min-width: 90px; }
    .history-box { margin-top: 12px; border: 1px solid #e1e8f5; border-radius: 10px; padding: 10px; background: #fcfdff; }
    .history-list { display: grid; gap: 8px; max-height: 220px; overflow: auto; margin-top: 8px; }
    .history-item { border: 1px solid #dfe7f2; border-radius: 8px; padding: 8px; background: #fff; display: flex; justify-content: space-between; gap: 10px; align-items: center; }
    .history-item small { color: #6b7280; }
    .thumbs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
    .thumb { border: 1px solid #dfe7f2; border-radius: 8px; overflow: hidden; background: #fff; }
    .thumb img { width: 100%; height: 90px; object-fit: cover; display: block; }
    .thumb small { display: block; padding: 4px 6px; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr 1fr; } .dgrid { grid-template-columns: 1fr; } .risk { grid-template-columns: 1fr; } .profile-grid { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } .thumbs { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>AGI CardioSense - Patient Diagnosis</h1>
      <p>Enter patient clinical values and generate AI diagnosis.</p>
      <form id="diag-form">
        <div class="profile-box">
          <label><b>Patient Profile</b></label>
          <div class="row-wrap">
            <select id="profile-picker" style="max-width:380px;">
              <option value="">Select profile to run diagnosis...</option>
            </select>
            <button type="button" id="refresh-profiles-btn">Refresh Profiles</button>
          </div>
          <div class="profile-grid">
            <input id="profile-name" placeholder="Full name (required)" />
            <input id="profile-age" type="number" min="1" max="120" placeholder="Age" />
            <select id="profile-sex">
              <option value="">Sex</option>
              <option value="0">Female</option>
              <option value="1">Male</option>
            </select>
            <input id="profile-notes" placeholder="Notes (optional)" />
            <button type="button" id="create-profile-btn">Create Profile</button>
          </div>
          <p class="hint">Diagnosis can run only when a profile is selected. Each run is saved to that profile history.</p>
        </div>
        <div class="row">
          <select id="sample-picker" style="max-width:340px;">
            <option value="">Load sample patient case...</option>
          </select>
          <button type="button" id="load-sample-btn">Load Sample</button>
        </div>
        <div class="grid">
          {% for f in fields %}
          <label>
            {{ f.label }}{% if f.unit %} ({{ f.unit }}){% endif %}
            {% if f.type == 'select' %}
            <select name="{{ f.name }}">
              {% for value, text in f.options %}
              <option value="{{ value }}" {% if value == f.value %}selected{% endif %}>{{ text }}</option>
              {% endfor %}
            </select>
            {% else %}
            <input type="number" name="{{ f.name }}" min="{{ f.min }}" max="{{ f.max }}" step="{{ f.step }}" value="{{ f.value }}" required />
            {% endif %}
          </label>
          {% endfor %}
        </div>
        <div class="row">
          <button type="submit" id="run-btn">Generate Diagnosis</button>
          <span class="hint">API endpoint: /api/profiles/&lt;id&gt;/diagnose</span>
        </div>
        <div class="upload-box">
          <label><b>Patient Input Images</b> (ECG, reports, scans)</label>
          <div class="row-wrap">
            <input type="file" id="patient-images" accept="image/*" multiple />
            <button type="button" id="generate-report-btn">Download Patient Report</button>
            <span class="hint">Uploads are used inside generated report file.</span>
          </div>
          <div id="image-preview" class="thumbs"></div>
        </div>
      </form>
    </div>
    <div class="card">
      <h2>Diagnosis Output</h2>
      <p class="muted" id="status">Run diagnosis to view structured results.</p>
      <div id="output"></div>
      <div class="history-box">
        <h3 style="margin:0;">Previous Diagnoses</h3>
        <div id="history-list" class="history-list">
          <p class="muted">Select a profile to load diagnosis history.</p>
        </div>
      </div>
      <details>
        <summary>Raw JSON</summary>
        <pre id="raw-output">Run diagnosis to view results...</pre>
      </details>
    </div>
  </div>
  <script>
    const form = document.getElementById('diag-form');
    const output = document.getElementById('output');
    const status = document.getElementById('status');
    const rawOutput = document.getElementById('raw-output');
    const runBtn = document.getElementById('run-btn');
    const profilePicker = document.getElementById('profile-picker');
    const refreshProfilesBtn = document.getElementById('refresh-profiles-btn');
    const createProfileBtn = document.getElementById('create-profile-btn');
    const profileName = document.getElementById('profile-name');
    const profileAge = document.getElementById('profile-age');
    const profileSex = document.getElementById('profile-sex');
    const profileNotes = document.getElementById('profile-notes');
    const historyList = document.getElementById('history-list');
    const imageInput = document.getElementById('patient-images');
    const imagePreview = document.getElementById('image-preview');
    const generateReportBtn = document.getElementById('generate-report-btn');
    const samplePicker = document.getElementById('sample-picker');
    const loadSampleBtn = document.getElementById('load-sample-btn');
    let sampleCases = [];
    let profiles = [];
    let selectedProfileId = null;
    let uploadedImages = [];
    let lastDiagnosis = null;
    function esc(v) {
      return String(v ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    }
    function riskClass(level) {
      if (level === 'CRITICAL') return 'risk-critical';
      if (level === 'HIGH') return 'risk-high';
      if (level === 'MODERATE') return 'risk-mid';
      return 'risk-low';
    }
    function renderList(items, emptyText) {
      if (!items || items.length === 0) return `<p class="muted">${emptyText}</p>`;
      return `<ul>${items.map((x) => `<li>${x}</li>`).join('')}</ul>`;
    }
    function renderReport(data) {
      const level = data?.risk_tier?.level || 'UNKNOWN';
      const action = data?.risk_tier?.action || 'N/A';
      const diseases = (data?.diseases || []).map((d) => `
        <article class="dcard">
          <div class="dhead">
            <strong>${esc(d.name)}</strong>
            <strong>${Number(d.probability).toFixed(1)}%</strong>
          </div>
          <p>${esc(d.description || '')}</p>
          <p><b>ICD:</b> ${esc(d.icd || '-')}</p>
        </article>
      `).join('');
      const recs = (data?.recommendations || []).map((r) => `[${esc(r.priority)}] ${esc(r.text)}`);
      const flags = (data?.abnormal_flags || []).map((f) => `[${esc(f.severity)}] ${esc(f.feature)}: ${esc(f.message)} (${esc(f.value)})`);
      const reasoning = (data?.reasoning_chain || []).map((s) => `<li><b>${esc(s.category)}:</b> ${esc(s.finding)} (${esc(s.weight)})</li>`).join('');
      const profileRows = Object.entries(data?.patient_profile || {}).map(([k, v]) => `<li><b>${esc(k)}:</b> ${esc(v)}</li>`).join('');
      output.innerHTML = `
        <div class="risk ${riskClass(level)}">
          <div><small>Overall Risk</small><strong>${Number(data?.master_probability || 0).toFixed(1)}%</strong></div>
          <div><small>Risk Tier</small><strong>${esc(level)}</strong></div>
          <div><small>Recommended Action</small><strong>${esc(action)}</strong></div>
        </div>
        <section class="section">
          <h3>Disease Cards</h3>
          <div class="dgrid">${diseases || '<p class="muted">No high-probability diseases found.</p>'}</div>
        </section>
        <section class="section">
          <h3>Recommendations</h3>
          ${renderList(recs, 'No recommendations returned.')}
        </section>
        <section class="section">
          <h3>Abnormal Flags</h3>
          ${renderList(flags, 'No abnormal flags detected.')}
        </section>
        <section class="section">
          <h3>Reasoning Chain</h3>
          ${reasoning ? `<ol>${reasoning}</ol>` : '<p class="muted">No reasoning steps returned.</p>'}
        </section>
        <section class="section">
          <h3>Patient Profile</h3>
          ${profileRows ? `<ul>${profileRows}</ul>` : '<p class="muted">No profile data.</p>'}
        </section>
      `;
    }
    function renderHistory(items) {
      if (!items || items.length === 0) {
        historyList.innerHTML = '<p class="muted">No previous diagnoses for this profile.</p>';
        return;
      }
      historyList.innerHTML = items.map((item) => `
        <div class="history-item">
          <div>
            <div><b>${esc(item.report_id || 'N/A')}</b></div>
            <small>${esc(item.created_at || '')} | ${esc(item.risk_level || 'UNKNOWN')} | ${Number(item.master_probability || 0).toFixed(1)}%</small>
          </div>
          <button type="button" data-history-id="${item.id}">View</button>
        </div>
      `).join('');
      historyList.querySelectorAll('button[data-history-id]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = Number(btn.getAttribute('data-history-id'));
          const found = items.find((x) => x.id === id);
          if (found && found.result_payload) {
            lastDiagnosis = found.result_payload;
            renderReport(found.result_payload);
            rawOutput.textContent = JSON.stringify(found.result_payload, null, 2);
            status.textContent = `Loaded previous diagnosis: ${found.report_id}`;
          }
        });
      });
    }
    async function loadHistory(profileId) {
      if (!profileId) {
        historyList.innerHTML = '<p class="muted">Select a profile to load diagnosis history.</p>';
        return;
      }
      try {
        const res = await fetch(`/api/profiles/${profileId}/diagnoses`);
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || 'Failed to load history');
        renderHistory(Array.isArray(data) ? data : []);
      } catch (err) {
        historyList.innerHTML = `<p class="muted">History load failed: ${esc(err.message || err)}</p>`;
      }
    }
    async function loadProfiles() {
      try {
        const res = await fetch('/api/profiles');
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || 'Failed to load profiles');
        profiles = Array.isArray(data) ? data : [];
        profilePicker.innerHTML = '<option value="">Select profile to run diagnosis...</option>';
        for (const p of profiles) {
          const opt = document.createElement('option');
          opt.value = p.id;
          opt.textContent = `${p.full_name} (#${p.id})`;
          if (selectedProfileId && Number(p.id) === Number(selectedProfileId)) opt.selected = true;
          profilePicker.appendChild(opt);
        }
      } catch (err) {
        status.textContent = `Profile load failed: ${err.message || err}`;
      }
    }
    async function createProfile() {
      const full_name = profileName.value.trim();
      if (!full_name) {
        status.textContent = 'Enter profile full name before creating profile.';
        return;
      }
      try {
        const payload = {
          full_name,
          age: profileAge.value ? Number(profileAge.value) : null,
          sex: profileSex.value === '' ? null : Number(profileSex.value),
          notes: profileNotes.value.trim(),
        };
        const res = await fetch('/api/profiles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || 'Failed to create profile');
        selectedProfileId = data.id;
        profileName.value = '';
        profileAge.value = '';
        profileSex.value = '';
        profileNotes.value = '';
        await loadProfiles();
        await loadHistory(selectedProfileId);
        status.textContent = `Profile created: ${data.full_name} (#${data.id})`;
      } catch (err) {
        status.textContent = `Profile create failed: ${err.message || err}`;
      }
    }
    function readFileAsDataUrl(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }
    function renderImagePreviews() {
      if (uploadedImages.length === 0) {
        imagePreview.innerHTML = '<p class="muted">No images selected.</p>';
        return;
      }
      imagePreview.innerHTML = uploadedImages.map((img) => `
        <div class="thumb">
          <img src="${img.dataUrl}" alt="${esc(img.name)}" />
          <small title="${esc(img.name)}">${esc(img.name)}</small>
        </div>
      `).join('');
    }
    async function loadSelectedImages(files) {
      const list = Array.from(files || []).slice(0, 8);
      uploadedImages = [];
      for (const file of list) {
        if (!file.type.startsWith('image/')) continue;
        const dataUrl = await readFileAsDataUrl(file);
        uploadedImages.push({ name: file.name, dataUrl });
      }
      renderImagePreviews();
    }
    function currentPayloadFromForm() {
      const payload = {};
      for (const [k, v] of new FormData(form).entries()) payload[k] = Number(v);
      return payload;
    }
    function generateReportHtml(diagnosis, inputPayload, images) {
      const ts = new Date().toISOString();
      const diseaseCards = (diagnosis.diseases || []).map((d) => `
        <div style="border:1px solid #dfe7f2;border-radius:8px;padding:10px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;"><b>${esc(d.name)}</b><b>${Number(d.probability).toFixed(1)}%</b></div>
          <div style="font-size:13px;color:#4b5563;">${esc(d.description || '')}</div>
          <div style="font-size:12px;color:#6b7280;">ICD: ${esc(d.icd || '-')}</div>
        </div>
      `).join('') || '<p>No disease cards available.</p>';
      const recs = (diagnosis.recommendations || []).map((r) => `<li>[${esc(r.priority)}] ${esc(r.text)}</li>`).join('') || '<li>No recommendations.</li>';
      const flags = (diagnosis.abnormal_flags || []).map((f) => `<li>[${esc(f.severity)}] ${esc(f.feature)}: ${esc(f.message)} (${esc(f.value)})</li>`).join('') || '<li>No abnormal flags.</li>';
      const profile = Object.entries(diagnosis.patient_profile || {}).map(([k, v]) => `<li><b>${esc(k)}:</b> ${esc(v)}</li>`).join('') || '<li>No profile values.</li>';
      const rawInputs = Object.entries(inputPayload || {}).map(([k, v]) => `<li><b>${esc(k)}:</b> ${esc(v)}</li>`).join('');
      const imgHtml = (images || []).map((img) => `
        <div style="margin:0 0 12px 0;">
          <div style="font-size:12px;color:#6b7280;margin-bottom:4px;">${esc(img.name)}</div>
          <img src="${img.dataUrl}" alt="${esc(img.name)}" style="max-width:100%;max-height:260px;border:1px solid #dfe7f2;border-radius:8px;" />
        </div>
      `).join('') || '<p>No patient images attached.</p>';
      return `<!doctype html><html><head><meta charset="utf-8"/><title>Patient Diagnosis Report</title></head>
      <body style="font-family:Arial,sans-serif;max-width:900px;margin:20px auto;color:#111827;line-height:1.4;">
        <h1 style="margin:0 0 4px 0;">AGI CardioSense - Patient Report</h1>
        <p style="margin:0 0 16px 0;color:#6b7280;">Generated at ${esc(ts)} | Report ID: ${esc(diagnosis.report_id || 'N/A')}</p>
        <h2>Risk Summary</h2>
        <p><b>Overall Risk:</b> ${Number(diagnosis.master_probability || 0).toFixed(1)}% | <b>Tier:</b> ${esc(diagnosis?.risk_tier?.level || 'UNKNOWN')}</p>
        <p><b>Action:</b> ${esc(diagnosis?.risk_tier?.action || 'N/A')}</p>
        <h2>Disease Cards</h2>${diseaseCards}
        <h2>Recommendations</h2><ul>${recs}</ul>
        <h2>Abnormal Flags</h2><ul>${flags}</ul>
        <h2>Patient Profile</h2><ul>${profile}</ul>
        <h2>Input Values Used</h2><ul>${rawInputs}</ul>
        <h2>Patient Images</h2>${imgHtml}
      </body></html>`;
    }
    function downloadReportFile(html, reportId) {
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const safeId = (reportId || 'REPORT').replace(/[^A-Za-z0-9_-]/g, '_');
      a.href = url;
      a.download = `Cardio_Report_${safeId}.html`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }
    async function loadSampleList() {
      try {
        const res = await fetch('/api/sample-cases');
        const data = await res.json();
        if (!Array.isArray(data)) return;
        sampleCases = data;
        for (const s of sampleCases) {
          const opt = document.createElement('option');
          opt.value = s.name;
          opt.textContent = s.name;
          samplePicker.appendChild(opt);
        }
      } catch (_) {}
    }
    function applySample(sample) {
      if (!sample) return;
      for (const [k, v] of Object.entries(sample)) {
        if (k === 'name') continue;
        const el = form.elements[k];
        if (el) el.value = v;
      }
      status.textContent = `Loaded sample: ${sample.name}`;
    }
    loadSampleBtn.addEventListener('click', () => {
      const selected = sampleCases.find((s) => s.name === samplePicker.value);
      applySample(selected);
    });
    refreshProfilesBtn.addEventListener('click', async () => {
      await loadProfiles();
      if (selectedProfileId) await loadHistory(selectedProfileId);
    });
    createProfileBtn.addEventListener('click', async () => {
      await createProfile();
    });
    profilePicker.addEventListener('change', async () => {
      selectedProfileId = profilePicker.value ? Number(profilePicker.value) : null;
      await loadHistory(selectedProfileId);
      if (selectedProfileId) status.textContent = `Selected profile #${selectedProfileId}`;
    });
    imageInput.addEventListener('change', async (e) => {
      await loadSelectedImages(e.target.files);
    });
    generateReportBtn.addEventListener('click', () => {
      if (!lastDiagnosis) {
        status.textContent = 'Run diagnosis first, then generate report.';
        return;
      }
      const payload = currentPayloadFromForm();
      const html = generateReportHtml(lastDiagnosis, payload, uploadedImages);
      downloadReportFile(html, lastDiagnosis.report_id);
      status.textContent = 'Patient report downloaded successfully.';
    });
    loadSampleList();
    loadProfiles();
    renderImagePreviews();
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!selectedProfileId) {
        status.textContent = 'Select or create a patient profile before running diagnosis.';
        return;
      }
      runBtn.disabled = true;
      status.textContent = `Running model for profile #${selectedProfileId}...`;
      output.innerHTML = '';
      const payload = currentPayloadFromForm();
      try {
        const res = await fetch(`/api/profiles/${selectedProfileId}/diagnose`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
          status.textContent = 'Diagnosis failed.';
          lastDiagnosis = null;
          output.innerHTML = `<p class="muted">${esc(data?.error || 'Unknown error')}</p>`;
        } else {
          status.textContent = `Diagnosis generated. Report ID: ${data.report_id}`;
          lastDiagnosis = data;
          renderReport(data);
          await loadHistory(selectedProfileId);
        }
        rawOutput.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        status.textContent = 'Request failed.';
        output.innerHTML = `<p class="muted">Request failed: ${esc(err)}</p>`;
        rawOutput.textContent = 'Request failed: ' + err;
      } finally {
        runBtn.disabled = false;
      }
    });
  </script>
</body>
</html>
"""
    return render_template_string(html, fields=fields)

@app.route('/db-view', methods=['GET'])
def db_view_page():
    html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AGI CardioSense - Database Viewer</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #f4f7fb; color: #0f172a; }
    .wrap { max-width: 1200px; margin: 24px auto; padding: 0 16px 30px; }
    .card { background: #fff; border: 1px solid #dbe3ef; border-radius: 12px; padding: 14px; margin-bottom: 14px; }
    .top { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; justify-content: space-between; }
    h1 { margin: 0; font-size: 24px; }
    h2 { margin: 0; font-size: 18px; }
    .muted { color: #64748b; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    input, select, button { border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 10px; font-size: 14px; }
    button { background: #0f766e; color: white; border-color: #0b625c; cursor: pointer; }
    button.secondary { background: #f8fafc; color: #0f172a; }
    .stats { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 8px; margin-top: 10px; }
    .stat { border: 1px solid #e2e8f0; border-radius: 10px; padding: 8px; background: #f8fafc; }
    .table-wrap { overflow: auto; border: 1px solid #e2e8f0; border-radius: 10px; margin-top: 8px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid #e2e8f0; text-align: left; padding: 8px; white-space: nowrap; vertical-align: top; }
    th { background: #f8fafc; position: sticky; top: 0; z-index: 1; }
    .json { white-space: pre-wrap; max-width: 420px; }
    @media (max-width: 900px) { .stats { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 600px) { .stats { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="top">
        <div>
          <h1>Database Viewer</h1>
          <p class="muted">Inspect <code>profiles</code> and <code>diagnoses</code> directly from the browser.</p>
        </div>
        <div class="row">
          <button id="refresh-btn">Refresh</button>
          <a href="/diagnose"><button class="secondary" type="button">Back to Diagnose</button></a>
        </div>
      </div>
      <div class="row">
        <input id="search-input" placeholder="Search by name, report id, risk..." style="min-width:260px;" />
        <select id="profile-filter">
          <option value="">All Profiles</option>
        </select>
      </div>
      <div class="stats">
        <div class="stat"><b>Total Profiles</b><div id="profiles-count">0</div></div>
        <div class="stat"><b>Total Diagnoses</b><div id="diagnoses-count">0</div></div>
        <div class="stat"><b>Latest Report ID</b><div id="latest-report">-</div></div>
        <div class="stat"><b>Latest Risk</b><div id="latest-risk">-</div></div>
      </div>
    </div>

    <div class="card">
      <h2>Profiles Table</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Full Name</th><th>Age</th><th>Sex</th><th>Notes</th><th>Created At</th><th>Details JSON</th>
            </tr>
          </thead>
          <tbody id="profiles-body"></tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <h2>Diagnoses Table</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Profile ID</th><th>Report ID</th><th>Risk Level</th><th>Master %</th><th>Created At</th><th>Input JSON</th>
            </tr>
          </thead>
          <tbody id="diagnoses-body"></tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const refreshBtn = document.getElementById('refresh-btn');
    const searchInput = document.getElementById('search-input');
    const profileFilter = document.getElementById('profile-filter');
    const profilesBody = document.getElementById('profiles-body');
    const diagnosesBody = document.getElementById('diagnoses-body');
    const profilesCount = document.getElementById('profiles-count');
    const diagnosesCount = document.getElementById('diagnoses-count');
    const latestReport = document.getElementById('latest-report');
    const latestRisk = document.getElementById('latest-risk');

    let profiles = [];
    let diagnoses = [];

    function esc(v) {
      return String(v ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    }

    function sexLabel(v) {
      if (v === 1 || v === '1') return 'Male';
      if (v === 0 || v === '0') return 'Female';
      return '-';
    }

    async function fetchAll() {
      const pRes = await fetch('/api/profiles');
      profiles = await pRes.json();
      if (!Array.isArray(profiles)) profiles = [];

      diagnoses = [];
      for (const p of profiles) {
        const dRes = await fetch(`/api/profiles/${p.id}/diagnoses`);
        const dData = await dRes.json();
        if (Array.isArray(dData)) diagnoses.push(...dData);
      }
      diagnoses.sort((a, b) => (b.id || 0) - (a.id || 0));
      render();
    }

    function renderFilters() {
      const selected = profileFilter.value;
      profileFilter.innerHTML = '<option value="">All Profiles</option>' +
        profiles.map((p) => `<option value="${p.id}">${esc(p.full_name)}</option>`).join('');
      profileFilter.value = selected;
    }

    function render() {
      renderFilters();
      const q = searchInput.value.trim().toLowerCase();
      const pFilter = profileFilter.value ? Number(profileFilter.value) : null;

      const filteredProfiles = profiles.filter((p) => {
        if (pFilter && p.id !== pFilter) return false;
        if (!q) return true;
        return (`${p.full_name} ${p.notes || ''} ${JSON.stringify(p.details || {})}`).toLowerCase().includes(q);
      });

      const filteredDiagnoses = diagnoses.filter((d) => {
        if (pFilter && d.profile_id !== pFilter) return false;
        if (!q) return true;
        return (`${d.report_id} ${d.risk_level} ${d.master_probability} ${JSON.stringify(d.input_payload || {})}`).toLowerCase().includes(q);
      });

      profilesBody.innerHTML = filteredProfiles.map((p) => `
        <tr>
          <td>${p.id}</td>
          <td>${esc(p.full_name)}</td>
          <td>${p.age ?? '-'}</td>
          <td>${sexLabel(p.sex)}</td>
          <td>${esc(p.notes || '-')}</td>
          <td>${esc(p.created_at || '-')}</td>
          <td class="json">${esc(JSON.stringify(p.details || {}, null, 2))}</td>
        </tr>
      `).join('') || '<tr><td colspan="7">No profiles found.</td></tr>';

      diagnosesBody.innerHTML = filteredDiagnoses.map((d) => `
        <tr>
          <td>${d.id}</td>
          <td>${d.profile_id}</td>
          <td>${esc(d.report_id || '-')}</td>
          <td>${esc(d.risk_level || '-')}</td>
          <td>${Number(d.master_probability || 0).toFixed(1)}</td>
          <td>${esc(d.created_at || '-')}</td>
          <td class="json">${esc(JSON.stringify(d.input_payload || {}, null, 2))}</td>
        </tr>
      `).join('') || '<tr><td colspan="7">No diagnoses found.</td></tr>';

      profilesCount.textContent = String(filteredProfiles.length);
      diagnosesCount.textContent = String(filteredDiagnoses.length);
      latestReport.textContent = filteredDiagnoses[0]?.report_id || '-';
      latestRisk.textContent = filteredDiagnoses[0]
        ? `${filteredDiagnoses[0].risk_level || '-'} (${Number(filteredDiagnoses[0].master_probability || 0).toFixed(1)}%)`
        : '-';
    }

    refreshBtn.addEventListener('click', fetchAll);
    searchInput.addEventListener('input', render);
    profileFilter.addEventListener('change', render);
    fetchAll();
  </script>
</body>
</html>
"""
    return render_template_string(html)

# ── Load models ───────────────────────────────────────────────────────────────
DIR = os.path.join(os.path.dirname(__file__), 'models')
MODEL_KEYS = ['master', 'cad', 'hf', 'arr', 'mi']
MODELS = {}
META = {}
FEATURES = []
scaler = None
RETRAIN_LOCK = threading.Lock()

def load_artifacts():
    global scaler, MODELS, META, FEATURES
    scaler = joblib.load(f'{DIR}/scaler.pkl')
    MODELS = {k: joblib.load(f'{DIR}/{k}_model.pkl') for k in MODEL_KEYS}
    with open(f'{DIR}/model_meta.json') as f:
        META = json.load(f)
    FEATURES = META['features']
    log.info(f"✅ {len(MODELS)} models loaded | master acc {META['models']['master']['accuracy']}%")

def retrain_and_reload():
    """Retrain models with current sklearn version and reload artifacts."""
    with RETRAIN_LOCK:
        log.warning("⚠️ Model compatibility issue detected. Retraining models now...")
        result = subprocess.run(
            [sys.executable, 'train_model.py'],
            cwd=os.path.dirname(__file__),
            text=True,
            capture_output=True,
            check=False
        )
        if result.returncode != 0:
            log.error("Model retrain failed: %s", result.stderr.strip()[-1000:])
            raise RuntimeError("Automatic model retraining failed. Please run backend/train_model.py manually.")
        load_artifacts()
        log.info("✅ Model retraining complete. Prediction retried with refreshed artifacts.")

def run_model_probs(X_scaled):
    probs = {}
    for key, mdl in MODELS.items():
        probs[key] = round(float(mdl.predict_proba(X_scaled)[0][1]) * 100, 1)
    return probs


def get_model_threshold_pct(model_key):
    model_meta = META.get('models', {}).get(model_key, {})
    threshold = float(model_meta.get('threshold', 0.5))
    threshold = min(max(threshold, 0.01), 0.99)
    return round(threshold * 100, 1)

load_artifacts()

# ── Feature labels & normal ranges ───────────────────────────────────────────
FEAT_INFO = {
    'age':              {'label':'Age (yrs)',            'unit':'',      'low':20,   'high':80,  'warn_high':65},
    'sex':              {'label':'Sex',                  'unit':'',      'cat':True},
    'cp':               {'label':'Chest Pain Type',      'unit':'',      'cat':True},
    'trestbps':         {'label':'Resting BP',           'unit':'mmHg',  'low':90,   'high':200, 'normal_max':130, 'warn_high':160},
    'chol':             {'label':'Cholesterol',          'unit':'mg/dL', 'low':100,  'high':580, 'normal_max':200, 'warn_high':240},
    'fbs':              {'label':'Fasting Blood Sugar',  'unit':'',      'cat':True},
    'restecg':          {'label':'Resting ECG',          'unit':'',      'cat':True},
    'thalach':          {'label':'Max Heart Rate',       'unit':'bpm',   'low':60,   'high':210, 'normal_min':140, 'warn_low':120},
    'exang':            {'label':'Exercise Angina',      'unit':'',      'cat':True},
    'oldpeak':          {'label':'ST Depression',        'unit':'mm',    'low':0,    'high':7,   'normal_max':1.0, 'warn_high':2.5},
    'slope':            {'label':'ST Slope',             'unit':'',      'cat':True},
    'ca':               {'label':'Blocked Vessels',      'unit':'',      'low':0,    'high':3,   'warn_high':1},
    'thal':             {'label':'Thalassemia',          'unit':'',      'cat':True},
    'bmi':              {'label':'BMI',                  'unit':'kg/m²', 'low':15,   'high':50,  'normal_max':25,  'warn_high':30},
    'smoking':          {'label':'Smoking',              'unit':'',      'cat':True},
    'diabetes':         {'label':'Diabetes',             'unit':'',      'cat':True},
    'family_history':   {'label':'Family History',       'unit':'',      'cat':True},
    'creatinine':       {'label':'Creatinine',           'unit':'mg/dL', 'low':0.3,  'high':5,   'normal_max':1.2, 'warn_high':2.0},
    'bnp':              {'label':'BNP',                  'unit':'pg/mL', 'low':0,    'high':2000,'normal_max':100, 'warn_high':400},
    'troponin':         {'label':'Troponin-I',           'unit':'ng/mL', 'low':0,    'high':4,   'normal_max':0.04,'warn_high':0.5},
    'ejection_fraction':{'label':'Ejection Fraction',   'unit':'%',     'low':15,   'high':80,  'normal_min':55,  'warn_low':40},
}

CAT_VALUES = {
    'sex':     {0:'Female', 1:'Male'},
    'cp':      {0:'Typical Angina', 1:'Atypical Angina', 2:'Non-Anginal Pain', 3:'Asymptomatic'},
    'fbs':     {0:'Normal (≤120)', 1:'Elevated (>120)'},
    'restecg': {0:'Normal', 1:'ST-T Abnormality', 2:'LV Hypertrophy'},
    'exang':   {0:'No', 1:'Yes'},
    'slope':   {0:'Upsloping', 1:'Flat', 2:'Downsloping'},
    'thal':    {1:'Normal', 2:'Fixed Defect', 3:'Reversible Defect'},
    'smoking': {0:'Non-Smoker', 1:'Smoker'},
    'diabetes':{0:'No', 1:'Yes'},
    'family_history':{0:'No', 1:'Yes'},
}

DEFAULT_PATIENT = {
    'age': 56, 'sex': 1, 'cp': 2, 'trestbps': 142, 'chol': 245, 'fbs': 0, 'restecg': 1,
    'thalach': 132, 'exang': 1, 'oldpeak': 2.1, 'slope': 1, 'ca': 1, 'thal': 2,
    'bmi': 28.4, 'smoking': 1, 'diabetes': 0, 'family_history': 1,
    'creatinine': 1.1, 'bnp': 178, 'troponin': 0.05, 'ejection_fraction': 51
}

# ── Clinical knowledge base ───────────────────────────────────────────────────
KB = {
    'cad': {
        'name': 'Coronary Artery Disease',
        'icd': 'I25.1',
        'description': 'Narrowing or blockage of coronary arteries due to atherosclerosis, restricting blood flow to the heart muscle.',
        'key_markers': ['cp','ca','thal','oldpeak','exang'],
        'treatments': ['Antiplatelet therapy (aspirin)', 'Statin therapy', 'Beta-blockers', 'ACE inhibitors', 'Coronary angiography consideration'],
        'urgency_threshold': 0.72,
    },
    'hf': {
        'name': 'Heart Failure',
        'icd': 'I50.9',
        'description': 'Heart\'s inability to pump sufficient blood to meet body demands, often linked to reduced ejection fraction.',
        'key_markers': ['ejection_fraction','bnp','thalach','trestbps','restecg'],
        'treatments': ['Loop diuretics (furosemide)', 'ACE inhibitors/ARBs', 'Beta-blockers (carvedilol)', 'Cardiac rehabilitation', 'Fluid restriction guidance'],
        'urgency_threshold': 0.65,
    },
    'arr': {
        'name': 'Arrhythmia',
        'icd': 'I49.9',
        'description': 'Abnormal heart rhythm caused by irregular electrical impulses, ranging from benign to life-threatening.',
        'key_markers': ['restecg','thalach','oldpeak','fbs','slope'],
        'treatments': ['Holter monitoring (24h ECG)', 'Antiarrhythmic agents', 'Rate control medications', 'Electrophysiology study', 'Possible ablation referral'],
        'urgency_threshold': 0.60,
    },
    'mi': {
        'name': 'Myocardial Infarction',
        'icd': 'I21.9',
        'description': 'Irreversible ischemic necrosis of heart muscle due to prolonged coronary artery occlusion — medical emergency.',
        'key_markers': ['troponin','cp','oldpeak','ca','slope'],
        'treatments': ['IMMEDIATE: Emergency PCI/thrombolysis', 'Aspirin 300mg stat', 'IV heparin', 'Oxygen therapy', 'ICU admission'],
        'urgency_threshold': 0.55,
    },
}

EXTENDED_DISEASE_KB = {
    'vhd': {
        'name': 'Valvular Heart Disease',
        'icd': 'I38',
        'description': 'Suspected valvular dysfunction (stenosis/regurgitation pattern) based on surrogate cardiac signals.',
        'key_markers': ['restecg', 'exang', 'thalach', 'ejection_fraction', 'oldpeak'],
        'treatments': ['Echocardiography with Doppler', 'Valve disease cardiology review', 'Symptom-guided medical optimization'],
    },
    'cardiomyopathy': {
        'name': 'Cardiomyopathy',
        'icd': 'I42.9',
        'description': 'Possible myocardial disease pattern affecting pumping efficiency inferred from structural/functional markers.',
        'key_markers': ['family_history', 'ejection_fraction', 'bnp', 'restecg', 'troponin'],
        'treatments': ['Cardiac MRI/Echo phenotype assessment', 'Guideline-directed HF therapy review', 'Family risk screening when indicated'],
    },
    'chd': {
        'name': 'Congenital Heart Disease (Adult Suspicion)',
        'icd': 'Q24.9',
        'description': 'Possible congenital-pattern signal inferred from age, rhythm/structural findings, and family risk context.',
        'key_markers': ['age', 'family_history', 'restecg', 'ejection_fraction'],
        'treatments': ['Adult congenital heart clinic referral', 'Targeted echocardiography', 'Functional status assessment'],
    },
    'pad': {
        'name': 'Peripheral Artery Disease',
        'icd': 'I73.9',
        'description': 'Atherosclerotic vascular risk profile suggestive of peripheral arterial involvement.',
        'key_markers': ['age', 'smoking', 'diabetes', 'chol', 'trestbps'],
        'treatments': ['ABI and lower-limb Doppler', 'Smoking cessation and lipid control', 'Antiplatelet risk-benefit assessment'],
    },
    'rheumatic_hd': {
        'name': 'Rheumatic Heart Disease',
        'icd': 'I09.9',
        'description': 'Valvular-rheumatic pattern cannot be confirmed without infection history; flagged only as low-confidence suspicion.',
        'key_markers': ['age', 'restecg', 'ejection_fraction'],
        'treatments': ['Detailed valvular echo review', 'Clinical history for prior rheumatic fever', 'Cardiology follow-up'],
    },
    'hypertensive_hd': {
        'name': 'Hypertensive Heart Disease',
        'icd': 'I11.9',
        'description': 'Cardiac strain pattern associated with persistent elevated blood pressure and LV remodeling markers.',
        'key_markers': ['trestbps', 'restecg', 'ejection_fraction', 'bnp'],
        'treatments': ['Blood-pressure control intensification', 'LV hypertrophy surveillance', 'Renal and metabolic risk control'],
    },
    'infective_hd': {
        'name': 'Infective Heart Disease Pattern',
        'icd': 'I33.9',
        'description': 'Inflammatory/infective cardiac disease cannot be diagnosed from current inputs; flagged only when biomarker stress pattern is significant.',
        'key_markers': ['troponin', 'bnp', 'restecg', 'fever', 'crp', 'esr'],
        'treatments': ['CRP/ESR and blood cultures when clinically indicated', 'Echo/MRI correlation', 'Urgent physician review for fever/chest pain'],
    },
    'pericardial_disease': {
        'name': 'Pericardial / Myopericardial Pattern',
        'icd': 'I31.9',
        'description': 'Potential pericardial-inflammatory pattern inferred from chest pain, inflammatory markers, and myocardial stress markers.',
        'key_markers': ['cp', 'fever', 'crp', 'esr', 'troponin'],
        'treatments': ['Inflammatory panel and echo review', 'Cardiology assessment for pericarditis/myopericarditis', 'Urgent care for persistent pain or hemodynamic instability'],
    },
}

RISK_TIERS = [
    {'max':40,   'level':'LOW',      'color':'#27ae60', 'emoji':'🟩', 'action':'Routine check-up and preventive care.'},
    {'max':70,   'level':'MODERATE', 'color':'#f39c12', 'emoji':'🟡', 'action':'Clinical review and risk-factor control advised.'},
    {'max':84.9, 'level':'HIGH',     'color':'#e67e22', 'emoji':'🟠', 'action':'Urgent cardiology review recommended.'},
    {'max':100, 'level':'CRITICAL', 'color':'#c0392b', 'emoji':'🔴', 'action':'Immediate medical attention recommended.'},
]

# ── Reasoning engine ──────────────────────────────────────────────────────────
def get_risk_tier(prob_pct):
    for t in RISK_TIERS:
        if prob_pct <= t['max']: return t
    return RISK_TIERS[-1]

def _safe_float(v, default=0.0):
    try:
        if v in (None, ''):
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def display_prob_pct(prob_pct, max_pct=98.0):
    return round(min(float(prob_pct), float(max_pct)), 1)


def compute_clinical_severity_pct(p):
    """
    Rule-based clinical severity estimate (0-100) used to calibrate raw model class probability.
    This keeps binary-class confidence from being shown directly as severity.
    """
    score = 12.0
    age = _safe_float(p.get('age'), 55)
    cp = int(_safe_float(p.get('cp'), 2))
    bp = _safe_float(p.get('trestbps'), 130)
    chol = _safe_float(p.get('chol'), 220)
    exang = int(_safe_float(p.get('exang'), 0))
    oldpeak = _safe_float(p.get('oldpeak'), 0.0)
    ca = int(_safe_float(p.get('ca'), 0))
    thal = int(_safe_float(p.get('thal'), 1))
    ef = _safe_float(p.get('ejection_fraction'), 55)
    bnp = _safe_float(p.get('bnp'), 80)
    troponin = _safe_float(p.get('troponin'), 0.02)
    creatinine = _safe_float(p.get('creatinine'), 1.0)
    diabetes = int(_safe_float(p.get('diabetes'), 0))
    smoking = int(_safe_float(p.get('smoking'), 0))
    fbs = int(_safe_float(p.get('fbs'), 0))

    if age >= 65:
        score += 10
    elif age >= 55:
        score += 6
    elif age >= 45:
        score += 3

    if cp == 0:
        score += 8
    elif cp == 1:
        score += 5
    elif cp == 2:
        score += 2
    elif cp == 3:
        score += 4

    if bp >= 170:
        score += 9
    elif bp >= 150:
        score += 6
    elif bp >= 140:
        score += 4
    elif bp >= 130:
        score += 2

    if chol >= 280:
        score += 6
    elif chol >= 240:
        score += 4
    elif chol >= 200:
        score += 2

    if exang == 1:
        score += 8
    if oldpeak >= 3.0:
        score += 12
    elif oldpeak >= 2.0:
        score += 8
    elif oldpeak >= 1.0:
        score += 4

    if ca >= 2:
        score += 18
    elif ca == 1:
        score += 8

    if thal == 3:
        score += 8
    elif thal == 2:
        score += 3

    if ef < 35:
        score += 20
    elif ef < 45:
        score += 14
    elif ef < 55:
        score += 7

    if bnp >= 900:
        score += 16
    elif bnp >= 400:
        score += 10
    elif bnp >= 200:
        score += 5
    elif bnp >= 100:
        score += 2

    if troponin >= 0.5:
        score += 22
    elif troponin >= 0.1:
        score += 12
    elif troponin >= 0.04:
        score += 4

    if creatinine >= 2.5:
        score += 10
    elif creatinine >= 1.8:
        score += 6
    elif creatinine >= 1.3:
        score += 3

    if diabetes == 1:
        score += 4
    if smoking == 1:
        score += 4
    if fbs == 1:
        score += 2
    return max(1.0, min(99.0, round(score, 1)))


def calibrate_master_risk(raw_model_pct, p):
    """Blend model confidence with clinical severity and enforce conservative guardrails."""
    clinical_pct = compute_clinical_severity_pct(p)
    calibrated = (0.62 * float(raw_model_pct)) + (0.38 * float(clinical_pct))

    ca = int(_safe_float(p.get('ca'), 0))
    ef = _safe_float(p.get('ejection_fraction'), 55)
    oldpeak = _safe_float(p.get('oldpeak'), 0)
    troponin = _safe_float(p.get('troponin'), 0.02)
    bnp = _safe_float(p.get('bnp'), 80)
    creatinine = _safe_float(p.get('creatinine'), 1.0)

    severe_organ_stress = (ef < 40) or (troponin >= 0.5) or (bnp >= 900) or (creatinine >= 2.5)
    severe_ischemia = (ca >= 2) or (oldpeak >= 3.0)
    if not severe_organ_stress and not severe_ischemia:
        calibrated = min(calibrated, 82.0)
    if ca <= 1 and ef >= 45 and oldpeak < 2.0 and troponin <= 0.05 and bnp < 250 and creatinine < 1.8:
        calibrated = min(calibrated, 68.0)

    return round(max(1.0, min(99.0, calibrated)), 1), round(clinical_pct, 1)


def _marker_is_supportive(marker, p):
    val = _safe_float(p.get(marker), 0)
    if marker == 'cp':
        return int(val) in (0, 1, 3)
    if marker == 'trestbps':
        return val >= 140
    if marker == 'chol':
        return val >= 200
    if marker == 'fbs':
        return int(val) == 1
    if marker == 'restecg':
        return int(val) in (1, 2)
    if marker == 'thalach':
        return val < 130
    if marker == 'exang':
        return int(val) == 1
    if marker == 'oldpeak':
        return val >= 1.0
    if marker == 'ca':
        return val >= 1
    if marker == 'thal':
        return int(val) in (2, 3)
    if marker == 'bmi':
        return val >= 30
    if marker == 'smoking':
        return int(val) == 1
    if marker == 'diabetes':
        return int(val) == 1
    if marker == 'family_history':
        return int(val) == 1
    if marker == 'creatinine':
        return val >= 1.3
    if marker == 'bnp':
        return val >= 100
    if marker == 'troponin':
        return val >= 0.04
    if marker == 'ejection_fraction':
        return val < 55
    return False


def build_primary_condition_summary(diseases, p):
    if not diseases:
        return None
    top = diseases[0]
    second = diseases[1] if len(diseases) > 1 else None
    prob = float(top.get('probability', 0))
    prob_display = display_prob_pct(prob)
    if prob >= 85:
        confidence = 'Critical'
    elif prob >= 71:
        confidence = 'High'
    elif prob >= 41:
        confidence = 'Moderate'
    else:
        confidence = 'Low'

    markers = top.get('key_markers') or []
    reasons = ["Highest model probability across detected conditions."]
    if markers:
        reasons.append(f"Supported by key markers: {', '.join(markers[:3])}.")
    risk_factors = []
    if int(_safe_float(p.get('diabetes'), 0)) == 1:
        risk_factors.append('diabetes')
    if int(_safe_float(p.get('smoking'), 0)) == 1:
        risk_factors.append('smoking')
    if _safe_float(p.get('trestbps'), 120) >= 140:
        risk_factors.append('hypertension')
    if int(_safe_float(p.get('ca'), 0)) >= 1:
        risk_factors.append('vessel involvement')
    if risk_factors:
        reasons.append(f"Risk profile includes: {', '.join(risk_factors)}.")

    summary = (
        f"{top.get('name', 'Primary condition')} ({prob_display:.1f}% probability) is the most likely primary condition "
        f"based on this model run and clinical marker pattern."
    )
    co_primary = False
    secondary = None
    if second is not None:
        second_prob = display_prob_pct(float(second.get('probability', 0)))
        delta = abs(prob_display - second_prob)
        co_primary = delta <= 5.0
        secondary = {
            'id': second.get('id'),
            'name': second.get('name'),
            'icd': second.get('icd'),
            'probability': second_prob,
            'delta_from_primary': round(delta, 1),
            'co_primary': co_primary,
        }

    # Acute ischemic overlap signal when both CAD and MI are strongly elevated.
    by_id = {str(d.get('id')): float(d.get('probability', 0)) for d in diseases}
    acs_overlap = (by_id.get('cad', 0.0) >= 70.0 and by_id.get('mi', 0.0) >= 70.0)
    acs_note = None
    if acs_overlap:
        acs_note = (
            f"CAD ({display_prob_pct(by_id.get('cad', 0.0)):.1f}%) and MI "
            f"({display_prob_pct(by_id.get('mi', 0.0)):.1f}%) are both high; treat as acute coronary syndrome overlap."
        )

    return {
        'id': top.get('id'),
        'name': top.get('name'),
        'icd': top.get('icd'),
        'probability': prob_display,
        'confidence': confidence,
        'co_primary': co_primary,
        'secondary_condition': secondary,
        'acs_overlap': acs_overlap,
        'acs_overlap_note': acs_note,
        'summary': summary,
        'reasons': reasons[:4],
        'next_steps': (top.get('treatments') or [])[:4],
    }


def build_reasoning_chain(p, probs):
    """Construct a step-by-step clinical reasoning narrative."""
    chain = []
    # Demographic
    age_risk = "elevated" if p['age'] > 65 else "moderate" if p['age'] > 55 else "baseline"
    chain.append({
        'step': 1, 'category': 'Demographic Assessment',
        'finding': f"Age {p['age']} ({CAT_VALUES['sex'][int(p['sex'])]}) — {age_risk} demographic cardiovascular risk",
        'weight': 'HIGH' if p['age'] > 65 else 'MODERATE'
    })
    # Symptom analysis
    cp_map = {0:'typical angina (highly concerning)', 1:'atypical angina', 2:'non-anginal chest pain', 3:'asymptomatic presentation'}
    chain.append({
        'step': 2, 'category': 'Symptom Analysis',
        'finding': f"Chest pain classified as: {cp_map.get(int(p['cp']),'unknown')}",
        'weight': 'CRITICAL' if p['cp']==3 else 'HIGH' if p['cp']==0 else 'MODERATE'
    })
    # Biomarkers
    if p.get('troponin',0) > 0.04:
        chain.append({'step':3, 'category':'Cardiac Biomarkers',
            'finding':f"Troponin-I elevated at {p['troponin']} ng/mL (normal <0.04) — myocardial injury marker",
            'weight':'CRITICAL' if p['troponin']>0.5 else 'HIGH'})
    if p.get('bnp',0) > 100:
        chain.append({'step':3, 'category':'Heart Failure Markers',
            'finding':f"BNP {p['bnp']} pg/mL (normal <100) — ventricular stress indicator",
            'weight':'HIGH' if p['bnp']>400 else 'MODERATE'})
    # Hemodynamics
    if p.get('trestbps',0) > 140:
        chain.append({'step':4, 'category':'Hemodynamic Assessment',
            'finding':f"Hypertension: BP {p['trestbps']} mmHg — increases cardiac afterload",
            'weight':'HIGH' if p['trestbps']>165 else 'MODERATE'})
    # ECG
    ecg_map = {0:'Normal sinus rhythm', 1:'ST-T wave abnormality (ischemic pattern)', 2:'Left ventricular hypertrophy'}
    chain.append({'step':5, 'category':'ECG Interpretation',
        'finding':ecg_map.get(int(p.get('restecg',0)), 'Normal'),
        'weight':'HIGH' if p.get('restecg')==1 else 'MODERATE' if p.get('restecg')==2 else 'LOW'})
    # Structural
    if p.get('ca',0) > 0:
        chain.append({'step':6, 'category':'Vascular Assessment',
            'finding':f"{int(p['ca'])} major vessel(s) with significant stenosis on fluoroscopy",
            'weight':'CRITICAL' if p['ca']>1 else 'HIGH'})
    if p.get('ejection_fraction',60) < 55:
        chain.append({'step':6, 'category':'Cardiac Function',
            'finding':f"Reduced ejection fraction: {p['ejection_fraction']}% (normal ≥55%)",
            'weight':'CRITICAL' if p['ejection_fraction']<40 else 'HIGH'})
    # Risk factors
    rf_list = []
    if p.get('smoking')==1: rf_list.append('active smoking')
    if p.get('diabetes')==1: rf_list.append('diabetes mellitus')
    if p.get('family_history')==1: rf_list.append('family history of CVD')
    if p.get('bmi',25) > 30: rf_list.append(f"obesity (BMI {p['bmi']})")
    if rf_list:
        chain.append({'step':7, 'category':'Modifiable Risk Factors',
            'finding':f"Identified: {', '.join(rf_list)}",
            'weight':'HIGH' if len(rf_list)>=3 else 'MODERATE'})
    # AI synthesis
    top_disease = max(probs.items(), key=lambda x: x[1] if x[0]!='master' else -1)
    chain.append({'step':8, 'category':'AI Model Synthesis',
        'finding':f"Ensemble of 4 ML models (RF+GBM+ExtraTrees+LR) converge on {probs['master']:.1f}% overall cardiovascular risk. Highest disease signal: {KB[top_disease[0]]['name']} ({top_disease[1]:.1f}%)",
        'weight':'INFO'})
    return chain

def get_recommendations(p, probs, risk_tier, master_pct=None):
    recs = []
    master = float(master_pct if master_pct is not None else probs['master'])
    if master > 75: recs.append({'priority':'URGENT','text':'🚨 Immediate cardiology referral — same-day evaluation recommended'})
    elif master > 55: recs.append({'priority':'HIGH','text':'📅 Cardiology appointment within 1 week'})
    else: recs.append({'priority':'ROUTINE','text':'📋 Schedule routine cardiac check-up'})

    if probs['mi'] > 50: recs.append({'priority':'URGENT','text':'⚡ Troponin elevation — rule out acute MI; ECG monitoring now'})
    if probs['hf'] > 55: recs.append({'priority':'HIGH','text':'💧 Signs of heart failure — echocardiogram and BNP trend recommended'})
    if probs['arr'] > 55: recs.append({'priority':'HIGH','text':'📊 Arrhythmia risk — 24h Holter ECG monitoring advised'})
    if probs['cad'] > 60: recs.append({'priority':'HIGH','text':'🔬 CAD risk elevated — stress test or coronary CT angiography'})
    if p.get('trestbps',0) > 160: recs.append({'priority':'HIGH','text':f"💊 Hypertension management — BP {p['trestbps']} mmHg requires treatment escalation"})
    if p.get('chol',0) > 240: recs.append({'priority':'MODERATE','text':f"🩺 Hypercholesterolaemia — statin therapy evaluation (chol {p['chol']} mg/dL)"})
    if p.get('smoking')==1: recs.append({'priority':'MODERATE','text':'🚭 Smoking cessation — reduces CV risk by 50% within 1 year'})
    if p.get('diabetes')==1: recs.append({'priority':'MODERATE','text':'🩸 Optimise glycaemic control — HbA1c target <7%'})
    if p.get('bmi',25) > 30: recs.append({'priority':'MODERATE','text':f"⚖️ Weight management — BMI {p['bmi']} kg/m2; target <25"})
    if p.get('ejection_fraction',60) < 50: recs.append({'priority':'HIGH','text':f"❤️ Reduced EF {p['ejection_fraction']}% — cardiac MRI + GDMT review"})
    recs.append({'priority':'ROUTINE','text':'🥗 Mediterranean diet + 150 min/week moderate aerobic activity'})
    return recs[:8]

def _safe_num(value, default=0.0):
    try:
        if value is None or value == '':
            return float(default)
        return float(value)
    except Exception:
        return float(default)

def _has_value(p, key):
    return key in p and p.get(key) not in (None, '')

def detect_extended_diseases(p):
    """Rule-based disease expansion using available + optional inputs."""
    val = lambda k, d=0.0: _safe_num(p.get(k, d), d)
    out = {}

    # 4) Valvular heart disease
    vhd = 0
    if val('restecg') in (1, 2): vhd += 25
    if val('ejection_fraction') < 50: vhd += 25
    if val('oldpeak') > 1.5: vhd += 20
    if val('exang') == 1: vhd += 15
    if val('thalach') < 110: vhd += 15
    if val('heart_murmur') == 1: vhd += 25
    out['vhd'] = min(95, vhd)

    # 5) Cardiomyopathy
    cm = 0
    if val('ejection_fraction') < 45: cm += 35
    if val('bnp') > 300: cm += 25
    if val('family_history') == 1: cm += 20
    if val('restecg') in (1, 2): cm += 10
    if val('troponin') > 0.04: cm += 10
    if val('dyspnea') == 1: cm += 10
    out['cardiomyopathy'] = min(95, cm)

    # 6) Congenital heart disease (adult suspicion only)
    chd = 0
    if val('age') < 40: chd += 20
    if val('family_history') == 1: chd += 20
    if val('restecg') in (1, 2): chd += 15
    if val('ejection_fraction') < 50: chd += 15
    if val('cyanosis') == 1: chd += 20
    if _has_value(p, 'oxygen_saturation') and val('oxygen_saturation') < 92: chd += 20
    if val('growth_delay') == 1: chd += 15
    out['chd'] = min(70, chd)

    # 7) Peripheral artery disease
    pad = 0
    if val('age') >= 55: pad += 20
    if val('smoking') == 1: pad += 20
    if val('diabetes') == 1: pad += 20
    if val('chol') > 220: pad += 20
    if val('trestbps') > 140: pad += 20
    if val('leg_pain_walking') == 1: pad += 20
    if _has_value(p, 'abi_index') and val('abi_index') < 0.9: pad += 30
    out['pad'] = min(95, pad)

    # 8) Rheumatic heart disease (very limited with current features)
    rhd = 0
    if out['vhd'] >= 50: rhd += 25
    if val('age') < 45: rhd += 20
    if val('restecg') in (1, 2): rhd += 15
    if val('strep_history') == 1: rhd += 30
    out['rheumatic_hd'] = min(65, rhd)

    # 9) Hypertensive heart disease
    hhd = 0
    if val('trestbps') >= 160: hhd += 40
    elif val('trestbps') >= 140: hhd += 25
    if val('restecg') == 2: hhd += 25
    if val('ejection_fraction') < 55: hhd += 15
    if val('bnp') > 100: hhd += 10
    out['hypertensive_hd'] = min(95, hhd)

    # 10) Infective heart disease pattern (cannot confirm without infection workup)
    inf = 0
    if val('fever') == 1: inf += 20
    if _has_value(p, 'crp') and val('crp') > 10: inf += 20
    if _has_value(p, 'esr') and val('esr') > 20: inf += 15
    if val('troponin') > 0.2: inf += 25
    if val('bnp') > 300: inf += 20
    if val('restecg') in (1, 2): inf += 15
    if val('ejection_fraction') < 45: inf += 15
    out['infective_hd'] = min(70, inf)

    # 11) Pericardial / myopericardial pattern
    peri = 0
    if val('cp') in (0, 1, 3): peri += 15
    if val('fever') == 1: peri += 20
    if _has_value(p, 'crp') and val('crp') > 10: peri += 20
    if _has_value(p, 'esr') and val('esr') > 20: peri += 15
    if val('troponin') > 0.04: peri += 15
    if val('restecg') in (1, 2): peri += 10
    out['pericardial_disease'] = min(75, peri)

    # use optional symptom signals to reinforce existing ML diseases
    if val('dyspnea') == 1:
        out['cardiomyopathy'] = min(95, out['cardiomyopathy'] + 8)
        out['hypertensive_hd'] = min(95, out['hypertensive_hd'] + 6)
    if val('edema') == 1:
        out['cardiomyopathy'] = min(95, out['cardiomyopathy'] + 6)
    if val('palpitations') == 1:
        out['vhd'] = min(95, out['vhd'] + 4)
    if val('syncope') == 1:
        out['cardiomyopathy'] = min(95, out['cardiomyopathy'] + 4)
    return out

def get_extended_recommendations(extended_probs):
    recs = []
    if extended_probs.get('vhd', 0) >= 55:
        recs.append({'priority': 'HIGH', 'text': '🫀 Suspected valvular disease pattern - perform Doppler echocardiography.'})
    if extended_probs.get('cardiomyopathy', 0) >= 55:
        recs.append({'priority': 'HIGH', 'text': '🧬 Cardiomyopathy signal - obtain detailed echo/MRI and family risk evaluation.'})
    if extended_probs.get('pad', 0) >= 55:
        recs.append({'priority': 'MODERATE', 'text': '🦵 PAD risk profile - consider ABI and lower-limb arterial Doppler.'})
    if extended_probs.get('hypertensive_hd', 0) >= 55:
        recs.append({'priority': 'HIGH', 'text': '📈 Hypertensive heart disease pattern - optimize blood pressure therapy and LVH follow-up.'})
    if extended_probs.get('infective_hd', 0) >= 45:
        recs.append({'priority': 'MODERATE', 'text': '🧪 Infective-pattern signal - correlate with fever/CRP/ESR/cultures before diagnosis.'})
    if extended_probs.get('pericardial_disease', 0) >= 45:
        recs.append({'priority': 'MODERATE', 'text': '🩺 Pericardial-inflammatory pattern - evaluate with ECG/echo and inflammatory markers.'})
    return recs

def get_input_requirements(p):
    requirements = []
    has = lambda k: _has_value(p, k)
    missing = lambda *keys: [k for k in keys if not has(k)]

    pad_missing = missing('abi_index', 'leg_pain_walking')
    if pad_missing:
        requirements.append({
            'disease': 'Peripheral Artery Disease',
            'needed_inputs': pad_missing,
            'reason': 'PAD confidence improves with ABI and claudication history.',
        })

    infective_missing = missing('fever', 'crp', 'esr')
    if infective_missing:
        requirements.append({
            'disease': 'Infective Heart Disease',
            'needed_inputs': infective_missing,
            'reason': 'Infective assessment needs inflammatory/infective evidence.',
        })

    rheumatic_missing = missing('strep_history', 'heart_murmur')
    if rheumatic_missing:
        requirements.append({
            'disease': 'Rheumatic/Valvular Heart Disease',
            'needed_inputs': rheumatic_missing,
            'reason': 'Rheumatic/valvular pattern needs strep history and murmur data.',
        })

    congenital_missing = missing('oxygen_saturation', 'cyanosis', 'growth_delay')
    if congenital_missing:
        requirements.append({
            'disease': 'Congenital Heart Disease',
            'needed_inputs': congenital_missing,
            'reason': 'Congenital screening needs oxygenation/cyanosis/growth context.',
        })

    arr_missing = missing('palpitations', 'syncope')
    if arr_missing:
        requirements.append({
            'disease': 'Arrhythmia',
            'needed_inputs': arr_missing,
            'reason': 'Rhythm risk interpretation improves with palpitation/syncope symptoms.',
        })
    return requirements

def flag_abnormals(p):
    flags = []
    checks = [
        ('trestbps', lambda v: v>160, 'Severe hypertension', 'CRITICAL'),
        ('trestbps', lambda v: v>140, 'Elevated blood pressure', 'WARNING'),
        ('chol',     lambda v: v>240, 'High cholesterol', 'WARNING'),
        ('troponin', lambda v: v>0.04,'Troponin elevated', 'CRITICAL' if p.get('troponin',0)>0.5 else 'HIGH'),
        ('bnp',      lambda v: v>400, 'BNP markedly elevated', 'HIGH'),
        ('bnp',      lambda v: v>100 and v<=400, 'BNP mildly elevated', 'WARNING'),
        ('ejection_fraction', lambda v: v<40, 'Severely reduced EF', 'CRITICAL'),
        ('ejection_fraction', lambda v: v>=40 and v<55, 'Mildly reduced EF', 'WARNING'),
        ('thalach',  lambda v: v<100, 'Very low max heart rate', 'HIGH'),
        ('creatinine',lambda v: v>2.0,'Renal impairment', 'HIGH'),
        ('oldpeak',  lambda v: v>3.0, 'Significant ST depression', 'HIGH'),
    ]
    for feat, cond, msg, sev in checks:
        if feat in p and cond(float(p[feat])):
            info = FEAT_INFO.get(feat, {})
            flags.append({'feature': info.get('label', feat), 'message': msg,
                          'value': f"{p[feat]} {info.get('unit','')}".strip(), 'severity': sev})
            break  # one flag per feature

    # Check specific flags
    for feat, cond, msg, sev in [
        ('cp',    lambda v: v==3,  'Asymptomatic chest presentation', 'HIGH'),
        ('thal',  lambda v: v==3,  'Reversible thalassemia defect', 'HIGH'),
        ('ca',    lambda v: v>0,   f"{int(p.get('ca',0))} vessel(s) occluded", 'CRITICAL' if p.get('ca',0)>1 else 'HIGH'),
        ('exang', lambda v: v==1,  'Exercise-induced angina present', 'HIGH'),
    ]:
        if feat in p and cond(float(p[feat])):
            flags.append({'feature': FEAT_INFO.get(feat,{}).get('label',feat),
                          'message': msg, 'value': CAT_VALUES.get(feat,{}).get(int(p[feat]),''),
                          'severity': sev})
    return flags

# ── Conversational AI ─────────────────────────────────────────────────────────
MEDICAL_KB = {
    r'(what is|explain|tell me about) (cad|coronary artery disease)': 
        "**Coronary Artery Disease (CAD)** occurs when plaque builds up inside the coronary arteries, narrowing them and reducing blood flow to the heart muscle. It's the most common form of heart disease. Risk factors include high cholesterol, hypertension, smoking, diabetes, and family history. Treatment may include lifestyle changes, medications (statins, beta-blockers), or procedures like angioplasty.",
    r'(what is|explain) (heart failure|hf)':
        "**Heart Failure** means the heart cannot pump blood effectively to meet the body's needs. It can affect the left side (most common), right side, or both. Symptoms include shortness of breath, fatigue, and fluid retention. The ejection fraction — the percentage of blood pumped with each beat — is a key diagnostic marker. Normal is ≥55%.",
    r'(what is|explain) (arrhythmia)':
        "**Arrhythmia** is an irregular heart rhythm caused by disruptions in the heart's electrical system. Types include atrial fibrillation, ventricular tachycardia, and bradycardia. Some are harmless; others can be life-threatening. A 24-hour Holter ECG monitor is commonly used for diagnosis.",
    r'(what is|explain) (mi|myocardial infarction|heart attack)':
        "**Myocardial Infarction (MI)**, commonly called a heart attack, occurs when blood flow to part of the heart is blocked, causing heart muscle cells to die. **Troponin** is the most sensitive blood marker. Symptoms: chest pain, shortness of breath, sweating. This is a medical emergency — call emergency services immediately.",
    r'(what does|explain) (ejection fraction|ef)':
        "**Ejection Fraction (EF)** is the percentage of blood the left ventricle pumps out with each beat. Normal: **55–70%**. Mildly reduced: 41–54%. Reduced (HFrEF): ≤40%. A low EF indicates the heart is not pumping effectively and is a key marker of heart failure severity.",
    r'(what does|explain) (troponin)':
        "**Troponin** is a protein released into the bloodstream when heart muscle is damaged. Normal levels are <0.04 ng/mL. Elevated troponin — especially troponin-I — strongly suggests myocardial injury or infarction. Serial measurements (0h, 3h, 6h) are used to confirm or rule out MI.",
    r'(what does|explain) (bnp|brain natriuretic peptide)':
        "**BNP (B-type Natriuretic Peptide)** is a hormone secreted by heart ventricles in response to pressure overload. Normal: <100 pg/mL. BNP >400 pg/mL has high sensitivity for heart failure. It's used to diagnose, monitor, and guide treatment of heart failure.",
    r'(what is|explain) (st depression|oldpeak)':
        "**ST Depression (oldpeak)** measured on ECG indicates the degree of ischemia (reduced blood supply) during exercise stress. Values >1.0 mm are mildly abnormal; >2.5 mm suggest significant ischemia and warrant urgent investigation.",
    r'risk (factor|factors)':
        "Major **cardiovascular risk factors**: 🔴 Non-modifiable: age (>55M, >65F), male sex, family history. 🟡 Modifiable: hypertension, hypercholesterolaemia, diabetes, smoking, obesity (BMI>30), physical inactivity, poor diet. Addressing modifiable factors can reduce CV risk by up to 80%.",
    r'(normal|reference) range':
        "Key **normal reference ranges**: BP <130/80 mmHg · Cholesterol <200 mg/dL · BMI 18.5–24.9 · Troponin-I <0.04 ng/mL · BNP <100 pg/mL · EF ≥55% · Resting HR 60–100 bpm · Creatinine 0.6–1.2 mg/dL",
    r'(statin|cholesterol medication)':
        "**Statins** (e.g. atorvastatin, rosuvastatin) are the cornerstone of cholesterol management. They reduce LDL by 30–55%, decrease cardiovascular events by ~25–35%, and have pleiotropic anti-inflammatory effects. Target LDL: <70 mg/dL for high-risk patients, <100 mg/dL for moderate risk.",
    r'(exercise|physical activity|lifestyle)':
        "**Exercise recommendations for heart health**: 150 min/week moderate aerobic activity (brisk walking, cycling) OR 75 min vigorous activity. Resistance training 2x/week. Regular exercise reduces BP by 5-8 mmHg, improves cholesterol, lowers heart failure risk by 35%, and reduces all-cause mortality.",
    r'(diet|nutrition|mediterranean)':
        "The **Mediterranean Diet** is the most evidence-backed diet for cardiovascular health: olive oil, fish (2x/week), nuts, legumes, whole grains, fruits, vegetables. It reduces CV events by 30%. Also limit: red meat, processed foods, sodium (<2.3g/day), refined sugars.",
    r'(ecg|ekg|electrocardiogram)':
        "An **ECG (Electrocardiogram)** records the heart's electrical activity. Key findings in CV disease: ST-segment changes (elevation = MI, depression = ischemia), T-wave inversions, QRS widening (bundle branch block), prolonged QT. The Resting ECG in this system classifies as: Normal, ST-T Abnormality, or LV Hypertrophy.",
    r'hello|hi |hey ':
        "Hello! 👋 I'm the **CardioAI Medical Assistant**. I can help you understand cardiovascular conditions, diagnostic tests, biomarkers, and treatment options. Ask me anything about the diagnosis, or type **'help'** to see example questions.",
    r'help|what can you':
        "I can answer questions about: \n• **Diseases**: CAD, Heart Failure, Arrhythmia, MI\n• **Biomarkers**: Troponin, BNP, Ejection Fraction, ST Depression\n• **Tests**: ECG, Echo, Stress Test, Angiography\n• **Treatments**: Statins, Beta-blockers, ACE inhibitors, PCI\n• **Risk Factors** and lifestyle modifications\n\nJust ask naturally — e.g. *'What is heart failure?'*",
    r'(beta.?blocker|metoprolol|carvedilol)':
        "**Beta-blockers** reduce heart rate and blood pressure by blocking adrenaline. Used in: heart failure (carvedilol, bisoprolol), post-MI, hypertension, arrhythmia. Benefits: reduce re-infarction risk by ~25%, improve survival in HF by 34% (MERIT-HF trial). Common: metoprolol, carvedilol, bisoprolol.",
    r'(ace inhibitor|arb|ramipril|lisinopril)':
        "**ACE inhibitors** (lisinopril, ramipril) block angiotensin-converting enzyme, reducing blood pressure and cardiac afterload. Essential in HFrEF (reduce mortality by 16–27%), post-MI, diabetic nephropathy. ARBs (losartan, valsartan) are used if ACE inhibitors cause cough.",
}

def chat_response(message):
    msg = message.lower().strip()
    for pattern, response in MEDICAL_KB.items():
        if re.search(pattern, msg):
            return response
    # Fallback
    if any(w in msg for w in ['diagnos','result','report','predict']):
        return "I can help interpret your diagnostic results. Your risk report includes a **risk score**, **disease-specific probabilities**, a **clinical reasoning chain**, and **recommendations**. Click through the report tabs for detailed explanations. What specific aspect would you like me to explain?"
    if any(w in msg for w in ['doctor','hospital','emergency','ambulan']):
        return "⚠️ If you're experiencing **chest pain, shortness of breath, sudden dizziness, or palpitations**, please **call emergency services immediately** (112 / 911). This AI system is a clinical decision support tool and does not replace emergency medical care."
    return f"I don't have specific information about '{message[:60]}'. Try asking about: CAD, heart failure, arrhythmia, MI, troponin, BNP, ejection fraction, statins, beta-blockers, or risk factors. Type **'help'** for a full list."

def precautions_text(message):
    msg = message.lower()
    lines = [
        "Precautions:",
        "1. Seek emergency care immediately for chest pain, severe breathlessness, fainting, or persistent palpitations.",
        "2. Continue prescribed medicines; do not stop cardiac drugs without physician advice.",
        "3. Monitor blood pressure, glucose, and symptoms daily; record sudden changes.",
        "4. Avoid smoking, excess salt, and heavy exertion until reviewed by a cardiologist.",
        "5. Schedule timely follow-up and carry prior reports/ECG results for review."
    ]
    if any(w in msg for w in ['mi', 'heart attack', 'troponin', 'chest pain']):
        lines.append("6. For possible MI symptoms, call emergency services now instead of self-transport.")
    if any(w in msg for w in ['hf', 'heart failure', 'bnp', 'edema', 'breath']):
        lines.append("6. For heart failure signs, restrict fluid/salt as advised and seek urgent care for worsening swelling or orthopnea.")
    if any(w in msg for w in ['arrhythmia', 'palpitation', 'ecg']):
        lines.append("6. Avoid stimulants (energy drinks/excess caffeine) and get ECG/Holter review if episodes recur.")
    return "\n".join(lines)

# ── ECG simulation data ───────────────────────────────────────────────────────
def simulate_ecg(patient_data, risk_pct):
    """Generate a plausible ECG-like waveform dataset for visualization."""
    np.random.seed(int(patient_data.get('age', 50)))
    t = np.linspace(0, 4, 1200)
    beats_per_sec = patient_data.get('thalach', 75) / 60 * 0.7
    signal = []
    for i, ti in enumerate(t):
        phase = (ti * beats_per_sec) % 1.0
        # PQRST waveform
        p_wave   = 0.25 * math.exp(-((phase - 0.15)**2) / 0.001)
        q_wave   = -0.15 * math.exp(-((phase - 0.28)**2) / 0.0004)
        r_wave   = 1.4  * math.exp(-((phase - 0.32)**2) / 0.0003)
        s_wave   = -0.35 * math.exp(-((phase - 0.37)**2) / 0.0004)
        t_wave   = 0.35 * math.exp(-((phase - 0.52)**2) / 0.003)
        baseline = 0.0
        if patient_data.get('restecg') == 1 and risk_pct > 50:
            baseline = -0.12 * math.sin(phase * math.pi)  # ST depression
        noise = np.random.normal(0, 0.015)
        val = p_wave + q_wave + r_wave + s_wave + t_wave + baseline + noise
        signal.append(round(val, 4))
    return signal[::4]  # downsample to 300 points

# ── Wearable data simulation ──────────────────────────────────────────────────
def simulate_wearable_trends(patient_data):
    np.random.seed(42)
    now = datetime.now()
    days = 7
    trend = []
    base_hr = patient_data.get('thalach', 72) * 0.65
    base_bp = patient_data.get('trestbps', 120)
    for d in range(days * 24):
        ts = now - timedelta(hours=(days*24 - d))
        hour = ts.hour
        diurnal = 8 * math.sin((hour - 6) * math.pi / 12)
        trend.append({
            'timestamp': ts.strftime('%m/%d %H:%M'),
            'hr': int(base_hr + diurnal + np.random.normal(0, 4)),
            'bp_sys': int(base_bp + diurnal * 0.8 + np.random.normal(0, 5)),
            'spo2': round(min(100, 96 + np.random.normal(0, 0.8)), 1),
        })
    # Return every 6h for display
    return trend[::6]

def summarize_ecg_image(file_storage):
    """Lightweight ECG image quality/waveform summary from uploaded picture."""
    raw = file_storage.read()
    if not raw:
        raise ValueError("Empty file.")
    if len(raw) > 12 * 1024 * 1024:
        raise ValueError("Image is too large. Maximum size is 12MB.")

    if Image is None:
        return {
            'status': 'limited',
            'summary': "ECG image received, but advanced image analysis is unavailable on this server.",
            'precautions': [
                "Use this as supportive information only.",
                "Confirm with a cardiologist and standard 12-lead ECG interpretation."
            ]
        }

    img = Image.open(BytesIO(raw)).convert('L')
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape
    mean_px = float(arr.mean())
    std_px = float(arr.std())
    dark_ratio = float((arr < 80).mean())
    edge_density = float((np.abs(np.diff(arr, axis=1)) > 22).mean())

    quality_flags = []
    if std_px < 20:
        quality_flags.append("Low contrast image; waveform may be faint.")
    if dark_ratio < 0.01:
        quality_flags.append("Very light tracing detected; ensure darker capture.")
    if edge_density < 0.02:
        quality_flags.append("Low waveform detail; recapture with full ECG strip in frame.")
    if edge_density > 0.22:
        quality_flags.append("High edge density; possible noise/grid dominance.")

    if edge_density < 0.03:
        rhythm_hint = "Limited visible signal pattern from this image."
    elif edge_density > 0.16:
        rhythm_hint = "Dense waveform transitions observed; verify for tachy/noisy tracing clinically."
    else:
        rhythm_hint = "Moderate repeating waveform pattern visible."

    summary = (
        f"ECG image analyzed ({w}x{h}). {rhythm_hint} "
        f"Estimated quality: {'Good' if len(quality_flags) == 0 else 'Needs review'}."
    )
    precautions = [
        "This image summary is not a definitive diagnosis.",
        "If chest pain, breathlessness, syncope, or persistent palpitations are present, seek emergency care.",
        "Confirm findings using standard ECG interpretation by a licensed clinician."
    ]
    return {
        'status': 'ok',
        'summary': summary,
        'metrics': {
            'width': w,
            'height': h,
            'mean_pixel': round(mean_px, 2),
            'contrast_std': round(std_px, 2),
            'dark_ratio': round(dark_ratio, 4),
            'edge_density': round(edge_density, 4),
        },
        'quality_flags': quality_flags,
        'precautions': precautions
    }

def summarize_cardiac_image(file_storage, modality='mri'):
    """Lightweight MRI/Cath-lab image quality summary with modality-specific guidance."""
    raw = file_storage.read()
    if not raw:
        raise ValueError("Empty file.")
    if len(raw) > 15 * 1024 * 1024:
        raise ValueError("Image is too large. Maximum size is 15MB.")

    if Image is None:
        return {
            'status': 'limited',
            'modality': modality.upper(),
            'summary': f"{modality.upper()} image received, but advanced image analysis is unavailable on this server.",
            'precautions': [
                "Use this as supportive information only.",
                "Confirm with a radiologist/cardiologist report before treatment decisions."
            ]
        }

    img = Image.open(BytesIO(raw)).convert('L')
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape
    mean_px = float(arr.mean())
    std_px = float(arr.std())
    dark_ratio = float((arr < 70).mean())
    bright_ratio = float((arr > 210).mean())
    edge_density = float((np.abs(np.diff(arr, axis=1)) > 25).mean())

    quality_flags = []
    if std_px < 18:
        quality_flags.append("Low contrast; anatomical structures may be hard to interpret.")
    if dark_ratio < 0.01 and bright_ratio > 0.85:
        quality_flags.append("Overexposed image; consider recapturing with better contrast.")
    if edge_density < 0.015:
        quality_flags.append("Low structural detail detected.")

    if modality == 'mri':
        tissue_hint = "Cardiac chamber and myocardial region boundaries appear"
        if edge_density < 0.02:
            pattern_hint = "limited for robust tissue characterization."
        elif edge_density > 0.14:
            pattern_hint = "complex with high boundary transitions; review for artifacts/edema/scar on full MRI series."
        else:
            pattern_hint = "moderately defined; correlate with official MRI sequence interpretation."
        summary = (
            f"MRI image analyzed ({w}x{h}). {tissue_hint} {pattern_hint} "
            f"Quality: {'Good' if len(quality_flags) == 0 else 'Needs review'}."
        )
        precautions = [
            "Single-image MRI summary is not a definitive MRI diagnosis.",
            "Correlate with cine/late gadolinium and radiology report.",
            "Urgent cardiology review is needed for severe chest pain, hypotension, or acute dyspnea."
        ]
    else:
        vessel_hint = "Coronary contrast pattern appears"
        if edge_density < 0.02:
            pattern_hint = "faint; vessel delineation may be insufficient."
        elif edge_density > 0.16:
            pattern_hint = "dense/complex; assess for overlap/noise on full angiographic run."
        else:
            pattern_hint = "moderately visible; verify stenosis severity with full cath series."
        summary = (
            f"Cath lab image analyzed ({w}x{h}). {vessel_hint} {pattern_hint} "
            f"Quality: {'Good' if len(quality_flags) == 0 else 'Needs review'}."
        )
        precautions = [
            "Single-frame cath image summary cannot replace full angiography interpretation.",
            "Confirm stenosis/occlusion with cardiologist and complete cath-lab sequence.",
            "If ongoing ischemic chest pain, activate emergency cardiac pathway immediately."
        ]

    return {
        'status': 'ok',
        'modality': modality.upper(),
        'summary': summary,
        'metrics': {
            'width': w,
            'height': h,
            'mean_pixel': round(mean_px, 2),
            'contrast_std': round(std_px, 2),
            'dark_ratio': round(dark_ratio, 4),
            'bright_ratio': round(bright_ratio, 4),
            'edge_density': round(edge_density, 4),
        },
        'quality_flags': quality_flags,
        'precautions': precautions
    }

def generate_diagnosis(data):
    missing = [f for f in FEATURES if f not in data or data[f] == '']
    if missing:
        raise ValueError(f"Missing: {missing}")

    X = pd.DataFrame([[float(data[f]) for f in FEATURES]], columns=FEATURES)
    Xs = pd.DataFrame(scaler.transform(X), columns=FEATURES)

    try:
        probs = run_model_probs(Xs)
    except AttributeError as e:
        if 'multi_class' in str(e):
            retrain_and_reload()
            probs = run_model_probs(Xs)
        else:
            raise

    raw_master_pct = probs['master']
    master_pct, clinical_severity_pct = calibrate_master_risk(raw_master_pct, data)
    tier = get_risk_tier(master_pct)

    diseases = []
    for key in ['cad','hf','arr','mi']:
        pct = probs[key]
        kb = KB[key]
        if pct > 25:
            pct_display = display_prob_pct(pct)
            diseases.append({
                'id': key, 'name': kb['name'], 'icd': kb['icd'],
                'probability': pct_display,
                'description': kb['description'],
                'key_markers': [FEAT_INFO.get(m,{}).get('label',m) for m in kb['key_markers']],
                'treatments': kb['treatments'],
                'urgent': pct > kb['urgency_threshold'] * 100,
            })

    extended_probs = detect_extended_diseases(data)
    for key, pct in extended_probs.items():
        if pct < 35:
            continue
        kb = EXTENDED_DISEASE_KB[key]
        pct_display = display_prob_pct(pct)
        diseases.append({
            'id': key,
            'name': kb['name'],
            'icd': kb['icd'],
            'probability': pct_display,
            'description': kb['description'],
            'key_markers': [FEAT_INFO.get(m, {}).get('label', m) for m in kb['key_markers']],
            'treatments': kb['treatments'],
            'urgent': pct >= 70,
            'evidence_mode': 'rule-based-surrogate',
        })
    diseases.sort(key=lambda x: -x['probability'])
    primary_condition = build_primary_condition_summary(diseases, data)

    reasoning = build_reasoning_chain(data, probs)
    reasoning.append({
        'step': 9,
        'category': 'Risk Calibration',
        'finding': (
            f"Raw model disease probability {raw_master_pct:.1f}% calibrated with "
            f"clinical severity {clinical_severity_pct:.1f}% to final risk {master_pct:.1f}%."
        ),
        'weight': 'HIGH'
    })
    recs = get_recommendations(data, probs, tier, master_pct=master_pct)
    recs.extend(get_extended_recommendations(extended_probs))
    recs = recs[:12]
    flags = flag_abnormals(data)
    input_requirements = get_input_requirements(data)
    fi = META['feature_importances']
    contributions = {f: round(fi.get(f,0) * master_pct / 100, 3) for f in FEATURES}
    ecg = simulate_ecg(data, master_pct)
    wearable = simulate_wearable_trends(data)

    profile = {}
    for f in ['age','sex','cp','trestbps','chol','thalach','ejection_fraction','bmi','troponin','bnp']:
        info = FEAT_INFO.get(f,{})
        val = data.get(f,'')
        if info.get('cat'):
            display = CAT_VALUES.get(f,{}).get(int(float(val)), str(val))
        else:
            display = f"{val} {info.get('unit','')}".strip()
        profile[info.get('label',f)] = display

    master_threshold_pct = get_model_threshold_pct('master')
    return {
        'prediction': int(master_pct >= master_threshold_pct),
        'master_probability': master_pct,
        'raw_model_probability': raw_master_pct,
        'clinical_severity_score': clinical_severity_pct,
        'master_threshold': master_threshold_pct,
        'disease_probabilities': probs,
        'extended_disease_probabilities': extended_probs,
        'risk_tier': tier,
        'diseases': diseases,
        'primary_condition': primary_condition,
        'reasoning_chain': reasoning,
        'recommendations': recs,
        'abnormal_flags': flags,
        'input_requirements': input_requirements,
        'feature_contributions': contributions,
        'feature_importances': fi,
        'ecg_signal': ecg,
        'wearable_trend': wearable,
        'patient_profile': profile,
        'report_id': f"AGI-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        'timestamp': datetime.now().isoformat(),
    }

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/api/health')
def health():
    return cors({'status':'ok','version':'2.0-AGI','models':len(MODELS),
                 'accuracy': META['models']['master']['accuracy'],
                 'auc': META['models']['master']['auc'],
                 'timestamp': datetime.now().isoformat()})

@app.route('/api/model-info')
def model_info():
    return cors({**META, 'version':'2.0', 'algorithm':'Voting Ensemble (RF+GBM+ET+LR)',
                 'feature_count': len(FEATURES)})

@app.route('/api/eval-report')
def eval_report():
    report_path = os.path.join(DIR, 'eval_report.json')
    if not os.path.exists(report_path):
        return cors({
            'error': 'Evaluation report not found. Run backend/train_model.py to generate models/eval_report.json.'
        }, 404)
    try:
        with open(report_path) as f:
            report = json.load(f)
        return cors(report)
    except Exception as e:
        log.error("Failed to read eval report: %s", e, exc_info=True)
        return cors({'error': 'Failed to read evaluation report.'}, 500)

@app.route('/api/profiles', methods=['GET'])
def list_profiles():
    user = _current_user_optional()
    if not user:
        return cors({'error': 'Unauthorized'}, 401)
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT id, full_name, age, sex, owner_user_id, details_json, notes, created_at
               FROM profiles WHERE owner_user_id = ? ORDER BY id DESC""",
            (user.get("user_id"),),
        ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item['details'] = json.loads(item['details_json']) if item.get('details_json') else {}
            out.append(item)
        return cors(out)
    finally:
        conn.close()

@app.route('/api/profiles', methods=['POST'])
def create_profile():
    user = _current_user_optional()
    if not user:
        return cors({'error': 'Unauthorized'}, 401)
    body = request.get_json(force=True) or {}
    full_name = str(body.get('full_name', '')).strip()
    if not full_name:
        return cors({'error': 'full_name is required'}, 400)

    age = body.get('age')
    sex = body.get('sex')
    notes = str(body.get('notes', '')).strip()
    details = body.get('details') or {}
    if not isinstance(details, dict):
        return cors({'error': 'details must be an object'}, 400)
    created_at = datetime.now().isoformat()

    conn = get_db()
    try:
        owner_user_id = user.get("user_id")
        cur = conn.execute(
            """INSERT INTO profiles
               (full_name, age, sex, owner_user_id, details_json, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (full_name, age, sex, owner_user_id, json.dumps(details), notes, created_at)
        )
        conn.commit()
        profile_id = cur.lastrowid
        row = conn.execute(
            """SELECT id, full_name, age, sex, owner_user_id, details_json, notes, created_at
               FROM profiles WHERE id = ?""",
            (profile_id,)
        ).fetchone()
        item = dict(row)
        item['details'] = json.loads(item['details_json']) if item.get('details_json') else {}
        return cors(item, 201)
    finally:
        conn.close()

@app.route('/api/profiles/<int:profile_id>/diagnoses', methods=['GET', 'DELETE'])
def profile_diagnoses(profile_id):
    user = _current_user_optional()
    if not user:
        return cors({'error': 'Unauthorized'}, 401)
    conn = get_db()
    try:
        p = conn.execute(
            "SELECT id, owner_user_id FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if not p:
            return cors({'error': 'Profile not found'}, 404)
        if not _profile_is_accessible(dict(p), user):
            return cors({'error': 'Forbidden for this profile'}, 403)
        if request.method == 'DELETE':
            deleted = conn.execute("DELETE FROM diagnoses WHERE profile_id = ?", (profile_id,)).rowcount
            conn.commit()
            return cors({'deleted_count': int(deleted), 'profile_id': profile_id})
        rows = conn.execute(
            """SELECT id, profile_id, report_id, risk_level, master_probability, input_payload, result_payload, created_at
               FROM diagnoses WHERE profile_id = ? ORDER BY id DESC""",
            (profile_id,)
        ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item['input_payload'] = json.loads(item['input_payload'])
            item['result_payload'] = json.loads(item['result_payload'])
            out.append(item)
        return cors(out)
    finally:
        conn.close()

@app.route('/api/profiles/<int:profile_id>/diagnoses/<int:diagnosis_id>', methods=['DELETE'])
def delete_single_diagnosis(profile_id, diagnosis_id):
    user = _current_user_optional()
    if not user:
        return cors({'error': 'Unauthorized'}, 401)
    conn = get_db()
    try:
        p = conn.execute(
            "SELECT id, owner_user_id FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if not p:
            return cors({'error': 'Profile not found'}, 404)
        if not _profile_is_accessible(dict(p), user):
            return cors({'error': 'Forbidden for this profile'}, 403)
        d = conn.execute(
            "SELECT id FROM diagnoses WHERE id = ? AND profile_id = ?",
            (diagnosis_id, profile_id)
        ).fetchone()
        if not d:
            return cors({'error': 'Diagnosis not found for this profile'}, 404)
        conn.execute("DELETE FROM diagnoses WHERE id = ? AND profile_id = ?", (diagnosis_id, profile_id))
        conn.commit()
        return cors({'deleted_id': diagnosis_id, 'profile_id': profile_id})
    finally:
        conn.close()

@app.route('/api/profiles/<int:profile_id>/diagnose', methods=['POST'])
def diagnose_for_profile(profile_id):
    user = _current_user_optional()
    if not user:
        return cors({'error': 'Unauthorized'}, 401)
    body = request.get_json(force=True) or {}
    conn = get_db()
    try:
        p = conn.execute(
            "SELECT id, owner_user_id FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if not p:
            return cors({'error': 'Profile not found'}, 404)
        if not _profile_is_accessible(dict(p), user):
            return cors({'error': 'Forbidden for this profile'}, 403)

        report = generate_diagnosis(body)
        created_at = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO diagnoses
               (profile_id, report_id, risk_level, master_probability, input_payload, result_payload, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id,
                report['report_id'],
                report.get('risk_tier', {}).get('level', ''),
                report.get('master_probability', 0.0),
                json.dumps(body),
                json.dumps(report),
                created_at
            )
        )
        conn.commit()
        return cors(report)
    except ValueError as e:
        return cors({'error': str(e)}, 400)
    finally:
        conn.close()

@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json(force=True) or {}
        report = generate_diagnosis(data)
        return cors(report)
    except ValueError as e:
        return cors({'error': str(e)}, 400)
    except Exception as e:
        log.error(f"Predict error: {e}", exc_info=True)
        return cors({'error': str(e)}, 500)

@app.route('/api/chat', methods=['POST'])
def chat():
    body = request.get_json(force=True) or {}
    message = body.get('message','').strip()
    if not message: return cors({'error':'No message'}, 400)
    role = str(body.get('role', 'doctor')).strip().lower()
    if role not in ['doctor', 'patient']:
        role = 'doctor'
    include_precautions = bool(body.get('include_precautions', False))
    context = body.get('context') or {}
    reply = chat_response(message)
    if isinstance(context, dict):
        ctx_parts = []
        profile_name = context.get('active_profile_name')
        current = context.get('current_summary') or {}
        history = context.get('history_summary') or []
        if profile_name:
            ctx_parts.append(f"Patient: {profile_name}.")
        if current:
            risk = current.get('risk_tier', 'UNKNOWN')
            prob = current.get('master_probability', 0)
            ctx_parts.append(f"Current diagnosis risk: {prob:.1f}% ({risk}).")
            tops = current.get('top_diseases') or []
            if tops:
                top_txt = ", ".join([f"{d.get('name','Unknown')} ({float(d.get('probability',0)):.1f}%)" for d in tops[:3]])
                ctx_parts.append(f"Top disease signals: {top_txt}.")
        if history:
            latest = history[0]
            ctx_parts.append(
                f"Previous report: {latest.get('report_id','N/A')} with risk {float(latest.get('master_probability',0)):.1f}% ({latest.get('risk_level','UNKNOWN')})."
            )
        if ctx_parts:
            reply = f"{reply}\n\nClinical context:\n" + " ".join(ctx_parts)

    if role == 'patient':
        reply = (
            "Patient-friendly response:\n"
            f"{reply}\n\n"
            "Simple care reminders:\n"
            "1. Follow medicines exactly as prescribed.\n"
            "2. Track symptoms daily and do not ignore worsening chest pain or breathlessness.\n"
            "3. Keep your follow-up appointment and share your latest report."
        )
    if include_precautions:
        reply = f"{reply}\n\n{precautions_text(message)}"
    return cors({'reply': reply, 'timestamp': datetime.now().isoformat(), 'role': role})

@app.route('/api/sample-cases')
def samples():
    return cors([
        {'name':'🔵 Default — Starter Profile', **DEFAULT_PATIENT},
        {'name':'🔴 Critical — Acute MI Suspect', 'age':68,'sex':1,'cp':3,'trestbps':168,'chol':295,'fbs':1,'restecg':1,'thalach':98,'exang':1,'oldpeak':4.2,'slope':2,'ca':3,'thal':3,'bmi':31.2,'smoking':1,'diabetes':1,'family_history':1,'creatinine':1.4,'bnp':620,'troponin':1.2,'ejection_fraction':32},
        {'name':'🟢 Minimal — Healthy Adult',    'age':38,'sex':0,'cp':1,'trestbps':112,'chol':178,'fbs':0,'restecg':0,'thalach':172,'exang':0,'oldpeak':0.1,'slope':0,'ca':0,'thal':1,'bmi':22.4,'smoking':0,'diabetes':0,'family_history':0,'creatinine':0.8,'bnp':45,'troponin':0.01,'ejection_fraction':68},
        {'name':'🟡 Moderate — Hypertensive Male','age':56,'sex':1,'cp':2,'trestbps':148,'chol':252,'fbs':0,'restecg':1,'thalach':135,'exang':1,'oldpeak':2.1,'slope':1,'ca':1,'thal':2,'bmi':28.8,'smoking':1,'diabetes':0,'family_history':1,'creatinine':1.1,'bnp':185,'troponin':0.06,'ejection_fraction':50},
        {'name':'🟠 High — HF with Low EF',      'age':72,'sex':0,'cp':2,'trestbps':155,'chol':218,'fbs':1,'restecg':1,'thalach':108,'exang':0,'oldpeak':1.5,'slope':1,'ca':1,'thal':1,'bmi':33.1,'smoking':0,'diabetes':1,'family_history':1,'creatinine':1.8,'bnp':850,'troponin':0.08,'ejection_fraction':38},
    ])

@app.route('/api/default-patient')
def default_patient():
    return cors(DEFAULT_PATIENT)

@app.route('/api/ecg-realtime')
def ecg_realtime():
    """Stream a synthetic ECG beat."""
    age = int(request.args.get('age', 55))
    hr  = int(request.args.get('hr', 72))
    data = {'age': age, 'thalach': hr, 'restecg': int(request.args.get('restecg',0))}
    signal = simulate_ecg(data, 40)
    return cors({'signal': signal, 'hr': hr, 'sample_rate': 300})

@app.route('/api/ecg-image-summary', methods=['POST'])
def ecg_image_summary():
    try:
        if 'ecg_image' not in request.files:
            return cors({'error': "Missing file field 'ecg_image'."}, 400)
        file_storage = request.files['ecg_image']
        if not file_storage or not file_storage.filename:
            return cors({'error': 'No ECG image selected.'}, 400)
        out = summarize_ecg_image(file_storage)
        out['timestamp'] = datetime.now().isoformat()
        return cors(out)
    except ValueError as e:
        return cors({'error': str(e)}, 400)
    except Exception as e:
        log.error(f"ECG image summary error: {e}", exc_info=True)
        return cors({'error': str(e)}, 500)

@app.route('/api/mri-image-summary', methods=['POST'])
def mri_image_summary():
    try:
        if 'mri_image' not in request.files:
            return cors({'error': "Missing file field 'mri_image'."}, 400)
        file_storage = request.files['mri_image']
        if not file_storage or not file_storage.filename:
            return cors({'error': 'No MRI image selected.'}, 400)
        out = summarize_cardiac_image(file_storage, modality='mri')
        out['timestamp'] = datetime.now().isoformat()
        return cors(out)
    except ValueError as e:
        return cors({'error': str(e)}, 400)
    except Exception as e:
        log.error(f"MRI image summary error: {e}", exc_info=True)
        return cors({'error': str(e)}, 500)

@app.route('/api/cathlab-image-summary', methods=['POST'])
def cathlab_image_summary():
    try:
        if 'cathlab_image' not in request.files:
            return cors({'error': "Missing file field 'cathlab_image'."}, 400)
        file_storage = request.files['cathlab_image']
        if not file_storage or not file_storage.filename:
            return cors({'error': 'No Cath Lab image selected.'}, 400)
        out = summarize_cardiac_image(file_storage, modality='cathlab')
        out['timestamp'] = datetime.now().isoformat()
        return cors(out)
    except ValueError as e:
        return cors({'error': str(e)}, 400)
    except Exception as e:
        log.error(f"Cath Lab image summary error: {e}", exc_info=True)
        return cors({'error': str(e)}, 500)

if __name__ == '__main__':
    host = os.getenv('AGI_BACKEND_HOST', '127.0.0.1')
    port = int(os.getenv('AGI_BACKEND_PORT', '5000'))
    print(f"🚀 AGI Cardiovascular API on http://{host}:{port}")
    app.run(debug=False, host=host, port=port)
