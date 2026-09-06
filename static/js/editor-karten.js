/* Karten und ihre Anschluesse zeichnen. Von hier kommt alles, was als SVG
   in der Leinwand steht: die Kaesten, ihre Masse, ihre Ports und der
   Verbindungsgriff.

   Herausgeloest aus static/js/editor.js, das mit 2017 Zeilen zu gross
   geworden war, um es beim Lesen im Kopf zu behalten. Die Methoden sind
   unveraendert; sie werden derselben Editor-Sammlung zugefuegt, zu der
   sie vorher gehoerten. Klassische Skripte teilen sich den globalen
   Gueltigkeitsbereich, deshalb ist Editor hier sichtbar - dieselbe
   Voraussetzung, unter der editor.js schon immer Pfeile aus
   static/js/pfeile.js benutzt hat.

   Geladen NACH editor.js und vor DOMContentLoaded (siehe
   templates/editor.html); dort wird zuerst gerufen. */

Object.assign(Editor, {
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

  // Bis zu dieser Zoomstufe herunter lohnt es sich, eine Anlage beim Oeffnen
  // GANZ zu zeigen statt nur ihren Anfang (siehe startAnsicht()). Sie ist
  // bewusst nicht DETAIL_ZOOM_SCHWELLE: dort geht es darum, ab wann die
  // Zusatzzeilen einer Karte (Gruppe, Werte) mehr stoeren als helfen -
  // hier darum, ab wann der NAME einer Karte nicht mehr zu lesen ist. Der
  // Name steht in 13px (siehe .karte-name in style.css); 0,6 laesst davon
  // knapp 8px uebrig, die Grenze des Lesbaren. Eine Beispielanlage einer
  // einzelnen Karte passt damit ganz ins Bild (gemessen: Zoom 0,72), eine
  // Vorlage mit 38 Karten nicht (0,37) - und die oeffnet weiter an ihrem
  // Anfang, wo man zu arbeiten beginnt.
  EINSTIEG_ZOOM_MIN: 0.6,

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
});
