document.getElementById('refreshBtn').addEventListener('click', async () => {
  const btn = document.getElementById('refreshBtn');
  btn.textContent = 'Refreshing…';
  btn.disabled = true;
  try {
    await fetch('/api/refresh');
    window.location.reload();
  } catch (e) {
    btn.textContent = 'Refresh failed';
    setTimeout(() => {
      btn.textContent = 'Refresh';
      btn.disabled = false;
    }, 2000);
  }
});
