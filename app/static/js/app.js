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

function initSortableTaskGrids() {
  var grids = document.querySelectorAll('.sortable-task-grid[data-reorder-url]');

  grids.forEach(function(grid) {
    var selector = '.task-card[data-task-id], .task-list-card[data-task-id]';
    var draggingCard = null;
    var startOrder = '';

    function getCards() {
      return Array.from(grid.querySelectorAll(selector));
    }

    function getOrderSignature() {
      return getCards().map(function(card) {
        return card.dataset.taskId;
      }).join(',');
    }

    function persistOrder() {
      var taskIds = getCards().map(function(card) {
        return Number(card.dataset.taskId);
      });

      fetch(grid.dataset.reorderUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ task_ids: taskIds })
      }).then(function(response) {
        if (!response.ok) throw new Error('Falha ao salvar ordem');
        showToast('Ordem das tarefas atualizada.');
      }).catch(function() {
        showToast('Nao foi possivel salvar a nova ordem.');
      });
    }

    getCards().forEach(function(card) {
      var handle = card.querySelector('.drag-handle');
      if (!handle) return;

      handle.setAttribute('draggable', 'true');

      handle.addEventListener('dragstart', function(event) {
        startOrder = getOrderSignature();
        draggingCard = card;
        card.classList.add('dragging');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', card.dataset.taskId);
      });

      handle.addEventListener('dragend', function() {
        var endOrder = getOrderSignature();
        card.classList.remove('dragging');
        getCards().forEach(function(item) { item.classList.remove('drag-over'); });
        draggingCard = null;
        if (startOrder && startOrder !== endOrder) {
          persistOrder();
        }
        startOrder = '';
      });

      card.addEventListener('dragover', function(event) {
        if (!draggingCard || draggingCard === card) return;
        event.preventDefault();
        card.classList.add('drag-over');
      });

      card.addEventListener('dragenter', function(event) {
        if (!draggingCard || draggingCard === card) return;
        event.preventDefault();
        card.classList.add('drag-over');
        grid.insertBefore(draggingCard, card);
      });

      card.addEventListener('dragleave', function() {
        card.classList.remove('drag-over');
      });

      card.addEventListener('drop', function(event) {
        event.preventDefault();
        card.classList.remove('drag-over');
      });
    });
  });
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

  initSortableTaskGrids();
});
