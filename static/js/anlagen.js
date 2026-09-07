/* Der Anlagenkatalog - Suche und Übernahme.

   Die Karten selbst stehen schon im HTML (routes/katalog.py fuellt sie
   serverseitig): Ihr Inhalt steht fest, sobald das Programm laeuft. Dieses
   Skript kommt zu einer Seite hinzu, die auch ohne es vollstaendig ist - es
   blendet aus, was nicht zur Suche passt, und oeffnet den Dialog, mit dem eine
   Vorlage in ein Projekt wandert.

   Eigenstaendiges Modul wie start.js, aus demselben Grund: Diese Seite laedt
   weder Editor noch Panel, und ein stiller Aufruf einer dort nur scheinbar
   vorhandenen Funktion waere ein Fehler, der erst beim Klicken auffiele.
   zeigeFehler(), htmlSicher() und die beiden Dialoge stehen in
   static/js/dialoge.js - sie standen hier und in start.js Wort fuer Wort
   gleich. */

const Katalog = {
  karten: [],
  gruppen: [],

  starte() {
    this.karten = [...document.querySelectorAll(".katalog-karte")];
    this.gruppen = [...document.querySelectorAll(".katalog-gruppe")];

    const feld = document.getElementById("feld-suche");
    feld.addEventListener("input", () => this.filtere());
    this.filtere();

    document.querySelectorAll("[data-uebernehmen]").forEach((knopf) => {
      knopf.addEventListener("click", () =>
        this.uebernehmenDialog(knopf.dataset.uebernehmen, knopf.dataset.name)
      );
    });
  },

  /* Gesucht wird in allem, was auf der Karte steht, samt Auslegung: Wer
     "Verdunstung" oder "Kaltwasser" eingibt, soll die passende Anlage finden,
     ohne zu wissen, wie sie heisst. Der Suchtext steht als data-Attribut an
     der Karte - serverseitig gebaut, damit hier nichts doppelt beschrieben
     wird. */
  filtere() {
    const suche = (document.getElementById("feld-suche").value || "")
      .trim()
      .toLowerCase();

    let sichtbar = 0;
    for (const karte of this.karten) {
      const passt = !suche || (karte.dataset.suchtext || "").includes(suche);
      karte.hidden = !passt;
      if (passt) sichtbar += 1;
    }
    for (const gruppe of this.gruppen) {
      gruppe.hidden = ![...gruppe.querySelectorAll(".katalog-karte")].some(
        (k) => !k.hidden
      );
    }

    document.getElementById("katalog-leer").hidden = sichtbar > 0;
    document.getElementById("katalog-treffer").textContent = suche
      ? `${sichtbar} von ${this.karten.length}`
      : `${this.karten.length} Anlagen`;
  },

  /* Eine Vorlage gehoert in ein Projekt - es gibt keine Anlage ohne eines.
     Gibt es noch keines, wird hier gleich eines angelegt, statt den Anwender
     erst auf die Startseite zu schicken und zurueckkommen zu lassen. */
  async uebernehmenDialog(kennung, name) {
    let projekte = [];
    try {
      projekte = await fetch("/api/projekte").then((a) => a.json());
    } catch (fehler) {
      zeigeFehler("Die Projekte konnten nicht geladen werden.");
      return;
    }
    const eigene = projekte.filter((p) => !p.ist_lehrmaterial);

    const huelle = document.createElement("div");
    huelle.className = "dialog-huelle";
    huelle.innerHTML = `
      <div class="dialog">
        <h2>${htmlSicher(name)} übernehmen</h2>
        <p class="abschnitt-hinweis">
          Die Anlage wird als Kopie in ein Projekt gelegt und lässt sich dort
          frei ändern. Die Vorlage selbst bleibt, wie sie ist.
        </p>
        <label class="panel-zeile">
          <span class="panel-label">Projekt</span>
          <select id="feld-projekt">
            ${eigene
              .map((p) => `<option value="${p.id}">${htmlSicher(p.name)}</option>`)
              .join("")}
            <option value="">– neues Projekt anlegen –</option>
          </select>
        </label>
        <label class="panel-zeile" id="zeile-neues-projekt" ${eigene.length ? "hidden" : ""}>
          <span class="panel-label">Name des Projekts</span>
          <input type="text" id="feld-neues-projekt" value="Neues Projekt">
        </label>
        <label class="panel-zeile">
          <span class="panel-label">Name der Anlage</span>
          <input type="text" id="feld-anlage-name" value="${htmlSicher(name)}">
        </label>
        <div class="dialog-knoepfe">
          <button id="btn-abbrechen">Abbrechen</button>
          <button class="knopf-haupt" id="btn-uebernehmen">Übernehmen</button>
        </div>
      </div>`;
    document.body.appendChild(huelle);

    const auswahl = huelle.querySelector("#feld-projekt");
    if (!eigene.length) auswahl.value = "";
    auswahl.addEventListener("change", () => {
      huelle.querySelector("#zeile-neues-projekt").hidden = auswahl.value !== "";
    });

    huelle.querySelector("#btn-abbrechen").onclick = () => huelle.remove();
    huelle.querySelector("#btn-uebernehmen").onclick = async () => {
      const knopf = huelle.querySelector("#btn-uebernehmen");
      const anlagenName = huelle.querySelector("#feld-anlage-name").value.trim();
      if (!anlagenName) {
        zeigeFehler("Bitte einen Namen für die Anlage eingeben.");
        return;
      }
      knopf.disabled = true;
      try {
        const projektId = await this.projektErmitteln(huelle, auswahl);
        if (projektId == null) return;
        const antwort = await fetch("/api/anlagen/aus_vorlage", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            projekt_id: projektId, vorlage: kennung, name: anlagenName,
          }),
        });
        if (!antwort.ok) {
          zeigeFehler("Die Anlage konnte nicht angelegt werden.");
          return;
        }
        const anlage = await antwort.json();
        window.location.href = `/anlage/${anlage.id}`;
      } finally {
        knopf.disabled = false;
      }
    };
  },

  async projektErmitteln(huelle, auswahl) {
    if (auswahl.value) return Number(auswahl.value);
    const name = (huelle.querySelector("#feld-neues-projekt").value || "").trim();
    if (!name) {
      zeigeFehler("Bitte einen Namen für das Projekt eingeben.");
      return null;
    }
    const antwort = await fetch("/api/projekte", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!antwort.ok) {
      zeigeFehler("Das Projekt konnte nicht angelegt werden.");
      return null;
    }
    return (await antwort.json()).id;
  },
};

document.addEventListener("DOMContentLoaded", () => Katalog.starte());
