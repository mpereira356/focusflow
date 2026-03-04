/**
 * FocusFlow - Real-time Timer Engine
 * Manages per-task timers with persistence to backend
 */

var timers = {};  // taskId -> { interval, elapsed, duration, status }

function canUseBrowserNotification() {
  return typeof window !== 'undefined' && 'Notification' in window;
}

function requestNotificationPermissionIfNeeded() {
  if (!canUseBrowserNotification()) return;
  if (Notification.permission === 'default') {
    Notification.requestPermission().catch(function() {});
  }
}

function notifyTimerCompleted(taskName) {
  if (!canUseBrowserNotification()) return;
  if (Notification.permission !== 'granted') return;

  var title = 'Tempo finalizado';
  var body = taskName ? ('A tarefa "' + taskName + '" foi concluida.') : 'Sua sessao foi concluida.';
  try {
    new Notification(title, { body: body });
  } catch (e) {
    console.error(e);
  }
}

function getTasksApiBase() {
  var taskLink = document.querySelector('a[href*="/tasks/"]');
  if (!taskLink) return '/tasks';

  var href = taskLink.getAttribute('href') || '';
  var idx = href.indexOf('/tasks/');
  return idx >= 0 ? href.slice(0, idx + 6) : '/tasks';
}

function apiUrl(path) {
  return getTasksApiBase() + path;
}

function requestJson(url, options) {
  return fetch(url, options).then(function(r) {
    var contentType = (r.headers.get('content-type') || '').toLowerCase();
    if (!contentType.includes('application/json')) {
      throw new Error('Resposta nao-JSON (possivel redirect de login ou erro interno).');
    }
    return r.json();
  });
}

function findActionButton(target) {
  var el = target;
  while (el && el !== document) {
    if (el.matches && el.matches('.ctrl-btn[data-action][data-task-id]')) {
      return el;
    }
    el = el.parentNode;
  }
  return null;
}

/**
 * Initialize timers from server-rendered data attributes
 */
document.addEventListener('DOMContentLoaded', function() {
  requestNotificationPermissionIfNeeded();

  var cards = document.querySelectorAll('.task-card[data-task-id]');
  cards.forEach(function(card) {
    var taskId   = parseInt(card.dataset.taskId, 10);
    var duration = parseInt(card.dataset.duration, 10);
    var elapsed  = parseInt(card.dataset.elapsed, 10);
    var status   = card.dataset.status || 'pending';
    var taskName = card.dataset.taskName || '';

    if (!taskId || isNaN(duration) || isNaN(elapsed)) {
      return;
    }

    timers[taskId] = {
      elapsed:  elapsed,
      duration: duration,
      taskName: taskName,
      status:   status,
      interval: null
    };

    updateUI(taskId);

    if (status === 'running') {
      startLocalTimer(taskId);
    }
  });

  // Reliable controls binding (works even if inline onclick is blocked)
  document.addEventListener('click', function(e) {
    var btn = findActionButton(e.target);
    if (!btn) return;

    e.preventDefault();
    var taskId = parseInt(btn.dataset.taskId, 10);
    var action = btn.dataset.action;
    if (!taskId || !action) return;

    if (action === 'start') timerStart(taskId);
    if (action === 'pause') timerPause(taskId);
    if (action === 'reset') timerReset(taskId);
  });
});

/* ─── Public API ─────────────────────────────────────────── */

function timerStart(taskId) {
  var t = timers[taskId];
  if (!t) return;
  requestNotificationPermissionIfNeeded();

  requestJson(apiUrl('/api/timer/start/' + taskId), { method: 'POST', credentials: 'same-origin' })
    .then(function(data) {
      if (data.error) { alert(data.error); return; }
      t.elapsed  = data.session.time_completed;
      t.duration = data.duration_seconds;
      t.status   = 'running';
      // Stop any other running timer locally
      Object.keys(timers).forEach(function(id) {
        if (parseInt(id) !== taskId && timers[id].status === 'running') {
          stopLocalTimer(parseInt(id));
          timers[id].status = 'paused';
          updateUI(parseInt(id));
        }
      });
      startLocalTimer(taskId);
      updateUI(taskId);
    })
    .catch(function(err) {
      showToast('Nao foi possivel iniciar o timer. Verifique a conexao.');
      console.error(err);
    });
}

function timerPause(taskId) {
  var t = timers[taskId];
  if (!t || t.status !== 'running') return;
  stopLocalTimer(taskId);
  // Sync elapsed to server
  syncToServer(taskId, t.elapsed, function(data) {
    requestJson(apiUrl('/api/timer/pause/' + taskId), { method: 'POST', credentials: 'same-origin' })
      .then(function(data) {
        t.status = 'paused';
        updateUI(taskId);
      })
      .catch(function(err) {
        showToast('Falha ao pausar o timer.');
        console.error(err);
      });
  });
}

function timerReset(taskId) {
  stopLocalTimer(taskId);
  requestJson(apiUrl('/api/timer/reset/' + taskId), { method: 'POST', credentials: 'same-origin' })
    .then(function(data) {
      var t = timers[taskId];
      if (!t) return;
      t.elapsed = 0;
      t.status  = 'pending';
      updateUI(taskId);
    })
    .catch(function(err) {
      showToast('Falha ao resetar o timer.');
      console.error(err);
    });
}

/* ─── Internal ───────────────────────────────────────────── */

function startLocalTimer(taskId) {
  var t = timers[taskId];
  if (t.interval) clearInterval(t.interval);

  t.interval = setInterval(function() {
    t.elapsed += 1;
    if (t.elapsed >= t.duration) {
      t.elapsed = t.duration;
      stopLocalTimer(taskId);
      t.status = 'completed';
      syncToServer(taskId, t.elapsed, null);
      updateUI(taskId);
      showToast('Tarefa concluida! Excelente foco!');
      notifyTimerCompleted(t.taskName);
      return;
    }
    updateUI(taskId);
    // Sync to server every 10 seconds
    if (t.elapsed % 10 === 0) {
      syncToServer(taskId, t.elapsed, null);
    }
  }, 1000);
}

function stopLocalTimer(taskId) {
  var t = timers[taskId];
  if (t && t.interval) {
    clearInterval(t.interval);
    t.interval = null;
  }
}

function syncToServer(taskId, elapsed, callback) {
  requestJson(apiUrl('/api/timer/sync/' + taskId), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ elapsed_seconds: elapsed })
  })
  .then(function(data) {
    if (callback) callback(data);
  })
  .catch(function(err) {
    console.error(err);
  });
}

/* ─── UI update ──────────────────────────────────────────── */

function updateUI(taskId) {
  var t = timers[taskId];
  if (!t) return;

  var card = document.getElementById('card-' + taskId);
  if (!card) return;

  var remaining = Math.max(0, t.duration - t.elapsed);
  var progress  = t.duration > 0 ? Math.min(100, Math.round((t.elapsed / t.duration) * 100)) : 0;

  // Time display
  var timeEl = document.getElementById('time-' + taskId);
  if (timeEl) {
    var mins = Math.floor(remaining / 60);
    var secs = remaining % 60;
    timeEl.textContent = pad(mins) + ':' + pad(secs);
  }

  // SVG ring (circumference = 2*pi*42 = ~263.9)
  var ringEl = document.getElementById('ring-' + taskId);
  if (ringEl) {
    var offset = 264 - (264 * progress / 100);
    ringEl.style.strokeDashoffset = offset;
  }

  // Linear progress fill
  var fillEl = document.getElementById('fill-' + taskId);
  if (fillEl) fillEl.style.width = progress + '%';

  // Percentage text
  var pctEl = document.getElementById('pct-' + taskId);
  if (pctEl) pctEl.textContent = progress + '%';

  // Card class
  card.classList.remove('running', 'completed');
  if (t.status === 'running') card.classList.add('running');
  if (t.status === 'completed') card.classList.add('completed');

  // Button visibility
  var playBtn  = document.getElementById('btn-play-'  + taskId);
  var pauseBtn = document.getElementById('btn-pause-' + taskId);
  if (playBtn && pauseBtn) {
    if (t.status === 'running') {
      playBtn.classList.add('hidden');
      pauseBtn.classList.remove('hidden');
    } else {
      playBtn.classList.remove('hidden');
      pauseBtn.classList.add('hidden');
    }
    playBtn.disabled  = (t.status === 'completed');
    pauseBtn.disabled = (t.status !== 'running');
  }
}

function pad(n) {
  return n < 10 ? '0' + n : '' + n;
}

// Sync on page unload to persist state
window.addEventListener('beforeunload', function() {
  Object.keys(timers).forEach(function(id) {
    var t = timers[id];
    if (t.status === 'running') {
      syncToServer(parseInt(id), t.elapsed, null);
    }
  });
});
