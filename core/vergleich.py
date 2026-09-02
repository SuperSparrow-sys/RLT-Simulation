"""Gegenueberstellung mehrerer Simulationslaeufe derselben Anlage ueber
verschiedene Wetterjahre.

Beschraenkung, ausdruecklich (siehe docs/superpowers/plans/
2026-09-02-rlt-simulation-stufe-2.md, Vorhaben B): verglichen werden Laeufe
DERSELBEN Anlage ueber verschiedene Wetterdatensaetze - nicht verschiedene
Anlagen gegeneinander (das braeuchte zuerst das Duplizieren einer Anlage,
ein eigenes Vorhaben). vergleichsdaten() prueft das und weist eine gemischte
Auswahl zurueck.

Datenbankzugriff bleibt an seinem angestammten Ort: core.ergebnisse fuer den
Lauf, core.wetter.speicher fuer den Wetterdatensatz - dieses Modul fragt nur
diese beiden, nie eine Tabelle selbst (dieselbe Regel wie core/bericht.py).
Die eigenen Labels/Farben hier dupliziert kleine Teile von core/bericht.py
bewusst, statt von dort zu importieren - core/bericht.py und core/zeichnung.py
werden parallel bearbeitet (siehe Aufgabenstellung), dieses Modul soll davon
unabhaengig bleiben. Aus core.zeichnung wird nur die stabile, oeffentliche
Bau-Funktion balkendiagramm() benutzt, keine core/bericht.py-Interna.
"""

from __future__ import annotations

from core import ergebnisse, zeichnung
from core.wetter import speicher

# Laeufe in diesem Status haben eine gespeicherte Bilanz - dieselbe Menge wie
# core.bericht.STATUS_MIT_ERGEBNIS (hier nicht importiert, siehe Docstring
# oben).
STATUS_MIT_ERGEBNIS = ("fertig", "abgebrochen")


class VergleichNichtMoeglich(ValueError):
    """Die angefragte Auswahl ist leer, oder ihre Laeufe gehoeren zu mehr als
    einer Anlage - siehe Modul-Docstring, "Beschraenkung, ausdruecklich"."""


def _wetter_bezeichnung(wetter):
    """'Name (Jahr)', ohne das Jahr zu wiederholen, wenn der frei vergebene
    Name es schon enthaelt - derselbe Kniff wie core.bericht._wetter_kopfzeile,
    hier unabhaengig nachgebaut (siehe Modul-Docstring)."""
    if not wetter:
        return "–"
    name = wetter.get("name") or "–"
    jahr = wetter.get("jahr")
    if jahr and str(int(jahr)) not in name:
        return f"{name} ({int(jahr)})"
    return name


def vergleichsdaten(simulation_ids):
    """Alle Angaben fuer die Gegenueberstellung der uebergebenen Laeufe.

    Liefert ein dict mit:
    - 'laeufe': je Lauf Kopfdaten (Wetterdatensatz, Zeitraum, Status, ob ein
      Ergebnis vorliegt, Gesamtkosten, Zahl der Warnungen) - in der
      Reihenfolge von 'simulation_ids'.
    - 'zeilen': je Bilanzgroesse (core.ergebnisse.BILANZ) eine Zeile mit Menge
      und Abweichung gegenueber dem ERSTEN Lauf der Auswahl, je Lauf.

    Ein Lauf ohne Ergebnis (Status 'laeuft' oder 'fehler', z.B. weil dieses
    Jahr innerhalb einer Reihe fehlschlug - core.laeufe._reihe_laufen)
    bekommt eine leere Bilanz statt die Anfrage abzulehnen: "der Vergleich
    zeigt, was da ist, und benennt, was fehlt" (Vorhaben B). Fehlt der
    Basislauf selbst sein Ergebnis, bleibt die Abweichung alle Zeilen ueber
    None (nicht berechenbar) - die Rohwerte der uebrigen Laeufe bleiben
    trotzdem sichtbar.

    Wirft VergleichNichtMoeglich, wenn die Liste leer ist oder die Laeufe zu
    mehr als einer Anlage gehoeren. Wirft KeyError, wenn eine simulation_id
    nicht existiert (core.ergebnisse.lade_simulation)."""
    simulation_ids = list(simulation_ids)
    if not simulation_ids:
        raise VergleichNichtMoeglich(
            "Für einen Vergleich wird mindestens ein Simulationslauf gebraucht."
        )

    laeufe = []
    anlage_ids = set()
    for simulation_id in simulation_ids:
        sim = ergebnisse.lade_simulation(simulation_id)
        anlage_ids.add(sim["anlage_id"])
        wetter = speicher.datensatz(sim["wetterdatensatz_id"])
        hat_ergebnis = sim["status"] in STATUS_MIT_ERGEBNIS
        bilanz_zeilen = ergebnisse.lade_bilanz(simulation_id) if hat_ergebnis else []
        bilanz = {z["groesse"]: z for z in bilanz_zeilen}
        anzahl_warnungen = 0
        if hat_ergebnis:
            anzahl_warnungen = (
                ergebnisse.lade_warnungen(simulation_id, anzahl=0)["anzahl"]
                + len(ergebnisse.lade_baustein_warnungen(simulation_id))
            )
        laeufe.append({
            "simulation_id": simulation_id,
            "status": sim["status"],
            "hat_ergebnis": hat_ergebnis,
            "wetterdatensatz_id": sim["wetterdatensatz_id"],
            "wetter_name": _wetter_bezeichnung(wetter),
            "von_stunde": sim["von_stunde"], "bis_stunde": sim["bis_stunde"],
            "gestartet_am": sim["gestartet_am"],
            "bilanz": {g: z["menge"] for g, z in bilanz.items()},
            "kosten_gesamt": sum(z["kosten"] for z in bilanz.values()),
            "anzahl_warnungen": anzahl_warnungen,
        })

    if len(anlage_ids) > 1:
        raise VergleichNichtMoeglich(
            "Ein Vergleich gilt nur für Läufe derselben Anlage – nicht für "
            "verschiedene Anlagen gegeneinander."
        )

    basis = laeufe[0]
    zeilen = []
    for groesse, (einheit, _preisschluessel, _faktor) in ergebnisse.BILANZ.items():
        basiswert = basis["bilanz"].get(groesse)
        werte = []
        for lauf in laeufe:
            menge = lauf["bilanz"].get(groesse)
            abweichung = None
            if menge is not None and basiswert not in (None, 0):
                abweichung = (menge - basiswert) / basiswert
            werte.append({"menge": menge, "abweichung": abweichung})
        zeilen.append({"groesse": groesse, "einheit": einheit, "werte": werte})

    return {
        "anlage_id": anlage_ids.pop() if anlage_ids else None,
        "laeufe": laeufe,
        "zeilen": zeilen,
    }


def diagramm(vergleichsdaten_ergebnis, breite=500, hoehe=290):
    """Balkendiagramm ueber die Jahre - Waerme/Kaelte/Strom je Lauf mit
    Ergebnis, aus derselben Zeichenschicht wie der Bericht
    (core.zeichnung.balkendiagramm, wie core/bericht.py sie fuer den
    Jahresverlauf in Monatswerten benutzt - hier eine Gruppe je Lauf statt je
    Monat). None, wenn kein Lauf der Auswahl ein Ergebnis hat."""
    laeufe = [l for l in vergleichsdaten_ergebnis["laeufe"] if l["hat_ergebnis"]]
    if not laeufe:
        return None

    beschriftungen = [l["wetter_name"] for l in laeufe]

    def summe(lauf, *groessen):
        return sum(lauf["bilanz"].get(g) or 0.0 for g in groessen)

    serien = [
        ("Wärme", zeichnung.FARBE_WAERME, False, [summe(l, "waerme") for l in laeufe]),
        ("Kälte", zeichnung.FARBE_KAELTE, True, [summe(l, "kaelte") for l in laeufe]),
        ("Strom", zeichnung.FARBE_STROM,
         False, [summe(l, "strom_ht", "strom_nt") for l in laeufe]),
    ]
    return zeichnung.balkendiagramm(
        breite, hoehe, "Jahresbilanz im Vergleich", beschriftungen, serien,
        y_einheit="MWh", nachkommastellen=1,
    )
