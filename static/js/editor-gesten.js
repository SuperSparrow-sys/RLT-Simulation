/* Kneifen und Ziehen mit zwei Fingern. Steht fuer sich, weil es die
   einzige Stelle ist, die mehrere Zeiger gleichzeitig verfolgt.

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
});
