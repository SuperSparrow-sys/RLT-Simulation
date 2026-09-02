/* Symbolpalette links: Kartentypen nach Gruppen, per Ziehen auf die Leinwand.

   zeigeFehler() unten ist nicht hier, sondern in editor.js definiert - eine
   ausdrueckliche Abhaengigkeit (siehe Kommentar dort), kein Zufall. Diese
   Datei setzt voraus, dass die Seite, die sie einbindet, editor.js ebenfalls
   einbindet (templates/editor.html tut das; siehe tests/test_pages.py). */

const Palette = {
  // Der per Finger "bereite" Kartentyp: {kennung, element} oder null. Siehe
  // armieren()/entwaffnen() weiter unten - das Gegenstueck zum Ziehen mit der
  // Maus (HTML5 Drag&Drop, siehe dragstart weiter unten), das auf einem
  // Touchscreen gar nicht erst ausgeloest wird (siehe Task, Befund 1).
  bereit: null,

  async laden() {
    let antwort;
    try {
      antwort = await fetch("/api/palette");
    } catch {
      zeigeFehler("Palette konnte nicht geladen werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Palette konnte nicht geladen werden.");
      return;
    }
    const gruppen = await antwort.json();
    const behaelter = document.getElementById("palette");
    behaelter.textContent = "";

    const reihenfolge = [
      "Luftbehandlung", "Verteilung", "Räume", "Regelung",
      "Zeit und Betrieb", "Quellen und Senken", "Verbraucher",
    ];
    // Unbekannte Gruppen (kuenftige Kartentypen) sollen ans Ende sortieren,
    // nicht an den Anfang - indexOf() liefert fuer sie -1.
    const rang = (name) => {
      const index = reihenfolge.indexOf(name);
      return index === -1 ? reihenfolge.length : index;
    };
    const namen = Object.keys(gruppen).sort(
      (a, b) => rang(a) - rang(b) || a.localeCompare(b, "de")
    );

    for (const name of namen) {
      const ueberschrift = document.createElement("h2");
      ueberschrift.className = "gruppe";
      ueberschrift.textContent = name;
      behaelter.appendChild(ueberschrift);

      const liste = document.createElement("div");
      liste.className = "gruppe-liste";
      for (const typ of gruppen[name]) {
        const eintrag = document.createElement("div");
        eintrag.className = "palette-eintrag";
        eintrag.draggable = true;
        eintrag.title = typ.name;
        // Per Tastatur erreichbar und bedienbar (siehe Task: Paletteneintraege
        // waren bisher kein tabindex entfernt) - Enter/Leertaste legen die
        // Karte an, siehe perTastaturHinzufuegen() unten. role="button", weil
        // ein <div> ohne das fuer Screenreader sonst kein interaktives
        // Element ist.
        eintrag.tabIndex = 0;
        eintrag.setAttribute("role", "button");
        eintrag.setAttribute("aria-label", `${typ.name} auf die Leinwand legen`);
        eintrag.innerHTML =
          `<img src="/static/symbole/${typ.symbol}" alt="">` +
          `<span>${typ.name}</span>`;
        // Bleibt fuer die Maus unveraendert: dragstart feuert nur bei einem
        // echten Maus-/Stiftzug, ein Touchscreen loest es gar nicht erst aus
        // (siehe Task, Befund 1) - die beiden Wege stoeren sich nicht.
        eintrag.addEventListener("dragstart", (e) => {
          e.dataTransfer.setData("text/kartentyp", typ.kennung);
        });
        eintrag.addEventListener("keydown", (e) => {
          if (e.key !== "Enter" && e.key !== " ") return;
          e.preventDefault();
          this.perTastaturHinzufuegen(typ.kennung);
        });
        // Antippen (nur Finger/Stift, siehe pointerType-Pruefung in
        // armieren() - eine Maus loest hier bewusst nichts aus, sie bleibt
        // bei dragstart oben) "bewaffnet" den Eintrag: der naechste Tipp auf
        // die Leinwand (siehe editor.js, bindeLeinwand()) legt die Karte
        // dort an. Zweiter Weg statt Ziehen-mit-dem-Finger (siehe Task,
        // "Der zweite Weg ist auf Beruehrungsgeraeten meist verlaesslicher")
        // - und ganz nebenbei derselbe Ablauf wie fuer die Tastatur, nur mit
        // einer selbst gewaehlten statt der Bildschirmmitte als Zielpunkt.
        eintrag.addEventListener("pointerup", (e) => {
          if (e.pointerType === "mouse") return;
          this.armieren(typ.kennung, eintrag);
        });
        liste.appendChild(eintrag);
      }
      behaelter.appendChild(liste);
    }
  },

  /* Fuegt eine Karte per Tastatur hinzu (Drag&Drop hat kein Tastaturaequivalent
     - siehe Kommentar oben bei tabIndex) in der Mitte des aktuell sichtbaren
     Leinwandausschnitts. Editor ist zu diesem Zeitpunkt sicher definiert -
     derselbe Grund wie bei zeigeFehler() oben: dieser Handler laeuft erst,
     lange nachdem alle Skripte geladen und Editor.laden() gelaufen ist. */
  perTastaturHinzufuegen(kennung) {
    const leinwand = document.getElementById("leinwand");
    const kasten = leinwand.getBoundingClientRect();
    const x = (kasten.width / 2 - Editor.sicht.x) / Editor.sicht.zoom;
    const y = (kasten.height / 2 - Editor.sicht.y) / Editor.sicht.zoom;
    Editor.karteHinzufuegen(kennung, Math.round(x), Math.round(y));
  },

  /* "Bewaffnet" einen Paletteneintrag fuer den naechsten Tipp auf die
     Leinwand (siehe editor.js, bindeLeinwand() - liest Palette.bereit direkt
     am Anfang des pointerdown-Lauschers). Erneutes Antippen desselben
     Eintrags entwaffnet wieder (Umschalten), ein anderer Eintrag ersetzt die
     Bewaffnung. Auf schmalem Hochformat mit Finger (siehe style.css, @media
     (max-width: 900px) and (pointer: coarse)) schliesst das ausserdem die
     Palette gleich mit - sie wuerde sonst die Leinwand genau dort verdecken,
     wo als naechstes angetippt werden soll. */
  armieren(kennung, element) {
    if (this.bereit && this.bereit.element === element) {
      this.entwaffnen();
      return;
    }
    if (this.bereit) this.bereit.element.classList.remove("palette-eintrag-bereit");
    this.bereit = { kennung, element };
    element.classList.add("palette-eintrag-bereit");
    // Kein "if (window.Editor)"-Wachposten: ein mit const/let erklaerter
    // Bezeichner haengt NICHT als Eigenschaft an window (anders als var oder
    // eine Funktionsdeklaration) - window.Editor waere hier immer
    // undefined, obwohl der blanke Name Editor laengst existiert. Genau wie
    // perTastaturHinzufuegen() oben verlaesst sich das hier auf die
    // Skriptreihenfolge in templates/editor.html: editor.js ist zu diesem
    // Zeitpunkt (ein Ereignis-Handler, ausgeloest lange nach dem Laden aller
    // Skripte) sicher ausgewertet.
    Editor.seitenbereichSchliessen("palette");
  },

  entwaffnen() {
    if (!this.bereit) return;
    this.bereit.element.classList.remove("palette-eintrag-bereit");
    this.bereit = null;
  },
};

// Escape bricht eine bewaffnete Palettenauswahl ab - dieselbe Abkuerzung wie
// bei Pfeile.ziehenStarten() (siehe pfeile.js).
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") Palette.entwaffnen();
});
