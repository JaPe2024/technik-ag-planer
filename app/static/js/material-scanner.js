(() => {
  const form = document.getElementById('scan-form');
  if (!form) return;
  const button = document.getElementById('camera');
  const preview = document.getElementById('preview');
  const status = document.getElementById('scan-status');
  let scanner, active = false, starting = false, busy = false, disposed = false;
  const recent = new Map();
  async function stop() {
    if (active) { active = false; try { await scanner.stop(); } catch {} }
    preview.hidden = true;
    button.textContent = 'Kamera starten';
  }
  window.addEventListener('pagehide', () => { disposed = true; void stop(); });
  async function submit(code) {
    const now = Date.now();
    if (busy || (recent.get(code) || 0) > now - 3000) return;
    busy = true;
    recent.set(code, now);
    for (const [key, time] of recent) if (time < now - 10000) recent.delete(key);
    status.textContent = 'Code wird verarbeitet …';
    try {
      const data = new FormData(form);
      data.set('code', code);
      const response = await fetch(form.action, {method: 'POST', body: data, headers: {Accept: 'application/json'}, credentials: 'same-origin'});
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Sitzung abgelaufen oder Anfrage fehlgeschlagen. Bitte Seite neu laden.');
      const result = await response.json();
      status.textContent = result.message;
      form.elements.code.value = '';
      if (result.ok) {
        const page = await fetch(location.href, {credentials: 'same-origin'});
        if (page.ok) {
          const documentState = new DOMParser().parseFromString(await page.text(), 'text/html');
          for (const id of ['reservation-state', 'teardown-state']) {
            const updated = documentState.getElementById(id);
            if (updated) document.getElementById(id).replaceWith(updated);
          }
        }
      }
    } catch (error) { status.textContent = error.message; }
    finally { busy = false; }
  }
  form.addEventListener('submit', event => { event.preventDefault(); void submit(form.elements.code.value.trim()); });
  button.addEventListener('click', async () => {
    if (starting) return;
    if (active) { await stop(); return; }
    starting = true;
    try {
      if (!window.isSecureContext) throw new Error('Die Kamera benötigt HTTPS oder localhost.');
      if (!window.Html5Qrcode) throw new Error('Kamerascanner konnte nicht geladen werden. Bitte Inventarcode eingeben.');
      preview.hidden = false;
      scanner = new Html5Qrcode('preview', {verbose: false});
      await scanner.start({facingMode: 'environment'}, {fps: 10, qrbox: (w, h) => {const size = Math.min(270, Math.floor(Math.min(w, h) * 0.8)); return {width: size, height: size};}}, code => { if (!disposed) void submit(code); }, () => {});
      active = true;
      if (disposed) { await stop(); return; }
      button.textContent = 'Kamera schließen';
      status.textContent = 'Kamera aktiv. Weitere Geräte können direkt gescannt werden.';
    } catch (error) { await stop(); status.textContent = error.message; }
    finally { starting = false; }
  });
})();
