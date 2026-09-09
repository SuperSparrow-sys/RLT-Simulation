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
  /* {element, platzhalter} - der Platzhalter ist ein leerer Kommentarknoten,
     der an der Stelle des Elements in der Leiste stehen bleibt, solange es im
     Menü ist. Er hält den Platz.

     Zuerst hatte ich mir stattdessen den NACHBARN gemerkt, vor dem das
     Element wieder einzusetzen sei. Das ging beim ersten Einräumen gut und
     ging bei der ersten Größenänderung danach kaputt: Die Messung räumt das
     Menü probeweise leer, und wenn "Rückgängig" wieder in seine Gruppe
     zurücksoll, steht sein Nachbar "Wiederholen" noch im Menü - insertBefore
     wirft dann NotFoundError, weil der Bezugsknoten kein Kind des Ziels ist.
     Die Schleife brach mitten im Umbau ab: Die Klasse .im-menue war schon
     entfernt, verschoben war nichts. "Rückgängig" stand danach als runder
     Knopf ohne Wort im Menü, alle anderen als Zeilen. Auf dem Schreibtisch
     fiel es nicht auf, weil dort nach dem Laden nichts mehr die Größe ändert;
     auf dem iPad genügt das Ein- und Ausfahren der Safari-Leiste.

     Ein Platzhalter kann nicht auswandern und ist deshalb immer ein gültiger
     Bezugspunkt - unabhängig davon, in welcher Reihenfolge die Elemente
     zurückkommen. */
  wandernde: [],
  stufeJetzt: null,
  pruefeLaeuft: false,
  nachholen: false,

  /* Die beiden Klappen der Kopfleiste: das Ausweichmenue und die Legende
     "Verbindungen". Ein natives <details> bleibt offen, bis man seinen Knopf
     wieder antippt - wer daneben tippt, laesst es stehen und deckt damit die
     Leinwand zu. Ausserhalb tippen schliesst es jetzt, Escape ebenso. */
  KLAPPEN: ".werkzeugmenue, .legende",

  klappenSchliessen(getippt) {
    document.querySelectorAll(this.KLAPPEN).forEach((klappe) => {
      if (!klappe.open) return;
      // Alles innerhalb der Klappe gehoert zu ihr: ihr eigener Knopf (den
      // <details> selbst umschaltet) und jeder Eintrag darin - etwa der
      // Schalter "Energie- und Meldewege anzeigen" in der Legende.
      if (getippt && (klappe === getippt || klappe.contains(getippt))) return;
      klappe.open = false;
    });
  },

  klappenBinden() {
    /* In der Erfassungsphase: Die Leinwand faengt pointerdown ab (Karten
       schieben, Pfeile ziehen) und haelt es teilweise an - ein Lauscher in
       der Blasenphase kaeme dort nie an. */
    document.addEventListener(
      "pointerdown",
      (e) => {
        const ziel = e.target && e.target.closest ? e.target : null;
        this.klappenSchliessen(ziel);
      },
      true
    );
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") this.klappenSchliessen(null);
    });
  },

  starte() {
    this.klappenBinden();
    this.leiste = document.querySelector(".app .leiste");
    this.menue = document.getElementById("werkzeugmenue");
    this.inhalt = document.getElementById("werkzeugmenue-inhalt");
    if (!this.leiste || !this.menue || !this.inhalt) return;

    this.wandernde = [...this.leiste.querySelectorAll("[data-weicht]")].map(
      (element) => {
        const platzhalter = document.createComment(" Platz von " + element.id + " ");
        element.parentElement.insertBefore(platzhalter, element);
        return { element, abStufe: element.dataset.weicht, platzhalter };
      }
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
    this.menue.addEventListener("toggle", () => {
      // Was während des offenen Menüs übersprungen wurde, wird beim
      // Schließen nachgeholt.
      if (!this.menue.open && this.nachholen) {
        this.nachholen = false;
        this.pruefe();
      }
      this.menueAusrichten();
    });
    /* Die Leiste lässt sich schieben, sobald ihr Inhalt nicht mehr hineinpasst
       (editor.css). Die Klappe ist fest gestellt und wandert deshalb nicht von
       selbst mit - sie wird nachgeführt. */
    this.leiste.addEventListener("scroll", () => this.menueAusrichten());
    // Klappt die Legende im Menü auf, wächst es - dann stimmt seine Höhe neu.
    this.inhalt.addEventListener("toggle", () => this.menueAusrichten(), true);
    window.addEventListener("resize", () => this.menueAusrichten());
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
    /* Nicht umbauen, solange jemand das Menue offen hat: Die Messung beginnt
       bei "voll", raeumt das Menue dafuer leer und schliesst es - dem
       Benutzer wuerde der Eintrag unter dem Finger weggezogen. Beim naechsten
       Schliessen wird nachgeholt (siehe starte()). */
    if (this.menue.open) {
      this.nachholen = true;
      return;
    }
    this.pruefeLaeuft = true;
    try {
      let gewaehlt = "knapp";
      let passt = false;
      for (const stufe of this.STUFEN) {
        this.stufeAnwenden(stufe);
        gewaehlt = stufe;
        passt = this.passt();
        if (passt) break;
      }
      this.stufeJetzt = gewaehlt;
      /* Passt auch die knappste Stufe nicht (ein Telefon mit rund 390
         Punkten), lässt sich die Leiste schieben - sonst wäre "Simulieren"
         nicht erreichbar. Nur dann: overflow schneidet ab, ob geschoben wird
         oder nicht, und die Klappe "Verbindungen" hängt in der Leiste. */
      this.leiste.classList.toggle("schiebt", !passt);
    } finally {
      this.pruefeLaeuft = false;
    }
  },

  /* Setzt die Klappe unter ihren Knopf.

     In Bildschirmkoordinaten, weil sie fest gestellt ist (position: fixed,
     siehe editor.css): Nur so entkommt sie dem Überlauf der Leiste, die sich
     seit dem Schieben nicht mehr nach ihren Kindern richtet. Rechtsbündig
     unter dem Knopf, aber nie über den linken Fensterrand hinaus - auf einem
     Telefon ist die Klappe breiter als der Platz rechts von ihrem Knopf. */
  RAND: 8,

  menueAusrichten() {
    if (!this.menue || !this.inhalt || !this.menue.open) return;
    const knopf = this.menue.getBoundingClientRect();
    this.inhalt.style.top = `${knopf.bottom + 6}px`;
    // Mit aufgeklappter Legende wird das Menü länger als ein Telefon hoch
    // ist - dann scrollt es in sich selbst, statt unten hinauszulaufen.
    this.inhalt.style.maxHeight =
      `${window.innerHeight - knopf.bottom - 6 - this.RAND}px`;
    // Erst rechtsbündig setzen, dann messen und, falls nötig, nach rechts
    // zurückschieben.
    this.inhalt.style.left = "auto";
    this.inhalt.style.right = `${window.innerWidth - knopf.right}px`;
    const klappe = this.inhalt.getBoundingClientRect();
    if (klappe.left < this.RAND) {
      this.inhalt.style.right = "auto";
      this.inhalt.style.left = `${this.RAND}px`;
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
        eintrag.platzhalter.parentElement.insertBefore(
          eintrag.element, eintrag.platzhalter
        );
      }
    }

    // Ein leeres Menü ist ein Knopf, hinter dem nichts steht.
    const leer = this.inhalt.children.length === 0;
    this.menue.hidden = leer;
    if (leer) this.menue.open = false;
  },
};

window.addEventListener("DOMContentLoaded", () => Leiste.starte());
