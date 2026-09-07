/* Erklärbereich (/bausteine): verdrahtet den Knopf "Beispielanlage öffnen".

   Die Kacheln selbst stehen schon in der Seite (templates/bausteine.html,
   gefüllt in routes/lehre.py: seite()). Dieses Skript baute sie bis zum Umbau
   der Oberfläche im Browser und holte sich die Kartentypen dafür erst nach dem
   Laden über /api/lehre/bausteine - bis die Antwort da war, stand auf der
   Seite "Bausteine werden geladen …", und in keinem Abzug der Seite war ihr
   eigentlicher Inhalt zu sehen.

   Eigenständiges Modul, wie schon start.js: diese Seite lädt weder editor.js
   noch panel.js noch pfeile.js, ein stiller Aufruf einer nur dort
   vorhandenen Funktion wäre ein Fehler, der erst beim Klicken auffiele. */

function zeigeFehler(nachricht) {
  const leiste = document.getElementById("fehlermeldung");
  if (!leiste) return;
  leiste.textContent = nachricht;
  leiste.hidden = false;
  window.clearTimeout(zeigeFehler.timer);
  zeigeFehler.timer = window.setTimeout(() => { leiste.hidden = true; }, 5000);
}

/* Legt die Beispielanlage zu einer Karte an und wechselt in den Editor. Sie
   entsteht erst beim Klick, nicht im Voraus: eine Anlage, die niemand sehen
   wollte, hätte in der Projektliste nichts zu suchen. */
async function beispielanlageAnlegen(kennung, knopf, statusfeld) {
  knopf.disabled = true;
  statusfeld.textContent = "Wird angelegt …";
  try {
    const antwort = await fetch(`/api/lehre/bausteine/${kennung}/anlage`, { method: "POST" });
    if (!antwort.ok) throw new Error();
    const daten = await antwort.json();
    window.location.href = `/anlage/${daten.id}`;
  } catch {
    statusfeld.textContent = "";
    knopf.disabled = false;
    zeigeFehler("Beispielanlage konnte nicht angelegt werden.");
  }
}

/* Ein Knopf ohne Beispielanlage ist schon in der Vorlage deaktiviert - er
   bekommt hier gar keine Handlung, statt eine, die nur absagt. */
window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".baustein-beispiel-knopf[data-kennung]").forEach((knopf) => {
    if (knopf.disabled) return;
    const statusfeld = knopf.parentElement.querySelector(".baustein-beispiel-status");
    knopf.addEventListener("click", () =>
      beispielanlageAnlegen(knopf.dataset.kennung, knopf, statusfeld)
    );
  });
});
