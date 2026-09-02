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
    if (typeof Vergleich !== "undefined" && Vergleich.aktiv) {
      zeigeFehler("Es läuft bereits eine Reihe für diese Anlage. Bitte warten oder abbrechen.");
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
        dialog.remove();
        if (zeile.dataset.status === "laeuft" && zeile.dataset.kennung) {
          if (this.aktiv) {
            zeigeFehler("Es läuft bereits eine Simulation. Bitte warten oder abbrechen.");
            return;
          }
          this._wiederAufnehmen(zeile.dataset.kennung);
        } else {
          this.zeigeBilanz(Number(zeile.dataset.simulationId));
        }
      });
    });

    // Ein Klick auf CSV/Excel soll nur herunterladen, nicht zugleich (wie ein
    // Klick auf die Zeile selbst) den Dialog schliessen und die Bilanz
    // oeffnen - derselbe stopPropagation()-Kniff wie beim Loeschen-Knopf.
    dialog.querySelectorAll(".frueherer-lauf-download").forEach((link) => {
      link.addEventListener("click", (e) => e.stopPropagation());
    });

    dialog.querySelectorAll(".frueherer-lauf-loeschen").forEach((knopf) => {
      // Eigener Klick-Handler, nicht die Zeile selbst - sonst wuerde ein
      // Klick auf "Löschen" zugleich die Zeile "oeffnen" (siehe oben).
      knopf.addEventListener("click", async (e) => {
        e.stopPropagation();
        const zeile = knopf.closest(".frueherer-lauf");
        const simulationId = knopf.dataset.simulationId;
        const bestaetigt = await bestaetigenDialog(
          "Simulationslauf löschen",
          "Dieser Simulationslauf wird endgültig gelöscht, mitsamt seiner " +
            "gespeicherten Stundenreihe und Bilanz."
        );
        if (!bestaetigt) return;

        knopf.disabled = true;
        let antwort;
        try {
          antwort = await fetch(`/api/simulation/${simulationId}`, { method: "DELETE" });
        } catch {
          zeigeFehler("Simulationslauf konnte nicht gelöscht werden.");
          knopf.disabled = false;
          return;
        }
        if (!antwort.ok) {
          let text = "Simulationslauf konnte nicht gelöscht werden.";
          try {
            const daten = await antwort.json();
            if (daten.fehler) text = daten.fehler;
          } catch {
            /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */
          }
          zeigeFehler(text);
          knopf.disabled = false;
          return;
        }

        zeile.remove();
        if (!dialog.querySelectorAll(".frueherer-lauf").length) {
          const liste = dialog.querySelector(".fruehere-laeufe");
          if (liste) {
            const hinweis = document.createElement("p");
            hinweis.className = "leerhinweis";
            hinweis.textContent = "Für diese Anlage wurde noch nicht simuliert.";
            liste.replaceWith(hinweis);
          }
        }
        // Der geloeschte Lauf koennte der war, auf den der Bericht-Weg in
        // der Kopfleiste gerade zeigte - neu ermitteln statt auf einen
        // geloeschten Bericht zeigen zu lassen.
        if (typeof Editor !== "undefined") {
          Editor.berichtLinkAktualisieren();
        }
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

  // Ein laufender Eintrag hat noch keine Bilanz (die entsteht erst beim
  // Abschluss, siehe core/ergebnisse.abschliesse) - "0.00 EUR" anzuzeigen
  // saehe wie ein Lauf ohne jeden Verbrauch aus, statt wie einer, der noch
  // rechnet. Stattdessen ein eigenes Kennzeichen, und ein Klick darauf
  // greift den Lauf wieder auf statt eine (noch nicht vorhandene) Bilanz zu
  // laden.
  _fruehereLaeufeHtml(laeufe) {
    if (!laeufe.length) {
      return `
        <div class="panel-zeile">
          <span class="panel-label">Frühere Läufe</span>
          <p class="leerhinweis">Für diese Anlage wurde noch nicht simuliert.</p>
        </div>`;
    }
    const zeilen = laeufe
      .slice(0, 5)
      .map((l) => {
        const laeuftNoch = l.status === "laeuft";
        const rechts = laeuftNoch
          ? `<span class="zahl frueherer-lauf-laeuft">läuft …</span>`
          : `<span class="zahl">${Zahlen.fest(l.kosten_gesamt, 2)} EUR</span>`;
        // Stundenwerte gibt es nur fuer einen Lauf mit gespeicherter
        // Zeitreihe (core.ausgabe.STATUS_MIT_ERGEBNIS) - 'laeuft' und
        // 'fehler' haben keine.
        const downloadLinks =
          l.status === "fertig" || l.status === "abgebrochen"
            ? `<a class="knopf-mini frueherer-lauf-download"
                  href="/api/simulation/${l.id}/stundenwerte.csv"
                  title="Stundenwerte als CSV herunterladen">CSV</a>
               <a class="knopf-mini frueherer-lauf-download"
                  href="/api/simulation/${l.id}/stundenwerte.xlsx"
                  title="Stundenwerte als Excel-Mappe herunterladen">Excel</a>`
            : "";
        // Ein laufender Lauf laesst sich hier nicht loeschen (siehe
        // core.ergebnisse.simulation_loeschen) - erst abbrechen, dann
        // loeschen, oder gleich die ganze Anlage loeschen.
        const loeschKnopf = laeuftNoch
          ? ""
          : `<button type="button" class="knopf-mini knopf-mini-gefahr frueherer-lauf-loeschen"
                     data-simulation-id="${l.id}" title="Diesen Lauf löschen">Löschen</button>`;
        return `<li class="frueherer-lauf" data-simulation-id="${l.id}"
              data-status="${htmlSicher(l.status)}" data-kennung="${htmlSicher(l.kennung || "")}">
          <span>${htmlSicher(l.wetter_name)} · Stunde ${l.von_stunde}–${l.bis_stunde}</span>
          <span class="frueherer-lauf-rechts">${rechts}${downloadLinks}${loeschKnopf}</span>
        </li>`;
      })
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
    this._wiederAufnehmen(kennung);
  },

  // Gemeinsamer Einstieg fuer einen frisch gestarteten Lauf (starten()), einen
  // nach dem Neuladen der Seite wiedergefundenen (pruefeLaufendenLauf()) und
  // einen aus "Fruehere Laeufe" erneut aufgegriffenen (dialogOeffnen()) - in
  // allen drei Faellen ist ab hier nur noch wichtig, unter welcher Kennung
  // beobachtet wird. 'anfangsstand' ist optional und zeigt sofort einen
  // sinnvollen Fortschritt an, statt bis zur ersten Abfrage in beobachte()
  // bei 0 zu stehen (siehe pruefeLaufendenLauf()).
  _wiederAufnehmen(kennung, anfangsstand) {
    this.kennung = kennung;
    this.aktiv = true;
    this._simulierenKnopfAktivieren(false);
    this.zeigeFortschritt(kennung);
    if (anfangsstand) {
      this._aktualisiereFortschrittsanzeige(anfangsstand.fertig, anfangsstand.gesamt);
    }
    this.beobachte(kennung);
  },

  // Beim Laden der Editorseite fragen, ob fuer diese Anlage bereits ein Lauf
  // rechnet (z.B. weil die Seite waehrend eines Jahreslaufs neu geladen
  // wurde) und dessen Fortschrittsanzeige und Abbruch wiederherstellen.
  // window.ANLAGE_ID statt Editor.anlage.id: editor.html setzt es in einem
  // Inline-Script vor allen js-Dateien, es steht also schon hier zur
  // Verfuegung, ohne auf Editor.laden() (das erst nach diesem DOMContentLoaded-
  // Handler laeuft, siehe editor.js) warten zu muessen.
  async pruefeLaufendenLauf() {
    if (this.aktiv || typeof window.ANLAGE_ID === "undefined") return;
    let antwort;
    try {
      antwort = await fetch(`/api/anlagen/${window.ANLAGE_ID}/laufende_simulation`);
    } catch {
      return; // Kein erkennbarer laufender Lauf ist hier keine Fehlermeldung wert.
    }
    if (!antwort.ok) return;
    const stand = await antwort.json();
    if (!stand || !stand.kennung) return;
    this._wiederAufnehmen(stand.kennung, stand);
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

  _aktualisiereFortschrittsanzeige(fertig, gesamt) {
    const anteil = gesamt ? fertig / gesamt : 0;
    const balken = document.getElementById("fortschritt-balken");
    // toFixed und nicht Zahlen.fest(): das hier ist eine CSS-Laenge, kein
    // angezeigter Text - "12,3%" waere fuer den Browser ungueltig.
    if (balken) balken.style.width = `${(anteil * 100).toFixed(1)}%`;
    const text = document.getElementById("fortschritt-text");
    if (text) {
      text.textContent = `Simulation läuft … ${fertig || 0} von ${gesamt || 0} Stunden`;
    }
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

      this._aktualisiereFortschrittsanzeige(stand.fertig, stand.gesamt);

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
        // Dieser Lauf ist der juengste (gerade erst beendet) und hat ein
        // Ergebnis ("fertig"/"abgebrochen", siehe oben) - der dauerhafte
        // Bericht-Weg in der Kopfleiste (editor.js, berichtLinkSetzen())
        // wird sofort nutzbar, ohne dass die Seite neu geladen werden muss.
        if (typeof Editor !== "undefined") {
          Editor.berichtLinkSetzen(stand.simulation_id);
        }
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
          <td class="zahl">${Zahlen.fest(z.menge, 3)}</td>
          <td>${z.einheit}</td>
          <td class="zahl">${Zahlen.fest(z.preis, 2)}</td>
          <td class="zahl">${Zahlen.fest(z.kosten, 2)} EUR</td>
        </tr>`
      )
      .join("");
    const summe = daten.bilanz.reduce((s, z) => s + z.kosten, 0);

    const warnungen = daten.warnungen || { anzahl: 0, beispiele: [] };
    const warnhinweisHtml = this._warnhinweisHtml(warnungen);
    const bausteinWarnhinweisHtml = this._bausteinWarnhinweisHtml(
      daten.baustein_warnungen || []
    );

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
                     <td class="zahl">${Zahlen.fest(summe, 2)} EUR</td></tr></tfoot>
        </table>
        ${warnhinweisHtml}
        ${bausteinWarnhinweisHtml}
        <div class="dialog-knoepfe">
          <a class="knopf-mini" href="/anlage/${Editor.anlage.id}/lauf/${simulationId}/bericht">Bericht ansehen</a>
          <a class="knopf-mini" href="/anlage/${Editor.anlage.id}/lauf/${simulationId}/bericht.pdf">PDF herunterladen</a>
          <button id="btn-protokoll">Stundenprotokoll</button>
          <a class="knopf-mini" href="/api/simulation/${simulationId}/stundenwerte.csv">Stundenwerte CSV</a>
          <a class="knopf-mini" href="/api/simulation/${simulationId}/stundenwerte.xlsx">Stundenwerte Excel</a>
          <button class="knopf-haupt" id="btn-schliessen">Schließen</button>
        </div>
      </div>`;
    document.body.appendChild(fenster);
    fenster.querySelector("#btn-schliessen").onclick = () => fenster.remove();
    fenster.querySelector("#btn-protokoll").onclick = () => this._zeigeProtokoll(simulationId);

    const mehrKnopf = fenster.querySelector("#btn-warn-beispiele");
    if (mehrKnopf) {
      mehrKnopf.onclick = () => {
        const liste = fenster.querySelector("#warn-beispiele");
        liste.hidden = !liste.hidden;
        mehrKnopf.textContent = liste.hidden ? "Beispiele ansehen" : "Beispiele verbergen";
      };
    }
  },

  /** Das Stundenprotokoll der am Datenlogger angeschlossenen Werte - ein
   * eigener Abruf statt Teil von zeigeBilanz(): bei einem Jahreslauf mehrere
   * Megabyte gross, und die meisten Anlagen haben ueberhaupt keinen
   * bestueckten Datenlogger (siehe routes/simulation.py, protokoll()). Wird
   * daher nur geladen, wenn tatsaechlich danach gefragt wird. */
  async _zeigeProtokoll(simulationId) {
    let antwort;
    try {
      antwort = await fetch(`/api/simulation/${simulationId}/protokoll`);
    } catch {
      zeigeFehler("Stundenprotokoll konnte nicht geladen werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Stundenprotokoll konnte nicht geladen werden.");
      return;
    }
    const { spalten } = await antwort.json();
    if (!spalten.length) {
      zeigeFehler(
        "Kein Datenlogger mit benannten Anschlüssen in dieser Anlage – " +
          "siehe Erklärbereich „Bausteine“, Abschnitt „Den Datenlogger einbauen“."
      );
      return;
    }

    const stundenzahl = spalten[0].werte.length;
    const kopfzellen = spalten
      .map(
        (s) =>
          `<th>${htmlSicher(s.name)}${s.einheit ? ` [${htmlSicher(s.einheit)}]` : ""}</th>`
      )
      .join("");
    const zeilen = [];
    for (let stunde = 0; stunde < stundenzahl; stunde++) {
      const zellen = spalten
        .map((s) => `<td>${Zahlen.fest(s.werte[stunde], 2)}</td>`)
        .join("");
      zeilen.push(`<tr><td>${stunde + 1}</td>${zellen}</tr>`);
    }

    const fenster = document.createElement("div");
    fenster.className = "dialog-huelle";
    fenster.innerHTML = `
      <div class="dialog dialog-breit">
        <h2>Stundenprotokoll</h2>
        <p class="protokoll-hinweis">${stundenzahl} Stunden · ${spalten.length}
          Spalte${spalten.length === 1 ? "" : "n"} vom Datenlogger.</p>
        <div class="protokoll-huelle">
          <table class="protokoll">
            <thead><tr><th>Stunde</th>${kopfzellen}</tr></thead>
            <tbody>${zeilen.join("")}</tbody>
          </table>
        </div>
        <div class="dialog-knoepfe">
          <button class="knopf-haupt" id="btn-schliessen">Schließen</button>
        </div>
      </div>`;
    document.body.appendChild(fenster);
    fenster.querySelector("#btn-schliessen").onclick = () => fenster.remove();
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

  /** Warntexte, die Bausteine waehrend der Rechnung in ihre Ausgabe
   * geschrieben haben (z.B. ein unterdimensionierter Kuehler) - anders als bei
   * den Konvergenzwarnungen des Solvers sind das schon je Karte und Wortlaut
   * gruppierte Eintraege (core.ergebnisse.lade_baustein_warnungen), nie mehr
   * als eine Handvoll Zeilen, darum ohne Einklapp-Knopf direkt sichtbar. */
  _bausteinWarnhinweisHtml(liste) {
    if (!liste.length) {
      return '<p class="warnhinweis warnhinweis-ok">Keine Warnungen aus Bausteinen.</p>';
    }
    const zeilen = liste
      .map((w) => {
        const beispiele = (w.beispiele || []).map((s) => `Stunde ${s}`).join(", ");
        const stundenwort = w.anzahl === 1 ? "Stunde" : "Stunden";
        return `<li><strong>${htmlSicher(w.karte_name)}</strong>: ${htmlSicher(w.text)}
          — ${w.anzahl} ${stundenwort} (z.B. ${beispiele})</li>`;
      })
      .join("");
    return `
      <div class="warnhinweis">
        <p>Warnungen aus Bausteinen</p>
        <ul class="warn-beispiele">${zeilen}</ul>
      </div>`;
  },
};

/* Vergleich mehrerer Wetterjahre derselben Anlage (Vorhaben B): ein Lauf je
   ausgewaehltem Wetterdatensatz, nacheinander im Hintergrund
   (core/laeufe.py, starte_reihe()) - dieselbe Idee wie Simulation oben, nur
   ueber eine ganze Reihe von Laeufen statt einem einzelnen. Bewusst ein
   eigenes Objekt statt Teil von Simulation: eigene Fortschrittsanzeige
   (Jahr X von Y ZUSAETZLICH zu Stunde A von B), eigener Abbruch (der auch
   die noch nicht begonnenen Jahre verhindert, core.laeufe.reihe_abbrechen),
   eigene Wiederaufnahme nach einem Neuladen. */
const Vergleich = {
  reihenKennung: null,
  aktiv: false,

  async dialogOeffnen() {
    if (this.aktiv) {
      zeigeFehler("Es läuft bereits eine Reihe für diese Anlage. Bitte warten oder abbrechen.");
      return;
    }
    if (typeof Simulation !== "undefined" && Simulation.aktiv) {
      zeigeFehler("Es läuft bereits eine Simulation. Bitte warten oder abbrechen.");
      return;
    }

    let wetter;
    let bereiche;
    try {
      const [wetterAntwort, bereichAntwort] = await Promise.all([
        fetch("/api/wetter"),
        fetch("/api/simulation/schnellwahl"),
      ]);
      if (!wetterAntwort.ok || !bereichAntwort.ok) {
        zeigeFehler("Vergleichsdialog konnte nicht geöffnet werden.");
        return;
      }
      wetter = await wetterAntwort.json();
      bereiche = await bereichAntwort.json();
    } catch {
      zeigeFehler("Vergleichsdialog konnte nicht geöffnet werden.");
      return;
    }

    if (wetter.length < 2) {
      zeigeFehler(
        "Für einen Vergleich werden mindestens zwei Wetterdatensätze gebraucht " +
          "– aktuell steht höchstens einer zur Verfügung."
      );
      return;
    }

    const dialog = document.createElement("div");
    dialog.className = "dialog-huelle";
    dialog.innerHTML = `
      <div class="dialog">
        <h2>Wetterjahre vergleichen</h2>
        <p class="vergleich-hinweis">Dieselbe Anlage wird nacheinander mit jedem
          ausgewählten Wetterdatensatz gerechnet – ein Jahreslauf dauert rund
          acht Minuten je Datensatz.</p>
        <label class="panel-zeile">
          <span class="panel-label">Wetterdatensätze – Strg/Cmd-Klick für mehrere</span>
          <select id="wahl-wetter-reihe" multiple size="6">
            ${wetter
              .map((w) => `<option value="${w.id}">${htmlSicher(w.name)} (${w.stunden} h)</option>`)
              .join("")}
          </select>
        </label>
        <label class="panel-zeile">
          <span class="panel-label">Zeitraum (für jedes Jahr gleich)</span>
          <select id="wahl-bereich-reihe">
            ${Object.keys(bereiche)
              .map((n) => `<option value="${n}">${BESCHRIFTUNG[n] || n}</option>`)
              .join("")}
            <option value="eigen">${BESCHRIFTUNG.eigen}</option>
          </select>
        </label>
        <div class="panel-zeile panel-zeile-nebeneinander" id="wahl-eigen-reihe" hidden>
          <label class="panel-zeile">
            <span class="panel-label">von Stunde</span>
            <input type="number" id="wahl-von-reihe" min="0" max="8759" value="0">
          </label>
          <label class="panel-zeile">
            <span class="panel-label">bis Stunde</span>
            <input type="number" id="wahl-bis-reihe" min="1" max="8760" value="8760">
          </label>
        </div>
        <div class="dialog-knoepfe">
          <button id="btn-vergleich-abbrechen">Abbrechen</button>
          <button class="knopf-haupt" id="btn-vergleich-los">Los</button>
        </div>
      </div>`;
    document.body.appendChild(dialog);

    const eigenBereich = dialog.querySelector("#wahl-eigen-reihe");
    dialog.querySelector("#wahl-bereich-reihe").addEventListener("change", (e) => {
      eigenBereich.hidden = e.target.value !== "eigen";
    });

    dialog.querySelector("#btn-vergleich-abbrechen").onclick = () => dialog.remove();
    dialog.querySelector("#btn-vergleich-los").onclick = () => {
      const auswahl = Array.from(
        dialog.querySelector("#wahl-wetter-reihe").selectedOptions
      ).map((o) => Number(o.value));
      if (auswahl.length < 1) {
        zeigeFehler("Bitte mindestens einen Wetterdatensatz auswählen.");
        return;
      }
      const bereichName = dialog.querySelector("#wahl-bereich-reihe").value;
      let von;
      let bis;
      if (bereichName === "eigen") {
        von = Number(dialog.querySelector("#wahl-von-reihe").value);
        bis = Number(dialog.querySelector("#wahl-bis-reihe").value);
        if (!Number.isFinite(von) || !Number.isFinite(bis) || von < 0 || bis <= von) {
          zeigeFehler("Der eigene Zeitraum ist ungültig.");
          return;
        }
      } else {
        von = bereiche[bereichName].von;
        bis = bereiche[bereichName].bis;
      }
      dialog.remove();
      this.starten(auswahl, von, bis);
    };
  },

  async starten(wetterdatensatzIds, von, bis) {
    let antwort;
    try {
      antwort = await fetch("/api/simulation/reihe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          anlage_id: Editor.anlage.id,
          wetterdatensatz_ids: wetterdatensatzIds,
          von, bis,
        }),
      });
    } catch {
      zeigeFehler("Reihe konnte nicht gestartet werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Reihe konnte nicht gestartet werden.");
      return;
    }
    const { reihen_kennung } = await antwort.json();
    this._wiederAufnehmen(reihen_kennung);
  },

  _wiederAufnehmen(reihenKennung) {
    this.reihenKennung = reihenKennung;
    this.aktiv = true;
    this._vergleichKnopfAktivieren(false);
    this.zeigeFortschritt(reihenKennung);
    this.beobachte(reihenKennung);
  },

  // Beim Laden der Editorseite fragen, ob fuer diese Anlage bereits eine
  // Reihe laeuft (z.B. weil die Seite mitten in einem Drei-Jahres-Vergleich
  // neu geladen wurde) - analog zu Simulation.pruefeLaufendenLauf().
  async pruefeLaufendeReihe() {
    if (this.aktiv || typeof window.ANLAGE_ID === "undefined") return;
    let antwort;
    try {
      antwort = await fetch(`/api/simulation/reihe/laufend/${window.ANLAGE_ID}`);
    } catch {
      return;
    }
    if (!antwort.ok) return;
    const stand = await antwort.json();
    if (!stand || !stand.reihen_kennung || stand.status !== "laeuft") return;
    this._wiederAufnehmen(stand.reihen_kennung);
  },

  _vergleichKnopfAktivieren(aktiviert) {
    const knopf = document.getElementById("btn-vergleich");
    if (knopf) knopf.disabled = !aktiviert;
  },

  _beendet() {
    this.aktiv = false;
    this._vergleichKnopfAktivieren(true);
  },

  zeigeFortschritt(reihenKennung) {
    const alte = document.querySelector(".reihen-fortschritt-huelle");
    if (alte) alte.remove();

    const huelle = document.createElement("div");
    huelle.className = "fortschritt-huelle reihen-fortschritt-huelle";
    huelle.innerHTML = `
      <div class="fortschritt">
        <div class="fortschritt-text" id="reihe-fortschritt-jahr">Reihe läuft …</div>
        <div class="fortschritt-schiene"><div id="reihe-fortschritt-jahr-balken"></div></div>
        <div class="fortschritt-text" id="reihe-fortschritt-stunde"></div>
        <div class="fortschritt-schiene"><div id="reihe-fortschritt-stunde-balken"></div></div>
        <button id="btn-reihe-abbrechen">Abbrechen</button>
      </div>`;
    document.body.appendChild(huelle);
    huelle.querySelector("#btn-reihe-abbrechen").onclick = async (e) => {
      const knopf = e.target;
      knopf.disabled = true;
      knopf.textContent = "Wird abgebrochen …";
      try {
        const antwort = await fetch(`/api/simulation/reihe/${reihenKennung}/abbrechen`, {
          method: "POST",
        });
        if (!antwort.ok) throw new Error("nicht ok");
      } catch {
        zeigeFehler("Abbruch konnte nicht übermittelt werden.");
        knopf.disabled = false;
        knopf.textContent = "Abbrechen";
      }
      // Der eigentliche Abbruch (aktuelles Jahr UND alle noch nicht
      // begonnenen) zeigt sich im naechsten Abfrageschritt von beobachte()
      // als Status "abgebrochen" - hier ist nichts weiter zu tun.
    };
  },

  _aktualisiereFortschrittsanzeige(reihenStand) {
    const jahrGesamt = reihenStand.jahr_gesamt || 0;
    const jahrIndex = reihenStand.jahr_index || 0;
    const jahrAnteil = jahrGesamt ? Math.max(0, jahrIndex - 1) / jahrGesamt : 0;
    const jahrBalken = document.getElementById("reihe-fortschritt-jahr-balken");
    if (jahrBalken) jahrBalken.style.width = `${(jahrAnteil * 100).toFixed(1)}%`;
    const jahrText = document.getElementById("reihe-fortschritt-jahr");
    if (jahrText) {
      jahrText.textContent = jahrGesamt
        ? `Jahr ${jahrIndex} von ${jahrGesamt}`
        : "Reihe läuft …";
    }

    const aktuellerLaufStand = reihenStand._aktuellerLaufStand || {};
    const fertig = aktuellerLaufStand.fertig || 0;
    const gesamtStunden = aktuellerLaufStand.gesamt || 0;
    const stundenAnteil = gesamtStunden ? fertig / gesamtStunden : 0;
    const stundenBalken = document.getElementById("reihe-fortschritt-stunde-balken");
    if (stundenBalken) stundenBalken.style.width = `${(stundenAnteil * 100).toFixed(1)}%`;
    const stundenText = document.getElementById("reihe-fortschritt-stunde");
    if (stundenText) {
      stundenText.textContent = gesamtStunden ? `Stunde ${fertig} von ${gesamtStunden}` : "";
    }
  },

  // 'reihenKennung' als Parameter uebernommen statt bei jedem Schleifendurchlauf
  // erneut aus this.reihenKennung gelesen - dieselbe Begruendung wie bei
  // Simulation.beobachte().
  async beobachte(reihenKennung) {
    const start = Date.now();
    let fehlversuche = 0;
    while (true) {
      let reihenStand;
      try {
        const antwort = await fetch(`/api/simulation/reihe/${reihenKennung}`);
        if (!antwort.ok) throw new Error("Antwort nicht ok");
        reihenStand = await antwort.json();
        fehlversuche = 0;
      } catch {
        fehlversuche += 1;
        if (fehlversuche >= FORTSCHRITT_MAX_FEHLVERSUCHE) {
          const huelle = document.querySelector(".reihen-fortschritt-huelle");
          if (huelle) huelle.remove();
          this._beendet();
          zeigeFehler("Verbindung zum Server verloren. Die Reihe läuft im Hintergrund weiter.");
          return;
        }
        await new Promise((r) => setTimeout(r, FORTSCHRITT_INTERVALL_KURZ_MS));
        continue;
      }

      // Der Fortschritt des laufenden Jahres selbst (Stunde X von Y) kommt
      // aus dem bestehenden Einzellauf-Endpunkt - der Reihen-Stand traegt
      // nur dessen Kennung, nicht seinen Stundenfortschritt.
      if (reihenStand.aktuelle_kennung) {
        try {
          const laufAntwort = await fetch(`/api/simulation/${reihenStand.aktuelle_kennung}`);
          if (laufAntwort.ok) reihenStand._aktuellerLaufStand = await laufAntwort.json();
        } catch {
          /* Der Reihen-Fortschritt (Jahr X von Y) bleibt trotzdem lesbar. */
        }
      }
      this._aktualisiereFortschrittsanzeige(reihenStand);

      if (["fertig", "abgebrochen"].includes(reihenStand.status)) {
        const huelle = document.querySelector(".reihen-fortschritt-huelle");
        if (huelle) huelle.remove();
        this._beendet();
        await this.zeigeErgebnis(reihenStand);
        return;
      }
      await new Promise((r) => setTimeout(r, naechstesIntervall(start)));
    }
  },

  /** Nach dem Ende der Reihe (fertig oder abgebrochen): die Ergebnisse der
   * gelungenen Jahre in eine Gegenueberstellung (core/vergleich.py) laden,
   * fehlgeschlagene Jahre als Hinweis benennen statt sie zu verschweigen -
   * "der Vergleich zeigt, was da ist, und benennt, was fehlt". */
  async zeigeErgebnis(reihenStand) {
    const ergebnisListe = reihenStand.ergebnisse || [];
    const ids = ergebnisListe.filter((e) => e.simulation_id).map((e) => e.simulation_id);

    let wetterListe = [];
    try {
      const wetterAntwort = await fetch("/api/wetter");
      if (wetterAntwort.ok) wetterListe = await wetterAntwort.json();
    } catch {
      /* Nur fuer die Namen der fehlenden Jahre unten - kein Abbruchgrund. */
    }
    const wetterName = (id) => {
      const treffer = wetterListe.find((w) => w.id === id);
      return treffer ? treffer.name : `Wetterdatensatz ${id}`;
    };
    const fehlendeHtml = ergebnisListe
      .filter((e) => !e.simulation_id || e.status === "fehler")
      .map(
        (e) =>
          `<li>${htmlSicher(wetterName(e.wetterdatensatz_id))}: ${htmlSicher(e.fehler || "kein Ergebnis")}</li>`
      )
      .join("");
    const nichtGerechnetHtml = fehlendeHtml
      ? `<div class="warnhinweis"><p>Nicht gerechnet:</p><ul class="warn-beispiele">${fehlendeHtml}</ul></div>`
      : "";

    if (!ids.length) {
      const fenster = document.createElement("div");
      fenster.className = "dialog-huelle";
      fenster.innerHTML = `
        <div class="dialog">
          <h2>Vergleich der Wetterjahre</h2>
          <p class="warnhinweis">Kein Lauf der Reihe hat ein Ergebnis geliefert.</p>
          ${nichtGerechnetHtml}
          <div class="dialog-knoepfe">
            <button class="knopf-haupt" id="btn-schliessen">Schließen</button>
          </div>
        </div>`;
      document.body.appendChild(fenster);
      fenster.querySelector("#btn-schliessen").onclick = () => fenster.remove();
      return;
    }

    let antwort;
    try {
      antwort = await fetch(`/api/simulation/vergleich?ids=${ids.join(",")}`);
    } catch {
      zeigeFehler("Vergleich konnte nicht geladen werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Vergleich konnte nicht geladen werden.");
      return;
    }
    const daten = await antwort.json();
    this._zeigeVergleichsfenster(daten, nichtGerechnetHtml, ids);
  },

  _zeigeVergleichsfenster(daten, nichtGerechnetHtml, ids) {
    const kopfzellen = daten.laeufe
      .map(
        (l) =>
          `<th>${htmlSicher(l.wetter_name)}${
            l.hat_ergebnis ? "" : ' <span class="vergleich-kein-ergebnis">(kein Ergebnis)</span>'
          }</th>`
      )
      .join("");
    const zeilen = daten.zeilen
      .map((zeile) => {
        const zellen = zeile.werte
          .map((w) => {
            if (w.menge === null || w.menge === undefined) {
              return `<td class="zahl">–</td>`;
            }
            let abweichungHtml = "";
            if (w.abweichung !== null && w.abweichung !== undefined) {
              const klasse =
                w.abweichung >= 0 ? "vergleich-abweichung-plus" : "vergleich-abweichung-minus";
              const vorzeichen = w.abweichung >= 0 ? "+" : "";
              abweichungHtml = ` <span class="vergleich-abweichung ${klasse}">${vorzeichen}${Zahlen.fest(
                w.abweichung * 100, 1
              )} %</span>`;
            }
            return `<td class="zahl">${Zahlen.fest(w.menge, 3)}${abweichungHtml}</td>`;
          })
          .join("");
        const label = `${GROESSEN[zeile.groesse] || zeile.groesse} [${zeile.einheit}]`;
        return `<tr><td>${label}</td>${zellen}</tr>`;
      })
      .join("");
    const kostenZeile = daten.laeufe
      .map(
        (l) =>
          `<td class="zahl">${l.hat_ergebnis ? `${Zahlen.fest(l.kosten_gesamt, 2)} EUR` : "–"}</td>`
      )
      .join("");
    const warnZeile = daten.laeufe
      .map((l) => `<td class="zahl">${l.hat_ergebnis ? l.anzahl_warnungen : "–"}</td>`)
      .join("");

    const fenster = document.createElement("div");
    fenster.className = "dialog-huelle";
    fenster.innerHTML = `
      <div class="dialog dialog-breit">
        <h2>Vergleich der Wetterjahre</h2>
        ${nichtGerechnetHtml}
        <div class="vergleich-tabelle-huelle">
          <table class="bilanz vergleich-tabelle">
            <thead><tr><th>Größe</th>${kopfzellen}</tr></thead>
            <tbody>
              ${zeilen}
              <tr class="vergleich-zeile-kosten"><td>Kosten gesamt</td>${kostenZeile}</tr>
              <tr class="vergleich-zeile-warnungen"><td>Warnungen</td>${warnZeile}</tr>
            </tbody>
          </table>
        </div>
        <img class="vergleich-diagramm" alt="Jahresbilanz im Vergleich"
             src="/api/simulation/vergleich/diagramm.svg?ids=${ids.join(",")}">
        <div class="dialog-knoepfe">
          <button class="knopf-haupt" id="btn-schliessen">Schließen</button>
        </div>
      </div>`;
    document.body.appendChild(fenster);
    fenster.querySelector("#btn-schliessen").onclick = () => fenster.remove();
  },
};

window.addEventListener("DOMContentLoaded", () => {
  const knopf = document.getElementById("btn-simulieren");
  if (knopf) knopf.onclick = () => Simulation.dialogOeffnen();
  Simulation.pruefeLaufendenLauf();

  const vergleichKnopf = document.getElementById("btn-vergleich");
  if (vergleichKnopf) vergleichKnopf.onclick = () => Vergleich.dialogOeffnen();
  Vergleich.pruefeLaufendeReihe();
});
