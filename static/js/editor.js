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
  const zeilen = [];
  let aktuell = "";

  // Ein einzelnes Wort, das fuer sich allein schon breiter ist als
  // maxBreite (z.B. "Wärmerückgewinnung" - ein zusammengesetztes Wort ganz
  // ohne Leerzeichen), kann nicht am Wortzwischenraum umbrechen. Ohne diese
  // zeichenweise Aufteilung liefe es ueber die Karte hinaus - genau das
  // Abschneiden, das dieser Umbruch eigentlich verhindern soll. Gibt das
  // letzte, noch passende Stueck zurueck; der Aufrufer haengt bei Bedarf
  // das naechste Wort daran.
  function schneide(wort) {
    let rest = wort;
    while (textBreite(rest, font) > maxBreite && rest.length > 1) {
      let i = rest.length - 1;
      while (i > 1 && textBreite(rest.slice(0, i) + "-", font) > maxBreite) i--;
      zeilen.push(rest.slice(0, i) + "-");
      rest = rest.slice(i);
    }
    return rest;
  }

  for (const wort of text.split(" ")) {
    const kandidat = aktuell ? `${aktuell} ${wort}` : wort;
    if (textBreite(kandidat, font) <= maxBreite) {
      aktuell = kandidat;
      continue;
    }
    if (aktuell) zeilen.push(aktuell);
    aktuell = schneide(wort);
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

/* Eigene Kopie statt Import: simulation.js definiert bereits eine identische
   htmlSicher() (siehe dortiger Kommentar) - editor.js braucht sie fuer die
   beiden folgenden Dialoge, ohne selbst eine Ladereihenfolge-Abhaengigkeit
   von simulation.js einzugehen (editor.html bindet simulation.js zwar vor
   editor.js ein, aber die Abhaengigkeitsrichtung soll trotzdem nicht davon
   abhaengen, welche Datei zufaellig zuerst geladen wird). */
function htmlSicher(text) {
  const traeger = document.createElement("span");
  traeger.textContent = text == null ? "" : String(text);
  return traeger.innerHTML;
}

/* Zwei wiederverwendete Dialoge fuer Loeschen und Umbenennen - dieselbe
   Idee (und fast derselbe Code) wie in start.js, dort aus demselben Grund
   noch einmal eigenstaendig definiert (siehe dortiger Kommentar zu
   zeigeFehler()/htmlSicher()). Beide geben ein Promise zurueck, das sich
   erst mit dem Schliessen des Dialogs aufloest. simulation.js verwendet
   beide fuer "Frueherer Lauf loeschen" mit, obwohl es sie nicht selbst
   definiert - dieselbe bestehende Abhaengigkeit wie bei zeigeFehler(). */
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

/* Steht der Tastaturfokus in einem Feld, in dem jemand gerade Text
   bearbeitet? Der Entf-Lauscher haengt am window und bekaeme sonst auch die
   Tastendruecke ab, die dem Bezeichnungsfeld einer Karte gelten - Entf
   loeschte dann statt eines Zeichens die ganze Karte samt ihren Pfeilen.
   Geprueft werden Eingabefeld, Textbereich, Auswahlfeld und jedes als
   contenteditable markierte Element; Knoepfe und die Leinwand selbst zaehlen
   ausdruecklich nicht dazu, dort soll die Taste weiter wirken. */
function istTexteingabe(element) {
  if (!element) return false;
  if (element.isContentEditable) return true;
  const name = (element.tagName || "").toUpperCase();
  return name === "INPUT" || name === "TEXTAREA" || name === "SELECT";
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

const Editor = {
  anlage: null,
  auswahl: null,
  sicht: { x: 0, y: 0, zoom: 1 },
  // Nur beim allerersten Laden automatisch in die Startansicht wechseln
  // (siehe laden() und startAnsicht() weiter unten) - nicht bei jedem
  // erneuten Laden nach einer Aenderung, sonst risse jede Aenderung (Karte
  // loeschen, Pfeil anlegen) den Bildausschnitt der Anwenderin unter ihr weg.
  _nochNichtGeoeffnet: true,

  // Untere/obere Schranke fuer die Zoomstufe - ein einziger Ort fuer Mausrad
  // (wheel) UND Kneifgeste (Pinch, siehe _kneifBewegen() weiter unten)
  // statt derselben zwei Zahlen an zwei Stellen.
  ZOOM_MIN: 0.08,
  ZOOM_MAX: 3,

  // Mehrfingerzustand der Leinwand (Schieben/Kneifen, siehe bindeLeinwand()
  // weiter unten): eine Map ueber alle gerade aktiven Zeiger (Finger oder
  // die eine Maustaste) statt eines einzelnen Satzes Ereignis-Lauscher pro
  // Geste (wie karteGreifen() und Pfeile.ziehenStarten() es machen) - nur so
  // kann ein zweiter, waehrend des Schiebens dazukommender Finger nahtlos in
  // eine Kneifgeste uebergehen, statt dass die Leinwand nur den ersten
  // Finger kennt.
  _zeiger: new Map(),
  _panAnker: null,
  _kneifAnker: null,

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
    if (this._nochNichtGeoeffnet) {
      this._nochNichtGeoeffnet = false;
      this.startAnsicht();
    }
  },

  async anlageUmbenennen() {
    const neuerName = await textEingabeDialog("Anlage umbenennen", this.anlage.name);
    if (neuerName === null) return;
    let antwort;
    try {
      antwort = await fetch(`/api/anlagen/${this.anlage.id}`, {
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
    this.anlage.name = neuerName;
    document.getElementById("anlagenname").textContent = neuerName;
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
  // Schriftgroesse und Zeilenhoehe des Kartennamens - eine einzige
  // Quelle fuer karteMasseBerechnen() (misst damit), zeichneKarte()
  // (zeichnet damit) UND aktualisiereBeschriftungen() (haelt die
  // Bildschirmgroesse damit ab). style.css' .karte-name tspan muss mit
  // KARTE_NAME_PX uebereinstimmen (dort als Kommentar vermerkt).
  KARTE_NAME_PX: 14,
  KARTE_NAME_ZEILENHOEHE: 17,
  // Unterhalb dieser Zoomstufe tragen Gruppenzeile und Werte nichts mehr
  // bei (die Gruppe steht ohnehin schon als Farbkante da) und verschwinden,
  // statt zu grauem Nebel zu verblassen - siehe aktualisiereBeschriftungen().
  DETAIL_ZOOM_SCHWELLE: 0.85,
  // Zoomstufe, mit der der Editor eine Anlage oeffnet (siehe startAnsicht()
  // weiter unten) - 1 entspricht der Groesse, fuer die Schrift und
  // Kartenmasse entworfen sind (KARTE_NAME_PX etc.), also von sich aus
  // lesbar, ohne jede Sondermassnahme. "Einpassen" bleibt daneben als
  // ausdrueckliche Uebersicht ueber die ganze Anlage (siehe einpassen()).
  START_ZOOM: 1,

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
    // der Name ist das Wichtigste auf der Karte.
    const zeilenHoehe = this.KARTE_NAME_ZEILENHOEHE;
    const font = `500 ${this.KARTE_NAME_PX}px Roboto, Arial, sans-serif`;
    // Umbruch auf die tatsaechliche Kartenbreite, nicht schmaler: der Name
    // skaliert seit der Ruecknahme der Gegenskalierung (siehe
    // aktualisiereBeschriftungen()) im gleichen Verhaeltnis wie der Kasten
    // selbst - er kann den Kasten also bei keiner Zoomstufe mehr verlassen,
    // ein engerer Umbruch nur noch unnoetig frueh auf eine weitere Zeile
    // umbrechen wuerde.
    const zeilenBreite = breite - textX - pad;
    const zeilen = zeilenUmbrechen(karte.name, zeilenBreite, font);
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

    // Der Name skaliert wie der Rest der Karte ganz normal mit dem Zoom mit
    // (siehe Kommentar bei aktualisiereBeschriftungen() zur fruehreren
    // Gegenskalierung und warum sie entfallen ist) - deshalb reicht ein
    // gewoehnliches <text> in absoluten Kartenkoordinaten, keine eigene
    // transformierte Huelle mehr noetig.
    const beschriftung = document.createElementNS(NS, "text");
    beschriftung.setAttribute("class", "karte-name");
    beschriftung.setAttribute("x", masse.textX);
    for (let i = 0; i < masse.zeilen.length; i++) {
      const zeile = document.createElementNS(NS, "tspan");
      zeile.setAttribute("x", masse.textX);
      zeile.setAttribute("y", masse.nameStartY + i * this.KARTE_NAME_ZEILENHOEHE);
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
    // Auf schmalem Hochformat mit Finger (siehe seitenbereichSchmal() weiter
    // unten) ist das Parameterfenster sonst ein eigener, unsichtbarer
    // Seitenbereich (siehe style.css) - eine Karte auszuwaehlen soll es
    // automatisch aufklappen, genau wie am Schreibtisch, wo es ohnehin
    // immer offen ist.
    if (this.seitenbereichSchmal()) this.seitenbereichOeffnen("panel");
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

  /* Baut aus [[anzahl, einzahl, mehrzahl], ...] den Satz 'Werden mit
     gelöscht: 5 Pfeile.' - dieselbe Idee (und fast derselbe Code) wie
     Start._verlustHinweis() in start.js, dort aus demselben Grund noch einmal
     eigenstaendig definiert (siehe dortiger Kommentar zu zeigeFehler()).
     Sind es null Pfeile, entfaellt der Satz: dann geht nichts weiter
     verloren als die Karte selbst. */
  _verlustHinweis(teile) {
    const genannt = teile
      .filter(([anzahl]) => anzahl)
      .map(([anzahl, einzahl, mehrzahl]) => `${anzahl} ${anzahl === 1 ? einzahl : mehrzahl}`);
    if (!genannt.length) return "";
    return ` <span class="dialog-text-verlust">Werden mit gelöscht: ${genannt.join(", ")}.</span>`;
  },

  /* Eine Karte zu loeschen reisst alle Pfeile mit, die an ihr haengen - der
     Server raeumt sie mit weg. Deshalb dieselbe Rueckfrage wie ueberall
     sonst (Projekt, Anlage, Wetterdaten, Lauf), und sie nennt die Zahl der
     Pfeile, damit vorher zu sehen ist, was verloren geht. */
  async karteLoeschenDialog(karteId) {
    const karte = this.karteNach(karteId);
    if (!karte) return;
    const pfeile = (this.anlage.pfeile || []).filter(
      (p) => p.von_karte_id === karteId || p.nach_karte_id === karteId
    ).length;

    const bestaetigt = await bestaetigenDialog(
      "Karte löschen",
      `Karte "${htmlSicher(karte.name)}" wirklich löschen?` +
        this._verlustHinweis([[pfeile, "Pfeil", "Pfeile"]])
    );
    if (!bestaetigt) return;

    let antwort;
    try {
      antwort = await fetch(`/api/karten/${karteId}`, { method: "DELETE" });
    } catch {
      zeigeFehler("Karte konnte nicht gelöscht werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Karte konnte nicht gelöscht werden.");
      return;
    }
    if (this.auswahl === karteId) {
      this.auswahl = null;
      panelLeeren();
    }
    await this.laden(this.anlage.id);
  },

  aktualisiereSicht() {
    document
      .getElementById("welt")
      .setAttribute(
        "transform",
        `translate(${this.sicht.x} ${this.sicht.y}) scale(${this.sicht.zoom})`
      );
    this.aktualisiereMinikarte();
    this.aktualisiereBeschriftungen();
  },

  /* Blendet Gruppenzeile und Werte unterhalb einer Zoomstufe aus - die
     Gruppe steht ohnehin schon als Farbkante da (siehe
     .karte-gruppenstreifen), sie verschwinden dort ganz statt zu
     unlesbarem Grau zu verblassen und kommen zurueck, sobald wieder genug
     Zoom da ist.

     Der Kartenname selbst braucht hier KEINE Massnahme mehr: er wurde
     frueher gegen den Zoom gegengeskaliert, damit er bei kleiner Zoomstufe
     nicht unter eine Mindestgroesse schrumpft (siehe Task-Nachbesserung
     "Die Schrift schrumpft mit, und das muss sie nicht") - genau das hat
     ihn bei 36 Karten ueber die Nachbarkarte hinauslaufen lassen, weil der
     Kasten mitschrumpfte, waehrend der Name seine Groesse behielt (siehe
     Task "Ueberlappende Karten im gezeichneten Bild"). Der Name skaliert
     jetzt wieder ganz normal mit dem Kasten mit - stattdessen oeffnet der
     Editor bei einer von vornherein lesbaren Zoomstufe (siehe
     startAnsicht() weiter unten); "Einpassen" bleibt eine ausdrueckliche
     Uebersicht, in der kleine Namen in Ordnung sind, solange nichts
     ueberlappt (karteMasseBerechnen() bricht dafuer auf die tatsaechliche
     Kartenbreite um, siehe dortiger Kommentar). */
  aktualisiereBeschriftungen() {
    const zoom = this.sicht.zoom;
    // el.hidden = ... setzt bei einem per createElementNS erzeugten SVG-
    // Element zwar die IDL-Eigenschaft, spiegelt sie aber nicht zuverlaessig
    // auf das tatsaechliche hidden-Attribut (und damit auf die CSS-Regel
    // [hidden]{display:none!important}) - deshalb hier ausdruecklich das
    // Attribut selbst setzen/entfernen statt der Kurzform, die anderswo auf
    // der Seite (bei gewoehnlichen HTML-Elementen) funktioniert.
    const zeigeDetails = zoom >= this.DETAIL_ZOOM_SCHWELLE;
    document.querySelectorAll(".karte-gruppe, .karte-werte").forEach((el) => {
      if (zeigeDetails) el.removeAttribute("hidden");
      else el.setAttribute("hidden", "");
    });
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
     - die ausdrueckliche Uebersicht ueber den Knopf "Einpassen" (siehe
     bindeEreignisse() weiter unten). Bei vielen Karten faellt der Zoom dabei
     so weit, dass Namen klein und teils nur noch als Farbkante erkennbar
     sind (siehe DETAIL_ZOOM_SCHWELLE) - das ist hier in Ordnung: eine
     Uebersicht sucht man in, statt in ihr zu lesen. Anders als frueher
     oeffnet der Editor eine Anlage NICHT mehr in dieser Ansicht (siehe
     startAnsicht() weiter unten und laden() oben) - bei 36 Karten war die
     Uebersicht so weit herausgezoomt, dass an ihr nichts mehr zu lesen war,
     ohne die Gegenskalierung, die das beheben sollte, wiederum Namen ueber
     die Nachbarkarte hinauslaufen liess (siehe Task "Ueberlappende Karten
     im gezeichneten Bild"). */
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

  /* Ansicht, in der der Editor eine Anlage oeffnet (siehe laden() oben):
     START_ZOOM statt voller Einpassung, verankert an der Karte, an der der
     Luftweg beginnt - dort, wo jemand zu arbeiten anfaengt, nicht an der
     Uebersicht ueber alles (die bleibt ueber "Einpassen" einen Klick
     entfernt, die Minikarte gibt dabei die Orientierung). "Wo der Luftweg
     beginnt" ist absichtlich nicht an einen Kartentyp wie "wetter"
     gebunden (das koppelte den Editor an eine bestimmte Vorlagenform) -
     stattdessen schlicht die am weitesten links liegende Karte, bei
     Gleichstand die am weitesten oben liegende: in jeder bisherigen
     Vorlage (siehe core/vorlagen/) steht die erste Stufe der Kette links. */
  startAnsicht() {
    const leinwand = document.getElementById("leinwand");
    const kasten = leinwand.getBoundingClientRect();
    if (!this.anlage || this.anlage.karten.length === 0 || kasten.width === 0) {
      this.sicht = { x: 0, y: 0, zoom: 1 };
      this.aktualisiereSicht();
      return;
    }
    let start = this.anlage.karten[0];
    for (const karte of this.anlage.karten) {
      if (
        karte.pos_x < start.pos_x ||
        (karte.pos_x === start.pos_x && karte.pos_y < start.pos_y)
      ) {
        start = karte;
      }
    }
    const zoom = this.START_ZOOM;
    this.sicht.zoom = zoom;
    const POLSTER = 90;
    const startHoehe = start._hoehe || 96;
    this.sicht.x = POLSTER - start.pos_x * zoom;
    this.sicht.y = kasten.height / 2 - (start.pos_y + startHoehe / 2) * zoom;
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

  /* Trifft SCHMAL (Hochformat-iPad, siehe Task Befund 6) UND FINGER
     zusammen zu - dieselbe Bedingung wie style.css' @media (max-width: 900px)
     and (pointer: coarse), hier noch einmal in JS gebraucht (Palette/Panel
     automatisch auf-/zuklappen), deshalb an einer einzigen Stelle benannt
     statt an mehreren Aufrufstellen dieselben zwei matchMedia-Strings zu
     wiederholen. Ein schmales MAUS-Fenster am Schreibtisch bleibt bewusst
     aussen vor (siehe dortiger Kommentar). */
  seitenbereichSchmal() {
    return window.matchMedia("(max-width: 900px) and (pointer: coarse)").matches;
  },

  /* Klappt Palette oder Parameterfenster auf/zu (bereich: "palette" oder
     "panel") - nur wirksam, wenn die zugehoerige CSS-Regel greift (siehe
     seitenbereichSchmal()); anderswo bleibt die Klasse folgenlos, weil dort
     kein transform darauf reagiert. Oeffnen des einen schliesst automatisch
     den anderen: fuer beide Seitenbereiche gleichzeitig ist auf 834 Punkten
     kein Platz neben der Leinwand (siehe Task). */
  seitenbereichOeffnen(bereich) {
    const anderer = bereich === "palette" ? "panel" : "palette";
    this.seitenbereichSchliessen(anderer);
    const el = document.getElementById(bereich);
    const knopf = document.getElementById(`btn-${bereich}-umschalten`);
    if (el) el.classList.add("seitenbereich-offen");
    if (knopf) knopf.setAttribute("aria-expanded", "true");
  },
  seitenbereichSchliessen(bereich) {
    const el = document.getElementById(bereich);
    const knopf = document.getElementById(`btn-${bereich}-umschalten`);
    if (el) el.classList.remove("seitenbereich-offen");
    if (knopf) knopf.setAttribute("aria-expanded", "false");
  },
  seitenbereichSchalten(bereich) {
    const el = document.getElementById(bereich);
    if (el && el.classList.contains("seitenbereich-offen")) {
      this.seitenbereichSchliessen(bereich);
    } else {
      this.seitenbereichOeffnen(bereich);
    }
  },

  /* Fasst die zwei aktiven Zeiger einer Kneifgeste zu Mittelpunkt und
     Abstand zusammen - von _kneifBewegen() gebraucht, siehe dort. */
  _kneifMasse(zeiger) {
    const [a, b] = zeiger;
    return {
      distanz: Math.hypot(a.x - b.x, a.y - b.y) || 1,
      mitteX: (a.x + b.x) / 2,
      mitteY: (a.y + b.y) / 2,
    };
  },

  /* Zoomt UND schiebt in einem Zug, solange genau zwei Finger auf der
     Leinwand liegen (siehe Task: "Auf- und Zuziehen zum Zoomen, Schieben zum
     Verschieben" - beides gleichzeitig moeglich, wie auf jedem Touchgeraet
     ueblich). Beim ersten Aufruf einer neuen Kneifgeste (_kneifAnker noch
     leer) wird nur der Ankerpunkt gemerkt - derselbe Weltpunkt bleibt dann
     bei jeder folgenden Bewegung exakt unter der aktuellen Fingermitte
     stehen, das ergibt Zoom UND Schieben zugleich aus derselben Formel wie
     Editor.einpassen() (Weltpunkt -> Bildschirmpunkt), nur umgekehrt
     angewendet. */
  _kneifBewegen() {
    const leinwand = document.getElementById("leinwand");
    const kasten = leinwand.getBoundingClientRect();
    const zeiger = [...this._zeiger.values()].slice(0, 2);
    const { distanz, mitteX, mitteY } = this._kneifMasse(zeiger);

    if (!this._kneifAnker) {
      this._kneifAnker = {
        distanz,
        zoom: this.sicht.zoom,
        weltX: (mitteX - kasten.left - this.sicht.x) / this.sicht.zoom,
        weltY: (mitteY - kasten.top - this.sicht.y) / this.sicht.zoom,
      };
      return;
    }
    const zoom = Math.min(
      this.ZOOM_MAX,
      Math.max(this.ZOOM_MIN, this._kneifAnker.zoom * (distanz / this._kneifAnker.distanz))
    );
    this.sicht.zoom = zoom;
    this.sicht.x = (mitteX - kasten.left) - this._kneifAnker.weltX * zoom;
    this.sicht.y = (mitteY - kasten.top) - this._kneifAnker.weltY * zoom;
    this.aktualisiereSicht();
  },

  /* Entfernt einen losgelassenen/abgebrochenen Zeiger (pointerup ODER
     pointercancel - Touch-Gesten koennen vom Betriebssystem abgebrochen
     werden, z.B. durch eine Systemgeste, siehe MDN zu pointercancel) aus der
     Zeiger-Map und setzt den Anker fuer das verbleibende Schieben/Kneifen
     neu, damit die Ansicht nicht mit einem Sprung weiterspringt. */
  _zeigerEntfernen(e) {
    if (!this._zeiger.has(e.pointerId)) return;
    this._zeiger.delete(e.pointerId);
    this._kneifAnker = null;
    if (this._zeiger.size === 1) {
      const [[, position]] = this._zeiger;
      this._panAnker = { x: position.x, y: position.y, sichtX: this.sicht.x, sichtY: this.sicht.y };
    } else {
      this._panAnker = null;
    }
  },

  bindeLeinwand() {
    const leinwand = document.getElementById("leinwand");

    const einpassenKnopf = document.getElementById("btn-einpassen");
    if (einpassenKnopf) {
      einpassenKnopf.addEventListener("click", () => this.einpassen());
    }

    // Umschaltknoepfe fuer Palette/Parameterfenster (siehe style.css, @media
    // (max-width: 900px) and (pointer: coarse)) - ausserhalb dieser
    // Bedingung unsichtbar, aber ungefaehrlich verdrahtet, "click" statt
    // "pointerdown" reicht hier, es gibt nichts zu ziehen.
    const paletteKnopf = document.getElementById("btn-palette-umschalten");
    if (paletteKnopf) {
      paletteKnopf.addEventListener("click", () => this.seitenbereichSchalten("palette"));
    }
    const panelKnopf = document.getElementById("btn-panel-umschalten");
    if (panelKnopf) {
      panelKnopf.addEventListener("click", () => this.seitenbereichSchalten("panel"));
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
      // Ein per Finger "bewaffneter" Paletteneintrag (siehe palette.js,
      // Palette.armieren()) wartet auf genau diesen Tipp - er legt die Karte
      // an der angetippten Stelle an, statt die Leinwand zu schieben oder
      // die Auswahl aufzuheben. Mit der Maus bleibt Palette.bereit immer
      // leer (armieren() prueft dort selbst schon den pointerType), dieser
      // Zweig greift also nie bei einem Mausklick.
      if (Palette.bereit) {
        const kasten = leinwand.getBoundingClientRect();
        const x = (e.clientX - kasten.left - this.sicht.x) / this.sicht.zoom;
        const y = (e.clientY - kasten.top - this.sicht.y) / this.sicht.zoom;
        const kennung = Palette.bereit.kennung;
        Palette.entwaffnen();
        this.karteHinzufuegen(kennung, Math.round(x), Math.round(y));
        return;
      }
      if (e.target.closest(".karte")) return;
      // Auf schmalem Hochformat schliesst ein Tipp auf die leere Leinwand
      // beide Seitenbereiche wieder - sie waeren sonst nur ueber die
      // Umschaltknoepfe wieder loszuwerden.
      if (this.seitenbereichSchmal()) {
        this.seitenbereichSchliessen("palette");
        this.seitenbereichSchliessen("panel");
      }
      this.auswahl = null;
      panelLeeren();
      this.entferneAuswahlKlasse();

      // setPointerCapture: dieser Zeiger meldet sich weiter bei der
      // Leinwand, auch wenn er den Bildschirmbereich des Elements verlaesst
      // (schneller Zug ueber den Rand hinaus) - ohne das braeuchte es dafuer
      // wieder Lauscher auf window wie vor diesem Umbau. Fuer Touch macht das
      // ohnehin schon die implizite Erfassung des Browsers, fuer die Maus
      // erst dieser Aufruf. try/catch: die Spezifikation laesst den Aufruf
      // ausdruecklich fehlschlagen, wenn der Browser diesen Zeiger nicht
      // (mehr) als aktiv fuehrt (z.B. schon losgelassen, bevor dieser
      // Handler dran kommt) - das darf das Schieben/Kneifen selbst nicht
      // abbrechen, es geht dann nur ohne den zusaetzlichen Schutz weiter.
      try {
        leinwand.setPointerCapture(e.pointerId);
      } catch {
        /* Zeiger nicht (mehr) aktiv - siehe Kommentar oben, kein Abbruch. */
      }
      this._zeiger.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (this._zeiger.size === 1) {
        this._panAnker = { x: e.clientX, y: e.clientY, sichtX: this.sicht.x, sichtY: this.sicht.y };
        this._kneifAnker = null;
      } else {
        // Zweiter Finger waehrend des Schiebens dazugekommen: ab jetzt
        // Kneifgeste statt Ein-Finger-Schieben (siehe _kneifBewegen()).
        this._panAnker = null;
        this._kneifAnker = null;
      }
    });

    leinwand.addEventListener("pointermove", (e) => {
      if (!this._zeiger.has(e.pointerId)) return;
      this._zeiger.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (this._zeiger.size >= 2) {
        this._kneifBewegen();
      } else if (this._panAnker) {
        this.sicht.x = this._panAnker.sichtX + (e.clientX - this._panAnker.x);
        this.sicht.y = this._panAnker.sichtY + (e.clientY - this._panAnker.y);
        this.aktualisiereSicht();
      }
    });

    leinwand.addEventListener("pointerup", (e) => this._zeigerEntfernen(e));
    leinwand.addEventListener("pointercancel", (e) => this._zeigerEntfernen(e));

    leinwand.addEventListener("wheel", (e) => {
      e.preventDefault();
      const faktor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
      // Untere Schranke bewusst unter der ueblichen Einpassen-Zoomstufe
      // (siehe einpassen()) - sonst liesse sich bei einer besonders grossen
      // Anlage nicht so weit herauszoomen, wie "Einpassen" selbst braucht.
      this.sicht.zoom = Math.min(this.ZOOM_MAX, Math.max(this.ZOOM_MIN, this.sicht.zoom * faktor));
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

    /* Der Lauscher haengt bewusst am window und nicht an der Leinwand: die
       Auswahl einer Karte bleibt auch bestehen, waehrend der Fokus im
       Parameterfenster daneben liegt. Genau deshalb muss er selbst pruefen,
       wo der Fokus steht - sonst loescht Entf beim Tippen im Feld
       "Bezeichnung" die ganze Karte statt eines Zeichens. */
    window.addEventListener("keydown", async (e) => {
      if (e.key !== "Delete" || this.auswahl === null) return;
      if (istTexteingabe(document.activeElement)) return;
      if (document.querySelector(".dialog-huelle")) return;
      await this.karteLoeschenDialog(this.auswahl);
    });
  },
};

/* Traegt die tatsaechlich sichtbare Hoehe (VisualViewport, nicht die
   Layout-Hoehe) als --app-hoehe nach - siehe Kommentar bei .app in
   style.css. Wichtig bei eingeblendeter Bildschirmtastatur: iOS Safari
   verkleinert dafuer die VisualViewport, nicht zuverlaessig die per dvh
   gemessene Layout-Hoehe (dvh reagiert nachweislich auf ein-/ausfahrende
   Werkzeugleisten, nicht in jedem Fall auf die Tastatur). Ohne diesen
   Nachtrag koennte .app (und damit .panel als sein Kind) unten laenger
   bleiben, als tatsaechlich zu sehen ist, sobald die Tastatur offen ist -
   ein Feld am unteren Rand des Parameterfensters liesse sich dann per
   scrollIntoView() zwar innerhalb des Panels erreichen, das Panel selbst
   ragte aber teils hinter die Tastatur. Nur die Editorseite bindet
   editor.js ein, kein Aufwand fuer Startseite/Bausteine noetig.
   window.visualViewport fehlt in aelteren Browsern - dann bleibt die
   CSS-Variable unbenutzt und .app faellt auf 100dvh zurueck (siehe
   style.css, var(--app-hoehe, 100dvh)). */
if (window.visualViewport) {
  const aktualisiereAppHoehe = () => {
    document.documentElement.style.setProperty(
      "--app-hoehe", `${window.visualViewport.height}px`
    );
  };
  window.visualViewport.addEventListener("resize", aktualisiereAppHoehe);
  aktualisiereAppHoehe();
}

window.addEventListener("DOMContentLoaded", async () => {
  Editor.bindeLeinwand();
  panelLeeren();
  await Palette.laden();
  await Editor.laden(window.ANLAGE_ID);
  pfeileBinden(Editor);

  const btnUmbenennen = document.getElementById("btn-anlage-umbenennen");
  if (btnUmbenennen) {
    btnUmbenennen.addEventListener("click", () => Editor.anlageUmbenennen());
  }
});
