/* Leinwand: Karten zeichnen, verschieben, auswaehlen. */

const NS = "http://www.w3.org/2000/svg";

/* Pfeile (Task 22) und Panel (Task 23) sind noch nicht angelegt; ohne diesen
   Schutz wuerde jeder Aufruf mit einem ReferenceError abbrechen und die
   Funktion, in der er steht, vorzeitig verlassen - auch dann, wenn danach
   noch wichtiger Code folgt (etwa das Registrieren der Zieh-Listener). Die
   spaeteren Tasks entfernen die jeweilige Abfrage wieder, sobald ihr Modul
   existiert. */
function pfeileZeichnen(anlage) {
  if (typeof Pfeile !== "undefined") Pfeile.zeichneAlle(anlage);
}
function pfeileBinden(editor) {
  if (typeof Pfeile !== "undefined") Pfeile.binde(editor);
}
function panelZeigen(karte) {
  if (typeof Panel !== "undefined") Panel.zeige(karte);
}
function panelLeeren() {
  if (typeof Panel !== "undefined") Panel.leeren();
}

/* Modester, einheitlicher Umgang mit fehlgeschlagenen Anfragen: kurze
   deutsche Meldung fuer die Anwenderin statt eines stillen Fehlschlags oder
   einer Konsolenmeldung, die niemand sieht. Kein eigenes
   Benachrichtigungssystem - nur eine einzelne, wiederverwendete Leiste. */
function zeigeFehler(nachricht) {
  const leiste = document.getElementById("fehlermeldung");
  if (!leiste) return;
  leiste.textContent = nachricht;
  leiste.hidden = false;
  window.clearTimeout(zeigeFehler.timer);
  zeigeFehler.timer = window.setTimeout(() => { leiste.hidden = true; }, 5000);
}

const Editor = {
  anlage: null,
  auswahl: null,
  sicht: { x: 0, y: 0, zoom: 1 },

  async laden(anlageId) {
    let antwort;
    try {
      antwort = await fetch(`/api/anlagen/${anlageId}`);
    } catch {
      zeigeFehler("Anlage konnte nicht geladen werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Anlage konnte nicht geladen werden.");
      return;
    }
    this.anlage = await antwort.json();
    document.getElementById("anlagenname").textContent = this.anlage.name;
    this.zeichne();
  },

  karteNach(id) {
    return this.anlage.karten.find((k) => k.id === id);
  },

  zeichne() {
    const ebene = document.getElementById("karten");
    ebene.textContent = "";
    for (const karte of this.anlage.karten) {
      ebene.appendChild(this.zeichneKarte(karte));
    }
    pfeileZeichnen(this.anlage);
    this.aktualisiereSicht();
  },

  zeichneKarte(karte) {
    const gruppe = document.createElementNS(NS, "g");
    gruppe.setAttribute("class", "karte");
    gruppe.setAttribute("data-id", karte.id);
    gruppe.setAttribute("transform", `translate(${karte.pos_x} ${karte.pos_y})`);
    if (this.auswahl === karte.id) gruppe.classList.add("gewaehlt");

    const rahmen = document.createElementNS(NS, "rect");
    rahmen.setAttribute("class", "karte-rahmen");
    rahmen.setAttribute("width", 150);
    rahmen.setAttribute("height", 96);
    rahmen.setAttribute("rx", 8);
    gruppe.appendChild(rahmen);

    const bild = document.createElementNS(NS, "image");
    bild.setAttribute("href", `/static/symbole/${karte.symbol}`);
    bild.setAttribute("x", 10);
    bild.setAttribute("y", 10);
    bild.setAttribute("width", 32);
    bild.setAttribute("height", 32);
    gruppe.appendChild(bild);

    const beschriftung = document.createElementNS(NS, "text");
    beschriftung.setAttribute("class", "karte-name");
    beschriftung.setAttribute("x", 50);
    beschriftung.setAttribute("y", 30);
    beschriftung.textContent = karte.name;
    gruppe.appendChild(beschriftung);

    const werte = document.createElementNS(NS, "text");
    werte.setAttribute("class", "karte-werte");
    werte.setAttribute("x", 10);
    werte.setAttribute("y", 66);
    werte.setAttribute("data-werte", karte.id);
    gruppe.appendChild(werte);

    for (const port of karte.ports) {
      gruppe.appendChild(this.zeichnePort(karte, port));
    }

    gruppe.addEventListener("pointerdown", (e) => this.karteGreifen(e, karte));
    return gruppe;
  },

  portPosition(karte, port) {
    const gleiche = karte.ports.filter(
      (p) => p.richtung === port.richtung && p.art === port.art
    );
    const index = gleiche.indexOf(port);
    const abstand = 96 / (gleiche.length + 1);
    const y = abstand * (index + 1);
    const x = port.richtung === "ein" ? 0 : 150;
    return { x, y };
  },

  zeichnePort(karte, port) {
    const { x, y } = this.portPosition(karte, port);
    const punkt = document.createElementNS(NS, "circle");
    punkt.setAttribute("class", `port port-${port.art}`);
    punkt.setAttribute("cx", x);
    punkt.setAttribute("cy", y);
    punkt.setAttribute("r", 4);
    punkt.setAttribute("data-port", port.id);
    const titel = document.createElementNS(NS, "title");
    titel.textContent = `${port.schluessel} (${port.rolle})`;
    punkt.appendChild(titel);
    return punkt;
  },

  /* Von karteGreifen() und der Leinwand selbst gebraucht, deshalb hier
     einmal benannt statt an beiden Stellen wiederholt. */
  entferneAuswahlKlasse() {
    document.querySelectorAll(".karte.gewaehlt").forEach((g) =>
      g.classList.remove("gewaehlt")
    );
  },

  karteGreifen(ereignis, karte) {
    if (ereignis.button !== 0) return;
    ereignis.stopPropagation();
    this.auswahl = karte.id;
    panelZeigen(karte);

    const start = { x: ereignis.clientX, y: ereignis.clientY };
    const anfang = { x: karte.pos_x, y: karte.pos_y };
    const gruppe = ereignis.currentTarget;
    this.entferneAuswahlKlasse();
    gruppe.classList.add("gewaehlt");

    const bewegen = (e) => {
      karte.pos_x = anfang.x + (e.clientX - start.x) / this.sicht.zoom;
      karte.pos_y = anfang.y + (e.clientY - start.y) / this.sicht.zoom;
      gruppe.setAttribute("transform", `translate(${karte.pos_x} ${karte.pos_y})`);
      pfeileZeichnen(this.anlage);
    };
    const loslassen = async () => {
      window.removeEventListener("pointermove", bewegen);
      window.removeEventListener("pointerup", loslassen);
      let antwort;
      try {
        antwort = await fetch(`/api/karten/${karte.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pos_x: karte.pos_x, pos_y: karte.pos_y }),
        });
      } catch {
        zeigeFehler("Position konnte nicht gespeichert werden.");
        return;
      }
      if (!antwort.ok) zeigeFehler("Position konnte nicht gespeichert werden.");
    };
    window.addEventListener("pointermove", bewegen);
    window.addEventListener("pointerup", loslassen);
  },

  async karteHinzufuegen(typ, x, y) {
    let antwort;
    try {
      antwort = await fetch("/api/karten", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ anlage_id: this.anlage.id, typ, pos_x: x, pos_y: y }),
      });
    } catch {
      zeigeFehler("Karte konnte nicht angelegt werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Karte konnte nicht angelegt werden.");
      return;
    }
    const karte = await antwort.json();
    this.anlage.karten.push(karte);
    this.zeichne();
  },

  aktualisiereSicht() {
    document
      .getElementById("welt")
      .setAttribute(
        "transform",
        `translate(${this.sicht.x} ${this.sicht.y}) scale(${this.sicht.zoom})`
      );
  },

  bindeLeinwand() {
    const leinwand = document.getElementById("leinwand");

    leinwand.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".karte")) return;
      this.auswahl = null;
      panelLeeren();
      this.entferneAuswahlKlasse();
      const start = { x: e.clientX, y: e.clientY };
      const anfang = { ...this.sicht };
      const bewegen = (m) => {
        this.sicht.x = anfang.x + (m.clientX - start.x);
        this.sicht.y = anfang.y + (m.clientY - start.y);
        this.aktualisiereSicht();
      };
      const loslassen = () => {
        window.removeEventListener("pointermove", bewegen);
        window.removeEventListener("pointerup", loslassen);
      };
      window.addEventListener("pointermove", bewegen);
      window.addEventListener("pointerup", loslassen);
    });

    leinwand.addEventListener("wheel", (e) => {
      e.preventDefault();
      const faktor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
      this.sicht.zoom = Math.min(3, Math.max(0.2, this.sicht.zoom * faktor));
      this.aktualisiereSicht();
    }, { passive: false });

    leinwand.addEventListener("dragover", (e) => e.preventDefault());
    leinwand.addEventListener("drop", (e) => {
      e.preventDefault();
      const typ = e.dataTransfer.getData("text/kartentyp");
      if (!typ) return;
      const kasten = leinwand.getBoundingClientRect();
      const x = (e.clientX - kasten.left - this.sicht.x) / this.sicht.zoom;
      const y = (e.clientY - kasten.top - this.sicht.y) / this.sicht.zoom;
      this.karteHinzufuegen(typ, Math.round(x), Math.round(y));
    });

    window.addEventListener("keydown", async (e) => {
      if (e.key !== "Delete" || this.auswahl === null) return;
      let antwort;
      try {
        antwort = await fetch(`/api/karten/${this.auswahl}`, { method: "DELETE" });
      } catch {
        zeigeFehler("Karte konnte nicht geloescht werden.");
        return;
      }
      if (!antwort.ok) {
        zeigeFehler("Karte konnte nicht geloescht werden.");
        return;
      }
      this.auswahl = null;
      await this.laden(this.anlage.id);
    });
  },
};

window.addEventListener("DOMContentLoaded", async () => {
  Editor.bindeLeinwand();
  await Palette.laden();
  await Editor.laden(window.ANLAGE_ID);
  pfeileBinden(Editor);
});
