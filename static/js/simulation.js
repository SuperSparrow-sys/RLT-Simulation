/* Simulationsdialog, Fortschritt und Jahresbilanz.

   Ein voller Jahreslauf dauert rund acht Minuten - dieses Modul zeigt darum
   echten Fortschritt statt die Seite waehrenddessen einzufrieren, und laesst
   den Lauf jederzeit wirklich abbrechen (nicht nur ein Merkmal setzen, das
   erst am Ende beachtet wird - das erledigt bereits core/laeufe.py). */

const BESCHRIFTUNG = {
  jahr: "ganzes Jahr",
  kalter_tag: "kalter Tag",
  heisser_tag: "heißer Tag",
  feuchter_tag: "feuchter Tag",
  eigen: "eigener Zeitraum",
};

const GROESSEN = {
  strom_ht: "Strom HT",
  strom_nt: "Strom NT",
  waerme: "Wärme",
  kaelte: "Kälte",
  wasser: "Wasser",
};

// Bei zu vielen aufeinanderfolgenden fehlgeschlagenen Abfragen aufgeben -
// ein einzelner Netzwerk-Hakler waehrend eines achtminuetigen Laufs soll die
// Anzeige nicht sofort verwerfen.
const FORTSCHRITT_MAX_FEHLVERSUCHE = 8;

// Reaktionsschnell zu Beginn, sparsamer danach - sonst waeren es bei acht
// Minuten Laufzeit rund 700 Anfragen. Ein Fehlversuch wartet immer kurz,
// unabhaengig davon, wie lange der Lauf schon geht, damit sich eine kurze
// Netzwerkstoerung schnell erholt.
const FORTSCHRITT_INTERVALL_KURZ_MS = 700;
const FORTSCHRITT_INTERVALL_LANG_MS = 3000;
const FORTSCHRITT_KURZ_DAUER_MS = 60000;

function naechstesIntervall(startzeit) {
  return Date.now() - startzeit < FORTSCHRITT_KURZ_DAUER_MS
    ? FORTSCHRITT_INTERVALL_KURZ_MS
    : FORTSCHRITT_INTERVALL_LANG_MS;
}

/* Frei vergebene Namen (Wetterdatensatz, Anlage) landen unverarbeitet in
   innerHTML-Vorlagen - ohne dieses Escapen wuerde ein Datensatzname wie
   '<img src=x onerror=...>' beim Hochladen zu ausfuehrbarem Markup. */
function htmlSicher(text) {
  const traeger = document.createElement("span");
  traeger.textContent = text == null ? "" : String(text);
  return traeger.innerHTML;
}

const Simulation = {
  kennung: null,
  // Ob gerade ein Lauf beobachtet wird - verhindert einen zweiten,
  // unbeobachteten Lauf im Hintergrund (siehe starten()/_beendet()).
  aktiv: false,

  async dialogOeffnen() {
    if (this.aktiv) {
      zeigeFehler("Es läuft bereits eine Simulation. Bitte warten oder abbrechen.");
      return;
    }

    let wetter;
    let bereiche;
    let fruehereLaeufe = [];
    try {
      const [wetterAntwort, bereichAntwort] = await Promise.all([
        fetch("/api/wetter"),
        fetch("/api/simulation/schnellwahl"),
      ]);
      if (!wetterAntwort.ok || !bereichAntwort.ok) {
        zeigeFehler("Simulationsdialog konnte nicht geöffnet werden.");
        return;
      }
      wetter = await wetterAntwort.json();
      bereiche = await bereichAntwort.json();
    } catch {
      zeigeFehler("Simulationsdialog konnte nicht geöffnet werden.");
      return;
    }

    if (!wetter.length) {
      zeigeFehler("Bitte zuerst einen Wetterdatensatz hochladen.");
      return;
    }

    try {
      const laeufeAntwort = await fetch(`/api/anlagen/${Editor.anlage.id}/simulationen`);
      if (laeufeAntwort.ok) fruehereLaeufe = await laeufeAntwort.json();
    } catch {
      // Fruehere Laeufe sind eine Zugabe im Dialog, kein Grund, ihn zu verweigern.
    }

    const dialog = document.createElement("div");
    dialog.className = "dialog-huelle";
    dialog.innerHTML = `
      <div class="dialog">
        <h2>Simulation starten</h2>
        <label class="panel-zeile">
          <span class="panel-label">Wetterdatensatz</span>
          <select id="wahl-wetter">
            ${wetter
              .map((w) => `<option value="${w.id}">${htmlSicher(w.name)} (${w.stunden} h)</option>`)
              .join("")}
          </select>
        </label>
        <label class="panel-zeile">
          <span class="panel-label">Zeitraum</span>
          <select id="wahl-bereich">
            ${Object.keys(bereiche)
              .map((n) => `<option value="${n}">${BESCHRIFTUNG[n] || n}</option>`)
              .join("")}
            <option value="eigen">${BESCHRIFTUNG.eigen}</option>
          </select>
        </label>
        <div class="panel-zeile panel-zeile-nebeneinander" id="wahl-eigen" hidden>
          <label class="panel-zeile">
            <span class="panel-label">von Stunde</span>
            <input type="number" id="wahl-von" min="0" max="8759" value="0">
          </label>
          <label class="panel-zeile">
            <span class="panel-label">bis Stunde</span>
            <input type="number" id="wahl-bis" min="1" max="8760" value="8760">
          </label>
        </div>
        ${this._fruehereLaeufeHtml(fruehereLaeufe)}
        <div class="dialog-knoepfe">
          <button id="btn-abbrechen">Abbrechen</button>
          <button class="knopf-haupt" id="btn-los">Los</button>
        </div>
      </div>`;
    document.body.appendChild(dialog);

    const eigenBereich = dialog.querySelector("#wahl-eigen");
    dialog.querySelector("#wahl-bereich").addEventListener("change", (e) => {
      eigenBereich.hidden = e.target.value !== "eigen";
    });

    dialog.querySelectorAll(".frueherer-lauf").forEach((zeile) => {
      zeile.addEventListener("click", () => {
        const simulationId = Number(zeile.dataset.simulationId);
        dialog.remove();
        this.zeigeBilanz(simulationId);
      });
    });

    dialog.querySelector("#btn-abbrechen").onclick = () => dialog.remove();
    dialog.querySelector("#btn-los").onclick = () => {
      const wetterId = Number(dialog.querySelector("#wahl-wetter").value);
      const bereichName = dialog.querySelector("#wahl-bereich").value;
      let von;
      let bis;
      if (bereichName === "eigen") {
        von = Number(dialog.querySelector("#wahl-von").value);
        bis = Number(dialog.querySelector("#wahl-bis").value);
        if (!Number.isFinite(von) || !Number.isFinite(bis) || von < 0 || bis <= von) {
          zeigeFehler("Der eigene Zeitraum ist ungültig.");
          return;
        }
      } else {
        von = bereiche[bereichName].von;
        bis = bereiche[bereichName].bis;
      }
      dialog.remove();
      this.starten(wetterId, von, bis);
    };
  },

  _fruehereLaeufeHtml(laeufe) {
    if (!laeufe.length) return "";
    const zeilen = laeufe
      .slice(0, 5)
      .map(
        (l) => `<li class="frueherer-lauf" data-simulation-id="${l.id}">
          <span>${htmlSicher(l.wetter_name)} · Stunde ${l.von_stunde}–${l.bis_stunde}</span>
          <span class="zahl">${l.kosten_gesamt.toFixed(2)} EUR</span>
        </li>`
      )
      .join("");
    return `
      <div class="panel-zeile">
        <span class="panel-label">Frühere Läufe</span>
        <ul class="fruehere-laeufe">${zeilen}</ul>
      </div>`;
  },

  async starten(wetterId, von, bis) {
    let antwort;
    try {
      antwort = await fetch("/api/simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          anlage_id: Editor.anlage.id,
          wetterdatensatz_id: wetterId,
          von,
          bis,
        }),
      });
    } catch {
      zeigeFehler("Simulation konnte nicht gestartet werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Simulation konnte nicht gestartet werden.");
      return;
    }
    const kennung = (await antwort.json()).kennung;
    this.kennung = kennung;
    this.aktiv = true;
    this._simulierenKnopfAktivieren(false);
    this.zeigeFortschritt(kennung);
    this.beobachte(kennung);
  },

  _simulierenKnopfAktivieren(aktiviert) {
    const knopf = document.getElementById("btn-simulieren");
    if (knopf) knopf.disabled = !aktiviert;
  },

  // Ein Lauf ist zu Ende beobachtet - egal ob fertig, abgebrochen,
  // fehlgeschlagen oder wegen dauerhaftem Verbindungsverlust aufgegeben.
  // Erst danach darf ein neuer Lauf gestartet werden (siehe dialogOeffnen()).
  _beendet() {
    this.aktiv = false;
    this._simulierenKnopfAktivieren(true);
  },

  zeigeFortschritt(kennung) {
    const alte = document.querySelector(".fortschritt-huelle");
    if (alte) alte.remove();

    const huelle = document.createElement("div");
    huelle.className = "fortschritt-huelle";
    huelle.innerHTML = `
      <div class="fortschritt">
        <div class="fortschritt-text" id="fortschritt-text">Simulation läuft …</div>
        <div class="fortschritt-schiene"><div id="fortschritt-balken"></div></div>
        <button id="btn-lauf-abbrechen">Abbrechen</button>
      </div>`;
    document.body.appendChild(huelle);
    // 'kennung' ist der Wert des Parameters dieses Aufrufs, nicht
    // this.kennung - so bleibt der Knopf auch dann an den richtigen Lauf
    // gebunden, wenn this.kennung sich inzwischen geaendert haette.
    huelle.querySelector("#btn-lauf-abbrechen").onclick = async (e) => {
      const knopf = e.target;
      knopf.disabled = true;
      knopf.textContent = "Wird abgebrochen …";
      let antwort;
      try {
        antwort = await fetch(`/api/simulation/${kennung}/abbrechen`, {
          method: "POST",
        });
      } catch {
        zeigeFehler("Abbruch konnte nicht übermittelt werden.");
        knopf.disabled = false;
        knopf.textContent = "Abbrechen";
        return;
      }
      if (!antwort.ok) {
        zeigeFehler("Abbruch konnte nicht übermittelt werden.");
        knopf.disabled = false;
        knopf.textContent = "Abbrechen";
      }
      // Der eigentliche Abbruch zeigt sich im naechsten Abfrageschritt von
      // beobachte() als Status "abgebrochen" - hier ist nichts weiter zu tun.
    };
  },

  // 'kennung' wird als Parameter uebernommen statt bei jedem Schleifendurchlauf
  // erneut aus this.kennung gelesen zu werden - sonst wuerde diese Schleife,
  // wenn inzwischen ein zweiter Lauf gestartet worden waere, unbemerkt auf
  // dessen Stand umschwenken und den urspruenglich beobachteten Lauf
  // verwaist und unbeobachtet im Hintergrund weiterlaufen lassen.
  async beobachte(kennung) {
    const start = Date.now();
    let fehlversuche = 0;
    while (true) {
      let stand;
      try {
        const antwort = await fetch(`/api/simulation/${kennung}`);
        if (!antwort.ok) throw new Error("Antwort nicht ok");
        stand = await antwort.json();
        fehlversuche = 0;
      } catch {
        fehlversuche += 1;
        if (fehlversuche >= FORTSCHRITT_MAX_FEHLVERSUCHE) {
          const huelle = document.querySelector(".fortschritt-huelle");
          if (huelle) huelle.remove();
          this._beendet();
          zeigeFehler("Verbindung zum Server verloren. Der Lauf läuft im Hintergrund weiter.");
          return;
        }
        await new Promise((r) => setTimeout(r, FORTSCHRITT_INTERVALL_KURZ_MS));
        continue;
      }

      const anteil = stand.gesamt ? stand.fertig / stand.gesamt : 0;
      const balken = document.getElementById("fortschritt-balken");
      if (balken) balken.style.width = `${(anteil * 100).toFixed(1)}%`;
      const text = document.getElementById("fortschritt-text");
      if (text) {
        text.textContent =
          `Simulation läuft … ${stand.fertig || 0} von ${stand.gesamt || 0} Stunden`;
      }

      if (["fertig", "abgebrochen", "fehler"].includes(stand.status)) {
        const huelle = document.querySelector(".fortschritt-huelle");
        if (huelle) huelle.remove();
        this._beendet();

        if (stand.status === "fehler") {
          zeigeFehler(`Simulation fehlgeschlagen: ${stand.fehler || "unbekannter Fehler"}`);
          return;
        }
        const hinweis =
          stand.status === "abgebrochen"
            ? `Lauf abgebrochen nach ${stand.fertig || 0} von ${stand.gesamt || 0} Stunden.`
            : null;
        await this.zeigeBilanz(stand.simulation_id, hinweis);
        return;
      }
      await new Promise((r) => setTimeout(r, naechstesIntervall(start)));
    }
  },

  async zeigeBilanz(simulationId, hinweis) {
    let antwort;
    try {
      antwort = await fetch(`/api/simulation/${simulationId}/bilanz`);
    } catch {
      zeigeFehler("Bilanz konnte nicht geladen werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Bilanz konnte nicht geladen werden.");
      return;
    }
    const daten = await antwort.json();

    Panel.zeigeWerte(daten.werte || {});

    const zeilen = daten.bilanz
      .map(
        (z) => `<tr>
          <td>${GROESSEN[z.groesse] || z.groesse}</td>
          <td class="zahl">${z.menge.toFixed(3)}</td>
          <td>${z.einheit}</td>
          <td class="zahl">${z.preis.toFixed(2)}</td>
          <td class="zahl">${z.kosten.toFixed(2)} EUR</td>
        </tr>`
      )
      .join("");
    const summe = daten.bilanz.reduce((s, z) => s + z.kosten, 0);

    const warnungen = daten.warnungen || { anzahl: 0, beispiele: [] };
    const warnhinweisHtml = this._warnhinweisHtml(warnungen);

    const fenster = document.createElement("div");
    fenster.className = "dialog-huelle";
    fenster.innerHTML = `
      <div class="dialog dialog-breit">
        <h2>Jahresbilanz</h2>
        ${hinweis ? `<p class="abbruchhinweis">${hinweis}</p>` : ""}
        <table class="bilanz">
          <thead><tr><th>Größe</th><th class="zahl">Menge</th><th>Einheit</th>
                     <th class="zahl">Preis</th><th class="zahl">Kosten</th></tr></thead>
          <tbody>${zeilen}</tbody>
          <tfoot><tr><td colspan="4">Summe</td>
                     <td class="zahl">${summe.toFixed(2)} EUR</td></tr></tfoot>
        </table>
        ${warnhinweisHtml}
        <div class="dialog-knoepfe">
          <button class="knopf-haupt" id="btn-schliessen">Schließen</button>
        </div>
      </div>`;
    document.body.appendChild(fenster);
    fenster.querySelector("#btn-schliessen").onclick = () => fenster.remove();

    const mehrKnopf = fenster.querySelector("#btn-warn-beispiele");
    if (mehrKnopf) {
      mehrKnopf.onclick = () => {
        const liste = fenster.querySelector("#warn-beispiele");
        liste.hidden = !liste.hidden;
        mehrKnopf.textContent = liste.hidden ? "Beispiele ansehen" : "Beispiele verbergen";
      };
    }
  },

  _warnhinweisHtml(warnungen) {
    if (!warnungen.anzahl) {
      return '<p class="warnhinweis warnhinweis-ok">Alle Stunden konvergiert.</p>';
    }
    const beispiele = (warnungen.beispiele || [])
      .map((w) => `<li>Stunde ${w.stunde}: ${w.text}</li>`)
      .join("");
    return `
      <div class="warnhinweis">
        <p>${warnungen.anzahl} Stunden ohne Konvergenz
          <button type="button" class="warn-mehr" id="btn-warn-beispiele">Beispiele ansehen</button>
        </p>
        <ul class="warn-beispiele" id="warn-beispiele" hidden>${beispiele}</ul>
      </div>`;
  },
};

window.addEventListener("DOMContentLoaded", () => {
  const knopf = document.getElementById("btn-simulieren");
  if (knopf) knopf.onclick = () => Simulation.dialogOeffnen();
});
