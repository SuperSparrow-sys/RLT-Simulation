/* Die Sicht auf die Anlage: verschieben, zoomen, einpassen, Minikarte.
   Nichts davon aendert die Anlage, nur den Ausschnitt, den man sieht.

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
    /* Auf einem schmalen Geraet (Tablett im Hochformat) wird immer
       eingepasst, auch wenn dabei kein Kartenname mehr zu lesen ist. Der
       verankerte Ausschnitt zeigt dort zwei Karten und einen Pfeil, der ins
       Nichts laeuft - das ist keine Arbeitsstelle, sondern Ratlosigkeit. Wer
       genauer hinsehen will, zieht auf; wer die Uebersicht braucht, hat sie
       dann wenigstens. */
    if (huelle && window.innerWidth <= this.SCHMALES_FENSTER) {
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
});
