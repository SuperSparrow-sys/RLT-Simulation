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

const BADGE_TEXT = {
  fertig: (l) => `Letzter Lauf: ${l.kosten_gesamt.toFixed(2)} EUR`,
  abgebrochen: () => "Letzter Lauf abgebrochen",
  fehler: () => "Letzter Lauf fehlgeschlagen",
};

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
    const titel = document.createElement("h2");
    titel.textContent = projekt.name;
    kopf.appendChild(titel);
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

    return link;
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
        <tr>
          <td>${htmlSicher(w.name)}</td>
          <td>${htmlSicher(w.quelle)}</td>
          <td>${htmlSicher(w.ort)}</td>
          <td>${w.jahr ?? ""}</td>
          <td class="zahl">${w.stunden}</td>
        </tr>`
      )
      .join("");

    const tabelle = document.createElement("table");
    tabelle.className = "bilanz wetter-tabelle";
    tabelle.innerHTML = `
      <thead>
        <tr><th>Name</th><th>Quelle</th><th>Ort</th><th>Jahr</th>
            <th class="zahl">Stunden</th></tr>
      </thead>
      <tbody>${zeilen}</tbody>`;
    bereich.appendChild(tabelle);
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
    knopf.disabled = false;
    knopf.textContent = urspruenglicherText;

    let liste;
    try {
      const listeAntwort = await fetch("/api/wetter");
      if (!listeAntwort.ok) throw new Error("Antwort nicht ok");
      liste = await listeAntwort.json();
    } catch {
      zeigeFehler(
        "Die Datei wurde hochgeladen, die Liste konnte aber nicht aktualisiert werden."
      );
      return;
    }
    this.wetter = liste;
    this.zeichneWetter();
  },
};

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-projekt-anlegen").addEventListener("click", () =>
    Start.projektAnlegenDialog()
  );
  document
    .getElementById("form-wetter-upload")
    .addEventListener("submit", (e) => Start.wetterHochladen(e));
  Start.laden();
});
