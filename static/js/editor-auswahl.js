/* Eine Karte auswaehlen, verschieben und loeschen - also alles, was am
   Zeiger haengt, solange er auf einer Karte liegt.

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
});
