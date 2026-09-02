/* Zahlen in deutscher Schreibweise.
   Ueberall dort gebraucht, wo eine Zahl als TEXT auf der Seite landet -
   Kosten, Mengen, Messwerte, Anteile. Nicht bei <input type="number">: dort
   uebernimmt der Browser die Schreibweise aus dem lang-Attribut der Seite
   (templates/*.html: lang="de"), weshalb Eingabefelder schon immer ein Komma
   zeigten und die daneben stehenden Texte einen Punkt - genau der Bruch, den
   diese Datei behebt.

   Dieselbe Schreibweise wie im Bericht (core/bericht.py) und in der Ausgabe
   (core/ausgabe.py): Komma als Dezimaltrenner, kein Tausenderpunkt (er macht
   in schmalen Tabellenspalten mehr Unruhe als Nutzen).

   Als eigene Datei und nicht in einer der bestehenden: sie wird von der
   Startseite UND vom Editor gebraucht, die sonst kein Skript teilen. */
const Zahlen = {
  /* Feste Anzahl Nachkommastellen - fuer Betraege und Messwerte, bei denen
     eine wechselnde Stellenzahl die Spalte unruhig machte. */
  fest(wert, stellen = 1) {
    const zahl = Number(wert);
    if (!Number.isFinite(zahl)) return "–";
    return zahl.toFixed(Math.max(0, stellen)).replace(".", ",");
  },
};
