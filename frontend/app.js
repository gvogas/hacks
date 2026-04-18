const API = '';
let sessionId = localStorage.getItem('study_session_id') || null;
let authToken = localStorage.getItem('auth_token') || null;
let currentUser = null;
let authMode = 'login'; // 'login' | 'signup'
let flashcards = [];
let cardIndex = 0;
let quizQuestions = [];
let shopState = null;
let studyTickTimer = null;
let lastStudyTickMs = null;

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
  if (currentUser) {
    document.getElementById('user-badge').textContent = currentUser.email;
  }
  if (sessionId) {
    document.getElementById('session-badge').textContent = 'session: ' + sessionId.slice(0, 8);
  }
  renderCoinBadge();
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
  const topic = document.getElementById('topic-input').value.trim();
  if (!topic) {
    toast('Please enter a topic first.', 'error');
    document.getElementById('topic-input').focus();
    return;
  }

  const btn = document.getElementById('start-btn');
  const status = document.getElementById('research-status');
  btn.disabled = true;
  setStatus(status, pendingFiles.length ? 'Uploading files...' : 'Searching the web...');

  try {
    if (pendingFiles.length) {
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
      setStatus(status, 'Searching the web...');
    }

    const res = await apiJson('/api/study/start', {
      method: 'POST',
      body: JSON.stringify({ topic, session_id: sessionId }),
    });

    setSession(res.session_id);
    renderNotes(res.notes, topic);
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
    html += `<div class="accordion-item">
      <div class="accordion-header" onclick="toggleAccordion(${i})">
        ${escHtml(sec.title)} <span>+</span>
      </div>
      <div class="accordion-body" id="acc-${i}">${escHtml(sec.content)}</div>
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

function renderFlashcards() {
  if (!flashcards.length) return;
  cardIndex = 0;
  showCard(0);
  document.getElementById('flashcard-nav').style.display = 'flex';
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
    if (res.coins_awarded) await loadShopState();
    toast(`Scored ${res.score} / ${res.total}${coinSuffix(res.coins_awarded)}`, 'success');
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
    .replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function bootstrap() {
  if (!authToken) {
    showAuth();
    return;
  }
  try {
    const res = await apiJson('/api/auth/me', { method: 'GET' });
    currentUser = res.user;
    showApp();
    updateTabLocks();
    await loadShopState();
    startStudyTicker();
    await loadSessionList();
  } catch {
    showAuth();
  }
}

bootstrap();
