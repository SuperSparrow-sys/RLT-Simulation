/* Palette und Parameterfenster auf schmalen Bildschirmen auf- und
   zuklappen.

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
});
