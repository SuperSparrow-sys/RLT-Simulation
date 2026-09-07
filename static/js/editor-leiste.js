/* Die Kopfleiste des Schreibtischs bei schmalem Fenster.

   Auf dem iPad im Hochformat standen "Bericht" und "Vergleich" über dem
   Knopf "Parameter", dessen Wort auf "Pa" abgeschnitten war, und
   "Simulieren" ragte aus dem Bild. Die Leiste hatte einen Schrumpfplan -
   erst fallen die Wörter weg, dann die Trennstriche -, aber unter 900 Punkten
   kamen die Umschalter für Palette und Parameter noch DAZU. Ab da schrumpften
   die Knöpfe unter ihre eigene Schrift.

   Vier Stufen, und in jeder gibt zuerst das Beiwerk nach:

     voll        alles mit Wort, Trennstriche zwischen den Gruppen
     zeichen     die linken Knöpfe legen ihr Wort ab (editor.css)
     gesammelt   Verlauf, Einpassen und Verbindungen ins Ausweichmenü
     knapp       auch Bericht und Vergleich ins Ausweichmenü

   Die Stufe wird GEMESSEN, nicht an Zahlen geraten: Die Leiste bekommt
   probeweise die höchste Stufe, und solange ihr Inhalt breiter ist als sie
   selbst, geht sie eine Stufe tiefer. Zwei Anläufe sind vorher an geratenen
   Schwellen gescheitert. Erst maß die Regel das Fenster, während die Leiste
   nur so breit ist wie die Bühne - bei 820 Punkten Fensterbreite nahmen
   Palette und Parameterfenster 460 davon. Dann stimmten die Schwellen nicht
   mehr, sobald die Umschalter für Palette und Parameter dazukamen, die es
   nur auf schmalen Geräten gibt. Gemessen stimmt es in jedem Fall, auch in
   künftigen, an die hier niemand gedacht hat.

   Die Stufe steht als data-stufe auf der Leiste; editor.css hängt daran,
   statt eigene Medienabfragen zu führen - zwei Wege zu derselben
   Entscheidung wären zwei Wege, die auseinanderlaufen.

   Immer sichtbar bleiben: Zurück, der Anlagenname (das einzige Glied, das
   mitschrumpft, mit "…" am Ende) und Simulieren.

   Verschoben werden DIESELBEN Elemente, nicht Kopien: Ein Knopf, den es
   zweimal gäbe - einmal in der Leiste, einmal im Menü -, müsste zweimal
   verdrahtet, zweimal freigeschaltet und zweimal beschriftet werden und liefe
   irgendwann auseinander. Jedes Element merkt sich beim ersten Umzug, wo es
   herkam, und findet dorthin zurück. */

const Leiste = {
  // Ab welcher Stufe ein Element weicht - dieselben Namen wie in
  // data-weicht (templates/editor.html).
  STUFEN: ["voll", "zeichen", "gesammelt", "knapp"],

  leiste: null,
  menue: null,
  inhalt: null,
  /* {element, heimat, davor} - die Heimat ist der ursprüngliche Elternknoten,
     davor der Nachbar, vor dem das Element dort wieder einzusetzen ist. Ohne
     diesen Nachbarn landete ein zurückgeholter Knopf am Ende seiner Gruppe,
     und die Reihenfolge der Leiste änderte sich mit jeder Größenänderung. */
  wandernde: [],
  stufeJetzt: null,
  pruefeLaeuft: false,

  starte() {
    this.leiste = document.querySelector(".app .leiste");
    this.menue = document.getElementById("werkzeugmenue");
    this.inhalt = document.getElementById("werkzeugmenue-inhalt");
    if (!this.leiste || !this.menue || !this.inhalt) return;

    this.wandernde = [...this.leiste.querySelectorAll("[data-weicht]")].map(
      (element) => ({
        element,
        abStufe: element.dataset.weicht,
        heimat: element.parentElement,
        davor: element.nextElementSibling,
      })
    );

    this.pruefe();
    /* ResizeObserver statt window.resize: Die Leiste wird auch schmaler,
       ohne dass sich das Fenster ändert - etwa wenn das Parameterfenster
       aufgeht. Ein Rückfall auf resize, falls der Browser den Beobachter
       nicht kennt. */
    if (window.ResizeObserver) {
      new ResizeObserver(() => this.pruefe()).observe(this.leiste);
    } else {
      window.addEventListener("resize", () => this.pruefe());
    }
  },


  /* Weicht dieses Element auf der aktuellen Stufe schon? "gesammelt" weicht
     auch bei "knapp" - die Stufen sind eine Reihenfolge, keine Menge. */
  weicht(abStufe, stufe) {
    return this.STUFEN.indexOf(stufe) >= this.STUFEN.indexOf(abStufe);
  },

  /* Von oben nach unten: die höchste Stufe anlegen, nachmessen, und solange
     eine tiefere nehmen, wie der Inhalt breiter ist als die Leiste. Immer von
     "voll" aus, damit ein wieder breiter gewordenes Fenster auch wieder
     hinaufkommt. */
  pruefe() {
    if (this.pruefeLaeuft) return;   // ResizeObserver meldet das eigene Umbauen
    this.pruefeLaeuft = true;
    try {
      let gewaehlt = "knapp";
      for (const stufe of this.STUFEN) {
        this.stufeAnwenden(stufe);
        gewaehlt = stufe;
        if (this.passt()) break;
      }
      this.stufeJetzt = gewaehlt;
    } finally {
      this.pruefeLaeuft = false;
    }
  },

  /* Passt der Inhalt in die Leiste?

     Gezaehlt werden die Breiten der Gruppen plus die Luecken dazwischen -
     nicht scrollWidth: Eine Flexleiste mit overflow:hidden meldet dort in
     Firefox ihre eigene Breite, gleich wieviel darin ueberlaeuft, und die
     Stufe blieb deshalb immer auf "voll" stehen. Die Gruppen selbst
     schrumpfen nicht (flex-shrink: 0), ihre gemessene Breite ist also ihre
     wirkliche; nur der Anlagenname gibt nach, und der hat einen Boden von
     110 Punkten (editor.css) - sonst schluckte er jeden Ueberlauf. */
  passt() {
    const stil = window.getComputedStyle(this.leiste);
    const luecke = parseFloat(stil.columnGap || stil.gap) || 0;
    const innen =
      (parseFloat(stil.paddingLeft) || 0) + (parseFloat(stil.paddingRight) || 0);
    const kinder = [...this.leiste.children].filter(
      (k) => !k.hidden && k.getClientRects().length > 0
    );
    const inhalt =
      kinder.reduce((summe, k) => summe + k.offsetWidth, 0) +
      luecke * Math.max(0, kinder.length - 1);
    return inhalt + innen <= this.leiste.clientWidth + 1;
  },

  stufeAnwenden(stufe) {
    this.leiste.dataset.stufe = stufe;

    for (const eintrag of this.wandernde) {
      const gehoertInsMenue = this.weicht(eintrag.abStufe, stufe);
      const stehtImMenue = eintrag.element.parentElement === this.inhalt;
      if (gehoertInsMenue === stehtImMenue) continue;

      if (gehoertInsMenue) {
        eintrag.element.classList.add("im-menue");
        this.inhalt.appendChild(eintrag.element);
      } else {
        eintrag.element.classList.remove("im-menue");
        eintrag.heimat.insertBefore(eintrag.element, eintrag.davor);
      }
    }

    // Ein leeres Menü ist ein Knopf, hinter dem nichts steht.
    const leer = this.inhalt.children.length === 0;
    this.menue.hidden = leer;
    if (leer) this.menue.open = false;
  },
};

window.addEventListener("DOMContentLoaded", () => Leiste.starte());
