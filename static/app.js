const state = {
  mode: 'live',
  stream: null,
  screening: false,
  intervalId: null,
  lastResult: null,
};

const els = {
  modeCards: document.querySelectorAll('.mode-card'),
  viewerTitle: document.getElementById('viewerTitle'),
  cameraStatus: document.getElementById('cameraStatus'),
  poseStatus: document.getElementById('poseStatus'),
  cameraVideo: document.getElementById('cameraVideo'),
  analysisCanvas: document.getElementById('analysisCanvas'),
  liveWrap: document.getElementById('liveWrap'),
  photoWrap: document.getElementById('photoWrap'),
  videoWrap: document.getElementById('videoWrap'),
  photoInput: document.getElementById('photoInput'),
  videoInput: document.getElementById('videoInput'),
  photoPreview: document.getElementById('photoPreview'),
  videoPreview: document.getElementById('videoPreview'),
  photoAnalyzeBtn: document.getElementById('photoAnalyzeBtn'),
  videoAnalyzeBtn: document.getElementById('videoAnalyzeBtn'),
  startCameraBtn: document.getElementById('startCameraBtn'),
  startScreeningBtn: document.getElementById('startScreeningBtn'),
  stopScreeningBtn: document.getElementById('stopScreeningBtn'),
  statusText: document.getElementById('statusText'),
  leftKneeValue: document.getElementById('leftKneeValue'),
  rightKneeValue: document.getElementById('rightKneeValue'),
  symmetryValue: document.getElementById('symmetryValue'),
  movementValue: document.getElementById('movementValue'),
  symmetryLabel: document.getElementById('symmetryLabel'),
  symmetryBar: document.getElementById('symmetryBar'),
  riskLevel: document.getElementById('riskLevel'),
  riskMarkers: document.getElementById('riskMarkers'),
  riskRegion: document.getElementById('riskRegion'),
  analysisTitle: document.getElementById('analysisTitle'),
  patientForm: document.getElementById('patientForm'),
  patientId: document.getElementById('patientId'),
  patientName: document.getElementById('patientName'),
  patientAge: document.getElementById('patientAge'),
  patientSex: document.getElementById('patientSex'),
  patientDistrict: document.getElementById('patientDistrict'),
  patientState: document.getElementById('patientState'),
  patientOccupation: document.getElementById('patientOccupation'),
  patientLocation: document.getElementById('patientLocation'),
  patientHeight: document.getElementById('patientHeight'),
  patientWeight: document.getElementById('patientWeight'),
  patientBMI: document.getElementById('patientBMI'),
  patientHistory: document.getElementById('patientHistory'),
  loadPatientBtn: document.getElementById('loadPatientBtn'),
  totalPatients: document.getElementById('totalPatients'),
  totalScreenings: document.getElementById('totalScreenings'),
  todayScreenings: document.getElementById('todayScreenings'),
  pendingSync: document.getElementById('pendingSync'),
  lowRisk: document.getElementById('lowRisk'),
  moderateRisk: document.getElementById('moderateRisk'),
  highRisk: document.getElementById('highRisk'),
  syncedRecords: document.getElementById('syncedRecords'),
  saveRecordBtn: document.getElementById('saveRecordBtn'),
};

function setStatus(text) {
  els.statusText.textContent = text;
}

function setMode(mode) {
  state.mode = mode;
  state.screening = false;
  if (state.intervalId) {
    clearInterval(state.intervalId);
    state.intervalId = null;
  }

  els.modeCards.forEach((card) => card.classList.toggle('active', card.dataset.mode === mode));
  els.liveWrap.classList.toggle('hidden', mode !== 'live');
  els.photoWrap.classList.toggle('hidden', mode !== 'photo');
  els.videoWrap.classList.toggle('hidden', mode !== 'video');

  if (mode === 'live') {
    els.viewerTitle.textContent = 'Live Camera Preview';
    els.analysisTitle.textContent = 'Live Analysis';
    els.cameraStatus.textContent = '● Camera Connected';
    els.poseStatus.textContent = '● Pose Detection Active';
    setStatus('Press Start Camera, then Start Screening for real-time analysis.');
  } else if (mode === 'photo') {
    els.viewerTitle.textContent = 'Photo Preview';
    els.analysisTitle.textContent = 'Photo Analysis';
    els.cameraStatus.textContent = '● Photo Ready';
    els.poseStatus.textContent = '● Static Pose Analysis';
    setStatus('Choose a clear knee/leg photo and click Analyze.');
  } else {
    els.viewerTitle.textContent = 'Video Preview';
    els.analysisTitle.textContent = 'Video Analysis';
    els.cameraStatus.textContent = '● Video Ready';
    els.poseStatus.textContent = '● Movement Tracking';
    setStatus('Choose a walking video and click Analyze.');
  }
}

function resetMetrics() {
  els.leftKneeValue.textContent = '--';
  els.rightKneeValue.textContent = '--';
  els.symmetryValue.textContent = '--';
  els.movementValue.textContent = '--';
  els.symmetryLabel.textContent = '--';
  els.symmetryBar.style.width = '0%';
  els.riskLevel.textContent = 'LOW RISK';
  els.riskMarkers.textContent = 'Possible markers: none detected';
  els.riskRegion.textContent = 'Possible region: insufficient data';
}

function updateUI(result) {
  state.lastResult = result;
  const left = result.left_knee_angle ?? 0;
  const right = result.right_knee_angle ?? 0;
  const symmetry = result.symmetry_pct ?? 0;
  const movement = result.movement_status || 'Normal';
  const risk = result.risk_level || 'LOW';

  els.leftKneeValue.textContent = `${left.toFixed(1)}°`;
  els.rightKneeValue.textContent = `${right.toFixed(1)}°`;
  els.symmetryValue.textContent = `${symmetry.toFixed(1)}%`;
  els.movementValue.textContent = movement;
  els.symmetryLabel.textContent = `${symmetry.toFixed(1)}%`;
  els.symmetryBar.style.width = `${Math.max(0, Math.min(100, symmetry))}%`;
  els.riskLevel.textContent = `${risk} RISK`;
  els.riskMarkers.textContent = `Possible markers: ${(result.possible_markers || []).join(', ') || 'none detected'}`;
  els.riskRegion.textContent = `Possible region: ${result.possible_region || 'insufficient data'}`;

  if (result.annotated_image_base64 && state.mode === 'live') {
    drawAnnotatedFrame(result.annotated_image_base64);
  }
}

function drawAnnotatedFrame(base64Image) {
  const overlay = els.analysisCanvas;
  const ctx = overlay.getContext('2d');
  const image = new Image();
  image.onload = () => {
    const width = els.cameraVideo.videoWidth || image.width || 640;
    const height = els.cameraVideo.videoHeight || image.height || 480;
    if (overlay.width !== width) overlay.width = width;
    if (overlay.height !== height) overlay.height = height;
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    ctx.drawImage(image, 0, 0, overlay.width, overlay.height);
  };
  image.src = `data:image/jpeg;base64,${base64Image}`;
}

async function startCamera() {
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
    els.cameraVideo.srcObject = state.stream;
    await els.cameraVideo.play();
    requestAnimationFrame(() => {
      const width = els.cameraVideo.videoWidth || 640;
      const height = els.cameraVideo.videoHeight || 480;
      els.analysisCanvas.width = width;
      els.analysisCanvas.height = height;
      els.analysisCanvas.getContext('2d').clearRect(0, 0, width, height);
    });
    setStatus('Camera connected. Press Start Screening to begin analysis.');
  } catch (error) {
    setStatus(`Camera error: ${error.message}`);
    els.cameraStatus.textContent = '● Camera Error';
  }
}

async function captureFrameForAnalysis() {
  if (!state.stream || !els.cameraVideo.videoWidth) return;

  const canvas = document.createElement('canvas');
  const width = els.cameraVideo.videoWidth;
  const height = els.cameraVideo.videoHeight;
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(els.cameraVideo, 0, 0, width, height);

  canvas.toBlob(async (blob) => {
    if (!blob) return;
    const formData = new FormData();
    formData.append('frame', blob, 'frame.jpg');
    try {
      const response = await fetch('/api/analyze-frame', { method: 'POST', body: formData });
      const payload = await response.json();
      if (!payload.success) {
        setStatus(payload.message || 'Frame analysis failed');
        return;
      }
      const result = payload.result;
      if (result.valid) {
        updateUI(result);
        if (result.annotated_image_base64) drawAnnotatedFrame(result.annotated_image_base64);
        els.cameraStatus.textContent = '● Camera Connected';
        els.poseStatus.textContent = '● Pose Detection Active';
        setStatus(result.status);
      } else {
        setStatus(result.status);
        els.riskMarkers.textContent = result.status;
      }
    } catch (error) {
      setStatus(`Analysis error: ${error.message}`);
    }
  }, 'image/jpeg', 0.92);
}

function startScreening() {
  if (state.mode !== 'live') {
    setStatus('Switch to Live Camera mode first.');
    return;
  }
  if (!state.stream) {
    setStatus('Start Camera first.');
    return;
  }
  state.screening = true;
  if (state.intervalId) clearInterval(state.intervalId);
  state.intervalId = setInterval(captureFrameForAnalysis, 500);
  setStatus('Screening active. Collecting movement data from real webcam frames.');
}

function stopScreening() {
  state.screening = false;
  if (state.intervalId) {
    clearInterval(state.intervalId);
    state.intervalId = null;
  }
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
    els.cameraVideo.srcObject = null;
  }
  resetMetrics();
  setStatus('Screening stopped. Ready for another analysis.');
}

async function analyzePhoto() {
  const file = els.photoInput.files[0];
  if (!file) {
    setStatus('Please choose a photo first.');
    return;
  }
  const formData = new FormData();
  formData.append('image', file);
  els.photoPreview.classList.remove('hidden');
  els.photoPreview.src = URL.createObjectURL(file);
  setStatus('Analyzing photo...');
  try {
    const response = await fetch('/api/analyze-image', { method: 'POST', body: formData });
    const payload = await response.json();
    if (!payload.success) {
      setStatus(payload.message || 'Photo analysis failed');
      return;
    }
    const result = payload.result;
    updateUI(result);
    if (result.annotated_image_base64) {
      els.photoPreview.src = `data:image/jpeg;base64,${result.annotated_image_base64}`;
    }
    els.riskLevel.textContent = `${result.risk_level} RISK`;
    setStatus(result.status);
  } catch (error) {
    setStatus(`Photo analysis error: ${error.message}`);
  }
}

async function analyzeVideo() {
  const file = els.videoInput.files[0];
  if (!file) {
    setStatus('Please choose a video first.');
    return;
  }
  const formData = new FormData();
  formData.append('video', file);
  els.videoPreview.classList.remove('hidden');
  els.videoPreview.src = URL.createObjectURL(file);
  setStatus('Analyzing video... this may take a moment.');
  try {
    const response = await fetch('/api/analyze-video', { method: 'POST', body: formData });
    const payload = await response.json();
    if (!payload.success) {
      setStatus(payload.message || 'Video analysis failed');
      return;
    }
    const result = payload.result;
    updateUI(result);
    els.riskLevel.textContent = `${result.risk_level} RISK`;
    if (result.processed_video_url) {
      els.videoPreview.src = result.processed_video_url;
    }
    setStatus(result.status);
  } catch (error) {
    setStatus(`Video analysis error: ${error.message}`);
  }
}

async function refreshDashboard() {
  try {
    const response = await fetch('/api/dashboard');
    const payload = await response.json();
    els.totalPatients.textContent = payload.totalPatients ?? 0;
    els.totalScreenings.textContent = payload.totalScreenings ?? 0;
    els.todayScreenings.textContent = payload.todayScreenings ?? 0;
    els.pendingSync.textContent = payload.pendingSync ?? 0;
    els.lowRisk.textContent = payload.lowRisk ?? 0;
    els.moderateRisk.textContent = payload.moderateRisk ?? 0;
    els.highRisk.textContent = payload.highRisk ?? 0;
    els.syncedRecords.textContent = payload.syncedRecords ?? 0;
  } catch (error) {
    setStatus('Dashboard refresh error: ' + error.message);
  }
}

async function registerPatient(event) {
  event.preventDefault();
  const payload = {
    patient_id: els.patientId.value,
    name: els.patientName.value,
    age: Number(els.patientAge.value || 0),
    sex: els.patientSex.value,
    district: els.patientDistrict.value,
    state: els.patientState.value,
    occupation: els.patientOccupation.value,
    location: els.patientLocation.value,
    height: Number(els.patientHeight.value || 0),
    weight: Number(els.patientWeight.value || 0),
    bmi: Number(els.patientBMI.value || 0),
    oa_history: els.patientHistory.value,
  };

  try {
    const response = await fetch('/api/patients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!result.success) {
      setStatus(result.message || 'Patient registration failed');
      return;
    }
    setStatus(`Patient ${result.patient.patient_id} registered successfully.`);
    els.patientId.value = result.patient.patient_id;
    await refreshDashboard();
  } catch (error) {
    setStatus('Patient registration error: ' + error.message);
  }
}

async function loadPatient() {
  const patientId = els.patientId.value.trim();
  if (!patientId) {
    setStatus('Enter a patient ID to load the record.');
    return;
  }

  try {
    const response = await fetch(`/api/patient/${encodeURIComponent(patientId)}`);
    const payload = await response.json();
    if (!payload.patient) {
      setStatus('Patient record not found');
      return;
    }
    const patient = payload.patient;
    els.patientName.value = patient.name || '';
    els.patientAge.value = patient.age || '';
    els.patientSex.value = patient.sex || '';
    els.patientDistrict.value = patient.district || '';
    els.patientState.value = patient.state || '';
    els.patientOccupation.value = patient.occupation || '';
    els.patientLocation.value = patient.location || '';
    els.patientHeight.value = patient.height || '';
    els.patientWeight.value = patient.weight || '';
    els.patientBMI.value = patient.bmi || '';
    els.patientHistory.value = patient.oa_history || '';
    setStatus(`Loaded patient record for ${patient.patient_id}.`);
  } catch (error) {
    setStatus('Load patient error: ' + error.message);
  }
}

async function saveCurrentScreeningResult() {
  const patientId = els.patientId.value.trim();
  if (!patientId) {
    setStatus('Register or load a patient before saving a screening record.');
    return;
  }

  const payload = {
    patient_id: patientId,
    pain_score: 0,
    mobility_score: 0,
    left_knee_angle: state.lastResult?.left_knee_angle ?? null,
    right_knee_angle: state.lastResult?.right_knee_angle ?? null,
    symmetry_pct: state.lastResult?.symmetry_pct ?? null,
    risk_score: state.lastResult?.risk_score ?? null,
    risk_level: state.lastResult?.risk_level ?? null,
    ai_status: state.lastResult ? 'Real pose-based screening result captured.' : 'No result available',
    notes: 'Screening saved from live camera or uploaded media.',
    movement_features: state.lastResult ? {
      left_knee_angle: state.lastResult.left_knee_angle,
      right_knee_angle: state.lastResult.right_knee_angle,
      knee_angle_range: Math.abs((state.lastResult.left_knee_angle ?? 0) - (state.lastResult.right_knee_angle ?? 0)),
      symmetry_pct: state.lastResult.symmetry_pct,
      pose_confidence: 0.9,
      valid_frames: 1,
      movement_consistency: state.lastResult.symmetry_pct ?? 0,
    } : null,
  };

  try {
    const response = await fetch('/api/screening', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!result.success) {
      setStatus(result.message || 'Save screening failed');
      return;
    }
    setStatus(`Screening ${result.screening.screening_id} saved to local database.`);
    await refreshDashboard();
  } catch (error) {
    setStatus('Save screening error: ' + error.message);
  }
}

els.modeCards.forEach((card) => card.addEventListener('click', () => setMode(card.dataset.mode)));
els.startCameraBtn.addEventListener('click', startCamera);
els.startScreeningBtn.addEventListener('click', startScreening);
els.stopScreeningBtn.addEventListener('click', stopScreening);
els.photoAnalyzeBtn.addEventListener('click', analyzePhoto);
els.videoAnalyzeBtn.addEventListener('click', analyzeVideo);
els.photoInput.addEventListener('change', () => {
  const file = els.photoInput.files[0];
  if (file) {
    els.photoPreview.classList.remove('hidden');
    els.photoPreview.src = URL.createObjectURL(file);
  }
});
els.videoInput.addEventListener('change', () => {
  const file = els.videoInput.files[0];
  if (file) {
    els.videoPreview.classList.remove('hidden');
    els.videoPreview.src = URL.createObjectURL(file);
  }
});
els.loadPatientBtn.addEventListener('click', loadPatient);
els.patientForm.addEventListener('submit', registerPatient);
els.saveRecordBtn.addEventListener('click', saveCurrentScreeningResult);

setMode('live');
resetMetrics();
refreshDashboard();
