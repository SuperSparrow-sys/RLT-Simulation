/* Pfeile im Editor: auswaehlen, beschreiben, das Loeschwerkzeug setzen.
   Zeichnen und Binden macht static/js/pfeile.js; hier steht, was der
   Editor selbst ueber den ausgewaehlten Pfeil weiss.

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
      // Die Spitze liegt auf der Bahn - eine zweite Trefferbahn dafuer waere
      // dieselbe Flaeche ein zweites Mal.
      if (bahn.classList.contains("pfeil-spitze")) continue;
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
      // Weder die Trefferbahn noch die Spitze: Gesucht ist die Mitte der
      // BAHN, und die Spitze ist nur sieben Punkte lang.
      `#pfeile path.pfeil[data-id="${this.pfeilAuswahl}"]`
        + `:not(.pfeil-treffer):not(.pfeil-spitze)`
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
});
