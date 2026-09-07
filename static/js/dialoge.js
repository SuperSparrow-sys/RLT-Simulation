/* Meldungsleiste und die beiden Dialoge, die mehrere Seiten brauchen.

   Start-, Wetter- und Anlagenseite laden je ein eigenes, kleines Modul; diese
   vier Bausteine sind das Einzige, was sie gemeinsam haben. Sie standen bis
   zur Aufteilung von start.js dreimal fast gleich da - einmal hier, einmal in
   anlagen.js, einmal im Editor.

   Klassisches Skript ohne Modulaufloesung: Es muss vor seinen Nutzern im
   <head>/<body> stehen (siehe tests/test_pages.py). */

function zeigeFehler(nachricht) {
  const leiste = document.getElementById("fehlermeldung");
  if (!leiste) return;
  leiste.textContent = nachricht;
  leiste.hidden = false;
  window.clearTimeout(zeigeFehler.timer);
  zeigeFehler.timer = window.setTimeout(() => { leiste.hidden = true; }, 5000);
}

/* Frei vergebene Namen (Projekt, Anlage, Wetterdatensatz) landen unverarbeitet
   in innerHTML-Vorlagen - ohne dieses Escapen wuerde ein Name wie
   '<img src=x onerror=...>' beim Anlegen zu ausfuehrbarem Markup. */
function htmlSicher(text) {
  const traeger = document.createElement("span");
  traeger.textContent = text == null ? "" : String(text);
  return traeger.innerHTML;
}

/* Zwei wiederverwendete Dialoge fuer Loeschen und Umbenennen - je ein
   Promise, das sich erst mit dem Schliessen des Dialogs aufloest, damit sich
   'const ok = await bestaetigenDialog(...)' schreiben laesst statt mit
   Callbacks zu hantieren. 'text' darf HTML enthalten (fuer eingebettete
   Zahlen/Namen) - Aufrufer muessen frei vergebene Namen selbst vorher mit
   htmlSicher() maskieren, genau wie ueberall sonst in dieser Datei. */
function bestaetigenDialog(titel, text, bestaetigenText = "Löschen") {
  return new Promise((abschliessen) => {
    const huelle = document.createElement("div");
    huelle.className = "dialog-huelle";
    huelle.innerHTML = `
      <div class="dialog">
        <h2>${htmlSicher(titel)}</h2>
        <p class="dialog-text">${text}</p>
        <div class="dialog-knoepfe">
          <button id="btn-abbrechen">Abbrechen</button>
          <button class="knopf-haupt-gefahr" id="btn-bestaetigen">${htmlSicher(bestaetigenText)}</button>
        </div>
      </div>`;
    document.body.appendChild(huelle);
    huelle.querySelector("#btn-abbrechen").onclick = () => { huelle.remove(); abschliessen(false); };
    huelle.querySelector("#btn-bestaetigen").onclick = () => { huelle.remove(); abschliessen(true); };
  });
}

function textEingabeDialog(titel, vorgabe) {
  return new Promise((abschliessen) => {
    const huelle = document.createElement("div");
    huelle.className = "dialog-huelle";
    huelle.innerHTML = `
      <div class="dialog">
        <h2>${htmlSicher(titel)}</h2>
        <label class="panel-zeile">
          <span class="panel-label">Name</span>
          <input type="text" id="feld-text-eingabe" value="${htmlSicher(vorgabe)}">
        </label>
        <div class="dialog-knoepfe">
          <button id="btn-abbrechen">Abbrechen</button>
          <button class="knopf-haupt" id="btn-uebernehmen">Übernehmen</button>
        </div>
      </div>`;
    document.body.appendChild(huelle);
    const feld = huelle.querySelector("#feld-text-eingabe");
    feld.focus();
    feld.select();
    const schliessen = (wert) => { huelle.remove(); abschliessen(wert); };
    huelle.querySelector("#btn-abbrechen").onclick = () => schliessen(null);
    const uebernehmen = () => {
      const wert = feld.value.trim();
      if (!wert) {
        zeigeFehler("Bitte einen Namen eingeben.");
        return;
      }
      schliessen(wert);
    };
    huelle.querySelector("#btn-uebernehmen").onclick = uebernehmen;
    feld.addEventListener("keydown", (e) => { if (e.key === "Enter") uebernehmen(); });
  });
}
