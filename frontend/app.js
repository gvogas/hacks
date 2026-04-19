const API = '';
let sessionId = localStorage.getItem('study_session_id') || null;
let authToken = localStorage.getItem('auth_token') || null;
let currentUser = null;
let authMode = 'login'; // 'login' | 'signup'
let flashcards = [];
let cardIndex = 0;
let quizQuestions = [];
let shopState = null;
let plantState = null;
let studyTickTimer = null;
let lastStudyTickMs = null;
let spotifyState = null;
let spotifySetupDone = false;
let spotifyDevices = [];
let selectedSpotifyDeviceId = localStorage.getItem('spotify_device_id') || '';
let spotifyWebPlayer = null;
let spotifyWebDeviceId = null;
let spotifySdkReady = false;

window.onSpotifyWebPlaybackSDKReady = () => {
  spotifySdkReady = true;
  if (authToken && spotifyState?.connected) initSpotifyWebPlayer();
};

const LEVEL_SPRITES = {
  bad:         '/sprites/MainFlower1.png',
  average:     '/sprites/MainFlower2.png',
  good:        '/sprites/MainFlower3.png',
  excellent:   '/sprites/MainFlower4.png',
  amazing:     '/sprites/Sunflower.png',
  phenomenal:  '/sprites/WhiteFlower.png',
  legendary:   '/sprites/CactiBro.png',
};
// Maps equipped skin name → sprite, matching the level order above.
const SKIN_SPRITES = {
  default:  '/sprites/MainFlower1.png',
  warm:     '/sprites/MainFlower2.png',
  lush:     '/sprites/MainFlower3.png',
  azure:    '/sprites/MainFlower4.png',
  sunset:   '/sprites/Sunflower.png',
  aurora:   '/sprites/WhiteFlower.png',
  golden:   '/sprites/CactiBro.png',
};
const FALLBACK_SPRITE = '/sprites/Cracked1.png';
const PLANT_DEAD_SPRITE = '/sprites/Broken.png';

function spriteForState(state) {
  return SKIN_SPRITES[state?.skin] || LEVEL_SPRITES[state?.level_id] || FALLBACK_SPRITE;
}
function plantImg(src) {
  return `<img src="${src}" alt="plant" class="plant-sprite" draggable="false">`;
}

function renderPlant(state, animate) {
  if (!state) return;
  const prevStage = plantState ? plantState.stage : -1;
  const prevHealth = plantState ? plantState.health : 100;
  plantState = state;

  const artEl = document.getElementById('plant-art');
  const nameEl = document.getElementById('plant-stage-name');
  const fillEl = document.getElementById('plant-health-fill');
  const labelEl = document.getElementById('plant-health-label');
  const hintEl = document.getElementById('plant-hint');
  if (!artEl) return;

  if (state.health <= 0) {
    artEl.innerHTML = `<img src="${PLANT_DEAD_SPRITE}" alt="withered plant" class="plant-sprite" draggable="false">`;
  } else {
    artEl.innerHTML = plantImg(spriteForState(state));
  }

  fillEl.style.width = state.health + '%';
  if (state.health > 60) {
    fillEl.style.background = 'linear-gradient(90deg,#66BB6A,#43A047)';
  } else if (state.health > 30) {
    fillEl.style.background = 'linear-gradient(90deg,#FDD835,#F9A825)';
  } else {
    fillEl.style.background = 'linear-gradient(90deg,#EF5350,#C62828)';
  }

  nameEl.textContent = state.stage_name;
  labelEl.textContent = state.health + '% health';

  artEl.className = 'plant-art skin-' + (state.skin || 'default');
  if (state.health <= 0) {
    artEl.classList.add('plant-dead');
    hintEl.textContent = 'Withered! -30 coins. Study to revive it.';
  } else if (state.health < 30) {
    artEl.classList.add('plant-wilting');
    hintEl.textContent = 'Your plant is struggling — keep studying to restore it!';
  } else if (state.health < 60) {
    artEl.classList.add('plant-stressed');
    hintEl.textContent = 'Your plant needs care — avoid wrong answers!';
  } else if (state.stage < 5) {
    hintEl.textContent = state.stage_progress + '% to next stage — keep studying!';
  } else {
    hintEl.textContent = 'Your plant is in full bloom! Keep it healthy.';
  }

  if (animate === 'wither') {
    artEl.classList.add('plant-wither-anim');
    setTimeout(() => artEl.classList.remove('plant-wither-anim'), 800);
  } else if (prevStage !== -1 && state.stage > prevStage) {
    artEl.classList.add('plant-grow-anim');
    setTimeout(() => artEl.classList.remove('plant-grow-anim'), 950);
    toast('Your plant grew! Now: ' + state.stage_name, 'success');
  } else if (state.health > prevHealth) {
    artEl.classList.add('plant-heal-anim');
    setTimeout(() => artEl.classList.remove('plant-heal-anim'), 650);
  }
}

const state = {
  notes: false,
  learning: false,
};

// ── Auth ─────────────────────────────────────────────────────────────────────

function showAuth() {
  document.getElementById('auth-overlay').style.display = 'flex';
  document.getElementById('app-shell').style.display = 'none';
  setTimeout(() => document.getElementById('auth-email')?.focus(), 50);
}

function showApp() {
  document.getElementById('auth-overlay').style.display = 'none';
  document.getElementById('app-shell').style.display = 'block';
  updateTabLocks();
  if (currentUser) {
    const btn = document.getElementById('profile-btn');
    if (btn) btn.title = currentUser.email;
  }
  if (sessionId) {
    document.getElementById('session-badge').textContent = 'session: ' + sessionId.slice(0, 8);
  }
  renderCoinBadge();
  if (!spotifySetupDone) {
    setupSpotifyControls();
    spotifySetupDone = true;
  }
  loadSpotifyStatus();
}

function toggleAuthMode() {
  authMode = authMode === 'login' ? 'signup' : 'login';
  const isLogin = authMode === 'login';
  document.getElementById('auth-title').textContent = isLogin ? 'Sign in' : 'Create account';
  document.getElementById('auth-submit').textContent = isLogin ? 'Sign in' : 'Sign up';
  document.getElementById('auth-toggle-text').textContent = isLogin ? 'No account?' : 'Already have an account?';
  document.getElementById('auth-toggle-btn').textContent = isLogin ? 'Create one' : 'Sign in';
  document.getElementById('auth-status').textContent = '';
  const pwd = document.getElementById('auth-password');
  pwd.setAttribute('autocomplete', isLogin ? 'current-password' : 'new-password');
}

async function submitAuth() {
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const status = document.getElementById('auth-status');
  const btn = document.getElementById('auth-submit');

  if (!email || !password) {
    setStatus(status, 'Email and password are required.', true);
    return;
  }
  if (authMode === 'signup' && password.length < 6) {
    setStatus(status, 'Password must be at least 6 characters.', true);
    return;
  }

  btn.disabled = true;
  setStatus(status, authMode === 'login' ? 'Signing in...' : 'Creating account...');

  try {
    const path = authMode === 'login' ? '/api/auth/login' : '/api/auth/signup';
    const res = await apiJson(path, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    authToken = res.token;
    currentUser = res.user;
    localStorage.setItem('auth_token', authToken);
    localStorage.removeItem('study_session_id');
    sessionId = null;
    setStatus(status, '');
    showApp();
    await loadShopState();
    startStudyTicker();
    await loadSessionList();
    toast(authMode === 'login' ? 'Welcome back!' : 'Account created.', 'success');
  } catch (err) {
    setStatus(status, err.message, true);
  } finally {
    btn.disabled = false;
  }
}

function logout() {
  if (!confirm('Log out? Your sessions stay saved on the server.')) return;
  localStorage.removeItem('auth_token');
  setSession(null);
  location.reload();
}

document.getElementById('auth-password')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); submitAuth(); }
});
document.getElementById('auth-email')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); document.getElementById('auth-password').focus(); }
});

// ── Spotify ──────────────────────────────────────────────────────────────────

function setupSpotifyControls() {
  const headerRight = document.querySelector('.header-right');
  if (!headerRight || document.getElementById('spotify-controls')) return;

  const group = document.createElement('div');
  group.id = 'spotify-controls';
  group.className = 'spotify-controls';

  const connectBtn = document.createElement('button');
  connectBtn.id = 'spotify-connect-btn';
  connectBtn.className = 'header-btn spotify-btn';
  connectBtn.type = 'button';
  connectBtn.title = 'Connect Spotify';
  connectBtn.textContent = 'Connect Spotify';
  connectBtn.addEventListener('click', handleSpotifyConnectButton);

  group.append(connectBtn);

  const logoutBtn = headerRight.querySelector('#logout-btn') || headerRight.querySelector('button[onclick="logout()"]');
  if (logoutBtn) headerRight.insertBefore(group, logoutBtn);
  else headerRight.appendChild(group);

  document.getElementById('spotify-play-btn')?.addEventListener('click', () => spotifyCommand('play'));
  document.getElementById('spotify-pause-btn')?.addEventListener('click', () => spotifyCommand('pause'));
  document.getElementById('spotify-next-btn')?.addEventListener('click', () => spotifyCommand('next'));

  renderSpotifyControls();
}

async function loadSpotifyStatus() {
  if (!authToken || !document.getElementById('spotify-controls')) return;
  try {
    spotifyState = await apiJson('/api/spotify/status', { method: 'GET' });
    renderSpotifyControls();
    if (spotifyState.connected) {
      loadSpotifyCurrent();
      if (spotifySdkReady && !spotifyWebPlayer) initSpotifyWebPlayer();
    }
  } catch (err) {
    console.warn('Could not load Spotify status:', err.message);
  }
}

function initSpotifyWebPlayer() {
  if (spotifyWebPlayer || !window.Spotify) return;

  spotifyWebPlayer = new window.Spotify.Player({
    name: 'Study Assistant (Browser)',
    getOAuthToken: async (cb) => {
      try {
        const res = await apiJson('/api/spotify/token', { method: 'GET' });
        cb(res.access_token);
      } catch (err) {
        console.warn('Could not fetch Spotify token:', err.message);
      }
    },
    volume: 0.5,
  });

  spotifyWebPlayer.addListener('ready', async ({ device_id }) => {
    spotifyWebDeviceId = device_id;
    selectedSpotifyDeviceId = device_id;
    localStorage.setItem('spotify_device_id', device_id);
    try {
      await apiJson('/api/spotify/transfer', {
        method: 'PUT',
        body: JSON.stringify({ device_id, play: false }),
      });
      toast('Spotify ready in browser.', 'success');
    } catch (err) {
      console.warn('Spotify transfer to browser failed:', err.message);
    }
    loadSpotifyDevices();
    loadSpotifyCurrent();
  });

  spotifyWebPlayer.addListener('not_ready', ({ device_id }) => {
    if (spotifyWebDeviceId === device_id) spotifyWebDeviceId = null;
  });

  spotifyWebPlayer.addListener('player_state_changed', () => loadSpotifyCurrent());
  spotifyWebPlayer.addListener('initialization_error', ({ message }) => console.warn('Spotify init error:', message));
  spotifyWebPlayer.addListener('authentication_error', ({ message }) => console.warn('Spotify auth error:', message));
  spotifyWebPlayer.addListener('account_error', ({ message }) => {
    toast('Spotify Premium is required to play in the browser.', 'error');
    console.warn('Spotify account error:', message);
  });

  spotifyWebPlayer.connect();
}

function renderSpotifyControls() {
  const connectBtn = document.getElementById('spotify-connect-btn');
  if (!connectBtn) return;

  const connected = !!spotifyState?.connected;
  connectBtn.disabled = false;
  connectBtn.classList.toggle('connected', connected);
  connectBtn.textContent = connected
    ? `Spotify: ${spotifyState.display_name || 'Connected'}`
    : (spotifyState?.configured === false ? 'Set up Spotify' : 'Connect Spotify');
  connectBtn.title = connected ? 'Disconnect Spotify' : 'Connect Spotify';

  const playbackBar = document.getElementById('spotify-playback-bar');
  if (playbackBar) playbackBar.style.display = connected ? 'flex' : 'none';

  renderSpotifyDevices();
  if (!connected) loadSpotifyCurrent();
}

async function handleSpotifyConnectButton() {
  if (spotifyState?.connected) {
    await disconnectSpotify();
  } else {
    await connectSpotify();
  }
}

async function connectSpotify() {
  const btn = document.getElementById('spotify-connect-btn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Connecting...';
  }

  try {
    const res = await apiJson('/api/spotify/connect', { method: 'POST' });
    window.location.href = res.auth_url;
  } catch (err) {
    toast('Spotify connect failed: ' + err.message, 'error');
    renderSpotifyControls();
  }
}

async function disconnectSpotify() {
  if (!confirm('Disconnect Spotify from this account?')) return;
  try {
    spotifyState = await apiJson('/api/spotify/disconnect', { method: 'POST' });
    renderSpotifyControls();
    toast('Spotify disconnected.', 'success');
  } catch (err) {
    toast('Spotify disconnect failed: ' + err.message, 'error');
  }
}

async function spotifyCommand(action) {
  const endpoints = {
    play: { path: '/api/spotify/play', method: 'PUT', label: 'Playback resumed.' },
    pause: { path: '/api/spotify/pause', method: 'PUT', label: 'Playback paused.' },
    next: { path: '/api/spotify/next', method: 'POST', label: 'Skipped track.' },
  };
  const endpoint = endpoints[action];
  if (!endpoint) return;

  try {
    const options = { method: endpoint.method };
    if (action === 'play' && selectedSpotifyDeviceId) {
      options.body = JSON.stringify({ device_id: selectedSpotifyDeviceId });
    }
    await apiJson(endpoint.path, options);
    loadSpotifyCurrent();
    toast(endpoint.label, 'success');
  } catch (err) {
    toast('Spotify command failed: ' + err.message, 'error');
  }
}

function handleSpotifyReturn() {
  const params = new URLSearchParams(window.location.search);
  const result = params.get('spotify');
  if (!result) return;
  const detail = params.get('spotify_detail');

  history.replaceState({}, document.title, window.location.pathname + window.location.hash);
  if (result === 'connected') {
    toast('Spotify connected.', 'success');
    loadSpotifyStatus();
  } else if (result === 'denied') {
    toast(detail || 'Spotify connection was cancelled.', 'error');
  } else {
    toast(detail ? 'Spotify connection failed: ' + detail : 'Spotify connection failed. Check your Spotify settings.', 'error');
  }
}

async function loadSpotifyDevices() {
  const status = document.getElementById('spotify-status');
  if (!authToken) return;
  if (!spotifyState?.connected) {
    setStatus(status, 'Connect Spotify first.', true);
    return;
  }

  setStatus(status, 'Loading devices...');
  try {
    const res = await apiJson('/api/spotify/devices', { method: 'GET' });
    spotifyDevices = (res.devices || []).filter(device => (device.type || '').toLowerCase() !== 'avr');
    const selectedExists = spotifyDevices.some(device => device.id === selectedSpotifyDeviceId);
    const activeDevice = spotifyDevices.find(device => device.is_active && device.id);
    if (!selectedExists) {
      selectedSpotifyDeviceId = activeDevice?.id || spotifyDevices.find(device => device.id)?.id || '';
      if (selectedSpotifyDeviceId) localStorage.setItem('spotify_device_id', selectedSpotifyDeviceId);
    }
    renderSpotifyDevices();
    setStatus(status, '');
  } catch (err) {
    setStatus(status, 'Could not load Spotify devices: ' + err.message, true);
  }
}

function renderSpotifyDevices() {
  const list = document.getElementById('spotify-device-list');
  const summary = document.getElementById('spotify-device-summary');
  if (!list || !summary) return;

  if (!spotifyState?.connected) {
    summary.textContent = 'Spotify not connected';
    list.innerHTML = '<div class="spotify-empty">Connect Spotify from the header first.</div>';
    return;
  }

  if (!spotifyDevices.length) {
    summary.textContent = 'No device selected';
    list.innerHTML = '<div class="spotify-empty">No Spotify devices found. Open Spotify on desktop or mobile, then refresh.</div>';
    return;
  }

  const selected = spotifyDevices.find(device => device.id === selectedSpotifyDeviceId);
  summary.textContent = selected ? `${selected.name} (${selected.type})` : 'Choose a device';
  list.innerHTML = spotifyDevices.map(device => {
    const disabled = !device.id || device.is_restricted;
    const active = device.id === selectedSpotifyDeviceId;
    return `<button type="button" class="spotify-device ${active ? 'selected' : ''}" data-device-id="${escHtml(device.id || '')}" ${disabled ? 'disabled' : ''}>
      <span>${escHtml(device.name || 'Unnamed device')}</span>
      <small>${escHtml(device.type || 'Device')}${device.is_active ? ' - active' : ''}</small>
    </button>`;
  }).join('');

  list.querySelectorAll('.spotify-device').forEach(btn => {
    btn.addEventListener('click', () => selectSpotifyDevice(btn.dataset.deviceId));
  });
}

async function selectSpotifyDevice(deviceId) {
  if (!deviceId) return;
  selectedSpotifyDeviceId = deviceId;
  localStorage.setItem('spotify_device_id', deviceId);
  renderSpotifyDevices();

  try {
    await apiJson('/api/spotify/transfer', {
      method: 'PUT',
      body: JSON.stringify({ device_id: deviceId, play: false }),
    });
    toast('Spotify device selected.', 'success');
    loadSpotifyCurrent();
  } catch (err) {
    toast('Device selected, but transfer failed: ' + err.message, 'error');
  }
}

async function searchSpotify() {
  const input = document.getElementById('spotify-search-input');
  const query = input?.value.trim();
  const status = document.getElementById('spotify-status');
  if (!query) {
    setStatus(status, 'Enter a playlist or song name.', true);
    input?.focus();
    return;
  }

  setStatus(status, 'Searching Spotify...');
  try {
    const res = await apiJson('/api/spotify/search?q=' + encodeURIComponent(query), { method: 'GET' });
    renderSpotifyResults(res);
    setStatus(status, '');
  } catch (err) {
    setStatus(status, 'Spotify search failed: ' + err.message, true);
  }
}

async function loadSpotifyPlaylists() {
  const status = document.getElementById('spotify-status');
  setStatus(status, 'Loading playlists...');
  try {
    const res = await apiJson('/api/spotify/playlists', { method: 'GET' });
    renderSpotifyResults({ tracks: [], playlists: res.playlists || [] });
    setStatus(status, '');
  } catch (err) {
    setStatus(status, 'Could not load playlists: ' + err.message, true);
  }
}

function renderSpotifyResults(res) {
  const container = document.getElementById('spotify-results');
  if (!container) return;
  const tracks = res.tracks || [];
  const playlists = res.playlists || [];
  if (!tracks.length && !playlists.length) {
    container.innerHTML = '<div class="spotify-empty">No Spotify results found.</div>';
    return;
  }

  let html = '';
  if (playlists.length) {
    html += '<h3>Playlists</h3>';
    html += playlists.map(item => spotifyResultCard(item, 'playlist')).join('');
  }
  if (tracks.length) {
    html += '<h3>Songs</h3>';
    html += tracks.map(item => spotifyResultCard(item, 'track')).join('');
  }
  container.innerHTML = html;
  container.querySelectorAll('[data-spotify-play]').forEach(btn => {
    btn.addEventListener('click', () => playSpotifyItem(btn.dataset.spotifyKind, btn.dataset.spotifyUri));
  });
}

function spotifyResultCard(item, kind) {
  const subtitle = kind === 'track'
    ? [item.artist, item.album].filter(Boolean).join(' - ')
    : [item.owner, item.tracks_total ? `${item.tracks_total} tracks` : ''].filter(Boolean).join(' - ');
  const art = item.image_url
    ? `<img src="${escHtml(item.image_url)}" alt="" loading="lazy" />`
    : '<div class="spotify-art-placeholder"></div>';
  return `<article class="spotify-result">
    <div class="spotify-art">${art}</div>
    <div class="spotify-result-info">
      <strong>${escHtml(item.name)}</strong>
      <span>${escHtml(subtitle || (kind === 'track' ? 'Song' : 'Playlist'))}</span>
    </div>
    <button class="btn-secondary" type="button" data-spotify-play="1" data-spotify-kind="${kind}" data-spotify-uri="${escHtml(item.uri || '')}" ${item.uri ? '' : 'disabled'}>
      Play
    </button>
  </article>`;
}

async function playSpotifyItem(kind, uri) {
  const status = document.getElementById('spotify-status');
  if (!uri) return;
  const body = kind === 'track' ? { uris: [uri] } : { context_uri: uri };
  if (selectedSpotifyDeviceId) body.device_id = selectedSpotifyDeviceId;

  setStatus(status, 'Starting Spotify playback...');
  try {
    await apiJson('/api/spotify/play', {
      method: 'PUT',
      body: JSON.stringify(body),
    });
    setStatus(status, '');
    toast('Spotify playback started.', 'success');
    loadSpotifyCurrent();
  } catch (err) {
    setStatus(status, 'Spotify play failed: ' + err.message, true);
  }
}

document.getElementById('spotify-search-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); searchSpotify(); }
});

async function loadSpotifyCurrent() {
  const title = document.getElementById('spotify-now-title');
  const container = document.getElementById('spotify-now-playing');
  if (!title || !container || !authToken) return;
  if (!spotifyState?.connected) {
    title.textContent = 'Spotify not connected';
    container.innerHTML = '<div class="spotify-empty">Connect Spotify to see what is playing.</div>';
    return;
  }

  try {
    const current = await apiJson('/api/spotify/current', { method: 'GET' });
    renderSpotifyCurrent(current);
  } catch (err) {
    title.textContent = 'Could not load playback';
    container.innerHTML = `<div class="spotify-empty">${escHtml(err.message)}</div>`;
  }
}

function renderSpotifyCurrent(current) {
  const title = document.getElementById('spotify-now-title');
  const container = document.getElementById('spotify-now-playing');
  if (!title || !container) return;

  if (!current?.item) {
    title.textContent = current?.is_playing ? 'Playing' : 'Nothing playing';
    container.innerHTML = '<div class="spotify-empty">Start a song or playlist from Spotify, then refresh.</div>';
    return;
  }

  const item = current.item;
  const device = current.device?.name ? ` on ${current.device.name}` : '';
  const playState = current.is_playing ? 'Playing' : 'Paused';
  const subtitle = [item.artist, item.album].filter(Boolean).join(' - ');
  const progress = current.duration_ms ? Math.min(100, Math.round((current.progress_ms / current.duration_ms) * 100)) : 0;
  const art = item.image_url
    ? `<img src="${escHtml(item.image_url)}" alt="" loading="lazy" />`
    : '<div class="spotify-art-placeholder"></div>';

  title.textContent = `${playState}${device}`;
  container.innerHTML = `<article class="spotify-current">
    <div class="spotify-art spotify-current-art">${art}</div>
    <div class="spotify-current-info">
      <strong>${escHtml(item.name)}</strong>
      <span>${escHtml(subtitle || item.type || 'Spotify')}</span>
      <div class="spotify-progress" aria-hidden="true"><span style="width:${progress}%"></span></div>
      <small>${formatDuration(current.progress_ms)} / ${formatDuration(current.duration_ms)}</small>
    </div>
    ${item.external_url ? `<a class="btn-secondary spotify-open-link" href="${escHtml(item.external_url)}" target="_blank" rel="noreferrer">Open</a>` : ''}
  </article>`;
}

function formatDuration(ms) {
  const totalSeconds = Math.max(0, Math.floor((ms || 0) / 1000));
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

// ── History sidebar ──────────────────────────────────────────────────────────

async function loadSessionList() {
  try {
    const res = await apiJson('/api/study/sessions', { method: 'GET' });
    renderSessionList(res.sessions || []);
  } catch (err) {
    console.warn('Could not load session list:', err.message);
  }
}

function renderSessionList(sessions) {
  const list = document.getElementById('history-list');
  if (!sessions.length) {
    list.innerHTML = '<div class="history-empty">No saved sessions yet.<br/>Start a topic to get going.</div>';
    return;
  }
  list.innerHTML = sessions.map(s => `
    <div class="history-item ${s.session_id === sessionId ? 'active' : ''}" data-id="${escHtml(s.session_id)}">
      <button type="button" class="delete-btn" title="Delete" onclick="deleteSessionConfirm(event, '${escHtml(s.session_id)}')">×</button>
      <span class="topic">${escHtml(s.topic || 'Untitled')}</span>
      <span class="meta">${formatDate(s.updated_at)}</span>
    </div>
  `).join('');
  list.querySelectorAll('.history-item').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.closest('.delete-btn')) return;
      loadSession(el.dataset.id);
    });
  });
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso + 'Z');
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function toggleHistory() {
  const sidebar = document.getElementById('history-sidebar');
  const backdrop = document.getElementById('history-backdrop');
  const open = sidebar.classList.toggle('open');
  backdrop.classList.toggle('show', open);
  sidebar.setAttribute('aria-hidden', String(!open));
  if (open) loadSessionList();
}

async function loadSession(id) {
  try {
    const s = await apiJson('/api/study/session/' + encodeURIComponent(id), { method: 'GET' });
    setSession(id);

    flashcards = s.flashcards || [];
    quizQuestions = s.quiz_questions || [];
    state.notes = !!s.notes;
    state.learning = !!(flashcards.length || quizQuestions.length);

    if (s.notes) {
      renderNotes(s.notes, s.topic || '');
    } else {
      document.getElementById('notes-content').innerHTML = '';
    }
    if (flashcards.length) renderFlashcards();
    if (quizQuestions.length) renderQuiz();

    if (s.topic) document.getElementById('topic-input').value = s.topic;

    updateTabLocks();
    if (s.notes) markCompleted('research');
    if (state.learning) markCompleted('notes');
    switchTab(s.notes ? 'notes' : 'research');
    toggleHistory();
    toast('Session loaded.', 'success');
  } catch (err) {
    toast('Could not load session: ' + err.message, 'error');
  }
}

async function deleteSessionConfirm(e, id) {
  e.stopPropagation();
  if (!confirm('Delete this session? This cannot be undone.')) return;
  try {
    await apiJson('/api/study/session/' + encodeURIComponent(id), { method: 'DELETE' });
    if (id === sessionId) setSession(null);
    loadSessionList();
    toast('Session deleted.', 'success');
  } catch (err) {
    toast('Delete failed: ' + err.message, 'error');
  }
}

// ── Session ──────────────────────────────────────────────────────────────────

function setSession(id) {
  sessionId = id;
  const badge = document.getElementById('session-badge');
  if (id) {
    localStorage.setItem('study_session_id', id);
    badge.textContent = 'session: ' + id.slice(0, 8);
  } else {
    localStorage.removeItem('study_session_id');
    badge.textContent = '';
  }
}

function resetSession() {
  if (!confirm('Start a new session? Your current notes, flashcards, quiz and plan will be cleared from this page.')) return;
  setSession(null);
  location.reload();
}

// ── Tab switching & locking ──────────────────────────────────────────────────

function isTabUnlocked(btn) {
  const req = btn.dataset.requires;
  if (!req) return true;
  return !!state[req];
}

function updateTabLocks() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    const unlocked = isTabUnlocked(btn);
    btn.classList.toggle('locked', !unlocked);
  });
}

function markCompleted(tabName) {
  const btn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
  if (btn) btn.classList.add('completed');
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.classList.contains('locked')) {
      const req = btn.dataset.requires;
      const msg = req === 'notes'
        ? 'Run Research first to unlock this tab.'
        : 'Generate flashcards & quiz from the Notes tab first.';
      toast(msg, 'error');
      return;
    }
    switchTab(btn.dataset.tab);
  });
});

function switchTab(name) {
  const btn = document.querySelector(`.tab-btn[data-tab="${name}"]`);
  if (btn && btn.classList.contains('locked')) return;
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === name);
  });
  document.querySelectorAll('.tab-section').forEach(s => {
    s.classList.toggle('active', s.id === 'tab-' + name);
  });
  if (name === 'profile') loadProfile();
  if (name === 'spotify') {
    loadSpotifyStatus().then(() => loadSpotifyDevices());
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── File upload ───────────────────────────────────────────────────────────────

const pendingFiles = [];

document.getElementById('file-input').addEventListener('change', e => {
  for (const f of e.target.files) pendingFiles.push(f);
  renderFileList();
  e.target.value = '';
});

function renderFileList() {
  const list = document.getElementById('file-list');
  if (!pendingFiles.length) { list.innerHTML = ''; return; }
  list.innerHTML = pendingFiles.map((f, i) => `
    <span class="file-chip">
      ${escHtml(f.name)}
      <button type="button" onclick="removeFile(${i})" title="Remove" aria-label="Remove ${escHtml(f.name)}">×</button>
    </span>
  `).join('');
}

function removeFile(i) {
  pendingFiles.splice(i, 1);
  renderFileList();
}

// Drag & drop
const uploadArea = document.getElementById('upload-area');
if (uploadArea) {
  uploadArea.addEventListener('click', e => {
    if (e.target.closest('button')) return;
    document.getElementById('file-input').click();
  });
  ['dragenter', 'dragover'].forEach(ev => {
    uploadArea.addEventListener(ev, e => {
      e.preventDefault();
      uploadArea.classList.add('drag');
    });
  });
  ['dragleave', 'drop'].forEach(ev => {
    uploadArea.addEventListener(ev, e => {
      e.preventDefault();
      if (ev === 'dragleave' && uploadArea.contains(e.relatedTarget)) return;
      uploadArea.classList.remove('drag');
    });
  });
  uploadArea.addEventListener('drop', e => {
    const allowed = ['.pdf', '.pptx', '.txt', '.md'];
    for (const f of e.dataTransfer.files) {
      const ok = allowed.some(ext => f.name.toLowerCase().endsWith(ext));
      if (ok) pendingFiles.push(f);
      else toast(`Skipped "${f.name}" — unsupported type.`, 'error');
    }
    renderFileList();
  });
}

// ── Research ──────────────────────────────────────────────────────────────────

async function startResearch() {
  const topicInput = document.getElementById('topic-input');
  const topic = topicInput.value.trim();
  const btn = document.getElementById('start-btn');
  const status = document.getElementById('research-status');
  const source = document.querySelector('input[name="study-source"]:checked')?.value || 'both';

  if (source !== 'files' && !topic) {
    toast('Please enter a topic first.', 'error');
    topicInput.focus();
    return;
  }

  btn.disabled = true;
  setStatus(status, pendingFiles.length ? 'Uploading files...' : source === 'files' ? 'Loading from files...' : 'Searching the web...');

  try {
    if (pendingFiles.length && source !== 'web') {
      const form = new FormData();
      form.append('file', pendingFiles[0]);
      if (sessionId) form.append('session_id', sessionId);
      const r = await apiJson('/api/upload', { method: 'POST', body: form });
      setSession(r.session_id);
      for (let i = 1; i < pendingFiles.length; i++) {
        const f2 = new FormData();
        f2.append('file', pendingFiles[i]);
        f2.append('session_id', sessionId);
        await apiJson('/api/upload', { method: 'POST', body: f2 });
      }
      setStatus(status, source === 'files' ? 'Loading from files...' : 'Searching the web...');
    }

    const res = await apiJson('/api/study/start', {
      method: 'POST',
      body: JSON.stringify({ topic: source === 'files' ? undefined : topic, session_id: sessionId, source }),
    });

    setSession(res.session_id);
    renderNotes(res.notes, topic || 'Uploaded materials');
    state.notes = true;
    markCompleted('research');
    updateTabLocks();
    setStatus(status, '');
    if (res.warnings?.length) {
      console.warn(res.warnings.join('\n'));
      toast('Notes ready, but web search was unavailable.', 'error');
    } else {
      toast('Notes ready! Taking you to the Notes tab.', 'success');
    }
    setTimeout(() => switchTab('notes'), 600);
    loadSessionList();
  } catch (err) {
    setStatus(status, 'Error: ' + err.message, true);
    toast(err.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

function updateStudySource() {
  const source = document.querySelector('input[name="study-source"]:checked')?.value || 'both';
  const topicInput = document.getElementById('topic-input');
  const uploadArea = document.getElementById('upload-area');
  const fileInput = document.getElementById('file-input');
  const browseBtn = uploadArea?.querySelector('.link-btn');
  if (!topicInput) return;

  topicInput.disabled = source === 'files';
  topicInput.placeholder = source === 'files'
    ? 'Using uploaded files only'
    : 'e.g. Photosynthesis, World War II, Linear Algebra';

  if (uploadArea && fileInput) {
    const disableUploads = source === 'web';
    uploadArea.classList.toggle('disabled', disableUploads);
    fileInput.disabled = disableUploads;
    if (browseBtn) browseBtn.disabled = disableUploads;
  }
}

window.addEventListener('DOMContentLoaded', updateStudySource);

// Enter-to-submit on topic input
document.getElementById('topic-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); startResearch(); }
});

// ── Notes ─────────────────────────────────────────────────────────────────────

function renderNotes(notes, topic) {
  const container = document.getElementById('notes-content');
  const genBtn = document.getElementById('generate-learning-btn');

  let html = `<div class="notes-summary">
    <h3>Summary — ${escHtml(topic)}</h3>
    <p>${escHtml(notes.summary || '')}</p>
  </div>`;

  if (notes.key_concepts?.length) {
    html += `<div class="notes-summary">
      <h3>Key Concepts</h3>
      <div class="key-concepts">
        ${notes.key_concepts.map(c => `<span class="concept-chip">${escHtml(c)}</span>`).join('')}
      </div>
    </div>`;
  }

  (notes.sections || []).forEach((sec, i) => {
    // Generate image URL using multiple fallback sources
    const searchQuery = sec.image_description 
      ? sec.image_description.split(' ').slice(0, 3).join('+')
      : sec.title.replace(/\s+/g, '+');
    
    // Create a hash for consistent seeding across sessions
    const hash = Math.abs(searchQuery.split('').reduce((a, b) => {a = ((a << 5) - a) + b.charCodeAt(0); return a & a;}, 0));
    
    // Use multiple image services with fallbacks
    const imageUrls = [
      `https://api.unsplash.com/photos/random?query=${encodeURIComponent(searchQuery)}&w=400&h=300&fit=crop&client_id=YOUR_CLIENT_ID`,
      `https://picsum.photos/400/300?random=${hash}`,
      `https://source.unsplash.com/400x300/?${searchQuery}`,
      'https://via.placeholder.com/400x300/5b5bf5/ffffff?text=Visual+Reference'
    ];
    
    // Use a working fallback since Unsplash may block direct requests
    const imageUrl = `https://picsum.photos/400/300?random=${hash + i}`;

    html += `<div class="accordion-item">
      <div class="accordion-header" onclick="toggleAccordion(${i})">
        ${escHtml(sec.title)} <span>+</span>
      </div>
      <div class="accordion-body" id="acc-${i}">
        <div class="section-content">
          <div class="section-text">${escHtml(sec.content)}</div>
          <div class="section-image">
            <img 
              src="${imageUrl}" 
              alt="Visual reference for ${escHtml(sec.title)}" 
              loading="lazy"
              onerror="this.src='https://via.placeholder.com/400x300/5b5bf5/ffffff?text=${encodeURIComponent((sec.title || 'Content').substring(0, 15).replace(/\s+/g, '+'))}'" 
            />
            ${sec.image_description ? `<p class="image-caption">${escHtml(sec.image_description)}</p>` : ''}
          </div>
        </div>
      </div>
    </div>`;
  });

  container.innerHTML = html;
  genBtn.style.display = 'inline-block';
}

function toggleAccordion(i) {
  const body = document.getElementById('acc-' + i);
  const header = body.previousElementSibling;
  const isOpen = body.classList.toggle('open');
  header.querySelector('span').textContent = isOpen ? '−' : '+';
}

// ── Flashcards & Quiz generation ─────────────────────────────────────────────

async function generateLearning() {
  const btn = document.getElementById('generate-learning-btn');
  const status = document.getElementById('learning-status');
  const flashcardsInput = document.getElementById('flashcards-count');
  const quizInput = document.getElementById('quiz-count');

  let numFlashcards = parseInt(flashcardsInput.value, 10);
  let numQuestions = parseInt(quizInput.value, 10);

  if (Number.isNaN(numFlashcards) || numFlashcards < 1) numFlashcards = 10;
  if (Number.isNaN(numQuestions) || numQuestions < 1) numQuestions = 5;
  numFlashcards = Math.min(Math.max(numFlashcards, 1), 30);
  numQuestions = Math.min(Math.max(numQuestions, 1), 20);

  btn.disabled = true;
  setStatus(status, 'Generating flashcards and quiz...');

  try {
    const res = await apiJson('/api/study/generate-learning', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        num_flashcards: numFlashcards,
        num_questions: numQuestions,
      }),
    });

    flashcards = res.flashcards || [];
    quizQuestions = res.quiz_questions || [];

    renderFlashcards();
    renderQuiz();
    state.learning = true;
    markCompleted('notes');
    updateTabLocks();
    setStatus(status, '');
    if (res.coins_awarded) await loadShopState();
    toast(
      `Created ${flashcards.length} flashcards and ${quizQuestions.length} quiz questions.${coinSuffix(res.coins_awarded)}`,
      'success'
    );
  } catch (err) {
    setStatus(status, 'Error: ' + err.message, true);
    toast(err.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

// ── Flashcards ────────────────────────────────────────────────────────────────

let healedCardKeys = new Set();

function renderFlashcards() {
  if (!flashcards.length) return;
  cardIndex = 0;
  healedCardKeys = new Set();
  showCard(0);
  document.getElementById('flashcard-nav').style.display = 'flex';
}

async function healFromFlashcard(cardKey) {
  if (!authToken) return;
  if (healedCardKeys.has(cardKey)) return;
  healedCardKeys.add(cardKey);
  try {
    const res = await apiJson('/api/plant/heal-flashcard', { method: 'POST' });
    if (res.plant) renderPlant(res.plant);
  } catch (err) {
    console.warn('Plant heal failed:', err.message);
  }
}

function showCard(i) {
  const card = flashcards[i];
  document.getElementById('flashcard-container').innerHTML = `
    <div class="flashcard-wrapper" onclick="flipCard(this)">
      <div class="flashcard" id="fc">
        <div class="flashcard-face flashcard-front">
          <div class="flashcard-label">Question</div>
          <div class="flashcard-text">${escHtml(card.front)}</div>
          <div class="flashcard-hint">Click or press Space to reveal</div>
        </div>
        <div class="flashcard-face flashcard-back">
          <div class="flashcard-label">Answer</div>
          <div class="flashcard-text">${escHtml(card.back)}</div>
        </div>
      </div>
    </div>`;
  document.getElementById('card-counter').textContent = `${i + 1} / ${flashcards.length}`;
  healFromFlashcard(`${sessionId || 'anon'}:${i}`);
}

function flipCard(wrapper) {
  wrapper.querySelector('.flashcard').classList.toggle('flipped');
}

function prevCard() {
  if (cardIndex > 0) showCard(--cardIndex);
}

function nextCard() {
  if (cardIndex < flashcards.length - 1) showCard(++cardIndex);
}

// Keyboard shortcuts for flashcards
document.addEventListener('keydown', e => {
  const activeTab = document.querySelector('.tab-section.active')?.id;
  if (activeTab !== 'tab-flashcards' || !flashcards.length) return;
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowLeft') { e.preventDefault(); prevCard(); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); nextCard(); }
  else if (e.key === ' ') {
    e.preventDefault();
    const wrapper = document.querySelector('.flashcard-wrapper');
    if (wrapper) flipCard(wrapper);
  }
});

// ── Quiz ──────────────────────────────────────────────────────────────────────

function renderQuiz() {
  if (!quizQuestions.length) return;
  const container = document.getElementById('quiz-container');
  document.getElementById('quiz-results').innerHTML = '';

  let html = '';
  quizQuestions.forEach((q, idx) => {
    html += `<div class="quiz-question">
      <p>Q${idx + 1}. ${escHtml(q.question)}</p>`;
    (q.options || []).forEach(opt => {
      const letter = opt.charAt(0);
      html += `<label class="option-label">
        <input type="radio" name="q${q.id}" value="${escHtml(letter)}" />
        ${escHtml(opt)}
      </label>`;
    });
    html += `</div>`;
  });

  container.innerHTML = html;
  document.getElementById('submit-quiz-btn').style.display = 'inline-block';
  document.getElementById('reset-quiz-btn').style.display = 'inline-block';
}

function resetQuiz() {
  document.getElementById('quiz-results').innerHTML = '';
  renderQuiz();
}

async function submitQuiz() {
  const answers = [];
  const unanswered = [];
  for (const q of quizQuestions) {
    const sel = document.querySelector(`input[name="q${q.id}"]:checked`);
    if (!sel) unanswered.push(q.id);
    answers.push({ question_id: q.id, selected: sel ? sel.value : '' });
  }

  if (unanswered.length) {
    if (!confirm(`You haven't answered ${unanswered.length} question${unanswered.length === 1 ? '' : 's'}. Submit anyway?`)) return;
  }

  const btn = document.getElementById('submit-quiz-btn');
  btn.disabled = true;

  try {
    const res = await apiJson('/api/quiz/submit', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, answers }),
    });

    renderQuizResults(res);
    markCompleted('quiz');
    if (res.coins_awarded || res.death_penalty) await loadShopState();
    if (res.plant) renderPlant(res.plant, res.wrong_count > 0 ? 'wither' : null);
    if (res.death_penalty) {
      setTimeout(() => toast(`Your plant died! Lost ${res.death_penalty} coins.`, 'error'), 400);
    } else {
      toast(`Scored ${res.score} / ${res.total}${coinSuffix(res.coins_awarded)}`, 'success');
    }
  } catch (err) {
    toast('Error submitting quiz: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

function renderQuizResults(res) {
  const weakHtml = res.weak_topics?.length
    ? res.weak_topics.map(t => `<span class="weak-tag">${escHtml(t)}</span>`).join(' ')
    : 'None identified';

  let html = `<div class="score-banner">
    <span><strong>Score:</strong> ${res.score} / ${res.total} (${res.percentage}%)</span>
    <span><strong>Weak areas:</strong> ${weakHtml}</span>
  </div>`;

  (res.results || []).forEach(r => {
    html += `<div class="quiz-result-item ${r.is_correct ? 'correct' : 'wrong'}">
      <strong>${escHtml(r.question)}</strong><br/>
      Your answer: <strong>${escHtml(r.selected)}</strong>
      ${!r.is_correct ? ` — Correct: <strong>${escHtml(r.correct_answer)}</strong>` : ' ✓'}
      <br/><em>${escHtml(r.explanation)}</em>
    </div>`;
  });

  document.getElementById('quiz-results').innerHTML = html;
  document.getElementById('quiz-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Study Plan ────────────────────────────────────────────────────────────────

async function generatePlan() {
  const days = parseInt(document.getElementById('days-input').value) || 7;
  const hours = parseFloat(document.getElementById('hours-input').value) || 2;
  const status = document.getElementById('plan-status');
  setStatus(status, 'Building your personalized study plan...');

  try {
    const res = await apiJson('/api/plan/generate', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, available_days: days, hours_per_day: hours }),
    });

    renderPlan(res.plan || []);
    markCompleted('plan');
    setStatus(status, '');
    if (res.coins_awarded) await loadShopState();
    toast(`Study plan ready.${coinSuffix(res.coins_awarded)}`, 'success');
  } catch (err) {
    setStatus(status, 'Error: ' + err.message, true);
    toast(err.message, 'error');
  }
}

function renderPlan(plan) {
  const container = document.getElementById('plan-content');
  if (!plan.length) { container.innerHTML = '<p class="placeholder">No plan generated.</p>'; return; }

  let html = '';
  plan.forEach(day => {
    html += `<div class="plan-day">
      <div class="plan-day-header">Day ${day.day}${day.focus ? ' — ' + escHtml(day.focus) : ''}</div>`;
    (day.tasks || []).forEach(task => {
      const priority = (task.priority || 'medium').toLowerCase();
      html += `<div class="plan-task">
        <div class="task-dot ${priority}" title="${priority} priority"></div>
        <div class="task-info">
          <strong>${escHtml(task.topic)}${task.is_weak_area ? '<span class="weak-badge">WEAK AREA</span>' : ''}</strong>
          <span>${escHtml(task.activity)}</span>
        </div>
        <div class="task-duration">${task.duration_mins} min</div>
      </div>`;
    });
    html += `</div>`;
  });

  container.innerHTML = html;
}

// Shop

async function loadShopState() {
  if (!authToken) return;
  try {
    shopState = await apiJson('/api/shop/state', { method: 'GET' });
    renderCoinBadge();
    renderShop();
    if (shopState.plant) renderPlant(shopState.plant);
  } catch (err) {
    console.warn('Could not load shop state:', err.message);
  }
}

function renderCoinBadge() {
  const badge = document.getElementById('coin-badge');
  if (!badge) return;
  const coins = shopState?.coins ?? 0;
  const rate = shopState?.coin_rate_per_minute ?? 0;
  badge.textContent = `$ ${coins}`;
  badge.title = rate ? `${rate} coins per minute while studying` : 'Coins earned while studying';
}

function renderShop() {
  if (!shopState) return;
  const total = document.getElementById('shop-coin-total');
  const rate = document.getElementById('shop-coin-rate');
  const time = document.getElementById('shop-study-time');
  const grid = document.getElementById('shop-grid');
  if (!grid) return;

  total.textContent = shopState.coins;
  rate.textContent = `${shopState.coin_rate_per_minute}/min`;
  time.textContent = formatStudyTime(shopState.study_seconds || 0);

  grid.innerHTML = (shopState.upgrades || []).map(upgrade => {
    const pct = Math.round((upgrade.level / upgrade.max_level) * 100);
    const buttonText = upgrade.maxed ? 'Maxed' : `${upgrade.next_cost} coins`;
    const disabled = upgrade.maxed || !upgrade.affordable;
    return `<article class="shop-card ${upgrade.maxed ? 'maxed' : ''}">
      <div class="shop-card-head">
        <div>
          <h3>${escHtml(upgrade.name)}</h3>
          <span class="shop-effect">${escHtml(upgrade.effect_label)}</span>
        </div>
        <span class="shop-level">Lv ${upgrade.level}/${upgrade.max_level}</span>
      </div>
      <p>${escHtml(upgrade.description)}</p>
      <div class="shop-progress" aria-hidden="true"><span style="width:${pct}%"></span></div>
      <button class="btn-primary shop-buy-btn" type="button" onclick="buyUpgrade('${escHtml(upgrade.id)}')" ${disabled ? 'disabled' : ''}>
        ${escHtml(buttonText)}
      </button>
    </article>`;
  }).join('');
}

async function buyUpgrade(upgradeId) {
  try {
    const res = await apiJson('/api/shop/purchase', {
      method: 'POST',
      body: JSON.stringify({ upgrade_id: upgradeId }),
    });
    shopState = res.state;
    renderCoinBadge();
    renderShop();
    toast(`Upgrade purchased. Level ${res.level}.`, 'success');
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ── Settings ─────────────────────────────────────────────────────────────────

const SETTINGS_DEFAULTS = {
  darkMode: false,
  compactMode: false,
  toasts: true,
  sound: false,
  defaultFlashcards: 10,
  defaultQuiz: 5,
  defaultPlanDays: 7,
  defaultPlanHours: 2,
};

let settings = loadSettingsFromStorage();

function loadSettingsFromStorage() {
  try {
    const raw = localStorage.getItem('app_settings');
    return raw ? { ...SETTINGS_DEFAULTS, ...JSON.parse(raw) } : { ...SETTINGS_DEFAULTS };
  } catch {
    return { ...SETTINGS_DEFAULTS };
  }
}

function saveSettings() {
  localStorage.setItem('app_settings', JSON.stringify(settings));
}

function applySettings() {
  document.body.classList.toggle('dark-mode', !!settings.darkMode);
  document.body.classList.toggle('compact-mode', !!settings.compactMode);
  const fc = document.getElementById('flashcards-count');
  const qc = document.getElementById('quiz-count');
  const pd = document.getElementById('days-input');
  const ph = document.getElementById('hours-input');
  if (fc) fc.value = settings.defaultFlashcards;
  if (qc) qc.value = settings.defaultQuiz;
  if (pd) pd.value = settings.defaultPlanDays;
  if (ph) ph.value = settings.defaultPlanHours;
}

function updateSetting(key, value) {
  settings[key] = value;
  saveSettings();
  if (key === 'darkMode' || key === 'compactMode') {
    document.body.classList.add('theme-switching');
    applySettings();
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.body.classList.remove('theme-switching');
      });
    });
  } else {
    applySettings();
  }
}

function openSettings() {
  const overlay = document.getElementById('settings-overlay');
  if (!overlay) return;
  document.getElementById('setting-dark-mode').checked = !!settings.darkMode;
  document.getElementById('setting-compact').checked = !!settings.compactMode;
  document.getElementById('setting-toasts').checked = !!settings.toasts;
  document.getElementById('setting-sound').checked = !!settings.sound;
  document.getElementById('setting-flashcards').value = settings.defaultFlashcards;
  document.getElementById('setting-quiz').value = settings.defaultQuiz;
  document.getElementById('setting-plan-days').value = settings.defaultPlanDays;
  document.getElementById('setting-plan-hours').value = settings.defaultPlanHours;
  document.getElementById('settings-email').textContent = currentUser?.email || '—';
  overlay.style.display = 'flex';
}

function closeSettings() {
  const overlay = document.getElementById('settings-overlay');
  if (overlay) overlay.style.display = 'none';
}

function handleSettingsBackdrop(e) {
  if (e.target.id === 'settings-overlay') closeSettings();
}

function resetSettings() {
  if (!confirm('Reset all settings to defaults?')) return;
  settings = { ...SETTINGS_DEFAULTS };
  saveSettings();
  applySettings();
  openSettings();
  toast('Settings reset to defaults.', 'success');
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    const ov = document.getElementById('settings-overlay');
    if (ov && ov.style.display === 'flex') closeSettings();
  }
});

// ── Profile ──────────────────────────────────────────────────────────────────

let profileData = null;
let selectedLevelId = null;

async function loadProfile() {
  if (!authToken) return;
  try {
    profileData = await apiJson('/api/profile/', { method: 'GET' });
    renderProfile();
  } catch (err) {
    toast('Could not load profile: ' + err.message, 'error');
  }
}

function renderProfile() {
  if (!profileData) return;
  const { stats, quiz_history, plant, levels } = profileData;

  document.getElementById('profile-study-time').textContent = formatStudyTime(stats.study_seconds || 0);
  document.getElementById('profile-coins').textContent = stats.coins;
  document.getElementById('profile-quizzes').textContent = stats.total_quizzes;
  document.getElementById('profile-avg-score').textContent = stats.avg_percentage + '%';

  // Quiz history
  const historyEl = document.getElementById('profile-history');
  if (!quiz_history.length) {
    historyEl.innerHTML = '<div class="profile-history-empty">No quizzes taken yet.</div>';
  } else {
    historyEl.innerHTML = quiz_history.map(q => {
      const pct = q.percentage ?? 0;
      const cls = pct >= 80 ? '' : pct >= 50 ? 'mid' : 'low';
      return `<div class="profile-history-item">
        <span class="topic">${escHtml(q.topic)}</span>
        <span class="score">${q.score}/${q.total}</span>
        <span class="pct ${cls}">${pct}%</span>
      </div>`;
    }).join('');
  }

  // Plant visual
  const artEl = document.getElementById('profile-plant-art');
  if (plant.health <= 0) {
    artEl.innerHTML = `<img src="${PLANT_DEAD_SPRITE}" alt="withered plant" class="plant-sprite" draggable="false">`;
  } else {
    artEl.innerHTML = plantImg(spriteForState(plant));
  }
  artEl.className = 'profile-plant-art skin-' + (plant.skin || 'default');
  document.getElementById('profile-plant-stage').textContent = plant.stage_name;
  document.getElementById('profile-plant-xp').textContent = plant.xp + ' XP';
  const fill = document.getElementById('profile-plant-health-fill');
  fill.style.width = plant.health + '%';
  if (plant.health > 60) fill.style.background = 'linear-gradient(90deg,#66BB6A,#43A047)';
  else if (plant.health > 30) fill.style.background = 'linear-gradient(90deg,#FDD835,#F9A825)';
  else fill.style.background = 'linear-gradient(90deg,#EF5350,#C62828)';

  // Vertical level tabs
  const tabsEl = document.getElementById('profile-level-tabs');
  tabsEl.innerHTML = levels.map(lvl => {
    const classes = ['level-tab'];
    if (!lvl.reached) classes.push('locked');
    if (lvl.claimed) classes.push('claimed');
    if (lvl.equipped) classes.push('equipped');
    if (selectedLevelId === lvl.id) classes.push('active');
    let tag = '';
    if (lvl.equipped) tag = 'Equipped';
    else if (lvl.claimed) tag = 'Owned';
    else if (lvl.reached) tag = `+${lvl.coin_reward}`;
    else tag = `${lvl.min_xp}xp`;
    const sprite = LEVEL_SPRITES[lvl.id] || FALLBACK_SPRITE;
    return `<button type="button" class="${classes.join(' ')}" onclick="selectLevel('${lvl.id}')">
      <img class="level-tab-sprite" src="${sprite}" alt="" draggable="false">
      <span>${escHtml(lvl.name)}</span>
      <span class="level-tab-tag">${escHtml(tag)}</span>
    </button>`;
  }).join('');

  // Keep description in sync with current selection
  if (selectedLevelId) {
    const stillExists = levels.find(l => l.id === selectedLevelId);
    if (stillExists) renderLevelDescription(stillExists);
    else selectedLevelId = null;
  }
}

function selectLevel(levelId) {
  if (!profileData) return;
  selectedLevelId = levelId;
  const lvl = profileData.levels.find(l => l.id === levelId);
  if (!lvl) return;
  // Mark active on tabs
  document.querySelectorAll('#profile-level-tabs .level-tab').forEach(el => el.classList.remove('active'));
  const idx = profileData.levels.findIndex(l => l.id === levelId);
  const el = document.querySelectorAll('#profile-level-tabs .level-tab')[idx];
  if (el) el.classList.add('active');
  renderLevelDescription(lvl);
}

function renderLevelDescription(lvl) {
  const desc = document.getElementById('profile-plant-desc');
  const action = lvl.reached
    ? (lvl.claimed
        ? (lvl.equipped
            ? `<button class="profile-plant-claim-btn" disabled>Skin equipped</button>`
            : `<button class="profile-plant-claim-btn" onclick="claimLevel('${lvl.id}')">Equip skin</button>`)
        : `<button class="profile-plant-claim-btn" onclick="claimLevel('${lvl.id}')">Claim +${lvl.coin_reward} coins &amp; skin</button>`)
    : `<button class="profile-plant-claim-btn" disabled>Locked — reach ${lvl.min_xp} XP</button>`;

  const previewSprite = LEVEL_SPRITES[lvl.id] || FALLBACK_SPRITE;
  desc.innerHTML = `
    <div class="profile-plant-desc-title">${escHtml(lvl.name)}</div>
    <img class="profile-plant-desc-preview" src="${previewSprite}" alt="${escHtml(lvl.name)} plant" draggable="false">
    <p class="profile-plant-desc-body">${escHtml(lvl.description)}</p>
    <div class="profile-plant-desc-meta">
      <span>Requires ${lvl.min_xp} XP</span>
      <span>Skin: ${escHtml(lvl.skin)}</span>
      <span>Reward: +${lvl.coin_reward} coins</span>
    </div>
    ${action}
  `;
}

async function claimLevel(levelId) {
  try {
    const res = await apiJson('/api/profile/claim', {
      method: 'POST',
      body: JSON.stringify({ level_id: levelId }),
    });
    profileData.plant = res.plant;
    profileData.levels = res.levels;
    if (res.shop) {
      shopState = res.shop;
      profileData.stats.coins = shopState.coins;
      profileData.stats.earned_coins = shopState.earned_coins;
      renderCoinBadge();
      renderShop();
    }
    renderPlant(res.plant);
    renderProfile();
    if (res.coins_awarded) {
      toast(`Claimed ${res.coins_awarded} coins & equipped ${res.skin} skin!`, 'success');
    } else {
      toast(`Equipped ${res.skin} skin.`, 'success');
    }
  } catch (err) {
    toast(err.message, 'error');
  }
}

let adminTriggerCount = 0;
let adminTriggerTimer = null;
function adminTriggerClick() {
  clearTimeout(adminTriggerTimer);
  adminTriggerCount++;
  if (adminTriggerCount >= 5) {
    adminTriggerCount = 0;
    document.getElementById('admin-unlock-btn').style.display = 'inline-block';
  }
  adminTriggerTimer = setTimeout(() => { adminTriggerCount = 0; }, 2000);
}

async function adminUnlock() {
  try {
    const res = await apiJson('/api/profile/admin-unlock', { method: 'POST' });
    profileData.plant = res.plant;
    profileData.levels = res.levels;
    if (res.shop) {
      shopState = res.shop;
      profileData.stats.coins = shopState.coins;
      profileData.stats.earned_coins = shopState.earned_coins;
      renderCoinBadge();
      renderShop();
    }
    renderPlant(res.plant);
    renderProfile();
    document.getElementById('admin-unlock-btn').style.display = 'none';
    toast('Admin mode: all skins unlocked & 9999 coins granted!', 'success');
  } catch (err) {
    toast(err.message, 'error');
  }
}

function startStudyTicker() {
  clearInterval(studyTickTimer);
  lastStudyTickMs = Date.now();
  studyTickTimer = setInterval(recordStudyTick, 60000);
}

async function recordStudyTick() {
  if (!authToken) return;
  if (document.hidden) {
    lastStudyTickMs = Date.now();
    return;
  }

  const now = Date.now();
  const elapsed = Math.min(300, Math.floor((now - (lastStudyTickMs || now)) / 1000));
  if (elapsed < 30) return;
  lastStudyTickMs = now;

  try {
    const res = await apiJson('/api/shop/study-tick', {
      method: 'POST',
      body: JSON.stringify({ elapsed_seconds: elapsed }),
    });
    shopState = res.state;
    renderCoinBadge();
    renderShop();
    if (res.plant) renderPlant(res.plant);
  } catch (err) {
    console.warn('Study coin tick failed:', err.message);
  }
}

document.addEventListener('visibilitychange', () => {
  lastStudyTickMs = Date.now();
});

function formatStudyTime(seconds) {
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const rest = mins % 60;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

function coinSuffix(amount) {
  return amount ? ` +${amount} coins` : '';
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function setStatus(el, msg, isError = false) {
  el.innerHTML = msg ? `<span class="spinner"></span>${escHtml(msg)}` : '';
  el.classList.toggle('error', isError);
  if (isError) el.textContent = msg;
}

async function apiJson(path, options = {}) {
  const opts = { ...options, headers: { ...(options.headers || {}) } };
  if (authToken) opts.headers['Authorization'] = 'Bearer ' + authToken;
  if (typeof opts.body === 'string' && !opts.headers['Content-Type']) {
    opts.headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(API + path, opts);
  const text = await response.text();
  let data = {};

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (response.status === 401 && !path.startsWith('/api/auth/')) {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('auth_token');
    showAuth();
    throw new Error('Session expired — please sign in again.');
  }

  if (!response.ok) {
    throw new Error(formatApiError(response, data));
  }

  return data;
}

function formatApiError(response, data) {
  const detail = data.detail || data.message || response.statusText || 'Request failed';
  if (Array.isArray(detail)) {
    return `${response.status} ${detail.map(formatValidationError).join('; ')}`;
  }
  return `${response.status} ${detail}`;
}

function formatValidationError(err) {
  if (err?.msg) {
    const loc = Array.isArray(err.loc) ? err.loc.join('.') : '';
    return loc ? `${loc}: ${err.msg}` : err.msg;
  }
  return String(err);
}

let toastTimer;
function toast(msg, kind = '') {
  if (settings && settings.toasts === false) return;
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = 'toast show ' + kind;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast ' + kind; }, 3200);
}

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/`/g, '&#96;')
    .replace(/\//g, '&#47;');
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function bootstrap() {
  applySettings();
  if (!authToken) {
    showAuth();
    return;
  }
  try {
    const res = await apiJson('/api/auth/me', { method: 'GET' });
    currentUser = res.user;
    showApp();
    handleSpotifyReturn();
    updateTabLocks();
    await loadShopState();
    startStudyTicker();
    await loadSessionList();
  } catch {
    showAuth();
  }
}

bootstrap();
