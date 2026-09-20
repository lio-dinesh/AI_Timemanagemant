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
