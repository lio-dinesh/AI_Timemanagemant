// Live Authoritative Client-side Timer & Idle Detector
(function() {
  let timerInterval = null;
  let idleSeconds = 0;
  let lastActiveTimestamp = Date.now();

  function updateDisplay() {
    const timerElem = document.getElementById('live-timer-display');
    if (!timerElem) return;

    const startedIso = timerElem.getAttribute('data-started-at');
    if (!startedIso) return;

    const startTime = new Date(startedIso).getTime();
    const now = Date.now();
    const elapsedSeconds = Math.max(0, Math.floor((now - startTime) / 1000));

    const hours = Math.floor(elapsedSeconds / 3600);
    const minutes = Math.floor((elapsedSeconds % 3600) / 60);
    const seconds = elapsedSeconds % 60;

    const pad = (num) => String(num).padStart(2, '0');
    timerElem.textContent = `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;

    // Pass idle seconds to hidden input if exists
    const idleInput = document.getElementById('timer-idle-seconds-input');
    if (idleInput) {
      idleInput.value = idleSeconds;
    }
  }

  // Idle tracking
  function resetActivity() {
    lastActiveTimestamp = Date.now();
  }

  window.addEventListener('mousemove', resetActivity);
  window.addEventListener('keydown', resetActivity);
  window.addEventListener('click', resetActivity);
  window.addEventListener('scroll', resetActivity);

  // Check idle interval (if inactive for > 60s, increment idle counter)
  setInterval(() => {
    const inactiveDuration = Math.floor((Date.now() - lastActiveTimestamp) / 1000);
    if (inactiveDuration >= 60) {
      idleSeconds += 1;
    }
  }, 1000);

  function startLiveTimer() {
    if (timerInterval) clearInterval(timerInterval);
    updateDisplay();
    timerInterval = setInterval(updateDisplay, 1000);
  }

  document.addEventListener('DOMContentLoaded', startLiveTimer);
  document.addEventListener('htmx:afterSwap', startLiveTimer);
})();
