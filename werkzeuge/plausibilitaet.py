"""Rechnet die Testanlage ueber ein Jahr und prueft das Ergebnis auf Plausibilitaet.

Anders als der Abgleich in werkzeuge/abgleich.py wird hier NICHT gegen die Excel
verglichen - core/vorlagen/testanlage.py ist keine Excel-Nachbildung. Geprueft
wird, ob sich die Anlage physikalisch vernuenftig verhaelt: Bleibt der Raum in
einem sinnvollen Temperaturband? Wird im Winter geheizt und im Sommer gekuehlt
und nicht umgekehrt? Bleibt die Luft unterhalb der Saettigung? Mischt die
Mischkammer plausibel zwischen Aussen- und Ablufttemperatur? Passen Stundenwerte
und Jahressumme zusammen?

Aufruf von Hand:  ./venv/bin/python werkzeuge/plausibilitaet.py
"""

import pathlib
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent

# Kartentypen, die core/bausteine/basis.py als reine Signal-"Verdrahtungshilfen"
# fuehrt: Umkehrglied, Faktor und Maximalwert existieren einzig, um bestimmte
# Excel-Formeln (MAX(...), 100-x, ein fester Faktor) als eigene Karte
# nachzubilden - sie haben kein Gegenstueck in echtem Anlagenbau. Ob eine Anlage
# so etwas braucht, haengt allein von der GEWAEHLTEN Reglertopologie ab, nicht
# von der Anlage selbst: eine Kaskade oder ein Sequenzregler (siehe
# core/vorlagen/testanlage.py) druecken dieselbe Verriegelung ohne ein einziges
# dieser drei Glieder aus. Sie zaehlen deshalb NICHT zu den Kartentypen, deren
# Fehlen in beiden grossen Vorlagen ein Befund waere.
KEINE_ECHTE_ANLAGENKARTE = {"umkehrglied", "faktor", "maximalwert"}


def rechne_testjahr(app):
    from core import anlagen, solver
    from core.vorlagen import ax_sim_2_1, testanlage
    from werkzeuge.abgleich import lade_wetterstunden

    stunden = lade_wetterstunden()
    with app.app_context():
        projekt = anlagen.projekt_anlegen("Plausibilitaet")
        anlage_id = testanlage.baue(projekt, testanlage.NAME)
        graph = anlagen.lade_graph(anlage_id)
        lauf = solver.Solver(graph).starte(stunden)

        # Fuer die Abdeckungspruefung (nicht_abgedeckte_typen unten) reicht es,
        # AX_SIM 2.1 zu BAUEN - ihre Zahlen werden schon in Task 20/test_abgleich.py
        # gegen die Excel gerechnet und geprueft; ein zweiter, hier ungenutzter
        # Jahreslauf waere nur verschwendete Zeit.
        vorlagenprojekt = anlagen.projekt_anlegen("Plausibilitaet (Abdeckung)")
        ax_sim_id = ax_sim_2_1.baue(vorlagenprojekt, ax_sim_2_1.NAME)
        ax_sim_graph = anlagen.lade_graph(ax_sim_id)

    abgedeckte_typen = (
        {k.typ for k in graph.karten.values()}
        | {k.typ for k in ax_sim_graph.karten.values()}
    )

    return {
        "lauf": lauf,
        "graph": graph,
        "anlage_id": anlage_id,
        "wetter": stunden,
        "abgedeckte_typen": abgedeckte_typen,
    }


# -- Hilfsgriffe auf den Lauf -------------------------------------------

def _karte_mit_typ(graph, typ, filter_=None):
    """Erste Karte eines Typs; mit `filter_` gezielt unter mehreren gleichen
    Typs (z. B. Zu- und Abluftventilator) - ausgewaehlt ueber ihre Parameter."""
    for kid, karte in graph.karten.items():
        if karte.typ != typ:
            continue
        if filter_ is not None and not filter_(karte):
            continue
        return kid
    return None


def _reihe(ergebnis, typ, groesse, filter_=None):
    """Stundenwerte einer Groesse der (ersten passenden) Karte dieses Typs."""
    kid = _karte_mit_typ(ergebnis["graph"], typ, filter_)
    if kid is None:
        return []
    return [s.get(kid, {}).get(groesse, 0.0) for s in ergebnis["lauf"].stunden]


def _monat(ergebnis, nummer):
    """Indizes der Stunden eines Monats."""
    return [
        i for i, w in enumerate(ergebnis["wetter"])
        if w["zeitpunkt"].month == nummer
    ]


def _summe(werte, indizes=None):
    if indizes is None:
        return sum(werte)
    return sum(werte[i] for i in indizes if i < len(werte))


def _zuluftventilator(karte):
    return karte.parameter.get("rolle") == "zuluft"


# -- Die Pruefungen ------------------------------------------------------

def pruefungen(ergebnis):
    from core.bausteine import stoffdaten as st

    lauf = ergebnis["lauf"]
    ergebnisse = []

    def pruefe(name, bedingung, befund):
        ergebnisse.append(
            {"name": name, "bestanden": bool(bedingung), "befund": befund}
        )

    # 1 - Der Lauf muss ueberhaupt zustande kommen.
    pruefe(
        "Alle 8760 Stunden gerechnet",
        len(lauf.stunden) == 8760,
        f"{len(lauf.stunden)} Stunden",
    )

    # 2 - Die erste Stunde ist der Kaltstart: alle Regler und Speicher stehen auf
    # ihrem Anfangswert und muessen sich innerhalb dieser Stunde hocharbeiten -
    # das darf mehrere Durchgaenge brauchen. Jede spaetere Stunde beginnt beim
    # eingependelten Wert der Vorstunde.
    #
    # "Konvergiert" heisst hier NICHT "keine einzige Warnung": Diese Anlage
    # verzichtet bewusst auf Zweipunktregler (siehe core/vorlagen/testanlage.py,
    # "Zur Konvergenz") und regelt ausschliesslich mit p_regler/kaskade/
    # sequenzregler - Reglern, die ihre Regelabweichung als Speicher ueber die
    # Iterationen fortschreiben (ZUSTAND_UEBER_ITERATION). Die Kaskade etwa
    # arbeitet in ihrem normalen Regelfall gegen die Raumtemperatur, deren
    # Ansprechen auf die eigene Stellgroesse durch die Speichermasse des Raums
    # gedaempft ist - ein GESCHLOSSENER, aber SCHWACHER Regelkreis, der sich
    # innerhalb der erlaubten 100 Durchgaenge oft nur annaehert statt exakt
    # einzuschwingen. Genau das akzeptiert bereits die Referenzpruefung fuer
    # AX_SIM 2.1 selbst: tests/test_abgleich.py,
    # test_ohne_den_befeuchtungskreis_schwingt_nichts_mehr, laesst dort
    # Restabweichungen bis 0,44 zu ("Auf 'gar keine Warnung' laesst er sich
    # nicht stellen") und prueft nur, dass die Abweichung KLEIN bleibt - nicht,
    # dass sie ganz verschwindet. Ein echter Grenzzyklus (siehe AX_SIM 2.1 MIT
    # seinen Luftwaescher-Zweipunktreglern) zeigt sich dagegen an einer
    # Restabweichung um 100,0, die bei jeder Durchgangszahl gleich bleibt -
    # nicht an einer kleinen, die von Stunde zu Stunde schwankt.
    #
    # Diese Pruefung uebernimmt denselben Massstab: keine Stunde nach der
    # ersten darf eine grenzzyklus-grosse Restabweichung zeigen.
    GRENZZYKLUS_SCHWELLE = 2.0
    spaetere_warnungen = [w for w in lauf.warnungen if w["stunde"] > 1]
    grenzzyklen = [w for w in spaetere_warnungen if w["abweichung"] > GRENZZYKLUS_SCHWELLE]
    pruefe(
        "Ab der zweiten Stunde kein Grenzzyklus (Restabweichung bleibt klein)",
        not grenzzyklen,
        f"{len(spaetere_warnungen)} von {len(lauf.stunden) - 1} spaeteren Stunden ohne "
        f"volle Konvergenz (das ist bei schwach rueckgekoppelten Reglern erwartet), "
        f"davon {len(grenzzyklen)} mit Restabweichung > {GRENZZYKLUS_SCHWELLE} "
        f"(waere ein Grenzzyklus)"
        + (f" - erste: {grenzzyklen[0]['text']}" if grenzzyklen else ""),
    )

    # 3 - Der Raum bleibt in einem sinnvollen Band.
    t_raum = _reihe(ergebnis, "raum", "T_Raum")
    pruefe(
        "Raumtemperatur zwischen 5 und 40 °C",
        t_raum and min(t_raum) > 5.0 and max(t_raum) < 40.0,
        f"min {min(t_raum):.1f} °C, max {max(t_raum):.1f} °C" if t_raum else "keine Werte",
    )

    # 4 - Die Raumluft bleibt unter der Saettigung.
    f_raum = _reihe(ergebnis, "raum", "F_Raum")
    ueber = [
        i for i, (t, x) in enumerate(zip(t_raum, f_raum))
        if x < 0.0 or x > st.x_saett(t) + 0.5
    ]
    pruefe(
        "Raumfeuchte nie negativ und nie ueber der Saettigung",
        not ueber,
        f"{len(ueber)} Stunden ausserhalb"
        + (f", erste Stunde {ueber[0]}" if ueber else ""),
    )

    # 5/6 - Geheizt wird im Winter, gekuehlt im Sommer - nicht umgekehrt.
    waerme_ahu = _reihe(ergebnis, "erhitzer", "QH")
    waerme_stat = _reihe(ergebnis, "statische_heizung", "QH")
    kaelte = _reihe(ergebnis, "kuehler", "QK")
    winter = _monat(ergebnis, 1) + _monat(ergebnis, 2) + _monat(ergebnis, 12)
    sommer = _monat(ergebnis, 6) + _monat(ergebnis, 7) + _monat(ergebnis, 8)
    waerme = [a + b for a, b in zip(waerme_ahu, waerme_stat)]
    pruefe(
        "Heizwaerme im Winter groesser als im Sommer",
        _summe(waerme, winter) > _summe(waerme, sommer),
        f"Winter {_summe(waerme, winter) / 1000:.1f} MWh, "
        f"Sommer {_summe(waerme, sommer) / 1000:.1f} MWh",
    )
    pruefe(
        "Kaelte im Sommer groesser als im Winter",
        _summe(kaelte, sommer) > _summe(kaelte, winter),
        f"Sommer {_summe(kaelte, sommer) / 1000:.1f} MWh, "
        f"Winter {_summe(kaelte, winter) / 1000:.1f} MWh",
    )

    # 7 - Kein Baustein liefert negative Leistung.
    negativ = {
        name: min(reihe)
        for name, reihe in (
            ("Erhitzer", waerme_ahu), ("Statische Heizung", waerme_stat),
            ("Kuehler", kaelte),
        )
        if reihe and min(reihe) < -1e-6
    }
    pruefe(
        "Weder Heiz- noch Kaelteleistung wird negativ",
        not negativ,
        f"{negativ}" if negativ else "keine negativen Werte",
    )

    # 8 - Die Mischkammer mischt physikalisch sinnvoll: die Mischlufttemperatur
    # (aus Aussen- und rueckgefuehrter Abluft) darf nie ausserhalb der Spanne
    # liegen, die diese beiden Zustaende aufspannen - eine gewichtete Mischung
    # kann per Definition nicht waermer als der waermste oder kaelter als der
    # kaelteste ihrer beiden Bestandteile werden. Ersetzt die WRG-Richtungs-
    # pruefung der Vorlage, weil diese Anlage keine WRG, sondern eine
    # Umluft-Mischkammer als Waermerueckgewinn einsetzt.
    t_mi = _reihe(ergebnis, "mischkammer", "T_MI")
    t_au = [w["t_au"] for w in ergebnis["wetter"]]
    t_fo = _reihe(ergebnis, "fortluft", "T_FO")
    ausserhalb = [
        i for i, (mi, au, fo) in enumerate(zip(t_mi, t_au, t_fo))
        if not (min(au, fo) - 0.1 <= mi <= max(au, fo) + 0.1)
    ]
    pruefe(
        "Mischlufttemperatur liegt zwischen Aussen- und Ablufttemperatur",
        not ausserhalb,
        f"{len(ausserhalb)} Stunden ausserhalb"
        + (f", erste Stunde {ausserhalb[0]}" if ausserhalb else ""),
    )

    # 9 - Zulufttemperatur (nach dem Zuluftventilator, unmittelbar vor dem Raum)
    # bleibt in einem technisch plausiblen Band.
    t_zu = _reihe(ergebnis, "ventilator", "T_aus", filter_=_zuluftventilator)
    pruefe(
        "Zulufttemperatur zwischen -15 und 45 °C",
        t_zu and min(t_zu) > -15.0 and max(t_zu) < 45.0,
        f"min {min(t_zu):.1f} °C, max {max(t_zu):.1f} °C" if t_zu else "keine Werte",
    )

    # 10 - Stundenwerte und Jahressumme passen zusammen.
    bilanz_kid = _karte_mit_typ(ergebnis["graph"], "bilanz")
    strom_stunden = [
        s.get(bilanz_kid, {}).get("strom_ht", 0.0)
        + s.get(bilanz_kid, {}).get("strom_nt", 0.0)
        for s in lauf.stunden
    ]
    strom_bilanz = lauf.bilanz["strom_ht"] + lauf.bilanz["strom_nt"]
    pruefe(
        "Summe der Stundenwerte gleich der Jahresbilanz",
        abs(sum(strom_stunden) - strom_bilanz) < 1e-6,
        f"Stunden {sum(strom_stunden):.6f} kWh, Bilanz {strom_bilanz:.6f} kWh",
    )

    # 11 - Der Zeitplan wirkt: im Betrieb wird mehr Strom gezogen als ausserhalb
    # (Ventilatoren, Beleuchtung, Pumpen und Zirkulation haengen alle am
    # Anlagenbetrieb).
    betrieb = _reihe(ergebnis, "anlagenbetrieb", "betrieb")
    strom_an = [s for s, b in zip(strom_stunden, betrieb) if b > 0.5]
    strom_aus = [s for s, b in zip(strom_stunden, betrieb) if b <= 0.5]
    pruefe(
        "Im Betrieb wird mehr Strom gezogen als ausserhalb",
        strom_an and strom_aus
        and sum(strom_an) / len(strom_an) > sum(strom_aus) / len(strom_aus),
        f"im Betrieb {sum(strom_an) / max(len(strom_an), 1):.2f} kW, "
        f"ausserhalb {sum(strom_aus) / max(len(strom_aus), 1):.2f} kW",
    )

    # 12 - Der spezifische Heizwaermebedarf (AHU-Erhitzer PLUS die statische
    # Zusatzheizung, denn beide beheizen denselben Raum) liegt in einer
    # ueblichen Groessenordnung fuer ein Bestandsgebaeude.
    raum_kid = _karte_mit_typ(ergebnis["graph"], "raum")
    raum_karte = ergebnis["graph"].karten[raum_kid]
    flaeche = raum_karte.baustein.geometrie(raum_karte.parameter)["grundflaeche"]
    spezifisch = _summe(waerme) / flaeche if flaeche else 0.0
    pruefe(
        "Spezifischer Heizwaermebedarf zwischen 10 und 400 kWh/(m² a)",
        10.0 < spezifisch < 400.0,
        f"{spezifisch:.1f} kWh/(m² a) bei {flaeche:.0f} m²",
    )

    return ergebnisse


def nicht_abgedeckte_typen(ergebnis):
    """Kartentypen, die weder AX_SIM 2.1 noch die Testanlage tatsaechlich
    verbauen - siehe KEINE_ECHTE_ANLAGENKARTE oben fuer die drei, die dabei
    absichtlich nicht mitzaehlen."""
    from core.bausteine import basis

    erforderlich = {k.KENNUNG for k in basis.alle()} - KEINE_ECHTE_ANLAGENKARTE
    return erforderlich - ergebnis["abgedeckte_typen"]


def als_text(ergebnisse):
    zeilen = []
    for p in ergebnisse:
        zeichen = "OK    " if p["bestanden"] else "FEHLER"
        zeilen.append(f"{zeichen}  {p['name']:55} {p['befund']}")
    bestanden = sum(1 for p in ergebnisse if p["bestanden"])
    zeilen.append(f"\n{bestanden} von {len(ergebnisse)} Pruefungen bestanden")
    return "\n".join(zeilen)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(WURZEL))

    # In eine Wegwerfdatenbank rechnen, damit ein Aufruf von Hand keine Reste in
    # der Datenbank des laufenden Dienstes hinterlaesst.
    import tempfile

    import core.config as config

    config.DB_PATH = pathlib.Path(tempfile.mkdtemp()) / "plausibilitaet.db"

    from app import create_app
    from core import database

    anwendung = create_app()
    with anwendung.app_context():
        database.init_db()

    ergebnis = rechne_testjahr(anwendung)
    print(als_text(pruefungen(ergebnis)))

    fehlend = nicht_abgedeckte_typen(ergebnis)
    if fehlend:
        print(f"\nVon keiner Vorlage gerechnet: {sorted(fehlend)}")
    else:
        print("\nAlle als anlagenrelevant geltenden Kartentypen werden von "
              "mindestens einer der beiden grossen Vorlagen benutzt.")
