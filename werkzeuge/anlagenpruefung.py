"""Rechnet alle mitgelieferten Anlagen durch und haelt die Ergebnisse gegen
ihre Erwartungsbaender.

Zwei Vorlagen sagen wenig darueber, ob die Rechenkette traegt: Beide sind an
derselben Hand entstanden und teilen deshalb dieselben blinden Flecken. Zehn
Anlagen verschiedener Bauart legen frei, was eine einzelne verdeckt - so wurde
etwa der Sprung der Luftmenge am Ventilator erst sichtbar, als eine Anlage mit
Waermerueckgewinnung UND Nachtabsenkung gebaut war (AX_SIM 2.1 faehrt konstant
auf Nennmenge, die Testanlage hat eine Mischkammer, die den Fehler verdeckt).

Geprueft wird dreierlei:

1. Der Zusammenbau - core/pruefung.py meldet stille Verdrahtungsfehler.
2. Die Rechnung - dieselben Pruefungen wie werkzeuge/plausibilitaet.py, also
   kein zweiter, abweichender Massstab.
3. Die Zahlen - jede Anlage traegt in ihrem Modul ERWARTUNG mit Baendern, die
   aus ihrer eigenen Auslegung hergeleitet sind (Herleitung im Kopf der Datei).

Aufruf:

    venv/bin/python -m werkzeuge.anlagenpruefung            # alle, ganzes Jahr
    venv/bin/python -m werkzeuge.anlagenpruefung buero      # nur eine
    venv/bin/python -m werkzeuge.anlagenpruefung --wochen   # nur drei Wochen

Ein Jahreslauf je Anlage dauert einige Minuten; die Wochenprobe ist fuer die
Arbeit am Code gedacht, der Jahreslauf fuer die Abnahme.
"""

import sys

from core import anlagen, pruefung, solver
from core.vorlagen import anlagen as vorlagen_anlagen
from werkzeuge import plausibilitaet
from werkzeuge.abgleich import lade_wetterstunden

#: Je eine Winter-, Uebergangs- und Sommerwoche - die Probe fuer zwischendurch.
WOCHEN = ((0, 168), (2900, 3068), (4700, 4868))

#: Dichte der Luft und ihre Waermekapazitaet, wie im Rechenkern.
RHO_CP = 1.2 * 1.007


def _stunden(nur_wochen):
    alle = lade_wetterstunden()
    if not nur_wochen:
        return alle
    ausschnitt = []
    for von, bis in WOCHEN:
        ausschnitt.extend(alle[von:bis])
    return ausschnitt


def _reihe(graph, lauf, typ, groesse):
    kid = next((k for k, v in graph.karten.items() if v.typ == typ), None)
    if kid is None:
        return []
    return [s.get(kid, {}).get(groesse, 0.0) for s in lauf.stunden]


def _alle_reihen(graph, lauf, typ, groesse):
    """Summe ueber ALLE Karten dieses Typs - eine Anlage kann mehrere Erhitzer
    oder mehrere Raeume haben."""
    ids = [k for k, v in graph.karten.items() if v.typ == typ]
    return [sum(s.get(k, {}).get(groesse, 0.0) for k in ids) for s in lauf.stunden]


def kennzahlen(modul, graph, lauf):
    """Die Groessen, gegen die ERWARTUNG geprueft wird - auf das Jahr bezogen."""
    stunden = len(lauf.stunden)
    if not stunden:
        return {}
    aufs_jahr = 8760.0 / stunden

    flaeche = getattr(modul, "FLAECHE_M2", 0.0) or 1.0
    luftmenge = getattr(modul, "LUFTMENGE_M3H", 0.0)

    waerme = sum(_alle_reihen(graph, lauf, "erhitzer", "QH"))
    waerme += sum(_alle_reihen(graph, lauf, "dampfbefeuchter", "QH"))
    waerme += sum(_alle_reihen(graph, lauf, "warmwasser", "QH"))
    waerme += sum(_alle_reihen(graph, lauf, "zirkulation", "QH"))
    kaelte = sum(_alle_reihen(graph, lauf, "kuehler", "QK"))

    strom_ventilatoren = sum(_alle_reihen(graph, lauf, "ventilator", "PE"))
    # SFP aus der geleisteten Foerderarbeit: Strom je gefoerderten Kubikmeter.
    gefoerdert = sum(
        s.get(k, {}).get("luft_aus").V
        for k, v in graph.karten.items() if v.typ == "ventilator"
        for s in lauf.stunden
        if hasattr(s.get(k, {}).get("luft_aus"), "V")
    )
    sfp = strom_ventilatoren * 1000.0 / gefoerdert if gefoerdert else 0.0

    # Die Raumhoehe kommt aus der Anlage, nicht aus einer Annahme: Eine
    # Schwimmhalle ist 6 m hoch, eine Turnhalle 7, ein Buero 3. Mit einer
    # festen Hoehe von 3 m meldete dieses Werkzeug fuer jede hohe Halle einen
    # zu grossen Luftwechsel - ein Fehler des Pruefstands, nicht der Anlage.
    hoehe = getattr(modul, "HOEHE_M", 3.0)
    volumen = flaeche * hoehe
    return {
        "heizwaerme_kwh_m2a": waerme * aufs_jahr / flaeche,
        "kaelte_kwh_m2a": kaelte * aufs_jahr / flaeche,
        "sfp_w_m3h": sfp,
        "luftwechsel_1h": luftmenge / volumen if volumen else 0.0,
    }


def pruefe_anlage(app, modul, nur_wochen=False):
    """Baut, rechnet und bewertet eine Anlage."""
    stunden = _stunden(nur_wochen)
    with app.app_context():
        projekt = anlagen.projekt_anlegen(f"Prüfung {modul.NAME}"[:60])
        anlage_id = modul.baue(projekt)
        graph = anlagen.lade_graph(anlage_id)
        zusammenbau = pruefung.pruefe(graph)
        lauf = solver.Solver(graph).starte(stunden)

    ergebnis = {"lauf": lauf, "graph": graph, "anlage_id": anlage_id,
                "wetter": stunden, "abgedeckte_typen": {k.typ for k in graph.karten.values()}}
    rechnung = plausibilitaet.pruefungen(ergebnis)

    zahlen = kennzahlen(modul, graph, lauf)
    baender = []
    # Die Jahreskennzahlen gelten nur nach einem Jahreslauf. Die Wochenprobe
    # nimmt je eine Winter-, Uebergangs- und Sommerwoche und rechnet sie mit
    # 8760/504 hoch - der Sommer waere darin dreifach ueberrepraesentiert, und
    # der Kaeltebedarf fiele entsprechend zu hoch aus (gemessen an der
    # Turnhalle: 49 statt der im Jahr erreichten Zahl). Die Probe taugt fuer
    # Zusammenbau und Rechnung, nicht fuer Jahreskennzahlen.
    for name, (unten, oben) in (
        {} if nur_wochen else getattr(modul, "ERWARTUNG", {})
    ).items():
        wert = zahlen.get(name)
        if wert is None:
            continue
        baender.append({
            "name": name, "wert": wert, "band": (unten, oben),
            "bestanden": unten <= wert <= oben,
        })

    return {
        "modul": modul, "graph": graph, "lauf": lauf,
        "zusammenbau": zusammenbau, "rechnung": rechnung,
        "kennzahlen": zahlen, "baender": baender,
    }


def als_text(befunde):
    zeilen = []
    fehler_gesamt = 0
    for b in befunde:
        modul = b["modul"]
        rechnung_fehler = [p for p in b["rechnung"] if not p["bestanden"]]
        band_fehler = [x for x in b["baender"] if not x["bestanden"]]
        fehler = len(_beanstandungen(b))
        fehler_gesamt += fehler

        marke = "OK    " if fehler == 0 else "FEHLER"
        zeilen.append(f"\n{marke}  {modul.NAME}")
        for m in b["zusammenbau"]:
            zeilen.append(f"          Zusammenbau: {m['text']}")
        for p in rechnung_fehler:
            zeilen.append(f"          Rechnung:    {p['name']} - {p['befund']}")
        for x in band_fehler:
            unten, oben = x["band"]
            zeilen.append(
                f"          Kennzahl:    {x['name']} = {x['wert']:.1f}, "
                f"erwartet {unten:.1f} bis {oben:.1f}"
            )
        if fehler == 0:
            werte = ", ".join(f"{k} {v:.1f}" for k, v in b["kennzahlen"].items())
            zeilen.append(f"          {werte}")

    sauber = sum(1 for b in befunde if not _beanstandungen(b))
    zeilen.append(
        f"\n{sauber} von {len(befunde)} Anlagen ohne Beanstandung"
    )
    return "\n".join(zeilen)


def _beanstandungen(befund):
    """Alles, was an einer Anlage zu bemaengeln ist - in einer Liste."""
    return (
        list(befund["zusammenbau"])
        + [p for p in befund["rechnung"] if not p["bestanden"]]
        + [x for x in befund["baender"] if not x["bestanden"]]
    )


def hauptprogramm(argumente=None):
    import tempfile
    from pathlib import Path

    argumente = list(argumente if argumente is not None else sys.argv[1:])
    nur_wochen = "--wochen" in argumente
    if nur_wochen:
        argumente.remove("--wochen")

    import core.config as config
    config.DB_PATH = Path(tempfile.mkdtemp()) / "anlagenpruefung.db"

    from app import create_app
    from core import database

    app = create_app()
    with app.app_context():
        database.init_db()

    module = vorlagen_anlagen.alle()
    if argumente:
        fehlend = [a for a in argumente if a not in module]
        if fehlend:
            print(f"Unbekannte Anlage: {', '.join(fehlend)}")
            print(f"Bekannt sind: {', '.join(module)}")
            return 2
        module = {k: v for k, v in module.items() if k in argumente}

    zeitraum = ("drei Wochen (ohne Jahreskennzahlen)" if nur_wochen
                else "ein Jahr")
    print(f"Prüfe {len(module)} Anlagen über {zeitraum} …")
    befunde = []
    for kennung, modul in module.items():
        print(f"   {modul.NAME} …", flush=True)
        befunde.append(pruefe_anlage(app, modul, nur_wochen=nur_wochen))
    print(als_text(befunde))
    return 0


if __name__ == "__main__":
    raise SystemExit(hauptprogramm())
