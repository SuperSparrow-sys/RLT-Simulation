/* Symbolpalette links: Kartentypen nach Gruppen, per Ziehen auf die Leinwand.

   zeigeFehler() unten ist nicht hier, sondern in editor.js definiert - eine
   ausdrueckliche Abhaengigkeit (siehe Kommentar dort), kein Zufall. Diese
   Datei setzt voraus, dass die Seite, die sie einbindet, editor.js ebenfalls
   einbindet (templates/editor.html tut das; siehe tests/test_pages.py). */

const Palette = {
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
        eintrag.innerHTML =
          `<img src="/static/symbole/${typ.symbol}" alt="">` +
          `<span>${typ.name}</span>`;
        eintrag.addEventListener("dragstart", (e) => {
          e.dataTransfer.setData("text/kartentyp", typ.kennung);
        });
        liste.appendChild(eintrag);
      }
      behaelter.appendChild(liste);
    }
  },
};
