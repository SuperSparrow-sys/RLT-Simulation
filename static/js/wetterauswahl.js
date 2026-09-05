/* Auswahl von Wetterdatensaetzen, nach Standort gebuendelt.
 *
 * Ein einziger TRY-Ordner vom DWD bringt sechs Datensaetze mit (zwei
 * Schluesseljahre mal mittleres Jahr, extremer Sommer, extremer Winter). Nach
 * drei Standorten waere eine flache Auswahlliste unbenutzbar. Darum zwei
 * Felder: erst der Standort, dann der Datensatz.
 *
 * Gemeinsame Datei, weil beides gebraucht wird - die Startseite gruppiert ihre
 * Tabelle danach (static/js/start.js), der Editor seine beiden
 * Simulationsdialoge (static/js/simulation.js). In zahlen.js gehoert es nicht,
 * das rechnet mit Zahlen.
 */

// Ueberschrift fuer Datensaetze mit leerem Ortsfeld. Alle vor der
// Standort-Gruppierung hochgeladenen Datensaetze haben eines - sie duerfen
// dadurch nicht aus der Auswahl fallen.
const OHNE_STANDORT = "Ohne Standort";

// Wert des Sammeleintrags im Standortfeld. Ein Wetterjahr-Vergleich ueber zwei
// Orte hinweg war vor der Gruppierung moeglich und muss es bleiben.
const ALLE_STANDORTE = " alle";
const ALLE_STANDORTE_TEXT = "Alle Standorte";

/* Datensaetze nach Standort buendeln.
 *
 * Die Reihenfolge der uebergebenen Liste bleibt erhalten, damit der zuletzt
 * angelegte Standort oben steht. "Ohne Standort" wandert ans Ende - es ist
 * kein Standort, sondern dessen Fehlen. */
function wetterNachStandort(datensaetze) {
  const gruppen = new Map();
  for (const eintrag of datensaetze) {
    const ort = (eintrag.ort || "").trim() || OHNE_STANDORT;
    if (!gruppen.has(ort)) gruppen.set(ort, []);
    gruppen.get(ort).push(eintrag);
  }
  const ohne = gruppen.get(OHNE_STANDORT);
  if (ohne) {
    gruppen.delete(OHNE_STANDORT);
    gruppen.set(OHNE_STANDORT, ohne);
  }
  return gruppen;
}

/* Fuellt ein Standort- und ein Datensatzfeld und haelt beide beieinander.
 *
 * Erwartet zwei leere <select> im uebergebenen Behaelter. Das Standortfeld
 * bleibt auch bei nur einem Standort sichtbar: ein Feld, das je nach Datenlage
 * erscheint und verschwindet, verwirrt mehr, als es spart.
 *
 * Rueckgabe: eine Funktion, die die aktuell gewaehlten Datensatz-Kennungen
 * liefert - bei einfacher Auswahl eine einelementige Liste. */
function wetterAuswahlFelder(behaelter, ortKennung, datensatzKennung, wetter, einstellungen = {}) {
  const { mehrfach = false, mitAlleStandorte = false } = einstellungen;
  const ortFeld = behaelter.querySelector(`#${ortKennung}`);
  const datensatzFeld = behaelter.querySelector(`#${datensatzKennung}`);
  const gruppen = wetterNachStandort(wetter);

  ortFeld.textContent = "";
  if (mitAlleStandorte && gruppen.size > 1) {
    ortFeld.appendChild(new Option(ALLE_STANDORTE_TEXT, ALLE_STANDORTE));
  }
  for (const [ort, eintraege] of gruppen) {
    ortFeld.appendChild(new Option(`${ort} (${eintraege.length})`, ort));
  }

  const datensatzfeldFuellen = () => {
    const gewaehlterOrt = ortFeld.value;
    const sichtbar =
      gewaehlterOrt === ALLE_STANDORTE ? wetter : gruppen.get(gewaehlterOrt) || [];
    datensatzFeld.textContent = "";
    for (const eintrag of sichtbar) {
      // Bei "Alle Standorte" waere der blosse Name mehrdeutig - dasselbe
      // Testreferenzjahr heisst an jedem Ort gleich.
      const beschriftung =
        gewaehlterOrt === ALLE_STANDORTE && (eintrag.ort || "").trim()
          ? `${eintrag.ort} · ${eintrag.name} (${eintrag.stunden} h)`
          : `${eintrag.name} (${eintrag.stunden} h)`;
      datensatzFeld.appendChild(new Option(beschriftung, String(eintrag.id)));
    }
    // Bei Mehrfachauswahl den ersten Eintrag vorwaehlen, damit ein Klick auf
    // "Los" nicht ins Leere geht.
    if (mehrfach && datensatzFeld.options.length) {
      datensatzFeld.options[0].selected = true;
    }
  };

  datensatzfeldFuellen();
  ortFeld.addEventListener("change", datensatzfeldFuellen);

  return () =>
    Array.from(datensatzFeld.selectedOptions).map((o) => Number(o.value));
}
