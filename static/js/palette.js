/* Symbolpalette links: Kartentypen nach Gruppen, per Ziehen auf die Leinwand. */

const Palette = {
  async laden() {
    const gruppen = await (await fetch("/api/palette")).json();
    const behaelter = document.getElementById("palette");
    behaelter.textContent = "";

    const reihenfolge = [
      "Luftbehandlung", "Verteilung", "Räume", "Regelung",
      "Zeit und Betrieb", "Quellen und Senken", "Verbraucher",
    ];
    const namen = Object.keys(gruppen).sort(
      (a, b) => reihenfolge.indexOf(a) - reihenfolge.indexOf(b)
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
