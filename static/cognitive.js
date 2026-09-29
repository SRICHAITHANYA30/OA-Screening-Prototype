/* ========================================================================
   Smirthi – Cognitive Companion for Elders
   Complete client: Splash → Login → Main App + 12 games + Activity Feed
   ======================================================================== */
(function () {
  'use strict';

  /* =====================================================================
     HELPERS
     ===================================================================== */
  const $ = (id) => document.getElementById(id);

  function toast(message) {
    const t = $('toast');
    if (!t) return;
    t.textContent = message;
    t.classList.remove('hidden');
    t.classList.add('show');
    clearTimeout(t._tid);
    t._tid = setTimeout(() => { t.classList.add('hidden'); t.classList.remove('show'); }, 3200);
  }

  /* =====================================================================
     STATE
     ===================================================================== */
  const state = {
    lang: localStorage.getItem('smirthi_lang') || '',
    splashLang: localStorage.getItem('smirthi_splash_lang') || '',
    patientId: localStorage.getItem('smirthi_patient') || '',
    user: null,
    role: localStorage.getItem('smirthi_role') || '',
    phone: localStorage.getItem('smirthi_phone') || '',
    screen: 'splash',
    voice: localStorage.getItem('smirthi_voice') === '1' || localStorage.getItem('smirthi_voice') === null,
    largeText: localStorage.getItem('smirthi_large') === '1',
    contrast: localStorage.getItem('smirthi_contrast') === '1',
    level: Number(localStorage.getItem('smirthi_level') || 1),
    pendingSessions: JSON.parse(localStorage.getItem('smirthi_pending') || '[]'),
    currentPuzzle: null,
    currentGame: null,
    gameTimer: null,
    timerStart: 0,
    hintsUsed: 0,
    correctActions: 0,
    totalActions: 0,
    score: 0,
    activityPollTimer: null,
    matched: 0,
    flips: 0,
    lockBoard: false,
    firstCard: null,
    puzzle: null,
    seqIndex: 0,
    expectedSeq: null,
    seqShown: false,
    routinePicked: 0,
    routineCorrects: 0,
    routineWrongs: 0,
  };

  /* =====================================================================
     SPEECH
     ===================================================================== */
  function speak(text, force) {
    if (!state.voice && !force) return;
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.rate = 0.85;
    u.pitch = 1.0;
    var langMap = {
      en: 'en-IN', hi: 'hi-IN', as: 'as-IN', bn: 'bn-IN',
      mni: 'mni-IN', khasi: 'en-IN', mizo: 'en-IN'
    };
    u.lang = langMap[state.lang] || 'en-IN';
    window.speechSynthesis.speak(u);
  }

  /* =====================================================================
     BUNDLE / i18n HELPERS
     ===================================================================== */
  function b() { return window.__COG_BUNDLE || {}; }
  function uiText(key, fallback) {
    return window.__COG_BUNDLE && window.__COG_BUNDLE[key] ? window.__COG_BUNDLE[key] : (fallback || key);
  }
  function escalt(text) { return String(text).replace(/'/g, "\\'").replace(/"/g, '&quot;'); }
  function formatTime(seconds) {
    var m = Math.floor(seconds / 60), s = seconds % 60;
    return m > 0 ? m + 'm ' + s + 's' : s + 's';
  }

  /* =====================================================================
     OFFLINE / PENDING SESSIONS
     ===================================================================== */
  function savePendingSession(session) {
    state.pendingSessions.push(Object.assign({}, session, { savedAt: new Date().toISOString() }));
    localStorage.setItem('smirthi_pending', JSON.stringify(state.pendingSessions));
    var chip = $('storageChip');
    if (chip) chip.textContent = state.pendingSessions.length + ' pending';
  }

  async function syncNow() {
    if (!navigator.onLine) { toast('You are offline. Data will sync when you reconnect.'); return; }
    if (state.pendingSessions.length === 0) { toast('All data is synced. ✓'); return; }
    var pending = state.pendingSessions.slice();
    var synced = 0, failed = [];
    for (var i = 0; i < pending.length; i++) {
      try {
        var res = await fetch('/api/cognitive/session', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(pending[i]),
        });
        var p = await res.json();
        if (p.success) synced++; else failed.push(pending[i]);
      } catch (e) { failed.push(pending[i]); }
    }
    state.pendingSessions = failed;
    localStorage.setItem('smirthi_pending', JSON.stringify(state.pendingSessions));
    var chip = $('storageChip');
    if (chip) chip.textContent = state.pendingSessions.length + ' pending';
    toast(synced > 0 ? 'Synced ' + synced + ' sessions ✓' : 'Nothing synced yet.');
    if (state.patientId) refreshDashboard();
  }

  function onlineHandler() {
    var banner = $('offlineBanner');
    if (banner) banner.classList.add('hidden');
    if (state.pendingSessions.length) syncNow();
  }
  function offlineHandler() {
    var banner = $('offlineBanner');
    if (banner) banner.classList.remove('hidden');
  }
  window.addEventListener('online', onlineHandler);
  window.addEventListener('offline', offlineHandler);

  /* =====================================================================
     1. SPLASH SCREEN
     ===================================================================== */
  async function loadLanguageGrid() {
    try {
      var res = await fetch('/api/cognitive/languages');
      var payload = await res.json();
      var grid = $('languageGrid');
      if (!grid) return;
      grid.innerHTML = '';
      (payload.languages || []).forEach(function (l) {
        var card = document.createElement('button');
        card.className = 'lang-card' + (state.splashLang === l.code ? ' selected' : '');
        card.dataset.code = l.code;
        card.innerHTML = '<span class="native">' + l.name + '</span><span class="english">' + l.code.toUpperCase() + '</span>';
        card.addEventListener('click', function () {
          grid.querySelectorAll('.lang-card').forEach(function (c) { c.classList.remove('selected'); });
          card.classList.add('selected');
          state.splashLang = l.code;
        });
        grid.appendChild(card);
      });
    } catch (e) {
      console.error('loadLanguageGrid', e);
    }
  }

  function showSplash() {
    state.screen = 'splash';
    var splash = $('splashScreen');
    var login = $('loginScreen');
    var main = $('mainApp');
    if (splash) splash.classList.remove('hidden');
    if (login) login.classList.add('hidden');
    if (main) main.classList.add('hidden');
    loadLanguageGrid();
  }

  function initSplash() {
    if (state.splashLang && state.phone) {
      /* Already fully logged in — skip both splash and login */
      var splash = $('splashScreen');
      var login = $('loginScreen');
      var main = $('mainApp');
      if (splash) splash.classList.add('hidden');
      if (login) login.classList.add('hidden');
      if (main) main.classList.remove('hidden');
      state.lang = state.splashLang;
      bootMainApp();
      return;
    }
    if (state.splashLang && !state.phone) {
      /* Language chosen but not logged in — skip splash, show login */
      showLogin();
      return;
    }
    showSplash();
  }

  /* =====================================================================
     2. LOGIN SCREEN
     ===================================================================== */
  var loginRole = 'patient';

  function showLogin() {
    state.screen = 'login';
    var splash = $('splashScreen');
    var login = $('loginScreen');
    var main = $('mainApp');
    if (splash) splash.classList.add('hidden');
    if (login) login.classList.remove('hidden');
    if (main) main.classList.add('hidden');
  }

  function setupLoginTabs() {
    document.querySelectorAll('.login-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        document.querySelectorAll('.login-tab').forEach(function (t) { t.classList.remove('active'); });
        tab.classList.add('active');
        loginRole = tab.dataset.role;
        var nameWrap = $('loginNameWrap');
        if (nameWrap) nameWrap.style.display = loginRole === 'patient' ? 'none' : 'block';
      });
    });
  }

  function setupLoginSkip() {
    var skipBtn = $('loginSkipBtn');
    if (skipBtn) {
      skipBtn.addEventListener('click', function () {
        var splash = $('splashScreen');
        var login = $('loginScreen');
        var main = $('mainApp');
        if (splash) splash.classList.add('hidden');
        if (login) login.classList.add('hidden');
        if (main) main.classList.remove('hidden');
        state.lang = state.splashLang || 'en';
        bootMainApp();
      });
    }
  }

  function setupLoginSubmit() {
    var submitBtn = $('loginSubmitBtn');
    if (!submitBtn) return;
    submitBtn.addEventListener('click', async function () {
      var phone = $('loginPhone') ? $('loginPhone').value.trim() : '';
      var name = $('loginName') ? $('loginName').value.trim() : '';
      var pin = $('loginPin') ? $('loginPin').value.trim() : '';
      if (!phone) { toast('Phone number is required.'); return; }
      if (!pin || !/^\d{4,6}$/.test(pin)) {
        toast('Please set a 4–6 digit safety PIN.'); return;
      }
      /* Offline-first: verify against local credential registry when offline */
      if (!navigator.onLine) {
        try {
          var registry = JSON.parse(localStorage.getItem('smirthi_creds') || '{}');
          var cached = registry[phone];
          if (cached && String(cached.pin) === pin) {
            state.phone = phone;
            state.role = cached.role || loginRole;
            state.patientId = cached.patient_id || cached.patientId || '';
            state.user = cached;
            localStorage.setItem('smirthi_phone', phone);
            localStorage.setItem('smirthi_role', state.role);
            if (state.patientId) localStorage.setItem('smirthi_patient', state.patientId);
            state.lang = state.splashLang || 'en';
            localStorage.setItem('smirthi_lang', state.lang);
            var splash = $('splashScreen');
            var login = $('loginScreen');
            var main = $('mainApp');
            if (splash) splash.classList.add('hidden');
            if (login) login.classList.add('hidden');
            if (main) main.classList.remove('hidden');
            bootMainApp();
            toast('Signed in offline. Data will sync when you reconnect.');
            return;
          }
          toast('Incorrect PIN, or not registered on this device.');
          return;
        } catch (e) { toast('Offline verify failed.'); return; }
      }
      if (loginRole !== 'patient' && !name) {
        toast('Name is required for new registration.');
        return;
      }
      try {
        var body = { phone: phone, name: name, role: loginRole, language: state.splashLang || 'en', pin: pin };
        var res = await fetch('/api/cognitive/login', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        var payload = await res.json();
        if (payload.success) {
          var user = payload.user;
          state.phone = phone;
          state.role = user.role || loginRole;
          state.patientId = user.patient_id || '';
          state.user = user;
          localStorage.setItem('smirthi_phone', phone);
          localStorage.setItem('smirthi_role', state.role);
          if (state.patientId) localStorage.setItem('smirthi_patient', state.patientId);
          state.lang = state.splashLang || 'en';
          localStorage.setItem('smirthi_lang', state.lang);
          // Save to offline credentials registry
          var registry = JSON.parse(localStorage.getItem('smirthi_creds') || '{}');
          registry[phone] = { pin: pin, role: state.role, patient_id: state.patientId, name: user.name };
          localStorage.setItem('smirthi_creds', JSON.stringify(registry));
          var splash = $('splashScreen');
          var login = $('loginScreen');
          var main = $('mainApp');
          if (splash) splash.classList.add('hidden');
          if (login) login.classList.add('hidden');
          if (main) main.classList.remove('hidden');
          bootMainApp();
          toast('Welcome' + (user.name ? ', ' + user.name : '') + '!');
        } else {
          toast(payload.message || 'Login failed.');
        }
      } catch (e) {
        toast('Network error. Try again.');
      }
    });
  }

  function setupSplashContinue() {
    var btn = $('splashContinueBtn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      if (!state.splashLang) { toast('Please select a language.'); return; }
      localStorage.setItem('smirthi_splash_lang', state.splashLang);
      var splash = $('splashScreen');
      if (splash) splash.classList.add('hidden');
      if (state.phone) {
        var main = $('mainApp');
        if (main) main.classList.remove('hidden');
        state.lang = state.splashLang;
        bootMainApp();
      } else {
        showLogin();
      }
    });
  }

  /* =====================================================================
     3. PATIENT MANAGEMENT
     ===================================================================== */
  async function loadPatientSelector() {
    try {
      var url = '/api/cognitive/overview';
      if (state.role === 'caregiver' && state.phone) {
        url = '/api/cognitive/patients?phone=' + encodeURIComponent(state.phone);
      }
      var res = await fetch(url);
      var payload = await res.json();
      if (!payload.success) return;
      var select = $('patientSelector');
      if (!select) return;
      select.innerHTML = '<option value="">Choose Patient</option>';
      var patients = payload.patients || [];
      patients.forEach(function (p) {
        var opt = document.createElement('option');
        opt.value = p.patient_id;
        opt.textContent = p.patient_id + ' — ' + (p.name || 'Unknown');
        select.appendChild(opt);
      });
      if (state.patientId && Array.from(select.options).some(function (o) { return o.value === state.patientId; })) {
        select.value = state.patientId;
      }
    } catch (e) { console.error('load patients', e); }
  }

  async function switchPatient(patientId) {
    if (!patientId) return;
    state.patientId = patientId;
    localStorage.setItem('smirthi_patient', patientId);
    try {
      var res = await fetch('/api/cognitive/patient?patient_id=' + encodeURIComponent(patientId));
      var payload = await res.json();
      if (payload.success) {
        var p = payload.patient;
        var nameEl = $('patientNameDisplay');
        var metaEl = $('patientMeta');
        var avatarEl = $('patientAvatar');
        if (nameEl) nameEl.textContent = p.name || p.patient_id;
        if (metaEl) metaEl.textContent = (p.age || '?') + ' yrs • ' + (p.district || '') + ' ' + (p.state || '') + ' • ' + (p.language || 'en').toUpperCase();
        if (avatarEl) avatarEl.textContent = p.sex === 'Female' ? '👵' : p.sex === 'Male' ? '👴' : '🧓';
        if (p.language) {
          state.lang = p.language;
          localStorage.setItem('smirthi_lang', p.language);
          var langSel = $('languageSelect');
          if (langSel) langSel.value = p.language;
        }
        await loadContent();
        refreshDashboard();
        refreshReminders();
        refreshCaregiver();
        speak('Welcome ' + (p.name || '') + "! Let's play a game today.");
      }
    } catch (e) { console.error('switch patient', e); }
  }

  /* =====================================================================
     4. CONTENT / TRANSLATIONS
     ===================================================================== */
  async function loadContent() {
    try {
      var res = await fetch('/api/cognitive/content?lang=' + state.lang);
      var payload = await res.json();
      window.__COG_BUNDLE = payload.bundle;
      applyBundle(payload.bundle);
    } catch (e) { console.error('content', e); }
  }

  function applyBundle(bund) {
    if (!bund) return;
    document.documentElement.lang = state.lang;
    var appEl = $('appName');
    var tagEl = $('tagline');
    var titleEl = $('gamesTitle');
    if (appEl) appEl.textContent = bund.app_name || 'Smirthi';
    if (tagEl) tagEl.textContent = bund.tagline || '';
    if (titleEl) titleEl.textContent = bund.pick_game || 'Pick a game';
    renderGameGrid();
  }

  /* =====================================================================
     5. TABS
     ===================================================================== */
  function activateTab(tabName) {
    document.querySelectorAll('.tab').forEach(function (t) { t.classList.toggle('active', t.dataset.tab === tabName); });
    document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.toggle('active', p.id === 'tab-' + tabName); });
    if (tabName === 'progress' && state.patientId) refreshDashboard();
    if (tabName === 'reminders' && state.patientId) refreshReminders();
    if (tabName === 'caregiver' && state.patientId) { refreshCaregiver(); startActivityFeedPoll(); }
    if (tabName !== 'caregiver') stopActivityFeedPoll();
  }

  /* =====================================================================
     6. ACTIVITY FEED (caregiver tab – polls every 5 s)
     ===================================================================== */
  function startActivityFeedPoll() {
    stopActivityFeedPoll();
    fetchActivityFeed();
    state.activityPollTimer = setInterval(fetchActivityFeed, 5000);
  }

  function stopActivityFeedPoll() {
    if (state.activityPollTimer) { clearInterval(state.activityPollTimer); state.activityPollTimer = null; }
  }

  async function fetchActivityFeed() {
    if (!state.patientId) return;
    try {
      var res = await fetch('/api/cognitive/activity-feed?patient_id=' + encodeURIComponent(state.patientId) + '&limit=15');
      var payload = await res.json();
      if (!payload.success) return;
      renderActivityFeed(payload.feed || []);
    } catch (e) { /* silent */ }
  }

  function renderActivityFeed(feed) {
    var el = $('activityFeed');
    if (!el) return;
    if (!feed.length) { el.innerHTML = '<div class="activity-empty">No recent activity.</div>'; return; }
    el.innerHTML = feed.map(function (f) {
      var icon = iconForGame(f.game_type) || '🎮';
      var label = f.game_type ? f.game_type.replace(/_/g, ' ') : 'Activity';
      var time = f.timestamp || f.activity_date || '';
      if (time.length > 16) time = time.slice(0, 16).replace('T', ' ');
      var detail = '';
      if (f.score != null) detail += 'Score: ' + f.score;
      if (f.accuracy_pct != null) detail += ' • Acc: ' + f.accuracy_pct + '%';
      if (f.mood) detail += ' • Mood: ' + f.mood;
      return '<div class="activity-item"><span class="act-icon">' + icon + '</span>' +
        '<div class="act-body"><strong>' + label + '</strong>' +
        '<small>' + (detail || 'Activity recorded') + '</small><br><small>' + time + '</small></div></div>';
    }).join('');
  }

  /* =====================================================================
     7. PDF DOWNLOAD
     ===================================================================== */
  function setupPdfDownload() {
    var btn = $('downloadPdfBtn');
    if (!btn) return;
    btn.addEventListener('click', async function () {
      if (!state.patientId) { toast('Select a patient first.'); return; }
      try {
        btn.disabled = true;
        btn.textContent = '⏳ Generating…';
        var res = await fetch('/api/cognitive/report/pdf?patient_id=' + encodeURIComponent(state.patientId));
        var payload = await res.json();
        if (payload.success && payload.download_url) {
          window.open(payload.download_url, '_blank');
          toast('Report generated ✓');
        } else {
          toast(payload.message || 'Could not generate report.');
        }
      } catch (e) {
        toast('Network error.');
      } finally {
        btn.disabled = false;
        btn.textContent = '📄 Download PDF Report';
      }
    });
  }

  /* =====================================================================
     8. GAME RENDERING – GRID
     ===================================================================== */
  function renderGameGrid() {
    var grid = $('gameGrid');
    if (!grid) return;
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types || {};
    var games = [
      { id: 'memory_match', icon: '🃏', cls: 'memory' },
      { id: 'sequence_memory', icon: '📝', cls: 'recall' },
      { id: 'pattern_recognition', icon: '🔮', cls: 'attention' },
      { id: 'daily_routine', icon: '🗓️', cls: 'recall' },
      { id: 'object_recognition', icon: '🔍', cls: 'recognition' },
      { id: 'color_sort', icon: '🎨', cls: 'attention' },
      { id: 'number_sequence', icon: '🔢', cls: 'memory' },
      { id: 'face_name_match', icon: '👤', cls: 'recognition' },
      { id: 'shopping_list', icon: '🛒', cls: 'memory' },
      { id: 'clock_reading', icon: '🕐', cls: 'attention' },
      { id: 'emotion_recognition', icon: '😊', cls: 'recognition' },
      { id: 'word_association', icon: '🔗', cls: 'recall' },
    ];
    grid.innerHTML = '';
    games.forEach(function (g) {
      var info = meta[g.id] || { title: g.id, desc: '' };
      var card = document.createElement('button');
      card.className = 'game-card ' + g.cls;
      card.innerHTML =
        '<span class="game-icon">' + g.icon + '</span>' +
        '<strong class="game-name">' + (info.title || '') + '</strong>' +
        '<small class="game-desc">' + (info.desc || '') + '</small>' +
        '<span class="game-begin">▶ ' + (bundle.begin || 'Begin') + '</span>';
      card.addEventListener('click', function () { startGame(g.id); });
      grid.appendChild(card);
    });
  }

  /* =====================================================================
     9. GAME PLAY – START / HEADER / RESULT / CONTROLS
     ===================================================================== */
  async function startGame(gameType) {
    if (!state.patientId) { toast('Please select a patient first.'); return; }
    document.querySelectorAll('#gameGrid .game-card').forEach(function (c) { c.style.pointerEvents = 'none'; });
    var grid = $('gameGrid');
    if (grid) grid.classList.add('hidden');
    var area = $('gameArea');
    if (!area) return;
    area.classList.remove('hidden');
    area.innerHTML = '<div class="loading">Loading game… 🎲</div>';
    try {
      var res = await fetch('/api/cognitive/game/new?game_type=' + gameType + '&lang=' + state.lang + '&level=' + state.level);
      var payload = await res.json();
      if (!payload.success) { area.innerHTML = '<div class="loading">' + (payload.message || 'Error') + '</div>'; return; }
      state.currentPuzzle = payload.puzzle;
      state.currentGame = gameType;
      state.hintsUsed = 0;
      state.correctActions = 0;
      state.totalActions = 0;
      state.timerStart = Date.now();
      var renderers = {
        memory_match: renderMemoryMatch,
        sequence_memory: renderSequenceMemory,
        pattern_recognition: renderPatternRecognition,
        daily_routine: renderDailyRoutine,
        object_recognition: renderObjectRecognition,
        color_sort: renderColorSort,
        number_sequence: renderNumberSequence,
        face_name_match: renderFaceNameMatch,
        shopping_list: renderShoppingList,
        clock_reading: renderClockReading,
        emotion_recognition: renderEmotionRecognition,
        word_association: renderWordAssociation,
      };
      if (renderers[gameType]) {
        renderers[gameType](payload.puzzle);
      } else {
        area.innerHTML = '<div class="loading">Unknown game type.</div>';
      }
      if (state.voice) {
        var meta = (window.__COG_BUNDLE && window.__COG_BUNDLE.game_types || {})[gameType];
        speak(meta && meta.desc ? meta.desc : "Let's play a game!");
      }
    } catch (e) {
      area.innerHTML = '<div class="loading">Could not load game. ' + e.message + '</div>';
    }
  }

  function gameHeader(title, subtitle) {
    subtitle = subtitle || '';
    return '<div class="game-header card"><div><h2>' + title + '</h2><p>' + subtitle + '</p></div>' +
      '<div class="game-controls"><span class="chip">🎯 ' + uiText('score', 'Score') + ': <strong id="gScore">0</strong></span>' +
      '<span class="chip">📶 Lv: <strong id="gLevel">' + state.level + '</strong></span>' +
      '<button class="btn ghost" onclick="window._smirthi.endGame(true)">Exit</button></div></div>';
  }

  function gameResultHtml(bundle, coinsEarned) {
    coinsEarned = coinsEarned || 0;
    var acc = state.totalActions ? Math.round((state.correctActions / state.totalActions) * 100) : 0;
    var time = Math.round((Date.now() - state.timerStart) / 1000);
    var score = Math.round(state.score * state.level);
    var congrats = bundle.congrats || 'Congratulations!';
    return '<div class="game-result card"><div class="result-big">🎉</div><h2>' + congrats + '</h2>' +
      '<p>' + (bundle.score || 'Score') + ': <strong>' + score + '</strong> &nbsp;•&nbsp; ' + (bundle.level || 'Level') + ': <strong>' + state.level + '</strong></p>' +
      '<p>Accuracy: <strong>' + acc + '%</strong> &nbsp;•&nbsp; Time: <strong>' + formatTime(time) + '</strong></p>' +
      '<p>Coins Earned: <strong>' + coinsEarned + ' 🪙</strong> &nbsp;•&nbsp; Correct: <strong>' + state.correctActions + '/' + state.totalActions + '</strong></p>' +
      '<div class="result-actions"><button class="btn primary" onclick="window._smirthi.endGame(false)">' + (bundle.play_again || 'Play Again') + '</button>' +
      '<button class="btn ghost" onclick="window._smirthi.closeGame()">Done</button></div>' +
      '<div class="speak-row"><button class="btn small" onclick="window._smirthi.speakResult(\'' + escalt(congrats) + '\')">🔊 ' + (bundle.listen || 'Listen') + '</button></div></div>';
  }

  function scoreRoundPoints(correct) {
    var base = correct ? 5 : 0;
    state.score = (state.score || 0) + base;
    var el = document.getElementById('gScore');
    if (el) el.textContent = state.score;
    return base;
  }

  function recordAction(correct) {
    state.correctActions += correct ? 1 : 0;
    state.totalActions += 1;
  }

  async function endGame(earlyExit) {
    clearInterval(state.gameTimer);
    var acc = state.totalActions ? Math.round((state.correctActions / state.totalActions) * 100) : 0;
    var time = Math.round((Date.now() - state.timerStart) / 1000);
    var score = Math.round((state.score || 0) * state.level);
    var coinsEarned = state.correctActions * 5;
    var session = {
      patient_id: state.patientId, game_type: state.currentGame,
      difficulty_level: Math.round(state.level), level: state.level,
      score: score, accuracy_pct: acc, completion_time_seconds: time,
      hints_used: state.hintsUsed, completed: !earlyExit,
      coins_earned: earlyExit ? 0 : coinsEarned,
      total_questions: state.totalActions,
      correct_answers: state.correctActions,
      language: state.lang,
      session_data: { puzzle_type: state.currentGame, timeline_action_count: state.totalActions },
    };
    try {
      var res = await fetch('/api/cognitive/session', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(session),
      });
      var payload = await res.json();
      if (payload.success && payload.next_level) {
        var oldLevel = state.level;
        state.level = Math.round(payload.next_level);
        localStorage.setItem('smirthi_level', String(state.level));
        if (payload.next_level > oldLevel) {
          toast('Level up! Now Level ' + state.level + ' 🌟');
          speak('Great job! Your level has increased to ' + state.level + '.');
        }
      }
    } catch (e) { session.offline = true; savePendingSession(session); }
    var area = $('gameArea');
    if (area) area.innerHTML = gameResultHtml(window.__COG_BUNDLE || {}, coinsEarned);
  }

  function closeGame() {
    var area = $('gameArea');
    var grid = $('gameGrid');
    if (area) { area.classList.add('hidden'); area.innerHTML = ''; }
    if (grid) grid.classList.remove('hidden');
    document.querySelectorAll('#gameGrid .game-card').forEach(function (c) { c.style.pointerEvents = ''; });
    if (state.patientId) {
      refreshDashboard();
      refreshCoins();
    }
  }

  function celebratePop() {
    var pop = document.createElement('div');
    pop.className = 'popup-good';
    pop.textContent = '✓';
    document.body.appendChild(pop);
    requestAnimationFrame(function () { pop.classList.add('show'); });
    setTimeout(function () { pop.remove(); }, 900);
  }

  /* =====================================================================
     10. GAME: Memory Match
     ===================================================================== */
  function renderMemoryMatch(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.memory_match || {};
    state.score = 0; state.matched = 0; state.flips = 0;
    state.lockBoard = false; state.firstCard = null; state.puzzle = puzzle;
    area.innerHTML = gameHeader(meta.title || 'Memory Match', meta.unit || 'Match all the pairs') +
      '<div class="memory-board" style="grid-template-columns:repeat(' + (puzzle.num_pairs < 5 ? 4 : 4) + ',1fr)">' +
      puzzle.cards.map(function (card, i) {
        return '<button class="memory-card" data-index="' + i + '" data-id="' + card.id + '">' +
          '<span class="mem-back">❔</span>' +
          '<span class="mem-front">' + card.emoji + '<small>' + card.name + '</small></span></button>';
      }).join('') + '</div>' +
      '<div class="game-footer-controls">' +
      '<button class="btn ghost" onclick="window._smirthi.gameHint()">🧭 ' + (bundle.hint || 'Hint') + '</button>' +
      '<button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';
    area.querySelectorAll('.memory-card').forEach(function (card) {
      card.addEventListener('click', function () { flipCard(card, puzzle); });
    });
  }

  function flipCard(card, puzzle) {
    if (state.lockBoard || card === state.firstCard || card.classList.contains('matched')) return;
    card.classList.add('flipped');
    var id = card.dataset.id;
    if (!state.firstCard) { state.firstCard = card; return; }
    state.lockBoard = true;
    var first = state.firstCard; state.firstCard = null;
    if (first.dataset.id === id) {
      first.classList.add('matched'); card.classList.add('matched');
      state.matched++; state.score += 10; recordAction(true);
      var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
      speak('Correct!'); celebratePop();
      state.lockBoard = false;
      if (state.matched === puzzle.num_pairs) setTimeout(function () { endGame(false); }, 700);
    } else {
      recordAction(false); speak('Try again!');
      setTimeout(function () { first.classList.remove('flipped'); card.classList.remove('flipped'); state.lockBoard = false; }, 900);
    }
  }

  function gameHint() {
    if (!state.puzzle || state.currentGame !== 'memory_match') return;
    state.hintsUsed++;
    var remaining = state.puzzle.cards.filter(function (c, i) {
      var el = document.querySelector('.memory-card[data-index="' + i + '"]');
      return el && !el.classList.contains('matched') && !el.classList.contains('flipped');
    });
    if (remaining.length < 2) return;
    var matchId = remaining[0].id;
    var pair = remaining.filter(function (c) { return c.id === matchId; }).slice(0, 2);
    pair.forEach(function (c) {
      var idx = remaining.indexOf(c);
      var el = document.querySelector('.memory-card[data-index="' + idx + '"]');
      if (el) { el.classList.add('hint'); setTimeout(function () { el.classList.remove('hint'); }, 1500); }
    });
    speak('Look here, these two are a pair.');
  }

  /* =====================================================================
     11. GAME: Sequence Memory (Words)
     ===================================================================== */
  function renderSequenceMemory(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.sequence_memory || {};
    state.score = 0; state.correctActions = 0; state.totalActions = 0;
    state.seqIndex = 0; state.expectedSeq = puzzle.sequence; state.seqShown = false;
    area.innerHTML = gameHeader(meta.title || 'Word Memory', meta.unit || 'Remember the words') +
      '<div class="sequence-display card" id="seqDisplay"><div class="seq-big" id="seqWords"></div>' +
      '<button class="btn primary big" id="seqStartBtn">👀 ' + uiText('look', 'Look & Remember') + '</button></div>' +
      '<div class="seq-options" id="seqOptions"></div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';
    document.getElementById('seqStartBtn').addEventListener('click', showSequenceTemporarily);
  }

  function showSequenceTemporarily() {
    var words = state.expectedSeq;
    var display = document.getElementById('seqWords');
    display.innerHTML = words.map(function (w) { return '<span class="word-pill">' + w + '</span>'; }).join(' ');
    speak(words.join(', '));
    document.getElementById('seqStartBtn').disabled = true;
    setTimeout(function () {
      display.innerHTML = '<em>' + uiText('memorize', 'Now pick the words in order') + '</em>';
      var options = $('seqOptions');
      options.innerHTML = state.currentPuzzle.options.map(function (w) {
        return '<button class="word-btn" data-w="' + w + '">' + w + '</button>';
      }).join('');
      options.querySelectorAll('.word-btn').forEach(function (btn) {
        btn.addEventListener('click', function () { pickWord(btn); });
      });
    }, Math.max(1500, state.currentPuzzle.sequence_length * 1000));
  }

  function pickWord(btn) {
    if (btn.disabled) return;
    var word = btn.dataset.w, expected = state.expectedSeq[state.seqIndex];
    btn.disabled = true;
    if (word === expected) {
      btn.classList.add('word-correct'); state.score += 10; state.seqIndex++; recordAction(true);
      var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
      speak('Correct!');
      if (state.seqIndex === state.expectedSeq.length) { toast('All words remembered!'); setTimeout(function () { endGame(false); }, 800); }
    } else {
      btn.classList.add('word-wrong'); recordAction(false); speak('Not quite, keep going.');
    }
  }

  /* =====================================================================
     12. GAME: Pattern Recognition
     ===================================================================== */
  function renderPatternRecognition(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.pattern_recognition || {};
    state.score = 0;
    area.innerHTML = gameHeader(meta.title || 'Pattern Finder', meta.unit || 'What comes next?') +
      '<div class="pattern-card card"><div class="pattern-line" id="patternLine"></div><div class="pattern-q">❓</div></div>' +
      '<div class="pattern-options" id="patternOptions"></div>' +
      '<div class="speak-row"><button class="btn small" onclick="window._smirthi.speakResult(\'' + escalt(uiText('pattern', 'What comes next in the pattern?')) + '\')">🔊 ' + (bundle.listen || 'Listen') + '</button></div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';
    document.getElementById('patternLine').innerHTML =
      puzzle.pattern.concat(['?']).map(function (e) { return '<span class="pattern-item">' + e + '</span>'; }).join('');
    var options = $('patternOptions');
    options.innerHTML = puzzle.options.map(function (e) { return '<button class="pattern-btn big-emoji">' + e + '</button>'; }).join('');
    options.querySelectorAll('.pattern-btn').forEach(function (btn) {
      btn.addEventListener('click', function (ev) {
        var picked = ev.target.textContent;
        if (picked === puzzle.correct_answer) {
          btn.classList.add('word-correct'); state.score = 20; recordAction(true);
          var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
          speak('Perfect!'); setTimeout(function () { endGame(false); }, 700);
        } else {
          btn.classList.add('word-wrong'); recordAction(false); speak('Look again at the pattern.');
        }
      });
    });
  }

  /* =====================================================================
     13. GAME: Daily Routine
     ===================================================================== */
  function renderDailyRoutine(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.daily_routine || {};
    state.score = 0; state.routinePicked = 0; state.routineCorrects = 0; state.routineWrongs = 0;
    area.innerHTML = gameHeader(meta.title || 'Daily Routine', meta.unit || 'Put the activities in order') +
      '<div class="routine-hint-row card"><span>👇 ' + uiText('tapOrder', 'Tap the activities in the correct daily order') + '</span>' +
      '<button class="btn small" onclick="window._smirthi.speakResult(\'' + escalt(puzzle.activities.map(function (a) { return a.text; }).join('. ')) + '\')">🔊 ' + (bundle.listen || 'Listen') + '</button></div>' +
      '<div class="routine-items" id="routineItems">' +
      puzzle.activities.map(function (a, i) {
        return '<button class="routine-item" data-id="' + a.id + '"><span class="routine-emoji">' + a.emoji + '</span><span class="routine-text">' + a.text + '</span></button>';
      }).join('') + '</div>' +
      '<div class="routine-done-row card" id="routineDoneRow"><span>✅ Order achieved:</span><div id="routineDone" class="routine-order-done"></div></div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';
    area.querySelectorAll('.routine-item').forEach(function (item) {
      item.addEventListener('click', function () { pickRoutine(item); });
    });
  }

  function pickRoutine(item) {
    if (item.classList.contains('placed')) return;
    var id = item.dataset.id, expected = state.currentPuzzle.correct_order[state.routinePicked];
    if (id === expected) {
      item.classList.add('placed');
      var span = document.createElement('span');
      span.className = 'routine-done-item';
      span.textContent = item.querySelector('.routine-emoji').textContent + ' ' + item.querySelector('.routine-text').textContent;
      document.getElementById('routineDone').appendChild(span);
      state.routinePicked++; state.score = (state.score || 0) + 10;
      var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
      recordAction(true); speak('Correct!');
      if (state.routinePicked === state.currentPuzzle.correct_order.length) { toast('Routine complete!'); setTimeout(function () { endGame(false); }, 700); }
    } else {
      item.classList.add('shake'); setTimeout(function () { item.classList.remove('shake'); }, 500);
      recordAction(false); speak('Not yet. Think about your daily routine.');
    }
  }

  /* =====================================================================
     14. GAME: Object Recognition
     ===================================================================== */
  function renderObjectRecognition(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.object_recognition || {};
    state.score = 0;
    var targetIndex = puzzle.answer_option;
    area.innerHTML = gameHeader(meta.title || 'Object Finder', meta.unit || 'Find the object') +
      '<div class="object-quest card"><span>❓ ' + uiText('findObject', 'Where is the hidden object?') + '</span>' +
      '<button class="btn small" onclick="window._smirthi.speakResult(\'' + escalt(puzzle.question) + '\')">🔊 ' + (bundle.listen || 'Listen') + '</button></div>' +
      '<div class="object-grid">' +
      puzzle.objects.map(function (obj) {
        return '<button class="object-cell" data-idx="' + obj.index + '">' +
          '<span class="object-box" style="background:linear-gradient(135deg,#ffe4e6,#fce7f3)">' + sciHint(obj.index, targetIndex) + '</span>' +
          '<small>Object ' + (obj.index + 1) + '</small></button>';
      }).join('') + '</div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';
    area.querySelectorAll('.object-cell').forEach(function (cell) {
      cell.addEventListener('click', function () {
        var idx = Number(cell.dataset.idx);
        if (idx === targetIndex) {
          cell.querySelector('.object-box').textContent = '🎁 FOUND!';
          cell.classList.add('word-correct'); state.score = 20; recordAction(true);
          var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
          speak('You found it! Wonderful!'); setTimeout(function () { endGame(false); }, 700);
        } else {
          cell.classList.add('word-wrong'); recordAction(false); speak('Not there. Try another box.');
        }
      });
    });
  }

  function sciHint(idx, target) {
    var emojis = ['🥮', '🫙', '🧂', '🧽', '🧴', '🍙', '🪥', '🧷'];
    return emojis[idx % emojis.length];
  }

  /* =====================================================================
     15. GAME: Color Sort
     ===================================================================== */
  function renderColorSort(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.color_sort || {};
    state.score = 0;
    area.innerHTML = gameHeader(meta.title || 'Color Match', meta.unit || 'Tap the color') +
      '<div class="color-target card"><span class="color-label">🎨 ' + uiText('findColor', 'Find this color') + '</span>' +
      '<div class="color-swatch" style="background:' + targetHex(puzzle) + '"></div>' +
      '<strong class="color-name">' + puzzle.target_label + '</strong>' +
      '<button class="btn small" onclick="window._smirthi.speakResult(\'' + escalt(puzzle.target_label) + '\')">🔊 ' + (bundle.listen || 'Listen') + '</button></div>' +
      '<div class="color-options">' +
      puzzle.colors.map(function (c) {
        return '<button class="color-btn word-btn" style="background:' + c.hex + '" data-hex="' + c.hex + '" data-name="' + c.name + '" title="' + c.name + '"><span class="color-option-label">' + c.name + '</span></button>';
      }).join('') + '</div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';
    area.querySelectorAll('.color-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.dataset.name === puzzle.correct_answer) {
          btn.classList.add('word-correct'); state.score = 20; recordAction(true);
          var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
          speak('Correct! Beautiful color!'); setTimeout(function () { endGame(false); }, 700);
        } else {
          btn.classList.add('word-wrong'); recordAction(false); speak('This is not it. Try again.');
        }
      });
    });
  }

  function targetHex(puzzle) {
    var match = puzzle.colors.find(function (c) { return c.name === puzzle.correct_answer; });
    return match ? match.hex : '#888';
  }

  /* =====================================================================
     16. GAME: Number Sequence (NEW #7)
     ===================================================================== */
  function renderNumberSequence(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.number_sequence || {};
    state.score = 0;
    state.seqIndex = 0;
    state.expectedSeq = puzzle.sequence;
    area.innerHTML = gameHeader(meta.title || 'Number Sequence', meta.unit || 'Remember the numbers') +
      '<div class="number-seq-area">' +
      '<div class="number-seq-prompt" id="numSeqPrompt">👀 Memorize the numbers!</div>' +
      '<div class="number-seq-display" id="numSeqDisplay"></div>' +
      '<button class="btn primary big" id="numSeqStartBtn">👀 Show Numbers</button>' +
      '<div class="number-seq-options" id="numSeqOptions" style="margin-top:20px"></div>' +
      '</div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';
    document.getElementById('numSeqStartBtn').addEventListener('click', showNumberSequence);
  }

  function showNumberSequence() {
    var nums = state.expectedSeq;
    var display = document.getElementById('numSeqDisplay');
    var prompt = document.getElementById('numSeqPrompt');
    display.innerHTML = nums.map(function (n) {
      return '<div class="number-seq-slot filled">' + n + '</div>';
    }).join('');
    prompt.textContent = 'Look carefully…';
    speak(nums.join(', '));
    document.getElementById('numSeqStartBtn').disabled = true;
    setTimeout(function () {
      display.innerHTML = nums.map(function () {
        return '<div class="number-seq-slot">?</div>';
      }).join('');
      prompt.textContent = 'Pick the numbers in order';
      var options = document.getElementById('numSeqOptions');
      options.innerHTML = puzzle.options.map(function (n) {
        return '<button class="number-btn word-btn" data-n="' + n + '">' + n + '</button>';
      }).join('');
      options.querySelectorAll('.number-btn').forEach(function (btn) {
        btn.addEventListener('click', function () { pickNumber(btn); });
      });
    }, Math.max(1500, nums.length * 800));
  }

  function pickNumber(btn) {
    if (btn.disabled) return;
    var num = btn.dataset.n;
    var expected = String(state.expectedSeq[state.seqIndex]);
    btn.disabled = true;
    if (num === expected) {
      btn.classList.add('word-correct');
      state.score += 10;
      state.seqIndex++;
      recordAction(true);
      var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
      speak('Correct!');
      if (state.seqIndex === state.expectedSeq.length) {
        toast('All numbers remembered!');
        setTimeout(function () { endGame(false); }, 800);
      }
    } else {
      btn.classList.add('word-wrong');
      recordAction(false);
      speak('Not quite, keep trying.');
    }
  }

  /* =====================================================================
     17. GAME: Face-Name Match (NEW #8)
     ===================================================================== */
  function renderFaceNameMatch(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.face_name_match || {};
    state.score = 0;
    area.innerHTML = gameHeader(meta.title || 'Face-Name Match', meta.unit || 'Who is this?') +
      '<div class="face-name-area">' +
      '<div class="face-name-prompt">👤 ' + uiText('whoIsThis', 'Who is this person?') + '</div>' +
      '<div class="face-display">' + (puzzle.face || '😊') + '</div>' +
      '<div class="face-name-options" id="faceNameOptions">' +
      puzzle.options.map(function (name) {
        return '<button class="face-name-btn word-btn" data-name="' + name + '">' + name + '</button>';
      }).join('') +
      '</div>' +
      '</div>' +
      '<div class="speak-row"><button class="btn small" onclick="window._smirthi.speakResult(\'' + escalt(uiText('whoIsThis', 'Who is this person?')) + '\')">🔊 ' + (bundle.listen || 'Listen') + '</button></div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';
    document.getElementById('faceNameOptions').querySelectorAll('.face-name-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.dataset.name === puzzle.correct_name) {
          btn.classList.add('word-correct'); state.score = 20; recordAction(true);
          var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
          speak('Correct! That is ' + puzzle.correct_name + '!');
          celebratePop();
          setTimeout(function () { endGame(false); }, 700);
        } else {
          btn.classList.add('word-wrong'); recordAction(false);
          speak('Not quite. Try again.');
        }
      });
    });
  }

  /* =====================================================================
     18. GAME: Shopping List (NEW #9)
     ===================================================================== */
  function renderShoppingList(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.shopping_list || {};
    state.score = 0;
    state.shoppingPicked = 0;
    state.shoppingCorrects = 0;
    var listItems = puzzle.list_items || [];
    var correctSet = {};
    listItems.forEach(function (item) { correctSet[item] = true; });
    area.innerHTML = gameHeader(meta.title || 'Shopping List', meta.unit || 'Remember and find all items') +
      '<div class="shopping-area">' +
      '<div class="shopping-header"><h3>🛒 Shopping List</h3><p id="shopPrompt">Memorize these items…</p></div>' +
      '<div class="shopping-list" id="shoppingListDisplay">' +
      listItems.map(function (item) {
        return '<div class="shopping-item" data-item="' + item + '">' +
          '<span class="shopping-check"></span>' +
          '<span class="shopping-item-text">' + item + '</span>' +
          '</div>';
      }).join('') +
      '</div>' +
      '<div class="shopping-list" id="shoppingOptions" style="margin-top:20px"></div>' +
      '</div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';
    /* Show list for 3 seconds then hide and show options */
    setTimeout(function () {
      document.getElementById('shopPrompt').textContent = 'Now find the items from the list!';
      var display = document.getElementById('shoppingListDisplay');
      display.innerHTML = '<div class="activity-empty" style="padding:20px">List hidden — pick the correct items below!</div>';
      var shuffled = (puzzle.options || listItems.slice()).slice();
      for (var i = shuffled.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var tmp = shuffled[i]; shuffled[i] = shuffled[j]; shuffled[j] = tmp;
      }
      var optDiv = document.getElementById('shoppingOptions');
      optDiv.innerHTML = shuffled.map(function (item) {
        return '<div class="shopping-item" data-item="' + item + '">' +
          '<span class="shopping-check"></span>' +
          '<span class="shopping-item-text">' + item + '</span>' +
          '</div>';
      }).join('');
      optDiv.querySelectorAll('.shopping-item').forEach(function (el) {
        el.addEventListener('click', function () { pickShoppingItem(el, correctSet); });
      });
    }, 3000);
  }

  function pickShoppingItem(el, correctSet) {
    if (el.classList.contains('checked')) return;
    var item = el.dataset.item;
    if (correctSet[item]) {
      el.classList.add('checked');
      el.querySelector('.shopping-check').textContent = '✓';
      state.score += 10;
      state.shoppingPicked++;
      recordAction(true);
      var sc = document.getElementById('gScore'); if (sc) sc.textContent = state.score;
      speak(item + ' — correct!');
      celebratePop();
      var totalItems = Object.keys(correctSet).length;
      if (state.shoppingPicked >= totalItems) {
        toast('All items found!');
        setTimeout(function () { endGame(false); }, 700);
      }
    } else {
      el.classList.add('word-wrong');
      setTimeout(function () { el.classList.remove('word-wrong'); }, 600);
      recordAction(false);
      speak('That is not on the list.');
    }
  }

  /* =====================================================================
     19. GAME: Clock Reading (NEW #10)
     ===================================================================== */
  function renderClockReading(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.clock_reading || {};
    state.score = 0;
    var hour = puzzle.hour || 0;
    var minute = puzzle.minute || 0;
    var hourAngle = (hour % 12) * 30 + minute * 0.5;
    var minuteAngle = minute * 6;
    /* Build SVG clock */
    var clockSvg = '<svg class="clock-svg" viewBox="0 0 260 260" width="260" height="260" style="display:block;margin:0 auto">' +
      '<circle cx="130" cy="130" r="124" fill="var(--card)" stroke="var(--primary-dark)" stroke-width="6"/>';
    /* Hour numbers */
    for (var h = 1; h <= 12; h++) {
      var angle = (h * 30 - 90) * Math.PI / 180;
      var nx = 130 + 100 * Math.cos(angle);
      var ny = 130 + 100 * Math.sin(angle);
      clockSvg += '<text x="' + nx.toFixed(1) + '" y="' + (ny + 7).toFixed(1) + '" text-anchor="middle" font-size="22" font-weight="800" fill="var(--text)">' + h + '</text>';
    }
    /* Hour tick marks */
    for (var t = 0; t < 12; t++) {
      var a = t * 30;
      var x1 = 130 + 110 * Math.cos((a - 90) * Math.PI / 180);
      var y1 = 130 + 110 * Math.sin((a - 90) * Math.PI / 180);
      var x2 = 130 + 118 * Math.cos((a - 90) * Math.PI / 180);
      var y2 = 130 + 118 * Math.sin((a - 90) * Math.PI / 180);
      clockSvg += '<line x1="' + x1.toFixed(1) + '" y1="' + y1.toFixed(1) + '" x2="' + x2.toFixed(1) + '" y2="' + y2.toFixed(1) + '" stroke="var(--primary-dark)" stroke-width="' + (t % 3 === 0 ? 4 : 2) + '"/>';
    }
    /* Hour hand */
    var hx = 130 + 55 * Math.cos((hourAngle - 90) * Math.PI / 180);
    var hy = 130 + 55 * Math.sin((hourAngle - 90) * Math.PI / 180);
    clockSvg += '<line x1="130" y1="130" x2="' + hx.toFixed(1) + '" y2="' + hy.toFixed(1) + '" stroke="var(--primary-dark)" stroke-width="7" stroke-linecap="round"/>';
    /* Minute hand */
    var mx = 130 + 90 * Math.cos((minuteAngle - 90) * Math.PI / 180);
    var my = 130 + 90 * Math.sin((minuteAngle - 90) * Math.PI / 180);
    clockSvg += '<line x1="130" y1="130" x2="' + mx.toFixed(1) + '" y2="' + my.toFixed(1) + '" stroke="var(--accent)" stroke-width="4" stroke-linecap="round"/>';
    /* Center dot */
    clockSvg += '<circle cx="130" cy="130" r="7" fill="var(--primary-dark)"/>';
    clockSvg += '</svg>';

    area.innerHTML = gameHeader(meta.title || 'Clock Reading', meta.unit || 'What time is shown?') +
      '<div class="clock-game-area">' +
      '<div class="clock-prompt">🕐 ' + uiText('whatTime', 'What time does the clock show?') + '</div>' +
      '<div class="clock-face-wrap">' + clockSvg + '</div>' +
      '<div class="clock-options" id="clockOptions">' +
      puzzle.options.map(function (t) {
        return '<button class="clock-option-btn word-btn" data-time="' + t + '">' + t + '</button>';
      }).join('') +
      '</div>' +
      '</div>' +
      '<div class="speak-row"><button class="btn small" onclick="window._smirthi.speakResult(\'' + escalt(uiText('whatTime', 'What time does the clock show?')) + '\')">🔊 ' + (bundle.listen || 'Listen') + '</button></div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';

    document.getElementById('clockOptions').querySelectorAll('.clock-option-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.dataset.time === puzzle.correct_answer) {
          btn.classList.add('word-correct'); state.score = 20; recordAction(true);
          var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
          speak('Correct! The time is ' + puzzle.correct_answer);
          celebratePop();
          setTimeout(function () { endGame(false); }, 700);
        } else {
          btn.classList.add('word-wrong'); recordAction(false);
          speak('Not quite. Look at the clock hands again.');
        }
      });
    });
  }

  /* =====================================================================
     20. GAME: Emotion Recognition (NEW #11)
     ===================================================================== */
  function renderEmotionRecognition(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.emotion_recognition || {};
    state.score = 0;
    area.innerHTML = gameHeader(meta.title || 'Emotion Recognition', meta.unit || 'How do they feel?') +
      '<div class="emotion-area">' +
      '<div class="emotion-prompt">😊 ' + uiText('howFeel', 'How does this person feel?') + '</div>' +
      '<div class="emotion-display">' + (puzzle.face || '😊') + '</div>' +
      '<div class="emotion-options" id="emotionOptions">' +
      puzzle.options.map(function (emotion) {
        return '<button class="emotion-btn word-btn" data-emotion="' + emotion + '">' +
          '<span class="emotion-btn-emoji">' + emotionEmoji(emotion) + '</span> ' + emotion +
          '</button>';
      }).join('') +
      '</div>' +
      '</div>' +
      '<div class="speak-row"><button class="btn small" onclick="window._smirthi.speakResult(\'' + escalt(uiText('howFeel', 'How does this person feel?')) + '\')">🔊 ' + (bundle.listen || 'Listen') + '</button></div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';

    document.getElementById('emotionOptions').querySelectorAll('.emotion-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.dataset.emotion === puzzle.correct_emotion) {
          btn.classList.add('word-correct'); state.score = 20; recordAction(true);
          var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
          speak('Correct! The person feels ' + puzzle.correct_emotion);
          celebratePop();
          setTimeout(function () { endGame(false); }, 700);
        } else {
          btn.classList.add('word-wrong'); recordAction(false);
          speak('Not quite. Look at the face again.');
        }
      });
    });
  }

  function emotionEmoji(emotion) {
    var map = {
      happy: '😊', sad: '😢', angry: '😠', surprised: '😲', scared: '😨',
      confused: '😕', tired: '😴', love: '🥰', neutral: '😐', worried: '😟',
    };
    return map[(emotion || '').toLowerCase()] || '😶';
  }

  /* =====================================================================
     21. GAME: Word Association (NEW #12)
     ===================================================================== */
  function renderWordAssociation(puzzle) {
    var area = $('gameArea');
    var bundle = window.__COG_BUNDLE || {};
    var meta = bundle.game_types && bundle.game_types.word_association || {};
    state.score = 0;
    state.wordAssocMatched = 0;
    state.wordAssocSelected = null;
    var pairs = puzzle.pairs || [];
    var totalPairs = pairs.length;
    /* Build two columns: first words on left, second words shuffled on right */
    var leftWords = [];
    var rightWords = [];
    pairs.forEach(function (pair) {
      leftWords.push(pair[0]);
      rightWords.push(pair[1]);
    });
    /* Shuffle right column */
    for (var i = rightWords.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = rightWords[i]; rightWords[i] = rightWords[j]; rightWords[j] = tmp;
    }
    var pairMap = {};
    pairs.forEach(function (pair) { pairMap[pair[0]] = pair[1]; });

    area.innerHTML = gameHeader(meta.title || 'Word Association', meta.unit || 'Match the pairs') +
      '<div class="word-assoc-area">' +
      '<div class="word-assoc-prompt">🔗 ' + uiText('matchPairs', 'Tap a word on the left, then its match on the right') + '</div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;max-width:600px;margin:0 auto 24px">' +
      '<div class="word-assoc-col" id="waLeftCol">' +
      leftWords.map(function (w) {
        return '<div class="word-assoc-card" data-word="' + w + '" data-side="left">' +
          '<span class="word-assoc-card-word">' + w + '</span></div>';
      }).join('') +
      '</div>' +
      '<div class="word-assoc-col" id="waRightCol">' +
      rightWords.map(function (w) {
        return '<div class="word-assoc-card" data-word="' + w + '" data-side="right">' +
          '<span class="word-assoc-card-word">' + w + '</span></div>';
      }).join('') +
      '</div>' +
      '</div>' +
      '</div>' +
      '<div class="game-footer-controls"><button class="btn primary" onclick="window._smirthi.endGame(false)">✅ Finish</button></div>';

    /* Wire click handlers */
    document.querySelectorAll('.word-assoc-card').forEach(function (card) {
      card.addEventListener('click', function () { pickWordAssoc(card, pairMap, totalPairs); });
    });
  }

  function pickWordAssoc(card, pairMap, totalPairs) {
    if (card.classList.contains('matched')) return;
    var side = card.dataset.side;
    var word = card.dataset.word;
    if (side === 'left') {
      /* Select/deselect left */
      document.querySelectorAll('.word-assoc-card[data-side="left"]').forEach(function (c) { c.classList.remove('selected'); });
      card.classList.add('selected');
      state.wordAssocSelected = word;
    } else if (side === 'right' && state.wordAssocSelected) {
      /* Check match */
      var leftWord = state.wordAssocSelected;
      var expectedRight = pairMap[leftWord];
      if (word === expectedRight) {
        /* Find left card and mark both matched */
        var leftCard = document.querySelector('.word-assoc-card[data-word="' + leftWord + '"][data-side="left"]');
        if (leftCard) leftCard.classList.add('matched');
        card.classList.add('matched');
        state.score += 10;
        state.wordAssocMatched++;
        recordAction(true);
        var el = document.getElementById('gScore'); if (el) el.textContent = state.score;
        speak('Correct!');
        celebratePop();
        state.wordAssocSelected = null;
        if (state.wordAssocMatched >= totalPairs) {
          toast('All pairs matched!');
          setTimeout(function () { endGame(false); }, 700);
        }
      } else {
        card.classList.add('wrong');
        recordAction(false);
        speak('Not a match. Try again.');
        setTimeout(function () { card.classList.remove('wrong'); }, 500);
      }
    }
  }

  /* =====================================================================
     22. DASHBOARD / PROGRESS
     ===================================================================== */
  async function refreshDashboard() {
    try {
      var res = await fetch('/api/cognitive/dashboard?patient_id=' + encodeURIComponent(state.patientId));
      var payload = await res.json();
      if (!payload.success) return;
      var stats = payload.stats || {};
      var el;
      el = $('statTotalGames'); if (el) el.textContent = stats.total_sessions || 0;
      el = $('statAvgScore'); if (el) el.textContent = stats.avg_score || 0;
      el = $('statAccuracy'); if (el) el.textContent = (stats.avg_accuracy || 0) + '%';
      el = $('statMinutes'); if (el) el.textContent = (stats.total_time_minutes || 0) + ' min';
      var trendMap = { improving: '📈 Improving', stable: '➖ Stable', declining: '📉 Declining', insufficient_data: '—' };
      el = $('statTrend'); if (el) el.textContent = trendMap[stats.cognitive_trend] || '—';
      var today = new Date().toISOString().slice(0, 10);
      var daily = payload.daily || [];
      var todayGames = daily.find(function (d) { return (d.activity_date || '').slice(0, 10) === today; });
      el = $('statGamesToday'); if (el) el.textContent = todayGames ? todayGames.games_played : 0;
      renderRecentScores(stats.recent_scores || []);
      renderGameBreakdown(stats.game_breakdown || {});
      await refreshCoins();
    } catch (e) { console.error('dashboard', e); }
  }

  function renderRecentScores(scores) {
    var el = $('recentScores');
    if (!el) return;
    if (!scores.length) { el.innerHTML = '<p class="muted">Play a game to see your progress here.</p>'; return; }
    el.innerHTML = scores.slice(0, 10).map(function (s) {
      var d = new Date(s.date);
      var when = isNaN(d) ? s.date : d.toLocaleDateString();
      return '<div class="score-row"><span>' + iconForGame(s.game_type) + ' ' + gameTitle(s.game_type) + '</span><strong>' + s.score + '</strong><small>' + when + ' • Lv ' + s.difficulty + '</small></div>';
    }).join('');
  }

  function renderGameBreakdown(breakdown) {
    var el = $('gameBreakdown');
    if (!el) return;
    var entries = Object.entries(breakdown || {});
    if (!entries.length) { el.innerHTML = '<p class="muted">No games played yet.</p>'; return; }
    var total = entries.reduce(function (sum, kv) { return sum + (kv[1].count || 0); }, 0);
    el.innerHTML = entries.map(function (kv) {
      var game = kv[0], info = kv[1];
      var pct = Math.round((info.count / total) * 100);
      return '<div class="breakdown-row"><span>' + iconForGame(game) + ' ' + gameTitle(game) + '</span>' +
        '<div class="breakdown-bar"><div class="breakdown-fill" style="width:' + pct + '%"></div></div>' +
        '<small>' + info.count + ' games</small></div>';
    }).join('');
  }

  function iconForGame(game) {
    var icons = {
      memory_match: '🃏', sequence_memory: '📝', pattern_recognition: '🔮',
      daily_routine: '🗓️', object_recognition: '🔍', color_sort: '🎨',
      number_sequence: '🔢', face_name_match: '👤', shopping_list: '🛒',
      clock_reading: '🕐', emotion_recognition: '😊', word_association: '🔗',
    };
    return icons[game] || '🎮';
  }

function gameTitle(game) {
    var meta = window.__COG_BUNDLE && window.__COG_BUNDLE.game_types && window.__COG_BUNDLE.game_types[game];
    return meta ? meta.title : (game || '').replace(/_/g, ' ');
  }

  /* =====================================================================
     22b. COINS / REWARDS
     ===================================================================== */
  async function refreshCoins() {
    if (!state.patientId) return;
    try {
      var res = await fetch('/api/cognitive/coins?patient_id=' + encodeURIComponent(state.patientId));
      var payload = await res.json();
      if (!payload.success) return;
      var balance = payload.coins_balance || 0;
      var today = payload.coins_today || 0;
      var total = payload.coins_total || 0;
      var el;
      el = $('topCoinsChip'); if (el) el.textContent = balance + ' 🪙';
      el = $('topCoinsValue'); if (el) el.textContent = balance;
      el = $('statCoinsToday'); if (el) el.textContent = today;
      el = $('statCoinsTotal'); if (el) el.textContent = total;
      el = $('cgPatientCoins'); if (el) el.textContent = balance + ' 🪙';
    } catch (e) { console.error('coins', e); }
  }

  /* =====================================================================
     22. DASHBOARD / PROGRESS
     ===================================================================== */
  async function refreshReminders() {
    try {
      var res = await fetch('/api/cognitive/reminders?patient_id=' + encodeURIComponent(state.patientId));
      var payload = await res.json();
      if (!payload.success) return;
      renderReminders(payload.reminders);
      renderSchedule(payload.reminders);
    } catch (e) { console.error('reminders', e); }
  }

  var reminderIcons = { medicine: '💊', hydration: '💧', activity: '🚶', appointment: '📅' };
  var reminderNames = { medicine: 'Medicine', hydration: 'Water', activity: 'Activity', appointment: 'Appointment' };

  function renderReminders(reminders) {
    var el = $('reminderList');
    if (!el) return;
    if (!reminders.length) { el.innerHTML = '<div class="card empty">No reminders yet. Add one below.</div>'; return; }
    el.innerHTML = reminders.map(function (r) {
      return '<div class="reminder-card card ' + (r.is_active ? '' : 'inactive') + '">' +
        '<span class="reminder-icon">' + (reminderIcons[r.reminder_type] || '🔔') + '</span>' +
        '<div class="reminder-body"><strong>' + (r.title || reminderNames[r.reminder_type]) + '</strong>' +
        '<small>' + (r.message || reminderNames[r.reminder_type]) + ' • ' + (r.scheduled_time || '') + ' • ' + r.recurrence + '</small></div>' +
        '<div class="reminder-actions"><label class="switch mini"><input type="checkbox" data-id="' + r.reminder_id + '" ' + (r.is_active ? 'checked' : '') + ' /><span></span></label>' +
        '<button class="btn tiny danger" data-del="' + r.reminder_id + '">✕</button></div></div>';
    }).join('');
    el.querySelectorAll('input[data-id]').forEach(function (chk) {
      chk.addEventListener('change', async function (ev) {
        try {
          await fetch('/api/cognitive/reminders/' + chk.dataset.id + '/toggle', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: ev.target.checked }),
          });
          refreshReminders();
        } catch (e) { /* offline */ }
      });
    });
    el.querySelectorAll('[data-del]').forEach(function (btn) {
      btn.addEventListener('click', async function () {
        if (!confirm('Delete this reminder?')) return;
        try { await fetch('/api/cognitive/reminders/' + btn.dataset.del, { method: 'DELETE' }); refreshReminders(); } catch (e) { /* */ }
      });
    });
  }

  function renderSchedule(reminders) {
    var el = $('scheduleList');
    if (!el) return;
    var active = reminders.filter(function (r) { return r.is_active; }).sort(function (a, b) { return (a.scheduled_time || '').localeCompare(b.scheduled_time || ''); });
    if (!active.length) { el.innerHTML = '<p class="muted">No scheduled items.</p>'; return; }
    el.innerHTML = active.map(function (r) {
      var now = new Date();
      var parts = r.scheduled_time ? r.scheduled_time.split(':').map(Number) : [0, 0];
      var passed = now.getHours() > parts[0] || (now.getHours() === parts[0] && now.getMinutes() >= parts[1]);
      return '<div class="schedule-row ' + (passed ? 'passed' : 'upcoming') + '">' +
        '<span class="schedule-time">' + (r.scheduled_time || '--:--') + '</span>' +
        '<span class="schedule-icon">' + (reminderIcons[r.reminder_type] || '🔔') + '</span>' +
        '<span class="schedule-title">' + (r.title || reminderNames[r.reminder_type]) + '</span>' +
        '<span class="schedule-state">' + (passed ? 'Done ✓' : 'Upcoming') + '</span></div>';
    }).join('');
  }

  /* =====================================================================
     24. CAREGIVER
     ===================================================================== */
  async function refreshCaregiver() {
    try {
      var res = await fetch('/api/cognitive/caregiver?patient_id=' + encodeURIComponent(state.patientId));
      var payload = await res.json();
      if (!payload.success) return;
      var d = payload.dashboard;
      var health = d.health_score || 0;
      var el;
      el = $('healthScore'); if (el) el.textContent = health;
      el = $('healthBar'); if (el) el.style.width = health + '%';
      var stats = d.overall_stats || {};
      el = $('caregiverStats');
      if (el) {
        el.innerHTML =
          '<div class="cg-stat"><span>Total Games</span><strong>' + (stats.total_sessions || 0) + '</strong></div>' +
          '<div class="cg-stat"><span>Completed</span><strong>' + (stats.completed_sessions || 0) + '</strong></div>' +
          '<div class="cg-stat"><span>Avg Accuracy</span><strong>' + (stats.avg_accuracy || 0) + '%</strong></div>' +
          '<div class="cg-stat"><span>Active Reminders</span><strong>' + (d.active_reminders || 0) + '</strong></div>' +
          '<div class="cg-stat"><span>Time (min)</span><strong>' + (stats.total_time_minutes || 0) + '</strong></div>' +
          '<div class="cg-stat"><span>Trend</span><strong class="' + (stats.cognitive_trend === 'declining' ? 'danger' : 'ok') + '">' + (stats.cognitive_trend || '—') + '</strong></div>';
      }
      renderCaregiverSessions(d.recent_sessions || []);
      renderWeekly(d.weekly_activity || []);
      renderAlerts(d);
      await refreshCaregiverNotifications();
    } catch (e) { console.error('caregiver', e); }
  }

  function renderCaregiverSessions(sessions) {
    var el = $('caregiverSessions');
    if (!el) return;
    if (!sessions.length) { el.innerHTML = '<p class="muted">No sessions yet.</p>'; return; }
    el.innerHTML = sessions.slice(0, 8).map(function (s) {
      return '<div class="cg-session-row"><span>' + iconForGame(s.game_type) + ' ' + gameTitle(s.game_type) + '</span><strong>' + (s.score || 0) + '</strong><small>Lv ' + (s.difficulty_level || 1) + ' • ' + (s.accuracy_pct || 0) + '%</small></div>';
    }).join('');
  }

  function renderWeekly(weekly) {
    var el = $('weeklyActivity');
    if (!el) return;
    if (!weekly.length) { el.innerHTML = '<p class="muted">No activity yet this week.</p>'; return; }
    var max = Math.max.apply(null, weekly.map(function (d) { return d.games_played || 0; }).concat([1]));
    var days = weekly.slice().sort(function (a, b) { return a.activity_date.localeCompare(b.activity_date); }).slice(-7);
    el.innerHTML = days.map(function (d) {
      var pct = Math.round(((d.games_played || 0) / max) * 100);
      var shortDay = new Date(d.activity_date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short' });
      return '<div class="bar-day"><small>' + shortDay + '</small><div class="bar-track"><div class="bar-fill" style="height:' + Math.max(8, pct) + '%"></div></div><small>' + (d.games_played || 0) + '</small></div>';
    }).join('');
  }

  function renderAlerts(d) {
    var alerts = [];
    var stats = d.overall_stats || {};
    if (stats.cognitive_trend === 'declining') alerts.push({ level: 'danger', text: 'Cognitive score is declining. Consider increasing session frequency.' });
    if (stats.completed_sessions === 0) alerts.push({ level: 'warn', text: 'Patient has not completed any games yet.' });
    if ((stats.total_time_minutes || 0) === 0) alerts.push({ level: 'warn', text: 'No engagement detected in the last week.' });
    if (!alerts.length) alerts.push({ level: 'ok', text: 'All metrics look healthy. Keep up the great engagement!' });
    var el = $('alertList');
    if (!el) return;
    el.innerHTML = alerts.map(function (a) {
      return '<div class="alert-item ' + a.level + '">' + (a.level === 'ok' ? '✅' : '⚠️') + ' ' + a.text + '</div>';
    }).join('');
  }

  async function refreshCaregiverNotifications() {
    if (!state.user || !state.user.phone) return;
    try {
      var res = await fetch('/api/cognitive/notifications?phone=' + encodeURIComponent(state.user.phone) + '&limit=20');
      var payload = await res.json();
      if (!payload.success) return;
      renderCaregiverNotifications(payload.notifications || []);
      var countEl = $('notifCount');
      if (countEl) countEl.textContent = payload.unread || 0;
    } catch (e) { console.error('notifications', e); }
  }

  function renderCaregiverNotifications(notifications) {
    var el = $('notifList');
    if (!el) return;
    if (!notifications.length) { el.innerHTML = '<div class="activity-empty">No notifications yet.</div>'; return; }
    var typeIcons = {
      game_completed: '🎮', low_performance: '⚠️', reminder: '🔔',
      game: '🎮', milestone: '🏆', activity: '📊'
    };
    el.innerHTML = notifications.map(function (n) {
      var icon = typeIcons[n.notification_type] || '🔔';
      var time = n.created_at || '';
      if (time.length > 16) time = time.slice(0, 16).replace('T', ' ');
      return '<div class="notif-item ' + (n.is_read ? '' : 'unread') + '">' +
        '<span class="notif-ico">' + icon + '</span>' +
        '<div class="notif-body"><strong>' + (n.detail || 'Notification') + '</strong>' +
        '<small>' + time + '</small></div></div>';
    }).join('');
  }

  /* =====================================================================
     25. SETTINGS / LANGUAGE
     ===================================================================== */
  async function loadLanguages() {
    try {
      var res = await fetch('/api/cognitive/languages');
      var payload = await res.json();
      var sel = $('languageSelect'), regLang = $('regLanguage');
      if (sel) sel.innerHTML = '';
      if (regLang) regLang.innerHTML = '';
      (payload.languages || []).forEach(function (l) {
        var opt = document.createElement('option');
        opt.value = l.code; opt.textContent = l.name;
        if (sel) sel.appendChild(opt.cloneNode(true));
        if (regLang) regLang.appendChild(opt);
      });
      if (sel) sel.value = state.lang;
      if (regLang) regLang.value = state.lang;
    } catch (e) { console.error('languages', e); }
  }

  async function setLanguage(lang) {
    state.lang = lang;
    localStorage.setItem('smirthi_lang', lang);
    var sel = $('languageSelect');
    if (sel) sel.value = lang;
    await loadContent();
    speak('Language changed.');
  }

  /* =====================================================================
     26. VIEW SETTINGS
     ===================================================================== */
  function initViewSettings() {
    document.body.classList.toggle('large-text', state.largeText);
    document.body.classList.toggle('high-contrast', state.contrast);
    var vc = $('voiceCheck'); if (vc) vc.checked = state.voice;
    var lc = $('largeCheck'); if (lc) lc.checked = state.largeText;
    var cc = $('contrastCheck'); if (cc) cc.checked = state.contrast;
    var vBtn = $('voiceToggleBtn');
    if (vBtn) { var sp = vBtn.querySelector('span'); if (sp) sp.textContent = state.voice ? 'ON' : 'OFF'; }
    if ('serviceWorker' in navigator || 'indexedDB' in window) {
      var chip = $('storageChip');
      if (chip) chip.textContent = state.pendingSessions.length + ' pending';
    }
  }

  /* =====================================================================
     27. EVENT WIRING
     ===================================================================== */
  function doLogout() {
    stopReminderChecker();
    stopActivityFeedPoll();
    var pending = state.pendingSessions || [];
    localStorage.setItem('smirthi_pending', JSON.stringify(pending));
    state.phone = '';
    state.role = '';
    state.patientId = '';
    state.user = null;
    localStorage.removeItem('smirthi_phone');
    localStorage.removeItem('smirthi_role');
    localStorage.removeItem('smirthi_patient');
    var splash = $('splashScreen');
    var login = $('loginScreen');
    var main = $('mainApp');
    if (splash) splash.classList.add('hidden');
    if (login) login.classList.remove('hidden');
    if (main) main.classList.add('hidden');
    setupLoginTabs();
    toast('Logged out. Offline data preserved.');
  }

  function wireEvents() {
    /* Tabs */
    document.querySelectorAll('.tab').forEach(function (tab) {
      tab.addEventListener('click', function () { activateTab(tab.dataset.tab); });
    });

    /* Voice toggle */
    var voiceBtn = $('voiceToggleBtn');
    if (voiceBtn) {
      voiceBtn.addEventListener('click', function () {
        state.voice = !state.voice;
        localStorage.setItem('smirthi_voice', state.voice ? '1' : '0');
        var vc = $('voiceCheck'); if (vc) vc.checked = state.voice;
        var sp = voiceBtn.querySelector('span'); if (sp) sp.textContent = state.voice ? 'ON' : 'OFF';
        if (state.voice) speak('Voice assistant is on.');
      });
    }

    /* Large text */
    var ltBtn = $('largeTextBtn');
    if (ltBtn) {
      ltBtn.addEventListener('click', function () {
        state.largeText = !state.largeText;
        localStorage.setItem('smirthi_large', state.largeText ? '1' : '0');
        document.body.classList.toggle('large-text', state.largeText);
        var lc = $('largeCheck'); if (lc) lc.checked = state.largeText;
      });
    }

    /* Contrast */
    var ctBtn = $('contrastBtn');
    if (ctBtn) {
      ctBtn.addEventListener('click', function () {
        state.contrast = !state.contrast;
        localStorage.setItem('smirthi_contrast', state.contrast ? '1' : '0');
        document.body.classList.toggle('high-contrast', state.contrast);
        var cc = $('contrastCheck'); if (cc) cc.checked = state.contrast;
      });
    }

    /* Settings checkboxes */
    var vc = $('voiceCheck');
    if (vc) vc.addEventListener('change', function (ev) {
      state.voice = ev.target.checked;
      localStorage.setItem('smirthi_voice', state.voice ? '1' : '0');
      var vBtn = $('voiceToggleBtn');
      if (vBtn) { var sp = vBtn.querySelector('span'); if (sp) sp.textContent = state.voice ? 'ON' : 'OFF'; }
    });
    var lc = $('largeCheck');
    if (lc) lc.addEventListener('change', function (ev) {
      state.largeText = ev.target.checked;
      localStorage.setItem('smirthi_large', state.largeText ? '1' : '0');
      document.body.classList.toggle('large-text', state.largeText);
    });
    var cc = $('contrastCheck');
    if (cc) cc.addEventListener('change', function (ev) {
      state.contrast = ev.target.checked;
      localStorage.setItem('smirthi_contrast', state.contrast ? '1' : '0');
      document.body.classList.toggle('high-contrast', state.contrast);
    });

    /* Language select */
    var langSel = $('languageSelect');
    if (langSel) langSel.addEventListener('change', function (ev) { setLanguage(ev.target.value); });

    /* Sync button */
    var syncBtn = $('syncNowBtn');
    if (syncBtn) syncBtn.addEventListener('click', syncNow);

    /* Logout button (topbar) */
    var logoutBtn = $('logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', function () { doLogout(); });
    }

    /* Logout button (settings) */
    var logoutBtnSettings = $('logoutBtnSettings');
    if (logoutBtnSettings) {
      logoutBtnSettings.addEventListener('click', function () { doLogout(); });
    }

    /* Patient selector */
    var patSel = $('patientSelector');
    if (patSel) patSel.addEventListener('change', function (ev) { switchPatient(ev.target.value); });

    /* Register modal */
    var regBtn = $('registerPatientBtn');
    if (regBtn) regBtn.addEventListener('click', function () { var m = $('registerModal'); if (m) m.classList.remove('hidden'); });
    var regCancel = $('regCancel');
    if (regCancel) regCancel.addEventListener('click', function () { var m = $('registerModal'); if (m) m.classList.add('hidden'); });

    /* Reminder modal */
    var remBtn = $('addReminderBtn');
    if (remBtn) remBtn.addEventListener('click', function () { var m = $('reminderModal'); if (m) m.classList.remove('hidden'); });
    var remCancel = $('remCancel');
    if (remCancel) remCancel.addEventListener('click', function () { var m = $('reminderModal'); if (m) m.classList.add('hidden'); });

    /* Register form submit */
    var regSubmit = $('regSubmit');
    if (regSubmit) {
      regSubmit.addEventListener('click', async function () {
        var payload = {
          patient_id: $('regPatientId') ? $('regPatientId').value.trim() : '',
          name: $('regName') ? $('regName').value.trim() : '',
          age: $('regAge') ? Number($('regAge').value) : 0,
          sex: $('regSex') ? $('regSex').value : '',
          district: $('regDistrict') ? $('regDistrict').value.trim() : '',
          state: $('regState') ? $('regState').value.trim() : '',
          language: $('regLanguage') ? $('regLanguage').value : state.lang,
          caregiver_name: $('regCaregiver') ? $('regCaregiver').value.trim() : '',
          caregiver_phone: $('regPhone') ? $('regPhone').value.trim() : '',
        };
        if (!payload.patient_id || !payload.name) { toast('Patient ID and name are required.'); return; }
        try {
          var res = await fetch('/api/cognitive/patient', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          var result = await res.json();
          if (result.success) {
            var m = $('registerModal'); if (m) m.classList.add('hidden');
            toast('Patient registered ✓');
            await loadPatientSelector();
            await switchPatient(payload.patient_id);
          } else { toast(result.message || 'Registration failed'); }
        } catch (e) { toast('Offline: saved locally.'); }
      });
    }

    /* Reminder form submit */
    var remSubmit = $('remSubmit');
    if (remSubmit) {
      remSubmit.addEventListener('click', async function () {
        if (!state.patientId) { toast('Select a patient first.'); return; }
        var payload = {
          patient_id: state.patientId,
          reminder_type: $('remType') ? $('remType').value : 'activity',
          title: $('remTitle') ? $('remTitle').value.trim() : '',
          message: $('remMessage') ? $('remMessage').value.trim() : '',
          scheduled_time: $('remTime') ? $('remTime').value : '08:00',
          rem_date: $('remDate') ? $('remDate').value : '',
          rem_repeat: $('remRepeat') ? $('remRepeat').value : 'daily',
        };
        if (!payload.title || !payload.scheduled_time) { toast('Title and time are required.'); return; }
        try {
          var res = await fetch('/api/cognitive/reminders', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          var result = await res.json();
          if (result.success) {
            var m = $('reminderModal'); if (m) m.classList.add('hidden');
            toast('Reminder added ✓');
            refreshReminders();
          }
        } catch (e) { toast('Could not save reminder.'); }
      });
    }
  }

  /* =====================================================================
     REMINDER CHECKER
     ===================================================================== */
  var reminderCheckTimer = null;

  function startReminderChecker() {
    stopReminderChecker();
    checkReminders();
    reminderCheckTimer = setInterval(checkReminders, 60000); // Check every minute
  }

  function stopReminderChecker() {
    if (reminderCheckTimer) { clearInterval(reminderCheckTimer); reminderCheckTimer = null; }
  }

  async function checkReminders() {
    if (!state.patientId || !state.voice) return;
    try {
      var res = await fetch('/api/cognitive/reminders?patient_id=' + encodeURIComponent(state.patientId));
      var payload = await res.json();
      if (!payload.success) return;
      var now = new Date();
      var currentTime = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
      var today = now.toISOString().slice(0, 10);
      (payload.reminders || []).forEach(function (r) {
        if (!r.is_active) return;
        var scheduled = r.scheduled_time || '';
        if (scheduled && scheduled.slice(0, 5) === currentTime) {
          // Check if already triggered today
          var triggeredKey = 'reminder_triggered_' + r.reminder_id + '_' + today;
          if (localStorage.getItem(triggeredKey)) return;
          localStorage.setItem(triggeredKey, '1');
          // Show visual notification
          toast('⏰ ' + (r.title || 'Reminder') + ': ' + (r.message || ''));
          // Speak in selected language
          var langText = r.message || r.title || 'Reminder';
          speak(langText, true);
          // Log trigger to backend if online
          if (navigator.onLine) {
            fetch('/api/cognitive/reminders/' + r.reminder_id + '/ack', {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({})
            }).catch(function () { /* ignore */ });
          }
        }
      });
    } catch (e) { console.error('checkReminders', e); }
  }

  /* =====================================================================
     28. BOOT MAIN APP
     ===================================================================== */
  async function bootMainApp() {
    initViewSettings();
    await loadLanguages();
    await loadContent();
    await loadPatientSelector();
    if (state.patientId) {
      await switchPatient(state.patientId);
      await refreshCoins();
    } else {
      toast('Welcome! Register or select a patient to start playing.');
    }
    if (!navigator.onLine) {
      var banner = $('offlineBanner');
      if (banner) banner.classList.remove('hidden');
    }
    if (!('speechSynthesis' in window)) {
      var vBtn = $('voiceToggleBtn');
      if (vBtn) vBtn.style.display = 'none';
    }
    if ('serviceWorker' in navigator) {
      try { navigator.serviceWorker.register('/static/sw.js'); } catch (e) { /* */ }
    }
    startReminderChecker();
  }

  /* =====================================================================
     29. PUBLIC API (for inline onclick handlers in HTML)
     ===================================================================== */
  window._smirthi = {
    endGame: endGame,
    closeGame: closeGame,
    gameHint: gameHint,
    speakResult: function (text) { speak(text, true); },
  };

  /* =====================================================================
     30. ENTRY POINT
     ===================================================================== */
  wireEvents();
  setupLoginTabs();
  setupLoginSkip();
  setupLoginSubmit();
  setupSplashContinue();
  setupPdfDownload();
  initSplash();

})();
