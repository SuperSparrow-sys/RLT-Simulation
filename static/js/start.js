/* Startseite: Projekte mit ihren Anlagen und der Dialog "Anlage anlegen".

   Die Listen selbst stehen fertig in der Seite (templates/index.html, gefuellt
   in routes/pages.py) - dieses Modul verdrahtet nur die Knoepfe daran, zeigt
   den Einstiegskasten beim allerersten Besuch und verfolgt einen gerade
   laufenden Rechenlauf.

   Der Wetterteil ist mit dem Umbau der Oberflaeche nach static/js/wetter.js
   gewandert: Er gehoert zur Wetterseite, und diese Seite brauchte von den 44 kB
   des frueheren gemeinsamen Moduls kaum die Haelfte. zeigeFehler(),
   htmlSicher() und die beiden Dialoge stehen in static/js/dialoge.js.

   Eigenstaendiges Modul statt Mitbenutzung von editor.js/simulation.js: diese
   Seite laedt weder Editor noch Panel noch Pfeile, und ein stiller Aufruf
   einer dort nur scheinbar vorhandenen Funktion waere ein Fehler, der erst
   beim Klicken auffiele. */

/* Der Haken der erledigten Einstiegsschritte. Als eigenes SVG statt als
   Schriftzeichen - dieselbe Regel wie in templates/bedienzeichen/. Ueber
   createElementNS gebaut, weil ein spaeteres textContent am selben Element
   ein eingehaengtes SVG stillschweigend mitloeschen wuerde. */
const NS_SVG = "http://www.w3.org/2000/svg";
function hakenSymbol() {
  const svg = document.createElementNS(NS_SVG, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.classList.add("einstieg-haken");
  const pfad = document.createElementNS(NS_SVG, "path");
  pfad.setAttribute("d", "M3 8.5 6.5 12 13 4.5");
  svg.appendChild(pfad);
  return svg;
}

const Start = {
  // Die Anlagenvorlagen fuer den Dialog "Anlage anlegen" - das Einzige, was
  // diese Seite noch nachlaedt.
  vorlagen: {},

  /* Projekte, Anlagen und Wetterdatensaetze stehen schon im HTML
     (routes/pages.py) - geholt wird nur noch, was auf keiner Seite steht: die
     Vorlagenliste fuer den Dialog "Anlage anlegen". Sie wird erst beim Oeffnen
     des Dialogs gebraucht, deshalb darf sie ruhig nachtroepfeln. */
  async laden() {
    let antwort;
    try {
      antwort = await fetch("/api/vorlagen");
    } catch {
      zeigeFehler("Die Anlagenvorlagen konnten nicht geladen werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Die Anlagenvorlagen konnten nicht geladen werden.");
      return;
    }
    this.vorlagen = await antwort.json();
  },

  /* Die Projektliste steht schon im HTML (routes/pages.py, _projektliste) -
     dieses Skript baut sie nicht mehr, es haengt nur seine Handlungen an die
     fertigen Elemente. Vorher baute es sie im Browser und fragte dafuer den
     Status JEDER Anlage einzeln nach: bei zehn Anlagen elf Anfragen fuer eine
     Liste, die in einer Abfrage steht - und bis sie durch waren, zeigte die
     Seite eine leere Flaeche.

     Nach einer Aenderung wird die Seite neu geladen, statt die Liste im
     Browser nachzuziehen. Das ist EINE Anfrage und kann nicht von dem
     abweichen, was der Server ohnehin liefert; zwei Wege zu derselben
     Darstellung waeren zwei Wege, die auseinanderlaufen. */
  bindeProjekte() {
    const bei = (auswahl, was) => {
      document.querySelectorAll(auswahl).forEach((element) => {
        element.addEventListener("click", (e) => {
          e.preventDefault();
          was(element);
        });
      });
    };

    bei("[data-projekt-umbenennen]", (el) =>
      this.projektUmbenennenDialog({
        id: Number(el.dataset.projektUmbenennen),
        name: el.closest(".projekt-block").dataset.name,
      })
    );
    bei("[data-projekt-loeschen]", (el) => {
      const block = el.closest(".projekt-block");
      this.projektLoeschenDialog({
        id: Number(el.dataset.projektLoeschen),
        name: block.dataset.name,
        anlagen: block.querySelectorAll(".anlage-zeile").length,
      });
    });
    bei("[data-anlage-umbenennen]", (el) =>
      this.anlageUmbenennenDialog({
        id: Number(el.dataset.anlageUmbenennen), name: el.dataset.name,
      })
    );
    bei("[data-anlage-loeschen]", (el) =>
      this.anlageLoeschenDialog({
        id: Number(el.dataset.anlageLoeschen), name: el.dataset.name,
      })
    );
    bei("[data-anlage-anlegen]", (el) => {
      const block = el.closest(".projekt-block");
      this.anlageAnlegenDialog({
        id: Number(el.dataset.anlageAnlegen), name: block.dataset.name,
      });
    });
    const erstes = document.getElementById("btn-erstes-projekt");
    if (erstes) erstes.addEventListener("click", () => this.projektAnlegenDialog());
  },

  /* Ein Lauf, der GERADE rechnet, ist das Einzige an der Liste, was sich
     ohne Zutun aendert - dafuer fragt die Seite weiter nach, aber nur fuer
     die Anlagen, deren Etikett "Laeuft" sagt. Der Fortschritt landet neben
     dem Etikett, in derselben Spalte wie sonst Kosten und Warnungen. */
  async laufendeVerfolgen() {
    const laufende = [...document.querySelectorAll(".anlage-zeile .etikett-laeuft")];
    if (!laufende.length) return;
    for (const etikett of laufende) {
      const zeile = etikett.closest("[data-anlage]");
      try {
        const antwort = await fetch(`/api/anlagen/${zeile.dataset.anlage}/laufende_simulation`);
        if (!antwort.ok) continue;
        const fortschritt = await antwort.json();
        if (fortschritt && fortschritt.gesamt) {
          zeile.querySelector(".anlage-zeile-angaben").textContent =
            `${fortschritt.fertig || 0} von ${fortschritt.gesamt} Stunden`;
        }
      } catch {
        // Der Fortschritt ist eine Zugabe zum blossen "Laeuft" - bleibt er
        // aus, steht dort weiterhin nur das Etikett.
      }
    }
    window.setTimeout(() => this.laufendeVerfolgen(), 3000);
  },

  // Beispielanlagen aus /bausteine landen serverseitig in einem eigenen,
  // technisch normalen Projekt (core.lehrinhalte.beispielanlagen:
  // NAME_PROJEKT "Bausteine"), core.anlagen.projekte() markiert es ueber
  // "ist_lehrmaterial". Getrennt von eigenenProjekte() gehalten, damit
  // weder der Einstiegskasten noch "Noch kein Projekt vorhanden" dieses
  // automatisch entstandene Projekt faelschlich als eigene Arbeit zaehlen.
  /* Wieviele eigene Projekte es gibt, steht auf der Seite - sie ist
     serverseitig gefuellt (routes/pages.py). Der Einstiegskasten fragt
     danach; er soll nur beim allerersten Besuch erscheinen. */
  eigeneProjekte() {
    return [...document.querySelectorAll("#start-projekte .projekt-block")];
  },



  // -- Einstieg -------------------------------------------------------------

  // Nur beim allerersten Besuch (noch kein Projekt): sobald ein Projekt
  // existiert, beantworten die Projekt-/Anlagenkarten selbst schon "was ist
  // der naechste Schritt" - ein dauerhafter Kasten waere dann nur noch
  // Wiederholung. Die drei Schritte stehen in der Reihenfolge, die
  // tatsaechlich zum ersten Ergebnis fuehrt (Wetter vor Anlage vor Rechnen) -
  // unabhaengig von der Reihenfolge der Abschnitte darunter, die stattdessen
  // nach Bedeutung sortiert sind: Projekte (der Zweck) vor Wetterdaten (eine
  // Voraussetzung, siehe static/css/start.css).
  zeichneEinstieg() {
    const bereich = document.getElementById("start-einstieg");
    if (!bereich) return;
    bereich.textContent = "";
    if (this.eigeneProjekte().length) return;

    const hatWetter = this.wetterAnzahl() > 0;

    const kasten = document.createElement("div");
    kasten.className = "start-einstieg";
    const titel = document.createElement("h2");
    titel.className = "start-einstieg-titel";
    titel.textContent = "Erster Einstieg";
    const hinweis = document.createElement("p");
    hinweis.className = "start-einstieg-hinweis";
    hinweis.textContent =
      "Eine Lüftungsanlage wird aus Karten zusammengesteckt und mit einem " +
      "Wetterjahr durchgerechnet. Drei Schritte führen zum ersten Ergebnis:";
    kasten.append(titel, hinweis);

    const schritte = document.createElement("div");
    schritte.className = "einstieg-schritte";
    schritte.append(
      this._einstiegSchrittElement(
        1, "Wetterdaten holen", hatWetter,
        hatWetter
          ? "Mindestens ein Datensatz ist vorhanden."
          : "Ort wählen, Jahr(e) ankreuzen – meist in unter einer Sekunde fertig.",
        hatWetter ? null : { text: "Zu den Wetterdaten",
                             ziel: () => { window.location.href = "/wetter"; } }
      ),
      this._einstiegSchrittElement(
        2, "Anlage aussuchen", false,
        "Zwölf fertig verdrahtete Anlagen stehen bereit – Büro, Schwimmhalle, " +
        "Rechenzentrum und weitere, jede mit vorgerechneter Auslegung. Oder " +
        "leer anfangen.",
        { text: "Zu den Anlagen", ziel: () => { window.location.href = "/anlagen"; } }
      ),
      this._einstiegSchrittElement(
        3, "Rechnen lassen", false,
        "Im Editor der Anlage über „Simulation“ einen Jahreslauf starten.",
        null
      ),
    );
    kasten.appendChild(schritte);
    bereich.appendChild(kasten);
  },

  _einstiegSchrittElement(nummer, titelText, erledigt, hinweisText, aktion) {
    const schritt = document.createElement("div");
    schritt.className = "einstieg-schritt" + (erledigt ? " einstieg-schritt-erledigt" : "");
    const nr = document.createElement("div");
    nr.className = "einstieg-nummer";
    // Ein Haken ist ein Zeichen fuer eine Sache, kein Text - deshalb ein SVG
    // und kein Schriftzeichen (siehe templates/bedienzeichen/, dieselbe Regel
    // gilt fuer die Kopfleiste des Editors). Als Schriftzeichen haenge es an
    // der Schriftart des Geraets und laesst sich in Strichstaerke und Groesse
    // nicht auf die uebrigen Zeichen abstimmen.
    if (erledigt) {
      nr.appendChild(hakenSymbol());
      nr.setAttribute("aria-label", "erledigt");
    } else {
      nr.textContent = String(nummer);
    }
    const text = document.createElement("div");
    text.className = "einstieg-text";
    // <h3>, nicht <h2>: Die Schritte stehen unter der Ueberschrift des
    // Kastens (start-einstieg-titel, <h2>), die wiederum unter der <h1> der
    // Seite steht - eine Vorlesehilfe liest die Gliederung so richtig.
    const h3 = document.createElement("h3");
    h3.textContent = titelText;
    const p = document.createElement("p");
    p.textContent = hinweisText;
    text.append(h3, p);
    if (aktion) {
      const knopf = document.createElement("button");
      knopf.type = "button";
      knopf.className = "knopf-sekundaer";
      knopf.textContent = aktion.text;
      knopf.addEventListener("click", aktion.ziel);
      text.appendChild(knopf);
    }
    schritt.append(nr, text);
    return schritt;
  },

  /* Wieviele Wetterdatensaetze es gibt, steht serverseitig am
     Einstiegskasten (routes/pages.py: index() -> wetter_anzahl). Er fragt
     danach, um seinen ersten Schritt abzuhaken - und ist der Einzige auf
     dieser Seite, der es noch wissen muss. */
  wetterAnzahl() {
    const kasten = document.getElementById("start-einstieg");
    return kasten ? Number(kasten.dataset.wetterAnzahl || 0) : 0;
  },

  // -- Projekte und Anlagen ------------------------------------------------

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
    window.location.reload();
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
    window.location.reload();
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
    window.location.reload();
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
    window.location.reload();
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
      window.location.reload();
    };
  },

  anlageAnlegenDialog(projekt) {
    /* Name zuerst, Beschreibung darunter: Vorher stand hier ausschliesslich
       der lange Beschreibungstext, und zwoelf davon untereinander waren nicht
       zu ueberblicken - man las zwoelf Absaetze, um "Schwimmhalle" zu finden.
       Wer mehr wissen will, findet die vollstaendige Auslegung im
       Anlagenkatalog; dorthin fuehrt der Verweis unter der Liste. */
    const vorlagenHtml = Object.entries(this.vorlagen)
      .map(
        ([kennung, vorlage]) => `
        <label class="vorlage-wahl">
          <input type="radio" name="vorlage" value="${htmlSicher(kennung)}">
          <span class="vorlage-wahl-text">
            <span class="vorlage-wahl-name">${htmlSicher(vorlage.name)}</span>
            <span class="vorlage-wahl-hinweis">${htmlSicher(vorlage.beschreibung)}</span>
          </span>
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
          <p class="vorlage-wahl-weg">
            Alle Anlagen mit ihrer vorgerechneten Auslegung:
            <a href="/anlagen">zum Anlagenkatalog</a>
          </p>
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
};

window.addEventListener("DOMContentLoaded", () => {
  const anlegen = document.getElementById("btn-projekt-anlegen");
  if (anlegen) anlegen.addEventListener("click", () => Start.projektAnlegenDialog());

  // Die Projektliste steht schon da - sie wird nur verdrahtet.
  Start.bindeProjekte();
  Start.zeichneEinstieg();
  Start.laufendeVerfolgen();
  Start.laden();
});
