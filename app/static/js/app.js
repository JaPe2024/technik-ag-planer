// Bottom-Sheets: öffnen, schließen (Button, Hintergrund, Escape) und nach unten wischen.
(() => {
  "use strict";

  const CLOSE_DISTANCE = 80; // px, ab denen ein Wisch nach unten schließt

  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-sheet-open]");
    if (opener) {
      const sheet = document.getElementById(opener.dataset.sheetOpen);
      if (sheet && !sheet.open) sheet.showModal();
      return;
    }

    const closer = event.target.closest("[data-sheet-close]");
    if (closer) {
      closer.closest("dialog")?.close();
      return;
    }

    // Klick auf den abgedunkelten Hintergrund
    if (event.target instanceof HTMLDialogElement && event.target.matches("[data-sheet]")) {
      const rect = event.target.getBoundingClientRect();
      const inside =
        event.clientX >= rect.left && event.clientX <= rect.right &&
        event.clientY >= rect.top && event.clientY <= rect.bottom;
      if (!inside) event.target.close();
    }
  });

  document.querySelectorAll("[data-sheet]").forEach((sheet) => {
    const grip = sheet.querySelector("[data-sheet-grip]");
    if (!grip) return;

    let startY = null;

    grip.addEventListener("pointerdown", (event) => {
      startY = event.clientY;
      grip.setPointerCapture(event.pointerId);
    });

    grip.addEventListener("pointermove", (event) => {
      if (startY === null) return;
      const offset = Math.max(0, event.clientY - startY);
      sheet.style.transform = `translateY(${offset}px)`;
    });

    const end = (event) => {
      if (startY === null) return;
      const offset = event.clientY - startY;
      startY = null;
      sheet.style.transform = "";
      if (offset > CLOSE_DISTANCE) sheet.close();
    };

    grip.addEventListener("pointerup", end);
    grip.addEventListener("pointercancel", end);
  });
})();

// Auswahlfelder, die beim Ändern direkt absenden (z. B. „AG wechseln“)
document.addEventListener("change", (event) => {
  const form = event.target.closest("form[data-auto-submit]");
  if (form && event.target.matches("select")) form.requestSubmit();
});

// Sicherheitsabfrage vor folgenreichen Aktionen: <form data-confirm="Wirklich …?">
document.addEventListener("submit", (event) => {
  const message = event.target.dataset?.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});

// Formulare im Bottom-Sheet: <a href="…" data-sheet-url> lädt die Seite ohne Rahmen ins Sheet.
// Ohne JavaScript öffnet der Link einfach die normale Seite.
document.addEventListener("click", async (event) => {
  const link = event.target.closest("a[data-sheet-url]");
  if (!link || event.metaKey || event.ctrlKey || event.shiftKey) return;
  const sheet = document.getElementById("sheet-form");
  if (!sheet) return;
  event.preventDefault();
  try {
    const response = await fetch(link.href, { headers: { "X-Sheet": "1" }, cache: "no-store" });
    if (!response.ok || response.redirected) throw new Error(String(response.status));
    const body = sheet.querySelector("[data-sheet-body]");
    body.innerHTML = await response.text();
    const heading = body.querySelector(".sheet-title");
    sheet.querySelector(".sheet__title").textContent = heading ? heading.textContent : "";
    document.getElementById("sheet-new")?.close();
    if (!sheet.open) sheet.showModal();
    initForms(body);
    body.querySelector("[autofocus]")?.focus();
  } catch {
    window.location.href = link.href;
  }
});

// Entwürfe: <form data-draft="schlüssel"> wird im Browser zwischengespeichert.
const DRAFT_PREFIX = "entwurf:";

function storage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function saveDraft(form) {
  const data = {};
  for (const element of form.elements) {
    if (!element.name || element.type === "hidden" || element.type === "password") continue;
    if (element.type === "checkbox") data[element.name] = element.checked;
    else if (element.type === "radio") {
      if (element.checked) data[element.name] = element.value;
    } else data[element.name] = element.value;
  }
  data.__rows = form.querySelector("[data-formset]")?.children.length || 0;
  try {
    storage()?.setItem(DRAFT_PREFIX + form.dataset.draft, JSON.stringify(data));
  } catch {
    /* Speicher voll oder gesperrt – Entwurf entfällt */
  }
}

function restoreDraft(form) {
  let data;
  try {
    data = JSON.parse(storage()?.getItem(DRAFT_PREFIX + form.dataset.draft) || "null");
  } catch {
    data = null;
  }
  if (!data) return;
  const container = form.querySelector("[data-formset]");
  while (container && container.children.length < (data.__rows || 0)) addFormsetRow(form, container.dataset.formset);
  for (const element of form.elements) {
    if (!element.name || !(element.name in data)) continue;
    if (element.type === "checkbox") element.checked = Boolean(data[element.name]);
    else if (element.type === "radio") element.checked = element.value === data[element.name];
    else element.value = data[element.name];
  }
  form.querySelector("[data-draft-note]")?.removeAttribute("hidden");
}

function clearDraft(form) {
  try {
    storage()?.removeItem(DRAFT_PREFIX + form.dataset.draft);
  } catch {
    /* nichts zu tun */
  }
}

// Formset: „+ Job“, „+ Link“ usw. fügt eine leere Zeile aus <template data-formset-template> ein.
function addFormsetRow(form, prefix) {
  const container = form.querySelector(`[data-formset="${prefix}"]`);
  const template = form.querySelector(`[data-formset-template="${prefix}"]`);
  const total = form.querySelector(`[name="${prefix}-TOTAL_FORMS"]`);
  if (!container || !template || !total) return;
  const index = Number(total.value);
  container.insertAdjacentHTML("beforeend", template.innerHTML.replaceAll("__prefix__", String(index)));
  total.value = String(index + 1);
}

function initForms(root) {
  root.querySelectorAll("form[data-draft]").forEach((form) => {
    if (form.dataset.draftReady) return;
    form.dataset.draftReady = "1";
    restoreDraft(form);
    form.addEventListener("input", () => saveDraft(form));
    form.addEventListener("change", () => saveDraft(form));
    form.addEventListener("submit", () => clearDraft(form));
    form.querySelector("[data-draft-discard]")?.addEventListener("click", () => {
      clearDraft(form);
      form.reset();
      form.querySelector("[data-draft-note]")?.setAttribute("hidden", "");
      const sheet = form.closest("dialog");
      if (sheet) sheet.close();
      else window.location.reload();
    });
  });
  root.querySelectorAll("[data-formset-add]").forEach((button) => {
    if (button.dataset.ready) return;
    button.dataset.ready = "1";
    button.addEventListener("click", () => {
      const form = button.closest("form");
      addFormsetRow(form, button.dataset.formsetAdd);
      if (form.dataset.draft) saveDraft(form);
    });
  });
}

initForms(document);

// Schulstunde gewählt → zugehöriges Zeitfeld sofort ausfüllen (Server rechnet zusätzlich um)
document.addEventListener("change", (event) => {
  const select = event.target.closest("select[data-period-map]");
  if (!select || !select.value) return;
  const target = document.getElementById(select.dataset.periodTarget.replace("__prefix__", ""))
    || select.closest(".time-period")?.querySelector('input[type="time"]');
  const times = JSON.parse(select.dataset.periodMap)[select.value];
  if (target && times) target.value = select.dataset.periodEdge === "start" ? times[0] : times[1];
});

// Board: neue Nachrichten alle 10 s holen, per fetch senden, Enter sendet (Shift+Enter = neue Zeile).
// Ohne JavaScript funktioniert alles über normale Formulare und Neuladen der Seite.
(() => {
  const board = document.querySelector("[data-board]");
  if (!board) return;
  const POLL_MS = 10000;
  const list = board.querySelector("[data-board-list]");
  const form = board.querySelector("[data-board-form]");
  const input = form.querySelector("textarea");
  let lastId = Number(board.dataset.lastId) || 0;
  let polling = null;

  // Bis ganz unten: Das Eingabefeld klebt über dem Seitenende und darf nichts verdecken
  const scrollToEnd = () =>
    requestAnimationFrame(() => window.scrollTo(0, document.documentElement.scrollHeight));

  function autosize() {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  }

  function poll() {
    // Läuft schon eine Abfrage, warten alle Aufrufer auf deren Ergebnis
    polling ??= fetchNew().finally(() => {
      polling = null;
    });
    return polling;
  }

  async function fetchNew() {
    try {
      const url = new URL(board.dataset.pollUrl, window.location.href);
      url.searchParams.set("nach", String(lastId));
      const response = await fetch(url, { cache: "no-store" });
      if (response.status !== 200) return;
      const nearEnd = window.innerHeight + window.scrollY >= document.body.scrollHeight - 160;
      list.querySelectorAll("[data-board-last]").forEach((el) => el.remove());
      const template = document.createElement("template");
      template.innerHTML = await response.text();
      // Datumstrenner nicht doppelt anzeigen
      template.content.querySelectorAll("[data-day]").forEach((day) => {
        if (list.querySelector(`[data-day="${day.dataset.day}"]`)) day.remove();
      });
      list.append(template.content);
      lastId = Number(list.querySelector("[data-board-last]")?.dataset.boardLast) || lastId;
      board.querySelector("[data-board-empty]")?.remove();
      if (nearEnd) scrollToEnd();
    } catch {
      /* offline – nächster Versuch beim nächsten Intervall */
    }
  }

  // Tastatur offen lassen: Der Senden-Knopf darf dem Eingabefeld den Fokus nicht nehmen
  const send = form.querySelector("[type=submit]");
  send.addEventListener("mousedown", (event) => event.preventDefault());
  send.addEventListener("touchend", (event) => {
    event.preventDefault();
    form.requestSubmit();
  });

  let sending = false;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (sending || !input.value.trim()) return;
    sending = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Board": "1" },
      });
      if (response.status === 204) {
        input.value = "";
        autosize();
        // Eine laufende Abfrage kennt die neue Nachricht vielleicht noch nicht
        await polling;
        await poll();
        scrollToEnd();
      } else if (response.status === 400) {
        window.alert(await response.text());
      } else {
        form.submit();
      }
    } catch {
      form.submit();
    } finally {
      sending = false;
    }
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener("input", autosize);

  window.setInterval(() => {
    if (document.visibilityState === "visible") poll();
  }, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") poll();
  });
  if (!window.location.hash || window.location.hash === "#ende") scrollToEnd();
})();

// Technik-Anfragen: „Kopieren“ (data-copy="Text") und „Einfügen“ (data-paste="feld-id").
// Einfügen nimmt den zuletzt auf der Seite kopierten Text – das klappt in jedem Browser –,
// sonst die Zwischenablage (nicht überall erlaubt).
(() => {
  let lastCopied = null;

  const flash = (button, text) => {
    const original = button.textContent;
    button.textContent = text;
    setTimeout(() => {
      button.textContent = original;
    }, 1200);
  };

  document.addEventListener("click", async (event) => {
    const copy = event.target.closest("[data-copy]");
    if (copy) {
      lastCopied = copy.dataset.copy;
      try {
        await navigator.clipboard.writeText(lastCopied);
      } catch {
        /* Zwischenablage gesperrt – „Einfügen“ funktioniert trotzdem */
      }
      flash(copy, "Kopiert ✓");
      return;
    }
    const paste = event.target.closest("[data-paste]");
    if (!paste) return;
    let text = lastCopied;
    if (text === null) {
      try {
        text = await navigator.clipboard.readText();
      } catch {
        text = null;
      }
    }
    const field = document.getElementById(paste.dataset.paste);
    if (text === null || !field) {
      flash(paste, "Erst kopieren");
      return;
    }
    field.value = text;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.focus();
  });

  // Geteilte Ansicht: auf schmalen Bildschirmen Umschalter „Anfrage | Produktion“
  document.querySelectorAll("[data-split]").forEach((split) => {
    split.classList.add("split--js");
    const links = split.querySelectorAll("[data-split-switch] [data-show]");
    const show = (name) => {
      split.querySelectorAll("[data-pane]").forEach((pane) => {
        pane.classList.toggle("is-active", pane.dataset.pane === name);
      });
      links.forEach((link) => {
        if (link.dataset.show === name) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
    };
    links.forEach((link) =>
      link.addEventListener("click", (event) => {
        event.preventDefault();
        show(link.dataset.show);
      }),
    );
    show(split.dataset.split || "anfrage");
  });
})();

// PDF-Vorschau: „Teilen“ über das Teilen-Menü des Geräts (Web Share API mit Datei).
// Das PDF wird vorab geladen, weil manche Browser das Teilen nur direkt nach dem Tippen erlauben.
// Ohne Unterstützung bleibt der Button ausgeblendet; dann helfen „Herunterladen“ und „Drucken“.
(() => {
  "use strict";

  const button = document.querySelector("[data-share-pdf]");
  if (!button || !navigator.canShare) return;

  fetch(button.dataset.sharePdf, { credentials: "same-origin" })
    .then((response) => (response.ok ? response.blob() : Promise.reject(response.status)))
    .then((blob) => {
      const file = new File([blob], button.dataset.shareName, { type: "application/pdf" });
      if (!navigator.canShare({ files: [file] })) return;
      button.hidden = false;
      button.addEventListener("click", () => {
        navigator.share({ files: [file], title: button.dataset.shareTitle }).catch(() => {});
      });
    })
    .catch(() => {});
})();

// Service Worker für Push-Mitteilungen (kein Offline-Modus). Nur über HTTPS bzw. localhost.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  });
}
