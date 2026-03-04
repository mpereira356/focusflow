// FocusFlow - App utilities

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  sidebar.classList.toggle('open');
  overlay.classList.toggle('open');
}

function togglePassword(inputId, btn) {
  const input = document.getElementById(inputId);
  const icon = btn.querySelector('.material-icons-round');
  if (input.type === 'password') {
    input.type = 'text';
    icon.textContent = 'visibility_off';
  } else {
    input.type = 'password';
    icon.textContent = 'visibility';
  }
}

function showToast(message) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  const msg = document.getElementById('toastMsg');
  if (msg) msg.textContent = message;
  toast.classList.add('show');
  setTimeout(function() { toast.classList.remove('show'); }, 3500);
}

document.addEventListener('DOMContentLoaded', function() {
  var cards = document.querySelectorAll('.task-card, .task-list-card, .history-day');
  cards.forEach(function(card, i) {
    card.style.opacity = '0';
    card.style.transform = 'translateY(16px)';
    card.style.transition = 'opacity 0.4s ease ' + (i * 0.06) + 's, transform 0.4s ease ' + (i * 0.06) + 's';
    setTimeout(function() {
      card.style.opacity = '';
      card.style.transform = '';
    }, 10);
  });
});
