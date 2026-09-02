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

/* Nach JEDEM Neuzeichnen der Pfeile zwei Nachtraege, die pfeile.js nicht
   selbst kennt: die breiteren, unsichtbaren Trefferbahnen (damit ein Finger
   einen 1,5 Pixel schmalen Signalpfeil ueberhaupt treffen kann) und die
   Markierung des ausgewaehlten Pfeils. Beides haengt hier statt in
   pfeile.js, weil die Auswahl zum Editor gehoert (wie die Auswahl einer
   Karte) - zeichneAlle() baut die Ebene bei jedem Aufruf neu auf und wuesste
   sonst nichts davon. */
function pfeileZeichnen(anlage) {
  Pfeile.zeichneAlle(anlage);
  Editor.pfeilTrefferbahnenNachtragen();
  Editor.pfeilAuswahlZeichnen();
}
function pfeileBinden(editor) {
  Pfeile.binde(editor);
}
/* Loeschen ueber pfeile.js, statt hier ein zweites fetch() zu schreiben:
   Pfeile.loeschen() meldet Fehlschlaege bereits selbst und laedt die Anlage
   danach neu. Ob es geklappt hat, liest pfeilLoeschen() danach an der neu
   geladenen Anlage ab. */
function pfeilLoeschenServerseitig(pfeilId) {
  return Pfeile.loeschen(pfeilId);
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
  const hinweis = document.getElementById("hinweismeldung");
  if (hinweis) hinweis.hidden = true;   // beide sitzen an derselben Stelle
  leiste.textContent = nachricht;
  leiste.hidden = false;
  window.clearTimeout(zeigeFehler.timer);
  zeigeFehler.timer = window.setTimeout(() => { leiste.hidden = true; }, 5000);
}

/* Die ruhige Schwester von zeigeFehler(): bestaetigt eine Handlung, statt
   vor etwas zu warnen ("Zurückgenommen: Karte 'Erhitzer' gelöscht"). Sie ist
   auf dem iPad der einzige Ort, an dem die Beschriftung eines
   Verlaufsschritts ohne Schweben zu lesen ist - am Schreibtisch steht
   dasselbe im title der beiden Knoepfe. Kuerzere Standzeit als eine
   Fehlermeldung: sie muss nur wahrgenommen, nicht gelesen und verstanden
   werden. Beide Leisten sitzen an derselben Stelle des Bildschirms und
   blenden einander deshalb gegenseitig aus. */
function zeigeHinweis(nachricht) {
  const leiste = document.getElementById("hinweismeldung");
  if (!leiste) return;
  const fehler = document.getElementById("fehlermeldung");
  if (fehler) fehler.hidden = true;
  leiste.textContent = nachricht;
  leiste.hidden = false;
  window.clearTimeout(zeigeHinweis.timer);
  zeigeHinweis.timer = window.setTimeout(() => { leiste.hidden = true; }, 3500);
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

  // Mausrad-Normierung (siehe bindeLeinwand(), addEventListener("wheel")):
  // deltaY kommt je nach Geraet/Browser in Pixeln, Zeilen oder Seiten
  // (e.deltaMode) - eine "Zeile" ist ohne Umrechnung mal 1 und mal 100.
  // WHEEL_LINE_PX naehert eine Zeile an die Zeilenhoehe der Oberflaeche an
  // (13px Schrift, Zeilenhoehe knapp 1.2 - siehe .leiste-knopf u.a. in
  // style.css). WHEEL_PX_MAX begrenzt den Betrag JE Ereignis, damit weder
  // eine grobe Rastung noch ein einzelnes Seiten-Ereignis (deltaMode 2) den
  // ganzen Zoombereich in einem Sprung durchlaeuft. WHEEL_PX_PRO_FAKTOR_1_1
  // ist der Massstab: bei so vielen genormten Pixeln soll die Aenderung dem
  // fruehreren Faktor 1,1 entsprechen - eine klassische Mausrad-Rastung
  // liefert in Chrome/Edge deltaY 100, genau dort war 1,1 also von Anfang an
  // richtig gewaehlt (Task-Rueckmeldung); nur die Auswertung nur des
  // Vorzeichens sprang bei feiner Rasterung (Trackpad, praezise Maus) durch
  // viele Ereignisse je Rastung katastrophal - bei vierzig kleinen
  // Ereignissen ergab 1,1^40 schon das 45-fache, der ganze Bereich von 0,08
  // bis 3 (37-fach) war in einer einzigen Rastung durchlaufen.
  WHEEL_LINE_PX: 16,
  WHEEL_PX_MAX: 120,
  WHEEL_PX_PRO_FAKTOR_1_1: 100,

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

  // Zustand der WebKit-eigenen Kneifgeste auf der Leinwand (siehe
  // bindeLeinwand(), gesturestart/-change/-end) - null, solange keine
  // solche Geste laeuft. Waehrend sie laeuft, haelt sich der
  // zeigerbasierte Pfad (_kneifBewegen()) zurueck: Safari bricht bei
  // preventDefault() auf gesturestart/-change in aller Regel die
  // zugehoerige Beruehrungsfolge ab (touchcancel), die Zeigerereignisse,
  // auf denen _kneifBewegen() aufbaut, wuerden also ohnehin mitten in der
  // Geste abreissen - dieses Feld verhindert zusaetzlich, dass beide Wege
  // sich in der kurzen Ueberlappung gegenseitig ins Gehege kommen. Bleibt
  // in Chromium/Firefox fuer immer null (dort feuert gesturestart nie),
  // der zeigerbasierte Pfad laeuft dort also unveraendert wie bisher.
  _gestenAnker: null,

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
    this.anlagennamenZeigen(this.anlage.name);
    this.zeichne();
    if (this._nochNichtGeoeffnet) {
      this._nochNichtGeoeffnet = false;
      this.startAnsicht();
    }
  },

  /* Der Anlagenname in der Kopfleiste - und an zwei weiteren Stellen, an
     denen er ganz zu lesen ist. Auf schmalen Geraeten bleibt fuer ihn wenig
     Platz: die Leiste gibt ihren Raum zuerst den Wegen zum Ergebnis (siehe
     style.css, "Kopfleiste des Editors"), sodass auf einem iPad quer nur
     noch rund sechs Zeichen und ein Auslassungszeichen uebrig bleiben
     (nachgemessen: 66 Punkte). Damit trotzdem beantwortbar bleibt, in
     welcher Anlage man ist, steht der ganze Name zusaetzlich im title des
     Elements (Zeigergeraete) und im Titel der Seite (Lesezeichen, Tab,
     Vorlesehilfen). */
  anlagennamenZeigen(name) {
    const feld = document.getElementById("anlagenname");
    feld.textContent = name;
    feld.title = name;
    document.title = `${name} – RLT-Simulation`;
  },

  // Setzt (oder deaktiviert) den dauerhaften Bericht-Weg in der Kopfleiste
  // (#link-bericht, siehe editor.html). 'simulationId' null/undefined
  // deaktiviert ihn - kein Lauf mit Ergebnis bekannt.
  berichtLinkSetzen(simulationId) {
    const link = document.getElementById("link-bericht");
    if (!link) return;
    if (simulationId) {
      link.href = `/anlage/${this.anlage.id}/lauf/${simulationId}/bericht`;
      link.removeAttribute("aria-disabled");
    } else {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
    }
  },

  // Beim Laden der Seite: welcher Lauf ist der juengste mit einem Ergebnis
  // (Status "fertig" oder "abgebrochen" - siehe core.bericht.STATUS_MIT_ERGEBNIS)?
  // Die Liste kommt bereits juengster-zuerst (core.ergebnisse.simulationen_von).
  // Ein frisch beendeter Lauf setzt den Link stattdessen direkt ueber
  // berichtLinkSetzen() (siehe static/js/simulation.js, beobachte()) - ohne
  // hierfuer erneut die ganze Liste abzufragen.
  async berichtLinkAktualisieren() {
    let antwort;
    try {
      antwort = await fetch(`/api/anlagen/${this.anlage.id}/simulationen`);
    } catch {
      zeigeFehler("Frühere Läufe konnten nicht geladen werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Frühere Läufe konnten nicht geladen werden.");
      return;
    }
    const laeufe = await antwort.json();
    const letzterMitBericht = laeufe.find(
      (l) => l.status === "fertig" || l.status === "abgebrochen"
    );
    this.berichtLinkSetzen(letzterMitBericht ? letzterMitBericht.id : null);
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
    this.anlagennamenZeigen(neuerName);
  },

  // -- Rueckgaengig und Wiederholen ---------------------------------------
  // Der Verlauf selbst liegt in der Datenbank und entsteht in
  // core/anlagen.py bei JEDER Aenderung (core/verlauf.py) - der Editor
  // haelt hier nur den zuletzt gelesenen Stand, um die beiden Knoepfe
  // beschriften und sperren zu koennen.
  _verlaufStand: null,

  async verlaufAktualisieren() {
    if (!this.anlage) return;
    let antwort;
    try {
      antwort = await fetch(`/api/anlagen/${this.anlage.id}/verlauf`);
    } catch {
      zeigeFehler("Der Verlauf konnte nicht gelesen werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Der Verlauf konnte nicht gelesen werden.");
      return;
    }
    this.verlaufKnoepfeSetzen(await antwort.json());
  },

  /* Gebuendelt statt sofort: eine einzelne Handlung der Anwenderin kann
     mehrere Anfragen ausloesen (das Parameterfenster speichert beim
     Verlassen eines Feldes und laedt danach die Karte neu). Ohne diese
     kurze Sammelfrist folgte auf jede davon eine eigene Abfrage des
     Verlaufsstands. */
  verlaufBaldAktualisieren() {
    window.clearTimeout(this._verlaufTimer);
    this._verlaufTimer = window.setTimeout(() => this.verlaufAktualisieren(), 150);
  },

  verlaufKnoepfeSetzen(stand) {
    this._verlaufStand = stand;
    const setze = (id, moeglich, text, wort) => {
      const knopf = document.getElementById(id);
      if (!knopf) return;
      knopf.disabled = !moeglich;
      // Der Knopf nennt, WAS er tut - nicht nur, dass er etwas tut.
      const beschriftung = moeglich && text ? `${wort}: ${text}` : wort;
      knopf.title = beschriftung;
      knopf.setAttribute("aria-label", beschriftung);
    };
    setze("btn-zurueck", stand.kann_zurueck, stand.zurueck_text, "Rückgängig");
    setze("btn-vor", stand.kann_vor, stand.vor_text, "Wiederholen");
  },

  /* Ein Schritt zurueck oder vor. Danach baut der Editor die Anlage neu auf;
     Ausschnitt und Zoomstufe bleiben, wo sie sind (siehe laden() und
     _nochNichtGeoeffnet) - wer etwas zurueecknimmt, will sehen, was sich
     aendert, und nicht die Ansicht suchen. */
  async verlaufSchritt(richtung) {
    if (!this.anlage) return;
    const stand = this._verlaufStand || {};
    const moeglich = richtung === "zurueck" ? stand.kann_zurueck : stand.kann_vor;
    if (moeglich === false) return;
    const text = richtung === "zurueck" ? stand.zurueck_text : stand.vor_text;
    const wort = richtung === "zurueck" ? "Rückgängig" : "Wiederholen";

    let antwort;
    try {
      antwort = await fetch(
        `/api/anlagen/${this.anlage.id}/verlauf/${richtung}`, { method: "POST" }
      );
    } catch {
      zeigeFehler(`${wort} ist fehlgeschlagen.`);
      return;
    }
    if (!antwort.ok) {
      zeigeFehler(`${wort} ist fehlgeschlagen.`);
      // Der Stand kann sich in einem zweiten Fenster verschoben haben -
      // frisch nachlesen statt auf einem ueberholten Stand beharren.
      await this.verlaufAktualisieren();
      return;
    }

    this.verlaufKnoepfeSetzen(await antwort.json());
    await this.laden(this.anlage.id);
    // Die gewaehlte Karte kann durch das Einspielen verschwunden (oder mit
    // anderen Werten wiedergekommen) sein - das Parameterfenster darf keine
    // Karte zeigen, die es nicht mehr gibt.
    const gewaehlt = this.auswahl === null ? null : this.karteNach(this.auswahl);
    if (this.auswahl !== null && !gewaehlt) {
      this.auswahl = null;
      panelLeeren();
    } else if (gewaehlt) {
      panelZeigen(gewaehlt);
    }
    zeigeHinweis(
      `${richtung === "zurueck" ? "Zurückgenommen" : "Wiederholt"}${text ? ": " + text : ""}`
    );
  },

  /* Melde- und Energiewege ein-/ausblenden (Legende in der Kopfleiste).
     Der Wunsch dahinter: "hier ist zu viel Gewirr" - in AX_SIM 2.1 laufen
     17 der 52 Signalwege als Meldung an die Bilanzkarte und den
     Datenlogger und queren dabei die halbe Anlage. Fuer die Rechnung sind
     sie noetig, beim Betrachten des Luftwegs stoeren sie.

     Von Haus aus SICHTBAR (nur blasser gezeichnet, siehe style.css):
     etwas stillschweigend zu verstecken, das der Benutzer selbst
     verdrahtet hat, waere die schlechtere Voreinstellung - er suchte dann
     eine Verbindung, die es gibt. Die Wahl bleibt im Browser gemerkt
     (localStorage), weil sie zur Arbeitsweise gehoert und nicht zur
     Anlage: sie darf keinen Verlaufsschritt erzeugen und nichts an den
     Daten aendern. localStorage kann in einem privaten Fenster werfen -
     deshalb ueberall in try/catch, ohne dass der Editor daran haengt. */
  MELDEWEGE_SCHLUESSEL: "rlt-meldewege-zeigen",

  meldewegeGemerkt() {
    try {
      return window.localStorage.getItem(this.MELDEWEGE_SCHLUESSEL) !== "nein";
    } catch {
      return true;
    }
  },

  meldewegeSetzen(zeigen) {
    const leinwand = document.getElementById("leinwand");
    if (leinwand) leinwand.classList.toggle("leinwand-ohne-meldewege", !zeigen);
    const schalter = document.getElementById("schalter-meldewege");
    if (schalter) schalter.checked = zeigen;
    // Ein Punkt an der Legende, solange etwas ausgeblendet ist: sonst
    // sucht man beim naechsten Oeffnen der Anlage eine Verbindung, die es
    // gibt - man sieht sie nur gerade nicht.
    const legende = document.querySelector(".legende");
    if (legende) legende.classList.toggle("legende-gefiltert", !zeigen);
    try {
      window.localStorage.setItem(this.MELDEWEGE_SCHLUESSEL, zeigen ? "ja" : "nein");
    } catch {
      /* Kein Speicher (privates Fenster) - die Wahl gilt dann nur fuer diese
         Sitzung, das ist kein Grund fuer eine Fehlermeldung. */
    }
  },

  // -- Einen Pfeil auswaehlen und loeschen ---------------------------------
  /* Bis hierher liess sich ein Pfeil nur per Doppelklick loeschen - und
     genau das ging nicht mehr: der pointerdown-Lauscher der Leinwand
     (bindeLeinwand weiter unten) erfasst den Zeiger, und ein erfasster
     Zeiger lenkt auch die nachfolgenden Maus-Ersatzereignisse (click,
     dblclick) auf das erfassende Element um - pfeile.js sah den Pfeil nie.
     Der Doppelklick ist jetzt wieder heil UND nur noch die Abkuerzung: ein
     Pfeil laesst sich anwaehlen wie eine Karte, hebt sich dann hervor und
     traegt einen Knopf zum Loeschen. Das ist mit dem Finger bedienbar (auf
     dem iPad gibt es keine Entf-Taste und keinen zuverlaessigen
     Doppeltipp) und mit der Tastatur (Entf, Esc). */
  pfeilAuswahl: null,

  pfeilNach(id) {
    return (this.anlage.pfeile || []).find((p) => p.id === id);
  },

  pfeilBeschreibung(pfeil) {
    const von = this.karteNach(pfeil.von_karte_id);
    const nach = this.karteNach(pfeil.nach_karte_id);
    return `${von ? von.name : "?"} → ${nach ? nach.name : "?"}`;
  },

  /* Eine zweite, deutlich breitere Bahn je Pfeil, mit derselben Kennung und
     derselben .pfeil-Klasse, aber durchsichtig (siehe style.css,
     .pfeil-treffer). Sie liegt HINTER der eigentlichen Bahn, damit deren
     eigene Lauscher (pfeile.js laesst beim Ueberfahren die beteiligten
     Anschluesse aufleuchten) unveraendert zuerst greifen - die Trefferbahn
     faengt nur, was daneben liegt. Ein Signalpfeil ist 1,5 Pixel breit; ein
     Finger trifft rund 9 Millimeter breit. */
  pfeilTrefferbahnenNachtragen() {
    const ebene = document.getElementById("pfeile");
    if (!ebene) return;
    for (const bahn of Array.from(ebene.querySelectorAll("path.pfeil"))) {
      if (bahn.classList.contains("pfeil-treffer")) continue;
      if (!bahn.dataset.id) continue;   // die Vorschau beim Ziehen hat keine
      const treffer = document.createElementNS(NS, "path");
      treffer.setAttribute("d", bahn.getAttribute("d"));
      // Die Meldeweg-Markierung wandert mit: sonst finge die Trefferbahn
      // eines ausgeblendeten Melde- oder Energiewegs weiter Klicks ab, und
      // man waehlte einen Pfeil aus, den man gar nicht sieht.
      treffer.setAttribute(
        "class",
        "pfeil pfeil-treffer"
          + (bahn.classList.contains("pfeil-meldeweg") ? " pfeil-meldeweg" : "")
      );
      treffer.setAttribute("data-id", bahn.dataset.id);
      ebene.insertBefore(treffer, bahn);
    }
  },

  pfeilAuswaehlen(id) {
    this.pfeilAuswahl = id;
    this.pfeilAuswahlZeichnen();
  },

  pfeilAbwaehlen() {
    this.pfeilAuswahl = null;
    this.pfeilAuswahlZeichnen();
  },

  /* Traegt die Markierung auf die (bei jedem Neuzeichnen frischen) Bahnen
     auf und fuehrt den Loeschknopf mit. Ist der ausgewaehlte Pfeil nicht
     mehr da - geloescht, oder durch ein Rueckgaengig/Wiederholen
     verschwunden -, faellt die Auswahl von selbst weg. */
  pfeilAuswahlZeichnen() {
    document.querySelectorAll("#pfeile path.gewaehlt").forEach((b) =>
      b.classList.remove("gewaehlt")
    );
    if (this.pfeilAuswahl !== null && !this.pfeilNach(this.pfeilAuswahl)) {
      this.pfeilAuswahl = null;
    }
    const werkzeug = document.getElementById("pfeil-werkzeug");
    if (this.pfeilAuswahl === null) {
      if (werkzeug) werkzeug.hidden = true;
      return;
    }
    document
      .querySelectorAll(`#pfeile path.pfeil[data-id="${this.pfeilAuswahl}"]`)
      .forEach((b) => b.classList.add("gewaehlt"));
    const text = document.getElementById("pfeil-werkzeug-text");
    if (text) text.textContent = this.pfeilBeschreibung(this.pfeilNach(this.pfeilAuswahl));
    if (werkzeug) werkzeug.hidden = false;
    this.pfeilWerkzeugPositionieren();
  },

  /* Setzt das Werkzeug auf die Mitte des ausgewaehlten Pfeils - in
     Bildschirmkoordinaten, nicht in Weltkoordinaten: als HTML-Element neben
     der Leinwand behaelt es beim Hineinzoomen seine Groesse, statt zu einer
     unlesbaren Briefmarke zu schrumpfen. Deshalb muss es bei jeder
     Sichtaenderung nachgefuehrt werden (siehe _setzeWeltTransform). */
  pfeilWerkzeugPositionieren() {
    const werkzeug = document.getElementById("pfeil-werkzeug");
    if (!werkzeug || this.pfeilAuswahl === null) return;
    const bahn = document.querySelector(
      `#pfeile path.pfeil[data-id="${this.pfeilAuswahl}"]:not(.pfeil-treffer)`
    );
    const buehne = werkzeug.offsetParent;
    if (!bahn || !buehne) return;
    let punkt;
    try {
      punkt = bahn.getPointAtLength(bahn.getTotalLength() / 2);
    } catch {
      return;   // Bahn (noch) ohne Laenge - kein Grund, irgendetwas zu kippen
    }
    const leinwand = document.getElementById("leinwand");
    const kasten = leinwand.getBoundingClientRect();
    const rahmen = buehne.getBoundingClientRect();
    const x = kasten.left - rahmen.left + this.sicht.x + punkt.x * this.sicht.zoom;
    const y = kasten.top - rahmen.top + this.sicht.y + punkt.y * this.sicht.zoom;
    werkzeug.style.left = `${x}px`;
    werkzeug.style.top = `${y}px`;
    /* ÜBER dem Pfeil, nicht auf ihm (siehe .pfeil-werkzeug in style.css) -
       und dicht am oberen Rand darunter. Das ist keine Kosmetik: eine
       Blase genau unter dem Zeiger verdeckt den Pfeil, den sie beschreibt.
       Der zweite Klick eines Doppelklicks landete dann auf ihr statt auf
       dem Pfeil (nachgemessen: der Doppelklick loeschte deshalb nichts
       mehr), und mit dem Finger saesse ein LOESCHKNOPF genau dort, wo
       gerade getippt wurde. */
    werkzeug.classList.toggle("pfeil-werkzeug-unten", y < 64);
  },

  async pfeilLoeschen(pfeilId) {
    const pfeil = this.pfeilNach(pfeilId);
    const beschreibung = pfeil ? this.pfeilBeschreibung(pfeil) : "";
    await pfeilLoeschenServerseitig(pfeilId);
    if (this.pfeilNach(pfeilId)) return;   // fehlgeschlagen, Meldung kam schon
    this.pfeilAbwaehlen();
    zeigeHinweis(
      `Verbindung ${beschreibung} gelöscht – „Rückgängig" holt sie zurück.`
    );
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
    this.pfeilAbwaehlen();   // immer nur eines von beiden ausgewaehlt
    this.auswahl = karte.id;
    panelZeigen(karte);
    this.entferneAuswahlKlasse();
    gruppe.classList.add("gewaehlt");
    // Auf schmalem Hochformat mit Finger (siehe seitenbereichSchmal() weiter
    // unten) ist das Parameterfenster sonst ein eigener, unsichtbarer
    // Seitenbereich (siehe style.css) - eine Karte auszuwaehlen soll es
    // automatisch aufklappen, genau wie am Schreibtisch, wo es ohnehin
    // immer offen ist. Bewusst NICHT mehr synchron innerhalb des
    // pointerdown-Handlers (siehe karteGreifen()): eine Klassenaenderung,
    // die eine CSS-Uebergangsflaeche mitten in derselben Beruehrung
    // verschiebt/einblendet, ist ein plausibler Ausloeser fuer ein
    // touchcancel auf iOS (siehe Bericht, dieselbe Wechselwirkung mit der
    // Gestenerkennung wie beim Zoomen) - requestAnimationFrame schiebt sie
    // einen Bildwechsel weiter, ohne dass es sichtbar verzoegert wirkt.
    if (this.seitenbereichSchmal()) {
      requestAnimationFrame(() => this.seitenbereichOeffnen("panel"));
    }
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

    // setPointerCapture: derselbe Grund wie bei der Leinwand selbst (siehe
    // dortiger Kommentar in bindeLeinwand()) - dieser Zeiger bleibt bei
    // dieser Karte gemeldet, auch wenn er sich schnell ueber ihren
    // Bildschirmbereich hinaus bewegt. try/catch: kann bei einem vom
    // Browser nicht mehr gefuehrten Zeiger legitim fehlschlagen, das darf
    // das Ziehen selbst nicht abbrechen.
    try {
      gruppe.setPointerCapture(ereignis.pointerId);
    } catch {
      /* Zeiger nicht (mehr) aktiv - kein Abbruch, siehe Kommentar oben. */
    }

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
    // loslassen() bedient sowohl pointerup (normal losgelassen) als auch
    // pointercancel (vom Browser abgebrochen, z.B. weil iOS die Beruehrung
    // gerade doch als Teil einer Systemgeste einstuft - siehe Bericht) -
    // BEIDE speichern die aktuelle Position, statt bei einem Abbruch in
    // einem halben Zustand (Lauscher haengen weiter, Position weder
    // gespeichert noch zurueckgesetzt) stehen zu bleiben. Ein Parameter
    // unterscheidet nur fuer die Aufraeum-Reihenfolge, nicht das Ergebnis:
    // die Karte bleibt dort stehen, wo sie beim Abbruch gerade war - das
    // ist die tatsaechliche, konsistente Position, kein Zwischenstand.
    const loslassen = async () => {
      window.removeEventListener("pointermove", bewegen);
      window.removeEventListener("pointerup", loslassen);
      window.removeEventListener("pointercancel", loslassen);
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
    window.addEventListener("pointercancel", loslassen);
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

  /* Nur die (billige) Transform-Eigenschaft von #welt setzen - kein
     Minikarte-Neuaufbau, keine Beschriftungspruefung. Von
     aktualisiereSicht() UND von _sichtAktualisierenGebuendelt() genutzt
     (siehe dort), damit beide exakt dieselbe eine Zeile schreiben. */
  _setzeWeltTransform() {
    document
      .getElementById("welt")
      .setAttribute(
        "transform",
        `translate(${this.sicht.x} ${this.sicht.y}) scale(${this.sicht.zoom})`
      );
    // Der Loeschknopf eines ausgewaehlten Pfeils haengt in
    // Bildschirmkoordinaten und muss jeder Verschiebung und jeder Zoomstufe
    // folgen - hier, weil das die eine Zeile ist, die JEDE Sichtaenderung
    // schreibt (siehe Kommentar oben).
    this.pfeilWerkzeugPositionieren();
  },

  aktualisiereSicht() {
    this._setzeWeltTransform();
    this.aktualisiereMinikarte();
    this.aktualisiereBeschriftungen();
  },

  /* Wie aktualisiereSicht(), aber fuer die haeufigen Zwischenschritte einer
     LAUFENDEN Geste (Kneifzoom, WebKit-Gestenpfad, Ein-Finger-Schieben,
     Mausrad-Serie) gedacht: die Transform selbst wird sofort gesetzt (das
     braucht es fuer die sichtbare Rueckmeldung), aber Minikarte-Neuaufbau
     und Beschriftungspruefung - beides nicht billig, siehe dort - werden
     auf den naechsten Bildwechsel gebuendelt statt bei JEDEM einzelnen
     Ereignis sofort zu laufen. Ohne dieses Buendeln feuert z.B. ein
     gesturechange auf iOS oft mehrfach pro Bildwechsel, und jeder einzelne
     Aufruf baute bisher die komplette Minikarte neu auf, noch bevor der
     Bildschirm ueberhaupt einmal fertig gezeichnet hatte - genau das erzeugt
     die kurz aufblitzenden weissen/unfertigen Kacheln bei bestimmten
     Zoomstufen (siehe Bericht). requestAnimationFrame statt z.B.
     setTimeout: laeuft garantiert vor dem naechsten Bildaufbau, nicht
     irgendwann danach. */
  _sichtRahmenAngefordert: false,
  _sichtAktualisierenGebuendelt() {
    this._setzeWeltTransform();
    if (this._sichtRahmenAngefordert) return;
    this._sichtRahmenAngefordert = true;
    requestAnimationFrame(() => {
      this._sichtRahmenAngefordert = false;
      this.aktualisiereMinikarte();
      this.aktualisiereBeschriftungen();
    });
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

  /* Die Zoomstufe, bei der die ganze Anlage samt Rand in die Leinwand passt.
     Getrennt von einpassen(), weil startAnsicht() dieselbe Zahl braucht, um
     zu entscheiden, ob eine Einpassung ueberhaupt sinnvoll ist - nicht um
     einzupassen. Nicht ueber 1 hinaus vergroessern: bei wenigen Karten soll
     "Einpassen" sie in Originalgroesse zentrieren, nicht auf Plakatgroesse
     aufblasen. */
  einpassZoom(huelle, kasten) {
    const POLSTER = 70;
    const inhaltBreite = huelle.maxX - huelle.minX + POLSTER * 2;
    const inhaltHoehe = huelle.maxY - huelle.minY + POLSTER * 2;
    return Math.min(kasten.width / inhaltBreite, kasten.height / inhaltHoehe, 1);
  },

  /* Passt Zoomstufe und Bildausschnitt so an, dass alle Karten sichtbar sind
     - die ausdrueckliche Uebersicht ueber den Knopf "Einpassen" (siehe
     bindeEreignisse() weiter unten). Bei vielen Karten faellt der Zoom dabei
     so weit, dass Namen klein und teils nur noch als Farbkante erkennbar
     sind (siehe DETAIL_ZOOM_SCHWELLE) - das ist hier in Ordnung: eine
     Uebersicht sucht man in, statt in ihr zu lesen. Beim OEFFNEN einer
     Anlage waehlt startAnsicht() (weiter unten, gerufen von laden() oben)
     zwischen dieser Ansicht und einem Ausschnitt: eine grosse Vorlage
     bekommt sie nicht mehr - bei 36 Karten war die
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
    const zoom = this.einpassZoom(huelle, kasten);
    this.sicht.zoom = zoom;
    const mitteX = (huelle.minX + huelle.maxX) / 2;
    const mitteY = (huelle.minY + huelle.maxY) / 2;
    this.sicht.x = kasten.width / 2 - mitteX * zoom;
    this.sicht.y = kasten.height / 2 - mitteY * zoom;
    this.aktualisiereSicht();
  },

  /* Ansicht, in der der Editor eine Anlage oeffnet (siehe laden() oben).
     Eine Regel, zwei Ausgaenge: passt alles in lesbarer Groesse hinein, wird
     eingepasst; sonst START_ZOOM, verankert an der Karte, an der der
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
    // Passt die ganze Anlage ohne Verkleinern unter die Lesbarkeitsschwelle
    // hinein, ist die Uebersicht der bessere Einstieg als ein Ausschnitt:
    // kleine Anlagen - etwa die Beispielanlagen einer einzelnen Karte
    // (core/lehrinhalte/) mit einer Handvoll Karten - wuerden sonst rechts
    // abgeschnitten geoeffnet, obwohl alles bequem Platz haette. Erst wenn
    // die Einpassung unter EINSTIEG_ZOOM_MIN fiele (bei 36 Karten war an ihr
    // nichts mehr zu lesen), greift die Verankerung darunter.
    const huelle = this.kartenHuelle();
    if (huelle && this.einpassZoom(huelle, kasten) >= this.EINSTIEG_ZOOM_MIN) {
      this.einpassen();
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
      svg.textContent = "";
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

    // Kein frueher Ausstieg mehr, wenn alles sichtbar ist (siehe Bericht):
    // der Inhalt wird IMMER zuerst neu gezeichnet, ausgeblendet wird erst
    // danach - eine ausgeblendete Minikarte darf trotzdem nie einen
    // veralteten Rahmen im Baum stehen lassen haben, falls sie aus
    // irgendeinem Grund doch (kurz) sichtbar wird. Zurueckhaltend bleibt sie
    // trotzdem: sobald wirklich alles zu sehen ist, gibt es nichts, wohin
    // ein Klick noch fuehren koennte, das Ausblenden selbst ist also nach
    // wie vor gerechtfertigt (siehe Kommentar oben) - nur der Inhalt muss
    // stimmen, bevor darueber entschieden wird.
    //
    // Massstab aus dem GEMEINSAMEN Bereich von Kartenhuelle UND Sichtfeld,
    // nicht nur der Kartenhuelle allein (siehe Bericht): ist man weiter
    // herausgezoomt als die ganze Anlage, waere der Rahmen sonst rechnerisch
    // groesser als die Flaeche, in die er gezeichnet wird, und liefe ueber
    // den Rand der Minikarte hinaus. Bei einer eingezoomten Ansicht (Anlage
    // groesser als das Sichtfeld) aendert das nichts - dann bestimmt weiter
    // allein die Kartenhuelle den Massstab, wie bisher.
    const minX = Math.min(huelle.minX, sichtX0);
    const minY = Math.min(huelle.minY, sichtY0);
    const maxX = Math.max(huelle.maxX, sichtX1);
    const maxY = Math.max(huelle.maxY, sichtY1);

    const MMB = 168, MMH = 108, POLSTER = 4;
    const inhaltBreite = Math.max(maxX - minX, 1);
    const inhaltHoehe = Math.max(maxY - minY, 1);
    const skala = Math.min((MMB - 2 * POLSTER) / inhaltBreite, (MMH - 2 * POLSTER) / inhaltHoehe);
    this._minikarteSkala = skala;
    const ox = POLSTER - minX * skala;
    const oy = POLSTER - minY * skala;
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

    huelle2.hidden = komplettSichtbar;
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

  /* Rechnet ein einzelnes wheel-Ereignis in einen Zoomfaktor um - eigene,
     reine Funktion (kein Seiteneffekt, direkt pruefbar) statt Inline-
     Rechnung im Lauscher. Normiert deltaY zunaechst auf Pixel (deltaMode),
     begrenzt den Betrag auf WHEEL_PX_MAX und leitet den Faktor STETIG aus
     dem Betrag ab (Exponentialfunktion): dieselbe insgesamt gedrehte Menge
     ergibt denselben Faktor, egal ob sie als ein grosses oder viele kleine
     Ereignisse ankommt - Summen im Exponenten werden zu Produkten der
     Faktoren (exp(a)*exp(b) = exp(a+b)), solange kein einzelnes Ereignis
     die Begrenzung erreicht. seitenHoehe ist die Bezugsgroesse fuer
     deltaMode 2 (Seiten, selten) - vom Aufrufer uebergeben statt hier
     window.innerHeight zu lesen, damit die Funktion ohne DOM testbar ist. */
  _wheelFaktor(deltaY, deltaMode, seitenHoehe) {
    let px = deltaY;
    if (deltaMode === 1) px *= this.WHEEL_LINE_PX;
    else if (deltaMode === 2) px *= seitenHoehe || 800;
    px = Math.max(-this.WHEEL_PX_MAX, Math.min(this.WHEEL_PX_MAX, px));
    const k = Math.log(1.1) / this.WHEEL_PX_PRO_FAKTOR_1_1;
    return Math.exp(-px * k);
  },

  /* Setzt sicht.zoom auf zoomZiel (auf ZOOM_MIN/MAX begrenzt) und
     verschiebt sicht.x/y so, dass der Weltpunkt (weltX, weltY) unter dem
     Bildschirmpunkt (punktX, punktY relativ zur Leinwandecke) stehen
     bleibt - das eigentliche "Zoom um einen Punkt". Gemeinsam von
     _kneifBewegen() (zeigerbasierter Pfad), dem WebKit-Gestenpfad (siehe
     bindeLeinwand(), gesturechange) UND dem Mausrad (siehe dort) genutzt,
     damit alle drei exakt dasselbe Verhalten zeigen: der Weltpunkt unter
     dem Zeiger/Finger bleibt an derselben Bildschirmstelle stehen, statt
     dass sich die Anlage zur Ecke (0,0) hin zusammenzieht (Task-
     Rueckmeldung - das Mausrad setzte sicht.zoom bis eben ohne Bezugspunkt,
     ein Rest aus der Zeit vor der Gestenarbeit). "Einpassen" (siehe dort)
     ist die zulaessige Ausnahme: es bestimmt Ausschnitt UND Zoom ohnehin
     gemeinsam neu, ein Bezugspunkt waere dort bedeutungslos. */
  _zoomeUmPunkt(zoomZiel, punktX, punktY, weltX, weltY) {
    const zoom = Math.min(this.ZOOM_MAX, Math.max(this.ZOOM_MIN, zoomZiel));
    this.sicht.zoom = zoom;
    this.sicht.x = punktX - weltX * zoom;
    this.sicht.y = punktY - weltY * zoom;
    // Gebuendelt (siehe _sichtAktualisierenGebuendelt()): beide Aufrufer
    // (Kneifzoom, WebKit-Gestenpfad) feuern waehrend einer laufenden Geste
    // oft mehrfach pro Bildwechsel.
    this._sichtAktualisierenGebuendelt();
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
    // Eine WebKit-Kneifgeste laeuft gerade (siehe bindeLeinwand(),
    // gesturestart) - deren preventDefault() bricht die Beruehrungsfolge in
    // Safari ohnehin meist ab (touchcancel raeumt _zeiger via
    // _zeigerEntfernen() auf), dieser fruehe Ausstieg ist die zusaetzliche,
    // ausdrueckliche Absicherung gegen die kurze Ueberlappung beider Pfade
    // (siehe Bericht und Kommentar bei _gestenAnker weiter oben).
    if (this._gestenAnker) return;
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
    const zoom = this._kneifAnker.zoom * (distanz / this._kneifAnker.distanz);
    this._zoomeUmPunkt(
      zoom, mitteX - kasten.left, mitteY - kasten.top,
      this._kneifAnker.weltX, this._kneifAnker.weltY
    );
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

      /* Ein Tipp oder Klick auf einen Pfeil waehlt ihn aus - und die
         Leinwand haelt sich dabei vollstaendig heraus: kein
         setPointerCapture, kein Schieben. Genau diese Erfassung war der
         Grund, warum der Doppelklick auf einen Pfeil nie bei pfeile.js
         ankam (ein erfasster Zeiger lenkt auch click/dblclick auf das
         erfassende Element um) - mit diesem frueheren Ausstieg ist auch die
         Abkuerzung wieder heil. Dass sich die Leinwand nicht mehr von einem
         Pfeil aus schieben laesst, faellt nicht ins Gewicht: ein Pfeil ist
         ein paar Pixel breit, daneben ist ueberall freie Flaeche. */
      const pfeilElement = e.target.closest(".pfeil");
      if (pfeilElement && pfeilElement.dataset.id) {
        this.auswahl = null;
        panelLeeren();
        this.entferneAuswahlKlasse();
        this.pfeilAuswaehlen(Number(pfeilElement.dataset.id));
        return;
      }
      this.pfeilAbwaehlen();

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
        // Gebuendelt (siehe _sichtAktualisierenGebuendelt()): pointermove
        // waehrend eines Ein-Finger-Zugs feuert oft mehrfach pro
        // Bildwechsel, die Minikarte muss nicht bei jedem einzelnen davon
        // komplett neu aufgebaut werden.
        this._sichtAktualisierenGebuendelt();
      }
    });

    leinwand.addEventListener("pointerup", (e) => this._zeigerEntfernen(e));
    leinwand.addEventListener("pointercancel", (e) => this._zeigerEntfernen(e));

    /* WebKit-eigene Kneifgeste AUF DER LEINWAND: siehe Bericht - ein
       preventDefault() auf gesturestart/-change bricht in Safari in aller
       Regel die zugehoerige Beruehrungsfolge ab (touchcancel), noch bevor
       der zeigerbasierte Pfad oben (_kneifBewegen()) ueberhaupt zum Zug
       kaeme. Deshalb hier dieselbe Geste UEBER gesturechange bedienen -
       event.scale (Faktor gegenueber dem Beginn der Geste) und
       event.clientX/clientY (Mittelpunkt) sind genau das, was
       _zoomeUmPunkt() braucht. stopPropagation() verhindert, dass
       document's allgemeine Sperre (siehe nurBeiBeruehrungVerhindern()
       weiter unten in dieser Datei) dieselbe Geste zusaetzlich behandelt -
       preventDefault() steht trotzdem auch hier, die Seite soll sich so
       oder so nicht mitvergroessern. Nur in WebKit/Safari ueberhaupt
       vorhanden: in Chromium/Firefox bindet addEventListener() hier
       folgenlos nichts an Vorhandenes, der zeigerbasierte Pfad oben bleibt
       dort unveraendert der einzige Weg (Chrome auf Android, Chromium mit
       Touchscreen am Schreibtisch). */
    leinwand.addEventListener("gesturestart", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const kasten = leinwand.getBoundingClientRect();
      this._gestenAnker = {
        zoom: this.sicht.zoom,
        weltX: (e.clientX - kasten.left - this.sicht.x) / this.sicht.zoom,
        weltY: (e.clientY - kasten.top - this.sicht.y) / this.sicht.zoom,
      };
    }, { passive: false });
    leinwand.addEventListener("gesturechange", (e) => {
      e.preventDefault();
      e.stopPropagation();
      // gestureend/-cancel verpasst o.ae. - sicherheitshalber statt eines
      // Absturzes auf einen fehlenden Anker.
      if (!this._gestenAnker) return;
      const kasten = leinwand.getBoundingClientRect();
      const zoom = this._gestenAnker.zoom * e.scale;
      this._zoomeUmPunkt(
        zoom, e.clientX - kasten.left, e.clientY - kasten.top,
        this._gestenAnker.weltX, this._gestenAnker.weltY
      );
    }, { passive: false });
    leinwand.addEventListener("gestureend", (e) => {
      e.preventDefault();
      e.stopPropagation();
      this._gestenAnker = null;
      // Der zeigerbasierte Zustand ist durch das touchcancel meist schon
      // geleert (siehe _zeigerEntfernen()) - ausdruecklich nachgezogen,
      // falls ein Browser hier von der ueblichen Reihenfolge abweicht,
      // damit kein Geisterzeiger einer abgebrochenen Geste die naechste
      // beeinflusst.
      this._kneifAnker = null;
      this._panAnker = null;
      this._zeiger.clear();
      // --app-hoehe wurde waehrend der Geste nicht nachgefuehrt (siehe
      // aktualisiereAppHoehe() weiter unten in dieser Datei - eine mit
      // "function" deklarierte, gehoistete Funktion, hier also schon
      // aufrufbar) - jetzt, wo Editor._gestenAnker wieder leer ist, den
      // tatsaechlich aktuellen Wert nachtragen, damit kein zu kleiner
      // Stand von einer Schwankung waehrend der Geste stehen bleibt.
      aktualisiereAppHoehe();
    }, { passive: false });

    leinwand.addEventListener("wheel", (e) => {
      // Strg+Mausrad gehoert dem Browser (Seitenzoom am Schreibtisch, eine
      // Zugaenglichkeitsfunktion) - kein preventDefault(), keine eigene
      // Reaktion, das Ereignis laeuft ungehindert weiter.
      if (e.ctrlKey) return;
      e.preventDefault();
      // Faktor aus der tatsaechlich gedrehten Menge, nicht nur dem
      // Vorzeichen von deltaY (siehe _wheelFaktor() und die Konstanten
      // WHEEL_* weiter oben - dort steht auch, warum das noetig war).
      const faktor = this._wheelFaktor(e.deltaY, e.deltaMode, leinwand.clientHeight);
      // Untere Schranke bewusst unter der ueblichen Einpassen-Zoomstufe
      // (siehe einpassen()) - sonst liesse sich bei einer besonders grossen
      // Anlage nicht so weit herauszoomen, wie "Einpassen" selbst braucht.
      const zielZoom = Math.min(this.ZOOM_MAX, Math.max(this.ZOOM_MIN, this.sicht.zoom * faktor));
      // Um den Mauszeiger herum zoomen statt zur Ecke (0,0) hin (siehe
      // _zoomeUmPunkt() oben, dort auch die Begruendung) - derselbe Weg wie
      // Kneifgeste und WebKit-Gestenpfad, hier mit dem Zeigerpunkt statt
      // einer Fingermitte. _zoomeUmPunkt() ruft _sichtAktualisierenGebuendelt()
      // selbst auf (bei einer schnellen Mausrad-/Trackpad-Serie oft mehrfach
      // pro Bildwechsel - siehe dort).
      const kasten = leinwand.getBoundingClientRect();
      const punktX = e.clientX - kasten.left;
      const punktY = e.clientY - kasten.top;
      const weltX = (punktX - this.sicht.x) / this.sicht.zoom;
      const weltY = (punktY - this.sicht.y) / this.sicht.zoom;
      this._zoomeUmPunkt(zielZoom, punktX, punktY, weltX, weltY);
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
      if (e.key === "Escape" && this.pfeilAuswahl !== null) {
        if (istTexteingabe(document.activeElement)) return;
        this.pfeilAbwaehlen();
        return;
      }
      if (e.key !== "Delete") return;
      if (istTexteingabe(document.activeElement)) return;
      if (document.querySelector(".dialog-huelle")) return;
      // Ein ausgewaehlter Pfeil geht ohne Rueckfrage - anders als eine
      // Karte, die Pfeile mitreisst: hier faellt genau das weg, was
      // markiert vor einem liegt, und der Verlauf holt es mit einem Druck
      // zurueck ("Pfeil von 'A' nach 'B' getrennt", siehe core/verlauf.py).
      if (this.pfeilAuswahl !== null) {
        await this.pfeilLoeschen(this.pfeilAuswahl);
        return;
      }
      if (this.auswahl === null) return;
      await this.karteLoeschenDialog(this.auswahl);
    });

    /* Strg+Z / Strg+Umschalt+Z, auf dem Mac ⌘Z - und Strg+Y, wie es unter
       Windows fuer "Wiederholen" ueblich ist. Dieselbe Vorsicht wie beim
       Entf-Lauscher darueber und aus demselben Anlass: steht der Fokus in
       einem Eingabefeld, gehoert das Zuruecknehmen DEM FELD, nicht der
       Anlage - istTexteingabe() entscheidet das an genau einer Stelle fuer
       beide Tasten. Auch waehrend eines offenen Dialogs bleibt die Taste
       stumm. preventDefault() erst NACH diesen Pruefungen, damit der
       Browser sein eigenes Rueckgaengig im Feld unangetastet behaelt. */
    window.addEventListener("keydown", (e) => {
      const taste = (e.key || "").toLowerCase();
      const zurueck = taste === "z" && (e.ctrlKey || e.metaKey) && !e.altKey;
      const vor =
        (taste === "y" && e.ctrlKey && !e.altKey) ||
        (zurueck && e.shiftKey);
      if (!zurueck && !vor) return;
      if (istTexteingabe(document.activeElement)) return;
      if (document.querySelector(".dialog-huelle")) return;
      e.preventDefault();
      this.verlaufSchritt(vor ? "vor" : "zurueck");
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
   style.css, var(--app-hoehe, 100dvh)).

   Zwei Nachbesserungen (siehe Bericht: "Sichtfeld wird beim Zoomen manchmal
   kleiner, rechts erscheint grau"): Safari meldet ueber "resize" auch
   waehrend einer laufenden Kneifgeste laufend leicht schwankende
   VisualViewport-Werte - fuer die Gestenerkennung selbst laeuft ja weiter,
   auch wenn preventDefault() am Ende die eigentliche Seiten-Vergroesserung
   unterbindet (siehe gesturestart/-change/-end weiter oben). Ohne Schutz
   schrumpfte .app (und damit die ganze Arbeitsflaeche) mitten in der Geste
   mit einer solchen Schwankung, und wo sie nicht mehr hinreichte, kam der
   Seitenhintergrund (--bg, ein helles Grau) zum Vorschein - "manchmal",
   je nachdem, ob am Ende noch ein "resize" mit dem richtigen, vollen Wert
   nachkam. --app-hoehe hat GENAU EINEN Zweck (die Bildschirmtastatur),
   nicht jede Schwankung: 1) ignoriert waehrend Editor._gestenAnker gesetzt
   ist (eine WebKit-Kneifgeste laeuft) komplett, mit einem erneuten Aufruf
   am Ende der Geste (siehe gestureend weiter oben), damit kein zu kleiner
   Wert stehen bleibt. 2) weicht nur bei einer DEUTLICH kleineren
   VisualViewport von 100dvh ab (SCHWELLE_TASTATUR_PX) - eine Tastatur
   nimmt immer einen grossen Teil des Bildschirms ein, eine kleine
   Schwankung waehrend einer Geste nicht annaehernd so viel; darunter wird
   die Eigenschaft entfernt, .app faellt auf 100dvh zurueck. */
const SCHWELLE_TASTATUR_PX = 100;
function aktualisiereAppHoehe() {
  if (!window.visualViewport) return;
  // Waehrend einer laufenden WebKit-Kneifgeste gar nicht nachfuehren (siehe
  // Kommentar oben) - der Aufruf am Ende der Geste (gestureend) holt den
  // dann aktuellen, echten Wert nach.
  if (Editor._gestenAnker) return;
  const luecke = window.innerHeight - window.visualViewport.height;
  if (luecke > SCHWELLE_TASTATUR_PX) {
    document.documentElement.style.setProperty(
      "--app-hoehe", `${window.visualViewport.height}px`
    );
  } else {
    document.documentElement.style.removeProperty("--app-hoehe");
  }
}
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", aktualisiereAppHoehe);
  aktualisiereAppHoehe();
}

/* Verhindert, dass sich die GANZE SEITE mit einer Kneifgeste aufziehen laesst
   (siehe Bericht: das ist der Weg, der nach der Wisch-Sperre oben als
   einziger uebrig blieb - Safari verschiebt eine gezoomte Seite ueber den
   visuellen Ausschnitt, den weder overflow:hidden noch touch-action
   erreichen). gesturestart/-change/-end sind WebKit-eigene, nicht
   standardisierte Ereignisse (Chromium/Firefox kennen den Typ nicht - die
   addEventListener()-Aufrufe unten binden dort folgenlos nichts an
   Vorhandenes, kein Fehler). Sie sind der von Apple selbst dokumentierte,
   verlaessliche Weg, das Aufziehen zu unterbinden, auch dort, wo
   touch-action aus bekannten WebKit-Eigenheiten nicht zuverlaessig
   durchkommt (siehe die Kommentare bei .palette/.legende-inhalt/... in
   style.css - die schliessen die Luecken zusaetzlich, nicht ersatzweise).

   NUR bei Beruehrung, NIE am Schreibtisch: matchMedia() wird bei jedem
   Ereignis frisch geprueft, nicht einmalig gespeichert - ein externer
   Bildschirm/Eingabewechsel waehrend der Sitzung soll sich sofort
   auswirken. Ohne diese Bedingung traefe preventDefault() auch die
   Kneifgeste auf dem Trackpad im Desktop-Safari, die als
   Zugaenglichkeitsfunktion (groessere Schrift fuer schwache Augen)
   unangetastet bleiben MUSS - deshalb hier ausdruecklich NICHT einfach
   "jedes gesturestart verhindern". */
function nurBeiBeruehrungVerhindern(ereignis) {
  if (!window.matchMedia("(pointer: coarse)").matches) return;
  ereignis.preventDefault();
}
document.addEventListener("gesturestart", nurBeiBeruehrungVerhindern, { passive: false });
document.addEventListener("gesturechange", nurBeiBeruehrungVerhindern, { passive: false });
document.addEventListener("gestureend", nurBeiBeruehrungVerhindern, { passive: false });

/* Doppeltippen zoomt in Safari ebenfalls (unabhaengig von der Kneifgeste) -
   derselbe zweite Weg wie oben, nur ueber zwei schnell aufeinanderfolgende
   Beruehrungen statt zwei gleichzeitiger. touch-action:none/pan-y (siehe
   style.css) unterdrueckt das in WebKit zwar meist schon mit, aber nicht
   nachweislich ueberall - dieselbe Vorsicht wie beim Ueberscrollen selbst
   (siehe Bericht: "verlass dich nicht auf einen einzelnen Mechanismus").
   Verhindert nur den ZWEITEN touchend innerhalb von 300ms an (ungefaehr)
   derselben Stelle - ein echter Doppeltipp auf eine Karte (zum Auswaehlen)
   bleibt unversehrt: preventDefault() auf touchend unterbindet die
   Standardaktion des Ereignisses (das native Zoomen), nicht die
   Maus-Ersatzereignisse (click/dblclick), ueber die z.B. das Loeschen
   eines Pfeils per Doppeltipp liefe (siehe pfeile.js, dblclick). */
let _letzteBeruehrungEnde = { zeit: 0, x: 0, y: 0 };
document.addEventListener("touchend", (e) => {
  if (!window.matchMedia("(pointer: coarse)").matches) return;
  const beruehrung = e.changedTouches && e.changedTouches[0];
  if (!beruehrung) return;
  const jetzt = Date.now();
  const { zeit, x, y } = _letzteBeruehrungEnde;
  const nah = Math.hypot(beruehrung.clientX - x, beruehrung.clientY - y) < 40;
  if (jetzt - zeit <= 300 && nah) {
    e.preventDefault();
  }
  _letzteBeruehrungEnde = { zeit: jetzt, x: beruehrung.clientX, y: beruehrung.clientY };
}, { passive: false });

/* Warum ein Mantel um fetch() statt eines Aufrufs an jeder Aenderungsstelle?

   Aendernde Anfragen gehen nicht nur von editor.js aus: das
   Parameterfenster (panel.js) speichert Felder und loest Verbindungen,
   pfeile.js legt Pfeile an und loescht sie. Nach jeder solchen Anfrage muss
   der Verlaufsstand neu gelesen werden, sonst bleiben die beiden Knoepfe
   auf einem ueberholten Stand ("nichts zurueckzunehmen", obwohl gerade
   etwas geschah). Denselben Aufruf in jede dieser Dateien einzeln zu
   streuen hiesse, ihn beim naechsten neuen Endpunkt zu vergessen - genau
   der Grund, aus dem das Festhalten der Zustaende in core/anlagen.py sitzt
   und nicht in den Routen (siehe core/verlauf.py). Ein Ort, der jede
   aendernde Anfrage sieht, ist hier der richtige Zuschnitt.

   Angefasst wird nichts: der Mantel reicht Argumente und Antwort
   unveraendert durch und wertet nur aus, WAS gefragt wurde. Nur erfolgreiche
   (response.ok), nicht-lesende Anfragen an /api/ zaehlen; die
   Verlaufsendpunkte selbst sind ausgenommen, sonst antwortete jeder
   Schritt mit einer weiteren Abfrage auf sich selbst. Fehler in dieser
   Auswertung duerfen die eigentliche Anfrage niemals kippen - deshalb das
   try/catch um die Auswertung, nicht um den Aufruf. */
const _fetchOhneVerlauf = window.fetch.bind(window);
window.fetch = async (...argumente) => {
  const antwort = await _fetchOhneVerlauf(...argumente);
  try {
    const [anfrage, optionen] = argumente;
    const ziel = String(
      typeof anfrage === "string" ? anfrage : (anfrage && anfrage.url) || ""
    );
    const methode = String(
      (optionen && optionen.method) || (anfrage && anfrage.method) || "GET"
    ).toUpperCase();
    if (
      antwort.ok
      && methode !== "GET"
      && ziel.includes("/api/")
      && !ziel.includes("/verlauf")
      && Editor.anlage
    ) {
      Editor.verlaufBaldAktualisieren();
    }
  } catch {
    /* Die Auswertung darf die Anfrage nicht kippen - siehe Kommentar oben. */
  }
  return antwort;
};

window.addEventListener("DOMContentLoaded", async () => {
  Editor.bindeLeinwand();
  panelLeeren();
  await Palette.laden();
  await Editor.laden(window.ANLAGE_ID);
  pfeileBinden(Editor);
  Editor.berichtLinkAktualisieren();

  Editor.verlaufAktualisieren();
  Editor.meldewegeSetzen(Editor.meldewegeGemerkt());

  const schalterMeldewege = document.getElementById("schalter-meldewege");
  if (schalterMeldewege) {
    schalterMeldewege.addEventListener("change", (e) =>
      Editor.meldewegeSetzen(e.target.checked)
    );
  }

  const btnPfeilLoeschen = document.getElementById("btn-pfeil-loeschen");
  if (btnPfeilLoeschen) {
    btnPfeilLoeschen.addEventListener("click", () => {
      if (Editor.pfeilAuswahl !== null) Editor.pfeilLoeschen(Editor.pfeilAuswahl);
    });
  }

  const btnZurueck = document.getElementById("btn-zurueck");
  if (btnZurueck) {
    btnZurueck.addEventListener("click", () => Editor.verlaufSchritt("zurueck"));
  }
  const btnVor = document.getElementById("btn-vor");
  if (btnVor) {
    btnVor.addEventListener("click", () => Editor.verlaufSchritt("vor"));
  }

  const btnUmbenennen = document.getElementById("btn-anlage-umbenennen");
  if (btnUmbenennen) {
    btnUmbenennen.addEventListener("click", () => Editor.anlageUmbenennen());
  }
});
