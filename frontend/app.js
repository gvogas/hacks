const API = '';
let sessionId = localStorage.getItem('study_session_id') || null;
let flashcards = [];
let cardIndex = 0;
let quizQuestions = [];

// ── Session ──────────────────────────────────────────────────────────────────

function setSession(id) {
  sessionId = id;
  localStorage.setItem('study_session_id', id);
  const badge = document.getElementById('session-badge');
  badge.textContent = 'session: ' + id.slice(0, 8);
}

// ── Tab switching ─────────────────────────────────────────────────────────────

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === name);
  });
  document.querySelectorAll('.tab-section').forEach(s => {
    s.classList.toggle('active', s.id === 'tab-' + name);
  });
}

// ── File upload ───────────────────────────────────────────────────────────────

const pendingFiles = [];

document.getElementById('file-input').addEventListener('change', e => {
  for (const f of e.target.files) pendingFiles.push(f);
  renderFileList();
});

function renderFileList() {
  document.getElementById('file-list').textContent =
    pendingFiles.length ? pendingFiles.map(f => '✓ ' + f.name).join('  ') : '';
}

async function uploadFiles(sid) {
  for (const file of pendingFiles) {
    const form = new FormData();
    form.append('file', file);
    form.append('session_id', sid);
    await fetch(API + '/api/upload', { method: 'POST', body: form });
  }
}

// ── Research ──────────────────────────────────────────────────────────────────

async function startResearch() {
  const topic = document.getElementById('topic-input').value.trim();
  if (!topic) { alert('Please enter a topic.'); return; }

  const btn = document.getElementById('start-btn');
  const status = document.getElementById('research-status');
  btn.disabled = true;
  setStatus(status, 'Uploading files...');

  try {
    // Upload files first (creates session if needed)
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
    }

    setStatus(status, 'Searching the web...');
    const res = await fetch(API + '/api/study/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, session_id: sessionId }),
    }).then(r => r.json());

    setSession(res.session_id);
    renderNotes(res.notes, topic);
    setStatus(status, 'Done! Notes are ready.');
    switchTab('notes');
  } catch (err) {
    setStatus(status, 'Error: ' + err.message, true);
  } finally {
    btn.disabled = false;
  }
}

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
    setStatus(status, `Generated ${flashcards.length} flashcards and ${quizQuestions.length} quiz questions.`);
  } catch (err) {
    setStatus(status, 'Error: ' + err.message, true);
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
          <div class="flashcard-hint">Click to reveal answer</div>
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
  for (const q of quizQuestions) {
    const sel = document.querySelector(`input[name="q${q.id}"]:checked`);
    answers.push({ question_id: q.id, selected: sel ? sel.value : '' });
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
  } catch (err) {
    alert('Error submitting quiz: ' + err.message);
  } finally {
    btn.disabled = false;
  }
}

function renderQuizResults(res) {
  const weakHtml = res.weak_topics?.length
    ? res.weak_topics.map(t => `<span class="weak-tag">${escHtml(t)}</span>`).join(' ')
    : 'None identified';

  let html = `<div class="score-banner">
    Score: ${res.score} / ${res.total} (${res.percentage}%)
    &nbsp;&nbsp;|&nbsp;&nbsp; Weak areas: ${weakHtml}
  </div>`;

  (res.results || []).forEach(r => {
    html += `<div class="quiz-result-item ${r.is_correct ? 'correct' : 'wrong'}">
      <strong>${escHtml(r.question)}</strong><br/>
      Your answer: <strong>${escHtml(r.selected)}</strong>
      ${!r.is_correct ? ` &mdash; Correct: <strong>${escHtml(r.correct_answer)}</strong>` : ' ✓'}
      <br/><em>${escHtml(r.explanation)}</em>
    </div>`;
  });

  document.getElementById('quiz-results').innerHTML = html;
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
    setStatus(status, '');
  } catch (err) {
    setStatus(status, 'Error: ' + err.message, true);
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
        <div class="task-dot ${priority}"></div>
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
