/* Startseite: Projekte mit ihren Anlagen, Anlage anlegen (leer oder aus
   Vorlage), Wetterdaten hochladen und einsehen.

   Eigenstaendiges Modul statt Mitbenutzung von editor.js/simulation.js: diese
   Seite laedt weder Editor noch Panel noch Pfeile, und ein stiller Aufruf
   einer dort nur scheinbar vorhandenen Funktion waere ein Fehler, der erst
   beim Klicken auffiele. zeigeFehler() und htmlSicher() sind hier deshalb
   noch einmal (kurz) selbst definiert statt aus editor.js/simulation.js
   importiert - im Editor ist genau eine solche stille Abhaengigkeit schon
   einmal angemerkt worden (siehe tests/test_pages.py). */

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

const BADGE_TEXT = {
  fertig: (l) => `Letzter Lauf: ${l.kosten_gesamt.toFixed(2)} EUR`,
  abgebrochen: () => "Letzter Lauf abgebrochen",
  fehler: () => "Letzter Lauf fehlgeschlagen",
};

// Anzeigetext je Quelle eines Wetterdatensatzes - der Rohwert aus der DB
// ("upload"/"open-meteo") ist fuer den Code praktisch, fuer die Liste aber
// zu technisch.
const WETTER_QUELLE_TEXT = {
  upload: "Datei-Upload",
  "open-meteo": "Online-Abruf",
};

// Erstes Jahr, das die Open-Meteo Archive-API anbietet (core/wetter/openmeteo.py:
// FRUEHESTES_JAHR) - hier dupliziert, weil die Grenze rein in der Oberflaeche
// gebraucht wird und dafuer keine eigene Schnittstelle lohnt.
const WETTER_FRUEHESTES_JAHR = 1940;

const Start = {
  projekte: [],
  anlagen: [],
  wetter: [],
  vorlagen: {},

  async laden() {
    let antworten;
    try {
      antworten = await Promise.all([
        fetch("/api/projekte"),
        fetch("/api/anlagen"),
        fetch("/api/wetter"),
        fetch("/api/vorlagen"),
      ]);
    } catch {
      zeigeFehler("Startseite konnte nicht geladen werden.");
      return;
    }
    if (antworten.some((a) => !a.ok)) {
      zeigeFehler("Startseite konnte nicht geladen werden.");
      return;
    }
    [this.projekte, this.anlagen, this.wetter, this.vorlagen] =
      await Promise.all(antworten.map((a) => a.json()));

    await this.zeichneProjekte();
    this.zeichneWetter();
  },

  // -- Projekte und Anlagen ------------------------------------------------

  async zeichneProjekte() {
    const bereich = document.getElementById("start-projekte");
    bereich.textContent = "";

    if (!this.projekte.length) {
      bereich.appendChild(this.leerhinweisElement());
      return;
    }

    const karten = await Promise.all(
      this.projekte.map((p) => this.projektKarteElement(p))
    );
    karten.forEach((karte) => bereich.appendChild(karte));
  },

  leerhinweisElement() {
    const div = document.createElement("div");
    div.className = "leerhinweis-gross";
    const titel = document.createElement("h2");
    titel.textContent = "Noch kein Projekt vorhanden";
    const text = document.createElement("p");
    text.textContent =
      "Lege zuerst ein Projekt an, dann darin eine Anlage – leer oder aus der " +
      "mitgelieferten Vorlage AX_SIM 2.1 (zwei Lüftungsgeräte an gemeinsamer " +
      "Wärmerückgewinnung, ein Raum). Für einen Simulationslauf werden außerdem " +
      "Wetterdaten gebraucht, weiter unten hochzuladen.";
    const knopf = document.createElement("button");
    knopf.className = "knopf-haupt";
    knopf.textContent = "Erstes Projekt anlegen";
    knopf.addEventListener("click", () => this.projektAnlegenDialog());
    div.append(titel, text, knopf);
    return div;
  },

  async projektKarteElement(projekt) {
    const div = document.createElement("div");
    div.className = "projekt-karte";

    const kopf = document.createElement("div");
    kopf.className = "projekt-kopf";
    const kopfZeile = document.createElement("div");
    kopfZeile.className = "projekt-kopf-zeile";
    const titel = document.createElement("h2");
    titel.textContent = projekt.name;
    kopfZeile.appendChild(titel);
    kopfZeile.appendChild(this.eintragAktionenElement(
      () => this.projektUmbenennenDialog(projekt),
      () => this.projektLoeschenDialog(projekt),
    ));
    kopf.appendChild(kopfZeile);
    if (projekt.beschreibung) {
      const beschreibung = document.createElement("p");
      beschreibung.className = "projekt-beschreibung";
      beschreibung.textContent = projekt.beschreibung;
      kopf.appendChild(beschreibung);
    }
    div.appendChild(kopf);

    const anlagenDesProjekts = this.anlagen.filter((a) => a.projekt_id === projekt.id);
    const liste = document.createElement("div");
    liste.className = "anlagen-liste";
    if (!anlagenDesProjekts.length) {
      const hinweis = document.createElement("p");
      hinweis.className = "leerhinweis";
      hinweis.textContent = "Noch keine Anlage in diesem Projekt.";
      liste.appendChild(hinweis);
    } else {
      const karten = await Promise.all(
        anlagenDesProjekts.map((a) => this.anlageKarteElement(a))
      );
      karten.forEach((karte) => liste.appendChild(karte));
    }
    div.appendChild(liste);

    const aktionen = document.createElement("div");
    aktionen.className = "projekt-aktionen";
    const btnAnlage = document.createElement("button");
    btnAnlage.textContent = "+ Anlage";
    btnAnlage.addEventListener("click", () => this.anlageAnlegenDialog(projekt));
    aktionen.appendChild(btnAnlage);
    div.appendChild(aktionen);

    return div;
  },

  async anlageKarteElement(anlage) {
    const status = await this.ladeStatus(anlage.id);

    const link = document.createElement("a");
    link.className = "anlage-karte";
    link.href = `/anlage/${anlage.id}`;

    const name = document.createElement("div");
    name.className = "anlage-name";
    name.textContent = anlage.name;
    link.appendChild(name);

    const info = document.createElement("div");
    info.className = "anlage-info";
    info.textContent = `${anlage.karten} ${anlage.karten === 1 ? "Karte" : "Karten"}`;
    link.appendChild(info);

    const badge = document.createElement("div");
    badge.className = "anlage-status";
    this._fuelleStatus(badge, status);
    link.appendChild(badge);

    // Umbenennen/Loeschen als eigene Zeile UNTER dem Link statt darin - ein
    // <button> innerhalb eines <a> wuerde beim Klick immer auch navigieren.
    const eintrag = document.createElement("div");
    eintrag.className = "anlage-eintrag";
    eintrag.appendChild(link);
    eintrag.appendChild(this.eintragAktionenElement(
      () => this.anlageUmbenennenDialog(anlage),
      () => this.anlageLoeschenDialog(anlage),
    ));
    return eintrag;
  },

  // Zwei kleine Knoepfe (Umbenennen/Loeschen) - fuer Projekt- und
  // Anlagekarten identisch aufgebaut, deshalb hier einmal gemeinsam gebaut.
  eintragAktionenElement(umbenennen, loeschen) {
    const zeile = document.createElement("div");
    zeile.className = "eintrag-aktionen";
    const btnUmbenennen = document.createElement("button");
    btnUmbenennen.type = "button";
    btnUmbenennen.className = "knopf-mini";
    btnUmbenennen.textContent = "Umbenennen";
    btnUmbenennen.addEventListener("click", (e) => { e.preventDefault(); umbenennen(); });
    const btnLoeschen = document.createElement("button");
    btnLoeschen.type = "button";
    btnLoeschen.className = "knopf-mini knopf-mini-gefahr";
    btnLoeschen.textContent = "Löschen";
    btnLoeschen.addEventListener("click", (e) => { e.preventDefault(); loeschen(); });
    zeile.append(btnUmbenennen, btnLoeschen);
    return zeile;
  },

  async projektUmbenennenDialog(projekt) {
    const neuerName = await textEingabeDialog("Projekt umbenennen", projekt.name);
    if (neuerName === null) return;
    let antwort;
    try {
      antwort = await fetch(`/api/projekte/${projekt.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: neuerName }),
      });
    } catch {
      zeigeFehler("Projekt konnte nicht umbenannt werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Projekt konnte nicht umbenannt werden.");
      return;
    }
    await this.laden();
  },

  // 'projekt.anlagen'/'projekt.simulationen' kommen bereits gezaehlt von
  // /api/projekte (core.anlagen.projekte()) - keine eigene Abfrage noetig,
  // um die Rueckfrage mit einer Zahl statt eines blossen "Wirklich loeschen?"
  // zu fuellen.
  async projektLoeschenDialog(projekt) {
    const bestaetigt = await bestaetigenDialog(
      "Projekt löschen",
      `Projekt "${htmlSicher(projekt.name)}" wirklich löschen?` +
        this._verlustHinweis([
          [projekt.anlagen, "Anlage", "Anlagen"],
          [projekt.simulationen, "Simulationslauf", "Simulationsläufen"],
        ])
    );
    if (!bestaetigt) return;
    let antwort;
    try {
      antwort = await fetch(`/api/projekte/${projekt.id}`, { method: "DELETE" });
    } catch {
      zeigeFehler("Projekt konnte nicht gelöscht werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Projekt konnte nicht gelöscht werden.");
      return;
    }
    await this.laden();
  },

  async anlageUmbenennenDialog(anlage) {
    const neuerName = await textEingabeDialog("Anlage umbenennen", anlage.name);
    if (neuerName === null) return;
    let antwort;
    try {
      antwort = await fetch(`/api/anlagen/${anlage.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: neuerName }),
      });
    } catch {
      zeigeFehler("Anlage konnte nicht umbenannt werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Anlage konnte nicht umbenannt werden.");
      return;
    }
    await this.laden();
  },

  async anlageLoeschenDialog(anlage) {
    const bestaetigt = await bestaetigenDialog(
      "Anlage löschen",
      `Anlage "${htmlSicher(anlage.name)}" wirklich löschen?` +
        this._verlustHinweis([
          [anlage.karten, "Karte", "Karten"],
          [anlage.simulationen, "Simulationslauf", "Simulationsläufen"],
        ])
    );
    if (!bestaetigt) return;
    let antwort;
    try {
      antwort = await fetch(`/api/anlagen/${anlage.id}`, { method: "DELETE" });
    } catch {
      zeigeFehler("Anlage konnte nicht gelöscht werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Anlage konnte nicht gelöscht werden.");
      return;
    }
    await this.laden();
  },

  // Baut aus [[anzahl, einzahl, mehrzahl], ...] den Satz 'Werden mit
  // gelöscht: 3 Anlagen, 12 Simulationsläufen.' - und, wenn alle Zahlen 0
  // sind (eine leere Anlage/ein leeres Projekt), gar nichts: dann geht
  // nichts weiter verloren, eine Rueckfrage ohne Zahlen waere hier keine
  // zusaetzliche Auskunft.
  _verlustHinweis(teile) {
    const genannt = teile
      .filter(([anzahl]) => anzahl)
      .map(([anzahl, einzahl, mehrzahl]) => `${anzahl} ${anzahl === 1 ? einzahl : mehrzahl}`);
    if (!genannt.length) return "";
    return ` <span class="dialog-text-verlust">Werden mit gelöscht: ${genannt.join(", ")}.</span>`;
  },

  _fuelleStatus(badge, status) {
    if (status.fehler) {
      badge.textContent = "Status nicht abrufbar";
      badge.classList.add("anlage-status-unbekannt");
      return;
    }
    if (status.letzter && status.letzter.status === "laeuft") {
      const fortschritt = status.fortschritt;
      badge.textContent =
        fortschritt && fortschritt.gesamt
          ? `läuft … ${fortschritt.fertig || 0}/${fortschritt.gesamt} Std.`
          : "läuft …";
      badge.classList.add("anlage-status-laeuft");
      return;
    }
    if (!status.letzter) {
      badge.textContent = "Noch nicht simuliert";
      badge.classList.add("anlage-status-offen");
      return;
    }
    const formatiere = BADGE_TEXT[status.letzter.status];
    badge.textContent = formatiere
      ? formatiere(status.letzter)
      : `Letzter Lauf: ${status.letzter.status}`;
    badge.classList.add(
      status.letzter.status === "fertig"
        ? "anlage-status-fertig"
        : "anlage-status-warnung"
    );
  },

  // Ob fuer eine Anlage gerade ein Lauf rechnet, und was der letzte Lauf ergab
  // - so weit die Endpunkte das hergeben. Ein Fehlschlag hier legt nicht die
  // ganze Seite lahm (die Karte bleibt als Verweis in den Editor nutzbar) -
  // er zeigt sich sichtbar als eigenes Abzeichen auf genau dieser Karte statt
  // ueber die gemeinsame Fehlerleiste, die sonst bei vielen Anlagen mehrfach
  // aufblitzen wuerde.
  async ladeStatus(anlageId) {
    let antwort;
    try {
      antwort = await fetch(`/api/anlagen/${anlageId}/simulationen`);
    } catch {
      return { fehler: true };
    }
    if (!antwort.ok) return { fehler: true };
    const laeufe = await antwort.json();
    const letzter = laeufe[0] || null;
    if (!letzter || letzter.status !== "laeuft") {
      return { letzter };
    }

    let fortschritt = null;
    try {
      const fortschrittAntwort = await fetch(
        `/api/anlagen/${anlageId}/laufende_simulation`
      );
      if (fortschrittAntwort.ok) fortschritt = await fortschrittAntwort.json();
    } catch {
      // Der Fortschrittswert ist eine Zugabe zum blossen "laeuft" - sein
      // Fehlen soll die Karte nicht als fehlerhaft zeigen.
    }
    return { letzter, fortschritt };
  },

  projektAnlegenDialog() {
    const huelle = document.createElement("div");
    huelle.className = "dialog-huelle";
    huelle.innerHTML = `
      <div class="dialog">
        <h2>Projekt anlegen</h2>
        <label class="panel-zeile">
          <span class="panel-label">Name</span>
          <input type="text" id="feld-projekt-name">
        </label>
        <label class="panel-zeile">
          <span class="panel-label">Beschreibung</span>
          <input type="text" id="feld-projekt-beschreibung">
        </label>
        <div class="dialog-knoepfe">
          <button id="btn-abbrechen">Abbrechen</button>
          <button class="knopf-haupt" id="btn-anlegen">Anlegen</button>
        </div>
      </div>`;
    document.body.appendChild(huelle);

    huelle.querySelector("#btn-abbrechen").onclick = () => huelle.remove();
    huelle.querySelector("#btn-anlegen").onclick = async () => {
      const name = huelle.querySelector("#feld-projekt-name").value.trim();
      if (!name) {
        zeigeFehler("Bitte einen Namen eingeben.");
        return;
      }
      const beschreibung = huelle.querySelector("#feld-projekt-beschreibung").value.trim();

      let antwort;
      try {
        antwort = await fetch("/api/projekte", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, beschreibung }),
        });
      } catch {
        zeigeFehler("Projekt konnte nicht angelegt werden.");
        return;
      }
      if (!antwort.ok) {
        zeigeFehler("Projekt konnte nicht angelegt werden.");
        return;
      }
      huelle.remove();
      await this.laden();
    };
  },

  anlageAnlegenDialog(projekt) {
    const vorlagenHtml = Object.entries(this.vorlagen)
      .map(
        ([kennung, vorlage]) => `
        <label class="vorlage-wahl">
          <input type="radio" name="vorlage" value="${htmlSicher(kennung)}">
          <span>${htmlSicher(vorlage.beschreibung)}</span>
        </label>`
      )
      .join("");

    const huelle = document.createElement("div");
    huelle.className = "dialog-huelle";
    huelle.innerHTML = `
      <div class="dialog">
        <h2>Anlage anlegen – ${htmlSicher(projekt.name)}</h2>
        <label class="panel-zeile">
          <span class="panel-label">Name</span>
          <input type="text" id="feld-anlage-name" value="Neue Anlage">
        </label>
        <div class="panel-zeile">
          <span class="panel-label">Vorlage</span>
          <label class="vorlage-wahl">
            <input type="radio" name="vorlage" value="" checked>
            <span>Leere Leinwand</span>
          </label>
          ${vorlagenHtml}
        </div>
        <div class="dialog-knoepfe">
          <button id="btn-abbrechen">Abbrechen</button>
          <button class="knopf-haupt" id="btn-anlegen">Anlegen</button>
        </div>
      </div>`;
    document.body.appendChild(huelle);

    huelle.querySelector("#btn-abbrechen").onclick = () => huelle.remove();
    huelle.querySelector("#btn-anlegen").onclick = async () => {
      const name = huelle.querySelector("#feld-anlage-name").value.trim();
      if (!name) {
        zeigeFehler("Bitte einen Namen eingeben.");
        return;
      }
      const vorlage = huelle.querySelector('input[name="vorlage"]:checked').value;
      const knopf = huelle.querySelector("#btn-anlegen");
      knopf.disabled = true;

      let antwort;
      try {
        antwort = vorlage
          ? await fetch("/api/anlagen/aus_vorlage", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ vorlage, projekt_id: projekt.id, name }),
            })
          : await fetch("/api/anlagen", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ projekt_id: projekt.id, name }),
            });
      } catch {
        zeigeFehler("Anlage konnte nicht angelegt werden.");
        knopf.disabled = false;
        return;
      }
      if (!antwort.ok) {
        let text = "Anlage konnte nicht angelegt werden.";
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
      const daten = await antwort.json();
      // Direkt in den Editor - die neue Anlage anzulegen, nur um sie dann
      // wieder in einer Liste anzuzeigen, waere ein unnoetiger Umweg.
      window.location.href = `/anlage/${daten.id}`;
    };
  },

  // -- Wetterdaten ----------------------------------------------------------

  zeichneWetter() {
    const bereich = document.getElementById("start-wetter-liste");
    bereich.textContent = "";

    if (!this.wetter.length) {
      const hinweis = document.createElement("p");
      hinweis.className = "leerhinweis";
      hinweis.textContent =
        "Noch keine Wetterdaten hochgeladen. Ohne einen Datensatz kann kein " +
        "Simulationslauf starten.";
      bereich.appendChild(hinweis);
      return;
    }

    const zeilen = this.wetter
      .map(
        (w) => `
        <tr data-id="${w.id}">
          <td>${htmlSicher(w.name)}</td>
          <td><span class="wetter-quelle-etikett">${htmlSicher(
            WETTER_QUELLE_TEXT[w.quelle] || w.quelle
          )}</span></td>
          <td>${htmlSicher(w.ort)}</td>
          <td>${w.jahr ?? ""}</td>
          <td class="zahl">${w.stunden}</td>
          <td class="wetter-tabelle-aktionen">
            <button type="button" class="knopf-mini wetter-umbenennen">Umbenennen</button>
            <button type="button" class="knopf-mini knopf-mini-gefahr wetter-loeschen"
                    ${w.simulationen ? "disabled" : ""}
                    title="${
                      w.simulationen
                        ? `Wird von ${w.simulationen} ${
                            w.simulationen === 1 ? "Simulationslauf" : "Simulationsläufen"
                          } verwendet`
                        : ""
                    }">Löschen</button>
          </td>
        </tr>`
      )
      .join("");

    const tabelle = document.createElement("table");
    tabelle.className = "bilanz wetter-tabelle";
    tabelle.innerHTML = `
      <thead>
        <tr><th>Name</th><th>Quelle</th><th>Ort</th><th>Jahr</th>
            <th class="zahl">Stunden</th><th></th></tr>
      </thead>
      <tbody>${zeilen}</tbody>`;
    bereich.appendChild(tabelle);

    tabelle.querySelectorAll("tbody tr").forEach((zeile) => {
      const datensatz = this.wetter.find((w) => w.id === Number(zeile.dataset.id));
      zeile.querySelector(".wetter-umbenennen").addEventListener("click", () =>
        this.wetterUmbenennenDialog(datensatz)
      );
      zeile.querySelector(".wetter-loeschen").addEventListener("click", () =>
        this.wetterLoeschenDialog(datensatz)
      );
    });
  },

  async wetterUmbenennenDialog(datensatz) {
    const neuerName = await textEingabeDialog("Wetterdatensatz umbenennen", datensatz.name);
    if (neuerName === null) return;
    let antwort;
    try {
      antwort = await fetch(`/api/wetter/${datensatz.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: neuerName }),
      });
    } catch {
      zeigeFehler("Wetterdatensatz konnte nicht umbenannt werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Wetterdatensatz konnte nicht umbenannt werden.");
      return;
    }
    await this._wetterListeAktualisieren(
      "Umbenannt, die Liste konnte aber nicht aktualisiert werden."
    );
  },

  // Der Loeschknopf ist bei einem verwendeten Datensatz schon deaktiviert
  // (siehe zeichneWetter()) - dieser Zweig greift nur bei einem inzwischen
  // veralteten Stand (z.B. ein zweiter, offener Tab hat gerade einen Lauf
  // gestartet), nicht als erster Weg dorthin.
  async wetterLoeschenDialog(datensatz) {
    const bestaetigt = await bestaetigenDialog(
      "Wetterdatensatz löschen",
      `Wetterdatensatz "${htmlSicher(datensatz.name)}" (${datensatz.stunden} Stunden) ` +
        "wirklich löschen?"
    );
    if (!bestaetigt) return;
    let antwort;
    try {
      antwort = await fetch(`/api/wetter/${datensatz.id}`, { method: "DELETE" });
    } catch {
      zeigeFehler("Wetterdatensatz konnte nicht gelöscht werden.");
      return;
    }
    if (!antwort.ok) {
      let text = "Wetterdatensatz konnte nicht gelöscht werden.";
      try {
        const daten = await antwort.json();
        if (daten.fehler) text = daten.fehler;
      } catch {
        /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */
      }
      zeigeFehler(text);
      return;
    }
    await this._wetterListeAktualisieren(
      "Gelöscht, die Liste konnte aber nicht aktualisiert werden."
    );
  },

  // Zeigt den gewaehlten Dateinamen neben dem eigenen Dateiknopf an (siehe
  // templates/index.html, .datei-eingabe) - der native Dateiname landet per
  // textContent auf der Seite, kein innerHTML noetig.
  wetterDateiAktualisieren() {
    const dateiFeld = document.getElementById("feld-wetter-datei");
    const anzeige = document.getElementById("feld-wetter-dateiname");
    if (!dateiFeld || !anzeige) return;
    const datei = dateiFeld.files[0];
    anzeige.textContent = datei ? datei.name : "Keine Datei ausgewählt";
  },

  async wetterHochladen(ereignis) {
    ereignis.preventDefault();
    const dateiFeld = document.getElementById("feld-wetter-datei");
    const nameFeld = document.getElementById("feld-wetter-name");
    const knopf = document.getElementById("btn-wetter-hochladen");

    const datei = dateiFeld.files[0];
    if (!datei) {
      zeigeFehler("Bitte eine Datei auswählen.");
      return;
    }

    const formular = new FormData();
    formular.append("datei", datei);
    if (nameFeld.value.trim()) formular.append("name", nameFeld.value.trim());

    const urspruenglicherText = knopf.textContent;
    knopf.disabled = true;
    knopf.textContent = "Wird hochgeladen …";

    let antwort;
    try {
      antwort = await fetch("/api/wetter/upload", { method: "POST", body: formular });
    } catch {
      zeigeFehler("Wetterdatei konnte nicht hochgeladen werden.");
      knopf.disabled = false;
      knopf.textContent = urspruenglicherText;
      return;
    }
    if (!antwort.ok) {
      let text = "Wetterdatei konnte nicht hochgeladen werden.";
      try {
        const daten = await antwort.json();
        if (daten.fehler) text = daten.fehler;
      } catch {
        /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */
      }
      zeigeFehler(text);
      knopf.disabled = false;
      knopf.textContent = urspruenglicherText;
      return;
    }

    dateiFeld.value = "";
    nameFeld.value = "";
    this.wetterDateiAktualisieren();
    knopf.disabled = false;
    knopf.textContent = urspruenglicherText;

    await this._wetterListeAktualisieren(
      "Die Datei wurde hochgeladen, die Liste konnte aber nicht aktualisiert werden."
    );
  },

  // Nach einem Upload oder Abruf neu von /api/wetter laden, statt den neuen
  // Datensatz von Hand in this.wetter einzufuegen - die Liste bleibt so immer
  // deckungsgleich mit dem, was die Datenbank tatsaechlich enthaelt.
  async _wetterListeAktualisieren(fehlerBeiFehlschlag) {
    try {
      const antwort = await fetch("/api/wetter");
      if (!antwort.ok) throw new Error("Antwort nicht ok");
      this.wetter = await antwort.json();
    } catch {
      zeigeFehler(fehlerBeiFehlschlag);
      return;
    }
    this.zeichneWetter();
  },

  // Fuellt das Jahr-Mehrfachauswahlfeld mit allen abgeschlossenen
  // Kalenderjahren, die die Open-Meteo Archive-API anbietet (1940 bis zum
  // Vorjahr) - neuestes zuerst, weil das der haeufigste Wunsch ist. So kann
  // die Oberflaeche gar nicht erst ein unzulaessiges Jahr anbieten, statt den
  // Benutzer erst beim Absenden auf den Fehler laufen zu lassen.
  wetterAbrufJahreFuellen() {
    const feld = document.getElementById("feld-wetter-abruf-jahre");
    const letztesVollstaendigesJahr = new Date().getFullYear() - 1;
    feld.textContent = "";
    for (let jahr = letztesVollstaendigesJahr; jahr >= WETTER_FRUEHESTES_JAHR; jahr--) {
      const option = document.createElement("option");
      option.value = String(jahr);
      option.textContent = String(jahr);
      feld.appendChild(option);
    }
    // Bequemer Einstieg: das juengste verfuegbare Jahr ist vorausgewaehlt.
    if (feld.options.length) feld.options[0].selected = true;
  },

  // Zeigt/versteckt die Koordinatenfelder, je nachdem ob ein vorbelegter Ort
  // oder "Eigene Koordinaten" gewaehlt ist.
  wetterAbrufOrtGewaehlt() {
    const auswahl = document.getElementById("feld-wetter-abruf-ort");
    const koordinatenBereich = document.getElementById("wetter-abruf-koordinaten");
    koordinatenBereich.hidden = auswahl.value !== "eigene";
  },

  async wetterAbrufen(ereignis) {
    ereignis.preventDefault();

    const ortAuswahl = document.getElementById("feld-wetter-abruf-ort");
    const jahreFeld = document.getElementById("feld-wetter-abruf-jahre");
    const nameFeld = document.getElementById("feld-wetter-abruf-name");
    const knopf = document.getElementById("btn-wetter-abrufen");

    let ort;
    let breite;
    let laenge;
    if (ortAuswahl.value === "eigene") {
      const breiteFeld = document.getElementById("feld-wetter-abruf-breite");
      const laengeFeld = document.getElementById("feld-wetter-abruf-laenge");
      const ortsnameFeld = document.getElementById("feld-wetter-abruf-ortsname");
      breite = parseFloat(breiteFeld.value);
      laenge = parseFloat(laengeFeld.value);
      if (!Number.isFinite(breite) || !Number.isFinite(laenge)) {
        zeigeFehler("Bitte Breite und Länge als Zahl eingeben.");
        return;
      }
      ort = ortsnameFeld.value.trim() || `${breite}, ${laenge}`;
    } else {
      const gewaehlteOption = ortAuswahl.selectedOptions[0];
      breite = parseFloat(gewaehlteOption.dataset.breite);
      laenge = parseFloat(gewaehlteOption.dataset.laenge);
      ort = ortAuswahl.value;
    }

    const jahre = Array.from(jahreFeld.selectedOptions).map((o) => parseInt(o.value, 10));
    if (!jahre.length) {
      zeigeFehler("Bitte mindestens ein Jahr auswählen.");
      return;
    }

    const eigenerName = nameFeld.value.trim();
    const urspruenglicherText = knopf.textContent;
    knopf.disabled = true;

    // Ein Abruf je Jahr, hintereinander statt parallel - der Server schickt
    // pro Jahr bereits fuenf parallele Teilabfragen an Open-Meteo los,
    // mehrere Jahre gleichzeitig wuerden das unnoetig vervielfachen. Fehler
    // bei einem Jahr sollen die uebrigen Jahre nicht verhindern.
    const fehlgeschlagen = [];
    let erfolge = 0;
    for (let i = 0; i < jahre.length; i++) {
      const jahr = jahre[i];
      knopf.textContent =
        jahre.length > 1 ? `Wird abgerufen … (${i + 1}/${jahre.length})` : "Wird abgerufen …";

      const name = eigenerName ? (jahre.length > 1 ? `${eigenerName} ${jahr}` : eigenerName) : "";

      let antwort;
      try {
        antwort = await fetch("/api/wetter/abrufen", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ breite, laenge, jahr, ort, name }),
        });
      } catch {
        fehlgeschlagen.push(`${jahr}: Wetterdaten konnten nicht abgerufen werden`);
        continue;
      }
      if (!antwort.ok) {
        let text = "Wetterdaten konnten nicht abgerufen werden";
        try {
          const daten = await antwort.json();
          if (daten.fehler) text = daten.fehler;
        } catch {
          /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */
        }
        fehlgeschlagen.push(`${jahr}: ${text}`);
        continue;
      }
      erfolge++;
    }

    knopf.disabled = false;
    knopf.textContent = urspruenglicherText;

    if (fehlgeschlagen.length) {
      zeigeFehler(
        erfolge
          ? `${erfolge} von ${jahre.length} Jahren abgerufen. Fehlgeschlagen: ${fehlgeschlagen.join("; ")}`
          : `Abruf fehlgeschlagen: ${fehlgeschlagen.join("; ")}`
      );
    }

    if (erfolge) {
      nameFeld.value = "";
      await this._wetterListeAktualisieren(
        "Die Wetterdaten wurden abgerufen, die Liste konnte aber nicht aktualisiert werden."
      );
    }
  },
};

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-projekt-anlegen").addEventListener("click", () =>
    Start.projektAnlegenDialog()
  );
  document
    .getElementById("form-wetter-upload")
    .addEventListener("submit", (e) => Start.wetterHochladen(e));
  document
    .getElementById("feld-wetter-datei")
    .addEventListener("change", () => Start.wetterDateiAktualisieren());

  Start.wetterAbrufJahreFuellen();
  document
    .getElementById("feld-wetter-abruf-ort")
    .addEventListener("change", () => Start.wetterAbrufOrtGewaehlt());
  document
    .getElementById("form-wetter-abruf")
    .addEventListener("submit", (e) => Start.wetterAbrufen(e));

  Start.laden();
});
