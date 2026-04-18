const API = '';
let sessionId = localStorage.getItem('study_session_id') || null;
let flashcards = [];
let cardIndex = 0;
let quizQuestions = [];

const state = {
  notes: false,
  learning: false,
};

// ── Session ──────────────────────────────────────────────────────────────────

function setSession(id) {
  sessionId = id;
  localStorage.setItem('study_session_id', id);
  const badge = document.getElementById('session-badge');
  badge.textContent = 'session: ' + id.slice(0, 8);
}

function resetSession() {
  if (!confirm('Start a new session? Your current notes, flashcards, quiz and plan will be cleared from this page.')) return;
  localStorage.removeItem('study_session_id');
  sessionId = null;
  flashcards = [];
  quizQuestions = [];
  cardIndex = 0;
  state.notes = false;
  state.learning = false;
  pendingFiles.length = 0;
  document.getElementById('session-badge').textContent = '';
  document.getElementById('topic-input').value = '';
  renderFileList();
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
      const r = await fetch(API + '/api/upload', { method: 'POST', body: form }).then(r => r.json());
      setSession(r.session_id);
      for (let i = 1; i < pendingFiles.length; i++) {
        const f2 = new FormData();
        f2.append('file', pendingFiles[i]);
        f2.append('session_id', sessionId);
        await fetch(API + '/api/upload', { method: 'POST', body: f2 });
      }
      setStatus(status, 'Searching the web...');
    }

    const res = await fetch(API + '/api/study/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, session_id: sessionId }),
    }).then(r => r.json());

    setSession(res.session_id);
    renderNotes(res.notes, topic);
    state.notes = true;
    markCompleted('research');
    updateTabLocks();
    setStatus(status, '');
    toast('Notes ready! Taking you to the Notes tab.', 'success');
    setTimeout(() => switchTab('notes'), 600);
  } catch (err) {
    setStatus(status, 'Error: ' + err.message, true);
    toast('Something went wrong — check the console.', 'error');
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
  btn.disabled = true;
  setStatus(status, 'Generating flashcards and quiz...');

  try {
    const res = await fetch(API + '/api/study/generate-learning', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, num_flashcards: 10, num_questions: 5 }),
    }).then(r => r.json());

    flashcards = res.flashcards || [];
    quizQuestions = res.quiz_questions || [];

    renderFlashcards();
    renderQuiz();
    state.learning = true;
    markCompleted('notes');
    updateTabLocks();
    setStatus(status, '');
    toast(`Created ${flashcards.length} flashcards and ${quizQuestions.length} quiz questions.`, 'success');
  } catch (err) {
    setStatus(status, 'Error: ' + err.message, true);
    toast('Failed to generate — check the console.', 'error');
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
    const res = await fetch(API + '/api/quiz/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, answers }),
    }).then(r => r.json());

    renderQuizResults(res);
    markCompleted('quiz');
    toast(`Scored ${res.score} / ${res.total}`, 'success');
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
    const res = await fetch(API + '/api/plan/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, available_days: days, hours_per_day: hours }),
    }).then(r => r.json());

    renderPlan(res.plan || []);
    markCompleted('plan');
    setStatus(status, '');
    toast('Study plan ready.', 'success');
  } catch (err) {
    setStatus(status, 'Error: ' + err.message, true);
    toast('Failed to generate plan.', 'error');
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

// ── Helpers ───────────────────────────────────────────────────────────────────

function setStatus(el, msg, isError = false) {
  el.innerHTML = msg ? `<span class="spinner"></span>${escHtml(msg)}` : '';
  el.classList.toggle('error', isError);
  if (isError) el.textContent = msg;
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

if (sessionId) {
  document.getElementById('session-badge').textContent = 'session: ' + sessionId.slice(0, 8);
}

updateTabLocks();
