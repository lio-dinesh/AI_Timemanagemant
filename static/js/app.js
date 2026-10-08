// Global Application JavaScript
document.addEventListener('DOMContentLoaded', function() {
  // CSRF support for HTMX
  document.body.addEventListener('htmx:configRequest', (event) => {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || getCookie('csrftoken');
    if (csrfToken) {
      event.detail.headers['X-CSRFToken'] = csrfToken;
    }
  });

  // Auto-dismiss alert messages after 5 seconds
  setTimeout(() => {
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    });
  }, 5000);

  // Universal Sidebar Drawer & Collapsible Toggle (Desktop & Mobile, 120Hz smooth)
  const toggleBtn = document.getElementById('sidebarToggle');
  const collapseBtn = document.getElementById('sidebarCollapseBtn');
  const closeBtn = document.getElementById('sidebarCloseBtn');
  const floatingToggleBtn = document.getElementById('sidebarFloatingToggle');
  const sidebar = document.querySelector('.app-sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');

  const isDesktop = () => window.innerWidth >= 992;

  // Restore saved desktop state from localStorage
  try {
    const savedState = localStorage.getItem('sidebar-collapsed');
    if (savedState === 'true' && isDesktop()) {
      document.body.classList.add('sidebar-collapsed');
    }
  } catch (err) {}

  function toggleSidebar() {
    requestAnimationFrame(() => {
      if (isDesktop()) {
        const isCollapsed = document.body.classList.toggle('sidebar-collapsed');
        try {
          localStorage.setItem('sidebar-collapsed', isCollapsed ? 'true' : 'false');
        } catch (err) {}
      } else {
        if (sidebar && sidebar.classList.contains('show')) {
          closeMobileSidebar();
        } else {
          openMobileSidebar();
        }
      }
    });
  }

  function openMobileSidebar() {
    requestAnimationFrame(() => {
      if (sidebar) sidebar.classList.add('show');
      if (backdrop) backdrop.classList.add('show');
      document.body.classList.add('sidebar-open');
    });
  }

  function closeMobileSidebar() {
    requestAnimationFrame(() => {
      if (sidebar) sidebar.classList.remove('show');
      if (backdrop) backdrop.classList.remove('show');
      document.body.classList.remove('sidebar-open');
    });
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      toggleSidebar();
    });
  }

  if (collapseBtn) {
    collapseBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      toggleSidebar();
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      if (isDesktop()) {
        document.body.classList.add('sidebar-collapsed');
        try { localStorage.setItem('sidebar-collapsed', 'true'); } catch (err) {}
      } else {
        closeMobileSidebar();
      }
    });
  }

  if (floatingToggleBtn) {
    floatingToggleBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      if (isDesktop()) {
        document.body.classList.remove('sidebar-collapsed');
        try { localStorage.setItem('sidebar-collapsed', 'false'); } catch (err) {}
      } else {
        openMobileSidebar();
      }
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', function() {
      closeMobileSidebar();
    }, { passive: true });
  }

  // Handle ESC key to close sidebar
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      if (!isDesktop() && sidebar && sidebar.classList.contains('show')) {
        closeMobileSidebar();
      }
    }
  }, { passive: true });

  // Notification dropdown auto-clear unread badge on interaction
  const notifBtn = document.getElementById('notificationDropdownBtn');
  if (notifBtn) {
    notifBtn.addEventListener('show.bs.dropdown', function() {
      const badges = document.querySelectorAll('#nav-notif-badge, #nav-dropdown-badge, #sidebar-notif-badge, .notif-badge-pill, .notif-dropdown-pill');
      badges.forEach(b => {
        b.style.display = 'none';
        b.remove();
      });

      // Clear count on server
      fetch('/notifications/read-all/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest'
        }
      }).catch(() => {});
    });
  }
});

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
