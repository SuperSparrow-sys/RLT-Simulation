/* Leinwand: Karten zeichnen, verschieben, auswaehlen. */

const NS = "http://www.w3.org/2000/svg";

// Dieselben sieben Palettengruppen wie palette.js (siehe dortige
// "reihenfolge") - hier auf einen kurzen, css-tauglichen Klassennamen
// abgebildet, damit jede Karte erkennbar traegt, zu welcher Gruppe sie
// gehoert (Farbstreifen UND Textkuerzel, siehe zeichneKarte() - Farbe allein
// waere fuer Anwenderinnen ohne Farbsinn keine verlaessliche Auskunft).
const GRUPPEN_KLASSE = {
  "Luftbehandlung": "luftbehandlung",
  "Verteilung": "verteilung",
  "Räume": "raeume",
  "Regelung": "regelung",
  "Zeit und Betrieb": "zeit",
  "Quellen und Senken": "quellen",
  "Verbraucher": "verbraucher",
};

// Textmasse fuer den Zeilenumbruch der Kartennamen: ein einzelner,
// wiederverwendeter Messkontext statt bei jeder Karte ein neues <canvas> zu
// erzeugen. Canvas statt DOM-Messung (getComputedTextLength), weil die Karte
// zu diesem Zeitpunkt noch gar nicht im DOM haengt - erst nach der Messung
// steht fest, wie hoch ihr <rect> werden muss.
let _messkontext = null;
function textBreite(text, font) {
  if (!_messkontext) _messkontext = document.createElement("canvas").getContext("2d");
  _messkontext.font = font;
  return _messkontext.measureText(text).width;
}

// Vollstaendiger Umbruch ohne Abschneiden (siehe Task: "Vollstaendige Namen
// ohne Abschneiden") - so viele Zeilen wie noetig, die Karte waechst mit.
function zeilenUmbrechen(text, maxBreite, font) {
  const woerter = text.split(" ");
  const zeilen = [];
  let aktuell = "";
  for (const wort of woerter) {
    const kandidat = aktuell ? `${aktuell} ${wort}` : wort;
    if (aktuell && textBreite(kandidat, font) > maxBreite) {
      zeilen.push(aktuell);
      aktuell = wort;
    } else {
      aktuell = kandidat;
    }
  }
  if (aktuell) zeilen.push(aktuell);
  return zeilen;
}

function pfeileZeichnen(anlage) {
  Pfeile.zeichneAlle(anlage);
}
function pfeileBinden(editor) {
  Pfeile.binde(editor);
}
function panelZeigen(karte) {
  Panel.zeige(karte);
}
function panelLeeren() {
  Panel.leeren();
}

/* Modester, einheitlicher Umgang mit fehlgeschlagenen Anfragen: kurze
   deutsche Meldung fuer die Anwenderin statt eines stillen Fehlschlags oder
   einer Konsolenmeldung, die niemand sieht. Kein eigenes
   Benachrichtigungssystem - nur eine einzelne, wiederverwendete Leiste.

   Absichtlich hier statt in einer eigenen Datei definiert: als einzige
   Funktion lohnt eine weitere <script>-Datei nicht, und templates/editor.html
   bindet ohnehin nur klassische, nicht-modulare Skripte ein. palette.js,
   pfeile.js, panel.js und simulation.js rufen diese Funktion auf, ohne sie
   selbst zu definieren - eine ausdrueckliche, hier dokumentierte Abhaengigkeit
   von editor.js, nicht die stillschweigende Annahme, dass es schon zufaellig
   irgendwo definiert sein wird. Sie geht gut, weil editor.html editor.js
   tatsaechlich einbindet (siehe tests/test_pages.py) und der Aufruf immer
   erst innerhalb eines async-Callbacks erfolgt, also lange nachdem alle
   Skripte der Seite geladen sind - nie beim Parsen der Datei selbst.
   Verglichen mit start.js: die Startseite laedt keines dieser Skripte und
   definiert sich zeigeFehler() deshalb bewusst selbst statt sich hierauf zu
   verlassen (siehe dortiger Kommentar). Kaeme ein weiteres eigenstaendiges
   Skript hinzu, das zeigeFehler() braucht, gehoert die Funktion in eine
   gemeinsame Datei statt in noch mehr Kopien. */
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
  // Nur beim allerersten Laden automatisch einpassen (siehe laden() und
  // einpassen() weiter unten) - nicht bei jedem erneuten Laden nach einer
  // Aenderung, sonst risse jede Aenderung (Karte loeschen, Pfeil anlegen)
  // den Bildausschnitt der Anwenderin unter ihr weg.
  _nochNichtEingepasst: true,

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
    if (this._nochNichtEingepasst) {
      this._nochNichtEingepasst = false;
      this.einpassen();
    }
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
    // Leere Leinwand: ohne diesen Hinweis sieht eine frisch angelegte Anlage
    // aus wie eine leere Flaeche ohne jeden Hinweis, wie man anfaengt (siehe
    // Task, Befund 6). Er verschwindet, sobald die erste Karte da ist.
    const hinweis = document.getElementById("leinwand-hinweis");
    if (hinweis) hinweis.hidden = this.anlage.karten.length > 0;
  },

  KARTE_BREITE: 190,

  /* Berechnet Breite, Hoehe und alle Textzeilen/-y-Positionen einer Karte,
     bevor sie gezeichnet wird - die Kartenhoehe waechst mit der Anzahl
     Namenszeilen, statt Text unter dem Rand abzuschneiden (siehe Task,
     Befund 3). zeichneKarte() nutzt das Ergebnis zum Zeichnen, pfeile.js
     liest die gespeicherte Breite/Hoehe (karte._breite/_hoehe, siehe
     zeichneKarte()) fuer die Pfeilgeometrie. */
  karteMasseBerechnen(karte) {
    const breite = this.KARTE_BREITE;
    const pad = 10;
    const icon = 20;
    const textX = pad + icon + 8;
    // 14px statt der sonst auf der Seite ueblichen 12px (siehe .karte-name
    // tspan in style.css - beide muessen zusammenbleiben, sonst misst diese
    // Funktion mit einer anderen Schrift, als tatsaechlich gezeichnet wird):
    // Bei 36 Karten passt die Vorlage beim automatischen Einpassen nur mit
    // spuerbarem Herauszoomen ins Bild (siehe Editor.einpassen()) - der
    // Name ist dort das Wichtigste auf der Karte, eine Stufe groesser haelt
    // ihn dabei noch lesbar, ohne die Kartenbreite (und damit die Zoomstufe)
    // zu beruehren, denn nur die Kartenhoehe waechst mit.
    const zeilenHoehe = 17;
    const zeilen = zeilenUmbrechen(karte.name, breite - textX - pad, "500 14px Roboto, Arial, sans-serif");
    const nameHoehe = zeilen.length * zeilenHoehe;
    const kopfHoehe = Math.max(icon, nameHoehe);
    const nameStartY = pad + (kopfHoehe - nameHoehe) / 2 + 11;
    const gruppenY = pad + kopfHoehe + 16;
    const werteY = gruppenY + 17;
    const hoehe = werteY + 11;
    return { breite, hoehe, zeilen, textX, nameStartY, gruppenY, werteY };
  },

  zeichneKarte(karte) {
    const masse = this.karteMasseBerechnen(karte);
    // Fuer pfeile.js (Pfeilgeometrie) und portPosition() weiter unten -
    // siehe Kommentar bei Pfeile.masse() in pfeile.js.
    karte._breite = masse.breite;
    karte._hoehe = masse.hoehe;

    const gruppe = document.createElementNS(NS, "g");
    gruppe.setAttribute("class", "karte");
    gruppe.setAttribute("data-id", karte.id);
    gruppe.setAttribute("data-gruppe", GRUPPEN_KLASSE[karte.gruppe] || "sonstige");
    gruppe.setAttribute("transform", `translate(${karte.pos_x} ${karte.pos_y})`);
    // Tastaturbedienbar: fokussierbar, mit Enter/Leertaste auswaehlbar (siehe
    // karteTaste() unten). Der sichtbare Fokusring kommt aus style.css
    // ([tabindex]:focus-visible), hier nur das Attribut selbst.
    gruppe.setAttribute("tabindex", "0");
    gruppe.setAttribute("role", "button");
    gruppe.setAttribute("aria-label", `${karte.name}, ${karte.gruppe}`);
    if (this.auswahl === karte.id) gruppe.classList.add("gewaehlt");

    const rahmen = document.createElementNS(NS, "rect");
    rahmen.setAttribute("class", "karte-rahmen");
    rahmen.setAttribute("width", masse.breite);
    rahmen.setAttribute("height", masse.hoehe);
    rahmen.setAttribute("rx", 8);
    gruppe.appendChild(rahmen);

    // Gruppenstreifen: Farbe UND (im Panel/Titel) Text - siehe Kommentar bei
    // GRUPPEN_KLASSE oben. Um 7px von oben/unten eingerueckt, damit er nicht
    // ueber die abgerundeten Ecken des Rahmens hinaussteht.
    const streifen = document.createElementNS(NS, "rect");
    streifen.setAttribute("class", "karte-gruppenstreifen");
    streifen.setAttribute("x", 0);
    streifen.setAttribute("y", 7);
    streifen.setAttribute("width", 4);
    streifen.setAttribute("height", Math.max(masse.hoehe - 14, 4));
    streifen.setAttribute("rx", 2);
    gruppe.appendChild(streifen);

    const bild = document.createElementNS(NS, "image");
    bild.setAttribute("href", `/static/symbole/${karte.symbol}`);
    bild.setAttribute("x", 10);
    bild.setAttribute("y", 10);
    bild.setAttribute("width", 20);
    bild.setAttribute("height", 20);
    gruppe.appendChild(bild);

    const beschriftung = document.createElementNS(NS, "text");
    beschriftung.setAttribute("class", "karte-name");
    for (let i = 0; i < masse.zeilen.length; i++) {
      const zeile = document.createElementNS(NS, "tspan");
      zeile.setAttribute("x", masse.textX);
      zeile.setAttribute("y", masse.nameStartY + i * 15);
      zeile.textContent = masse.zeilen[i];
      beschriftung.appendChild(zeile);
    }
    gruppe.appendChild(beschriftung);

    // Gruppenname als Text (nicht nur der Farbstreifen) - siehe Kommentar bei
    // GRUPPEN_KLASSE oben zur Begruendung.
    const gruppentext = document.createElementNS(NS, "text");
    gruppentext.setAttribute("class", "karte-gruppe");
    gruppentext.setAttribute("x", 10);
    gruppentext.setAttribute("y", masse.gruppenY);
    gruppentext.textContent = karte.gruppe;
    gruppe.appendChild(gruppentext);

    const werte = document.createElementNS(NS, "text");
    werte.setAttribute("class", "karte-werte");
    werte.setAttribute("x", 10);
    werte.setAttribute("y", masse.werteY);
    werte.setAttribute("data-werte", karte.id);
    gruppe.appendChild(werte);

    for (const port of karte.ports) {
      gruppe.appendChild(this.zeichnePort(karte, port));
    }
    gruppe.appendChild(this.zeichneVerbindungsgriff(karte, masse));

    gruppe.addEventListener("pointerdown", (e) => this.karteGreifen(e, karte));
    gruppe.addEventListener("keydown", (e) => this.karteTaste(e, karte, gruppe));
    return gruppe;
  },

  /* Der einzige, deutlich sichtbare Anknuepfpunkt am Kartenrand (siehe Task:
     "erscheint an ihrem Rand ein deutlicher Anknuepfpunkt, den man auf die
     Zielkarte zieht"). In der Grundansicht unsichtbar (opacity 0 in
     style.css), erscheint er beim Ueberfahren oder Fokussieren der Karte
     sowie waehrend des Ziehens selbst (.karte.verbindet-von, von
     Pfeile.ziehenStarten() gesetzt) - das ist die Entdeckungsroute fuer das
     Verbinden ohne Vorwissen. Umschalt+Ziehen (siehe pfeile.js binde())
     bleibt als Abkuerzung fuer Geuebte bestehen. */
  zeichneVerbindungsgriff(karte, masse) {
    const griff = document.createElementNS(NS, "g");
    griff.setAttribute("class", "verbindungs-griff");
    griff.setAttribute("transform", `translate(${masse.breite} ${masse.hoehe / 2})`);

    const kreis = document.createElementNS(NS, "circle");
    kreis.setAttribute("class", "verbindungs-griff-kreis");
    kreis.setAttribute("r", 9);
    griff.appendChild(kreis);

    const kreuz = document.createElementNS(NS, "path");
    kreuz.setAttribute("class", "verbindungs-griff-kreuz");
    kreuz.setAttribute("d", "M -4 0 H 4 M 0 -4 V 4");
    griff.appendChild(kreuz);

    const titel = document.createElementNS(NS, "title");
    titel.textContent = "Ziehen, um diese Karte mit einer anderen zu verbinden";
    griff.appendChild(titel);

    griff.addEventListener("pointerdown", (e) => {
      // Nicht auch noch karteGreifen() ausloesen (Verschieben/Auswaehlen) -
      // dieser Pointerdown gehoert allein dem Verbinden.
      e.stopPropagation();
      Pfeile.ziehenStarten(karte, e);
    });
    return griff;
  },

  portPosition(karte, port) {
    const gleiche = karte.ports.filter(
      (p) => p.richtung === port.richtung && p.art === port.art
    );
    const index = gleiche.indexOf(port);
    const hoehe = karte._hoehe || 96;
    const abstand = hoehe / (gleiche.length + 1);
    const y = abstand * (index + 1);
    const x = port.richtung === "ein" ? 0 : (karte._breite || this.KARTE_BREITE);
    return { x, y };
  },

  /* Luft, Signal und Energie muessen sich auch ohne Farbsinn unterscheiden
     lassen (siehe Task) - deshalb nicht nur eine andere Farbe je Art, sondern
     eine andere Form: Kreis fuer Luft, Quadrat fuer Signal, Dreieck (Spitze
     in Fliessrichtung) fuer die vier Energierollen aus Pfeile.ENERGIEROLLEN
     (dieselbe Liste wie fuer die Pfeilfarbe in pfeile.js). */
  portKategorie(port) {
    if (port.art === "luft") return "luft";
    return Pfeile.ENERGIEROLLEN.includes(port.rolle) ? "energie" : "signal";
  },

  zeichnePort(karte, port) {
    const { x, y } = this.portPosition(karte, port);
    const kategorie = this.portKategorie(port);
    let form;
    if (kategorie === "luft") {
      form = document.createElementNS(NS, "circle");
      form.setAttribute("cx", x);
      form.setAttribute("cy", y);
      form.setAttribute("r", 5);
    } else if (kategorie === "energie") {
      const r = 5.5;
      const spitzeX = port.richtung === "ein" ? x - r : x + r;
      const basisX = port.richtung === "ein" ? x + r : x - r;
      form = document.createElementNS(NS, "polygon");
      form.setAttribute("points", `${spitzeX},${y} ${basisX},${y - r} ${basisX},${y + r}`);
    } else {
      form = document.createElementNS(NS, "rect");
      const seite = 8;
      form.setAttribute("x", x - seite / 2);
      form.setAttribute("y", y - seite / 2);
      form.setAttribute("width", seite);
      form.setAttribute("height", seite);
    }
    form.setAttribute("class", `port port-${kategorie}`);
    form.setAttribute("data-port", port.id);
    const titel = document.createElementNS(NS, "title");
    titel.textContent = `${port.schluessel} (${port.rolle})`;
    form.appendChild(titel);
    return form;
  },

  /* Von karteGreifen() und der Leinwand selbst gebraucht, deshalb hier
     einmal benannt statt an beiden Stellen wiederholt. */
  entferneAuswahlKlasse() {
    document.querySelectorAll(".karte.gewaehlt").forEach((g) =>
      g.classList.remove("gewaehlt")
    );
  },

  /* Waehlt eine Karte aus (Panel + .gewaehlt-Klasse), ohne sie zu verschieben
     - der gemeinsame Kern von karteGreifen() (Maus) und karteTaste()
     (Tastatur). */
  karteAuswaehlen(karte, gruppe) {
    this.auswahl = karte.id;
    panelZeigen(karte);
    this.entferneAuswahlKlasse();
    gruppe.classList.add("gewaehlt");
  },

  /* Tastaturbedienung einer Karte (siehe Task: Karten muessen "fokussierbar
     und mit der Tastatur bedienbar" sein). Verschieben bleibt der Maus
     vorbehalten - eine Karte per Tastatur zu verbinden oder zu verschieben
     ist ein groesseres, eigenes Vorhaben und nicht Teil dieses Auftrags. */
  karteTaste(ereignis, karte, gruppe) {
    if (ereignis.key !== "Enter" && ereignis.key !== " ") return;
    ereignis.preventDefault();
    this.karteAuswaehlen(karte, gruppe);
  },

  karteGreifen(ereignis, karte) {
    if (ereignis.button !== 0) return;
    // Umschalt+Klick auf einer Karte ist Pfeile.ziehenStarten() vorbehalten
    // (siehe pfeile.js) - ohne diese Abfrage wuerde stopPropagation() weiter
    // unten den Klick abfangen, bevor er die Leinwand erreicht.
    if (ereignis.shiftKey) return;
    ereignis.stopPropagation();
    const gruppe = ereignis.currentTarget;
    this.karteAuswaehlen(karte, gruppe);

    const start = { x: ereignis.clientX, y: ereignis.clientY };
    const anfang = { x: karte.pos_x, y: karte.pos_y };

    const bewegen = (e) => {
      karte.pos_x = anfang.x + (e.clientX - start.x) / this.sicht.zoom;
      karte.pos_y = anfang.y + (e.clientY - start.y) / this.sicht.zoom;
      gruppe.setAttribute("transform", `translate(${karte.pos_x} ${karte.pos_y})`);
      pfeileZeichnen(this.anlage);
    };
    const zuruecksetzen = () => {
      karte.pos_x = anfang.x;
      karte.pos_y = anfang.y;
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
        zuruecksetzen();
        return;
      }
      if (!antwort.ok) {
        zeigeFehler("Position konnte nicht gespeichert werden.");
        zuruecksetzen();
      }
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
    this.aktualisiereMinikarte();
  },

  /* Berechnet die Weltkoordinaten-Huelle aller Karten (kleinstes Rechteck,
     das sie alle einschliesst). Von einpassen() und aktualisiereMinikarte()
     gebraucht, deshalb hier einmal benannt statt an beiden Stellen
     wiederholt. Liefert null, wenn es keine Karten gibt. */
  kartenHuelle() {
    if (!this.anlage || this.anlage.karten.length === 0) return null;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const karte of this.anlage.karten) {
      const b = karte._breite || this.KARTE_BREITE;
      const h = karte._hoehe || 96;
      minX = Math.min(minX, karte.pos_x);
      minY = Math.min(minY, karte.pos_y);
      maxX = Math.max(maxX, karte.pos_x + b);
      maxY = Math.max(maxY, karte.pos_y + h);
    }
    return { minX, minY, maxX, maxY };
  },

  /* Passt Zoomstufe und Bildausschnitt so an, dass alle Karten sichtbar sind
     - siehe Task: "Beim Öffnen wird die ganze Anlage eingepasst [...] und
     über einen Knopf jederzeit wieder herstellbar." Ohne das lief eine
     grosse Vorlage bei 36 Karten weit rechts aus dem Bild, ohne jeden
     Hinweis darauf, dass da noch mehr ist. */
  einpassen() {
    const huelle = this.kartenHuelle();
    const leinwand = document.getElementById("leinwand");
    const kasten = leinwand.getBoundingClientRect();
    if (!huelle || kasten.width === 0 || kasten.height === 0) {
      this.sicht = { x: 0, y: 0, zoom: 1 };
      this.aktualisiereSicht();
      return;
    }
    const POLSTER = 70;
    const inhaltBreite = huelle.maxX - huelle.minX + POLSTER * 2;
    const inhaltHoehe = huelle.maxY - huelle.minY + POLSTER * 2;
    // Nicht ueber 1 hinaus vergroessern - bei wenigen Karten soll "Einpassen"
    // sie in Originalgroesse zentrieren, nicht auf Plakatgroesse aufblasen.
    const zoom = Math.min(kasten.width / inhaltBreite, kasten.height / inhaltHoehe, 1);
    this.sicht.zoom = zoom;
    const mitteX = (huelle.minX + huelle.maxX) / 2;
    const mitteY = (huelle.minY + huelle.maxY) / 2;
    this.sicht.x = kasten.width / 2 - mitteX * zoom;
    this.sicht.y = kasten.height / 2 - mitteY * zoom;
    this.aktualisiereSicht();
  },

  /* Zurueckhaltender Positionsanzeiger (siehe Task: "es muss sichtbar
     bleiben, wo man sich befindet, sobald man hineinzoomt oder
     verschiebt"). Eine kleine Karte unten rechts, NUR sichtbar, wenn
     tatsaechlich etwas ausserhalb des aktuellen Bildausschnitts liegt -
     direkt nach dem Einpassen (per Knopf oder beim ersten Laden) ist sie
     also weg, weil dann ohnehin alles zu sehen ist. Zeigt jede Karte als
     kleines Rechteck plus ein Rahmen fuer den aktuell sichtbaren
     Weltausschnitt. */
  aktualisiereMinikarte() {
    const huelle2 = document.getElementById("minikarte-huelle");
    const svg = document.getElementById("minikarte");
    if (!huelle2 || !svg) return;
    const huelle = this.kartenHuelle();
    const leinwand = document.getElementById("leinwand");
    const kasten = leinwand.getBoundingClientRect();
    if (!huelle || kasten.width === 0) {
      huelle2.hidden = true;
      return;
    }

    const sichtX0 = -this.sicht.x / this.sicht.zoom;
    const sichtY0 = -this.sicht.y / this.sicht.zoom;
    const sichtX1 = sichtX0 + kasten.width / this.sicht.zoom;
    const sichtY1 = sichtY0 + kasten.height / this.sicht.zoom;
    const komplettSichtbar =
      sichtX0 <= huelle.minX && sichtY0 <= huelle.minY &&
      sichtX1 >= huelle.maxX && sichtY1 >= huelle.maxY;
    huelle2.hidden = komplettSichtbar;
    if (komplettSichtbar) return;

    const MMB = 168, MMH = 108, POLSTER = 4;
    const inhaltBreite = Math.max(huelle.maxX - huelle.minX, 1);
    const inhaltHoehe = Math.max(huelle.maxY - huelle.minY, 1);
    const skala = Math.min((MMB - 2 * POLSTER) / inhaltBreite, (MMH - 2 * POLSTER) / inhaltHoehe);
    this._minikarteSkala = skala;
    const ox = POLSTER - huelle.minX * skala;
    const oy = POLSTER - huelle.minY * skala;
    this._minikarteVerschiebung = { ox, oy };

    svg.textContent = "";
    for (const karte of this.anlage.karten) {
      const b = karte._breite || this.KARTE_BREITE;
      const h = karte._hoehe || 96;
      const r = document.createElementNS(NS, "rect");
      r.setAttribute("x", ox + karte.pos_x * skala);
      r.setAttribute("y", oy + karte.pos_y * skala);
      r.setAttribute("width", Math.max(b * skala, 1.5));
      r.setAttribute("height", Math.max(h * skala, 1.5));
      r.setAttribute("class", "minikarte-karte");
      svg.appendChild(r);
    }
    const rahmen = document.createElementNS(NS, "rect");
    rahmen.setAttribute("x", ox + sichtX0 * skala);
    rahmen.setAttribute("y", oy + sichtY0 * skala);
    rahmen.setAttribute("width", (sichtX1 - sichtX0) * skala);
    rahmen.setAttribute("height", (sichtY1 - sichtY0) * skala);
    rahmen.setAttribute("class", "minikarte-sichtfenster");
    svg.appendChild(rahmen);
  },

  bindeLeinwand() {
    const leinwand = document.getElementById("leinwand");

    const einpassenKnopf = document.getElementById("btn-einpassen");
    if (einpassenKnopf) {
      einpassenKnopf.addEventListener("click", () => this.einpassen());
    }

    // Minikarte anklicken springt an die entsprechende Stelle - macht den
    // reinen Positionsanzeiger nebenbei zur Navigation, ohne dass das
    // zusaetzliche Bedienung braucht.
    const minikarte = document.getElementById("minikarte");
    if (minikarte) {
      minikarte.addEventListener("pointerdown", (e) => {
        if (!this._minikarteSkala) return;
        const kasten2 = minikarte.getBoundingClientRect();
        const { ox, oy } = this._minikarteVerschiebung;
        const weltX = (e.clientX - kasten2.left - ox) / this._minikarteSkala;
        const weltY = (e.clientY - kasten2.top - oy) / this._minikarteSkala;
        const zielKasten = leinwand.getBoundingClientRect();
        this.sicht.x = zielKasten.width / 2 - weltX * this.sicht.zoom;
        this.sicht.y = zielKasten.height / 2 - weltY * this.sicht.zoom;
        this.aktualisiereSicht();
      });
    }

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
      // Untere Schranke bewusst unter der ueblichen Einpassen-Zoomstufe
      // (siehe einpassen()) - sonst liesse sich bei einer besonders grossen
      // Anlage nicht so weit herauszoomen, wie "Einpassen" selbst braucht.
      this.sicht.zoom = Math.min(3, Math.max(0.08, this.sicht.zoom * faktor));
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
      panelLeeren();
      await this.laden(this.anlage.id);
    });
  },
};

window.addEventListener("DOMContentLoaded", async () => {
  Editor.bindeLeinwand();
  panelLeeren();
  await Palette.laden();
  await Editor.laden(window.ANLAGE_ID);
  pfeileBinden(Editor);
});
