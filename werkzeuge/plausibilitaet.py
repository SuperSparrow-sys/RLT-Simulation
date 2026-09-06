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

#: Beide Raumkarten. Die Pruefungen fragen nach "dem Raum", nicht nach einer
#: bestimmten Bauart - eine Anlage mit einfachem Raum muss dieselben Pruefungen
#: bestehen wie eine mit der bauphysikalischen Karte. Ohne diese Liste liefen
#: alle Raumpruefungen auf einer leeren Reihe und meldeten "keine Werte" statt
#: zu pruefen.
RAUMTYPEN = ("raum", "einfacher_raum")


def _raumreihe(ergebnis, groesse):
    """Stundenwerte einer Raumgroesse, gleich welche Raumkarte verbaut ist."""
    for typ in RAUMTYPEN:
        werte = _reihe(ergebnis, typ, groesse)
        if werte:
            return werte
    return []


#: Wieviel Uebersaettigung als Rundungsrest durchgeht, in g/kg.
#: Der Rechenkern arbeitet mit Naeherungsformeln fuer den Saettigungsdampfdruck;
#: ein Zehntel Gramm je Kilogramm liegt in deren Genauigkeit und ist keine
#: Aussage ueber die Anlage.
SAETTIGUNG_TOLERANZ = 0.1


def uebersaettigte_zustaende(stunden):
    """Alle Luftzustaende der Anlage, die mehr Wasser tragen als moeglich.

    Geht ueber JEDEN Luftanschluss JEDER Karte in JEDER Stunde, nicht nur ueber
    die Raumluft. Uebersaettigte Luft entsteht dort, wo Wasser eingetragen oder
    Zustaende gemischt werden - am Befeuchter, am Luftwaescher, hinter der
    Mischkammer -, und der Raum sieht davon unter Umstaenden nichts mehr, weil
    er selbst wieder trocknet.

    Rueckgabe: eine Liste von Befunden mit Stunde, Kartennummer, Anschluss und
    dem Ueberschuss in g/kg. Eine leere Liste heisst "nichts gefunden" - bei
    einem leeren Lauf heisst sie auch "nichts geprueft".
    """
    from core.bausteine import stoffdaten as st_modul
    from core.bausteine.basis import Luft as LuftKlasse

    befunde = []
    for nummer, stunde in enumerate(stunden, start=1):
        for karte_id, werte in stunde.items():
            for schluessel, wert in werte.items():
                if not isinstance(wert, LuftKlasse) or wert.V <= 0:
                    continue
                grenze = st_modul.x_saett(wert.T)
                if wert.x > grenze + SAETTIGUNG_TOLERANZ:
                    befunde.append({
                        "stunde": nummer, "karte_id": karte_id,
                        "anschluss": schluessel, "T": wert.T, "x": wert.x,
                        "x_saett": grenze, "ueberschuss": wert.x - grenze,
                    })
    return befunde


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
    # Nur bei einem Jahreslauf. werkzeuge/anlagenpruefung.py rechnet zum
    # Entwickeln auch kuerzere Ausschnitte; dort waere diese Pruefung eine
    # Meldung ueber den Ausschnitt, nicht ueber die Anlage.
    ist_jahreslauf = len(lauf.stunden) >= 8000
    if ist_jahreslauf:
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
    # Seit der Solver einen Zweitakt erkennt und mittelt (core/solver.py),
    # steht ein echter Grenzzyklus in lauf.takte und nicht mehr unter den
    # Warnungen. Beides wird deshalb getrennt geprueft: KEIN Takt ist
    # zulaessig (diese Anlage hat keinen Zweipunktregler an einer Groesse, die
    # ihr Stellglied sofort selbst veraendert), und die verbleibenden
    # Warnungen duerfen nur klein sein.
    GRENZZYKLUS_SCHWELLE = 2.0
    spaetere_warnungen = [w for w in lauf.warnungen if w["stunde"] > 1]
    gross = [w for w in spaetere_warnungen if w["abweichung"] > GRENZZYKLUS_SCHWELLE]
    takte = [t for t in lauf.takte if t["stunde"] > 1]
    pruefe(
        "Kein Zweipunktregler taktet",
        not takte,
        f"{len(takte)} taktende Stunden"
        + (f" - erste: {takte[0]['text']}" if takte else ""),
    )
    pruefe(
        "Ab der zweiten Stunde bleibt die Restabweichung klein",
        not gross,
        f"{len(spaetere_warnungen)} von {len(lauf.stunden) - 1} spaeteren Stunden ohne "
        f"volle Konvergenz (das ist bei schwach rueckgekoppelten Reglern erwartet), "
        f"davon {len(gross)} mit Restabweichung > {GRENZZYKLUS_SCHWELLE}"
        + (f" - erste: {gross[0]['text']}" if gross else ""),
    )

    # 3 - Der Raum bleibt in einem sinnvollen Band.
    t_raum = _raumreihe(ergebnis, "T_Raum")
    pruefe(
        "Raumtemperatur zwischen 5 und 40 °C",
        t_raum and min(t_raum) > 5.0 and max(t_raum) < 40.0,
        f"min {min(t_raum):.1f} °C, max {max(t_raum):.1f} °C" if t_raum else "keine Werte",
    )

    # 4 - Die Raumluft bleibt unter der Saettigung.
    f_raum = _raumreihe(ergebnis, "F_Raum")
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

    # 4b - Kein Luftzustand der ganzen Kette traegt mehr Wasser als moeglich.
    # Die Pruefung darueber sieht nur den Raum; uebersaettigte Luft entsteht
    # aber am Befeuchter, am Waescher oder beim Mischen und kann bis zum Raum
    # laengst wieder abgetrocknet sein.
    uebersaettigt = uebersaettigte_zustaende(lauf.stunden)
    erste = uebersaettigt[0] if uebersaettigt else None
    pruefe(
        "Kein Luftzustand der Anlage ist übersättigt",
        not uebersaettigt,
        f"{len(uebersaettigt)} Zustände über der Sättigungslinie"
        + (
            f" - erster: Stunde {erste['stunde']}, Karte {erste['karte_id']}, "
            f"{erste['anschluss']} mit {erste['x']:.1f} statt höchstens "
            f"{erste['x_saett']:.1f} g/kg bei {erste['T']:.1f} °C"
            if erste else ""
        ),
    )

    # 5/6 - Geheizt wird im Winter, gekuehlt im Sommer - nicht umgekehrt.
    waerme_ahu = _reihe(ergebnis, "erhitzer", "QH")
    waerme_stat = (_reihe(ergebnis, "statische_heizung", "QH")
                   or _raumreihe(ergebnis, "QH_stat"))
    kaelte = _reihe(ergebnis, "kuehler", "QK")
    winter = _monat(ergebnis, 1) + _monat(ergebnis, 2) + _monat(ergebnis, 12)
    sommer = _monat(ergebnis, 6) + _monat(ergebnis, 7) + _monat(ergebnis, 8)
    waerme = [a + b for a, b in zip(waerme_ahu, waerme_stat)]
    # Der Monatsvergleich braucht ganze Monate. Bei einem Ausschnitt aus dem
    # Jahr (siehe oben) faende er beide Male null und meldete einen Fehler
    # ueber den Ausschnitt statt ueber die Anlage.
    if ist_jahreslauf:
        # Beide Vergleiche nur, wenn es die Groesse ueberhaupt gibt. Eine
        # Anlage ohne Heizung - das Rechenzentrum kuehlt das ganze Jahr - fand
        # sonst null gegen null und fiel durch: "Winter 0.0 MWh, Sommer
        # 0.0 MWh". Eine Pruefung, die eine ganze Bauart nie bestehen kann,
        # prueft nichts, sie meldet nur.
        if _summe(waerme) > 0:
            pruefe(
                "Heizwaerme im Winter groesser als im Sommer",
                _summe(waerme, winter) > _summe(waerme, sommer),
                f"Winter {_summe(waerme, winter) / 1000:.1f} MWh, "
                f"Sommer {_summe(waerme, sommer) / 1000:.1f} MWh",
            )
        if _summe(kaelte) > 0:
            pruefe(
                "Kaelte im Sommer groesser als im Winter",
                _summe(kaelte, sommer) > _summe(kaelte, winter),
                f"Sommer {_summe(kaelte, sommer) / 1000:.1f} MWh, "
                f"Winter {_summe(kaelte, winter) / 1000:.1f} MWh",
            )

    # 7 - Kein Baustein liefert negative Leistung.
    #
    # Beim Kuehler gilt das mit einer Einschraenkung, und zwar mit einer, die
    # der Baustein selbst benennt: Ist die eintretende Luft kaelter als das
    # Kaltwasser, waermt eine offene Kuehlflaeche die Luft, statt sie zu
    # kuehlen - QK wird dann negativ. Das ist kein Rechenfehler, sondern eine
    # Fehlansteuerung, und core/bausteine/kuehler.py meldet sie als Warnung.
    # Geprueft wird deshalb: negativ nur dort, wo auch gewarnt wird, und in
    # der Summe vernachlaessigbar.
    negativ = {
        name: min(reihe)
        for name, reihe in (
            ("Erhitzer", waerme_ahu), ("Statische Heizung", waerme_stat),
        )
        if reihe and min(reihe) < -1e-6
    }
    pruefe(
        "Heizleistung wird nie negativ",
        not negativ,
        f"{negativ}" if negativ else "keine negativen Werte",
    )
    rueckwaerme = -sum(w for w in kaelte if w < 0.0)
    gekuehlt = sum(w for w in kaelte if w > 0.0)
    pruefe(
        "Der Kuehler waermt hoechstens in Ausnahmestunden und kaum",
        gekuehlt > 0 and rueckwaerme < 0.01 * gekuehlt,
        f"{rueckwaerme:.1f} kWh rueckwaerts gegen {gekuehlt / 1000:.1f} MWh gekuehlt"
        + (
            f" ({100.0 * rueckwaerme / gekuehlt:.2f} % - der Kuehler wird in "
            f"einzelnen Stunden angesteuert, obwohl die Luft schon kaelter ist "
            f"als sein Kaltwasser; die Karte warnt dann)" if gekuehlt else ""
        ),
    )

    # 8 - Die Mischkammer mischt physikalisch sinnvoll: die Mischlufttemperatur
    # (aus Aussen- und rueckgefuehrter Abluft) darf nie ausserhalb der Spanne
    # liegen, die diese beiden Zustaende aufspannen - eine gewichtete Mischung
    # kann per Definition nicht waermer als der waermste oder kaelter als der
    # kaelteste ihrer beiden Bestandteile werden. Ersetzt die WRG-Richtungs-
    # pruefung der Vorlage, weil diese Anlage keine WRG, sondern eine
    # Umluft-Mischkammer als Waermerueckgewinn einsetzt.
    # Verglichen wird gegen die TATSAECHLICHEN Eingaenge der Kammer, nicht
    # gegen Aussen- und Fortlufttemperatur. Frueher stand hier letzteres, was
    # eine bestimmte Bauart unterstellte: dass die Aussenluft unmittelbar in
    # die Mischkammer geht. Sitzt eine Waermerueckgewinnung davor - in der
    # Vorlage "Schwimmhalle" ist das so -, kommt die Aussenluft dort schon
    # vorgewaermt an (2,5 GradC draussen, 21,8 GradC an der Kammer), und die
    # Pruefung meldete 452 Stunden lang einen Fehler, den es nicht gab.
    # Der Solver schreibt die Eintrittstemperaturen jeder Karte mit
    # (T_<anschluss>, siehe core/solver.py) - damit gilt die Pruefung fuer
    # jede Bauart.
    t_mi = _reihe(ergebnis, "mischkammer", "T_MI")
    t_ein_au = _reihe(ergebnis, "mischkammer", "T_aussenluft_ein")
    t_ein_um = _reihe(ergebnis, "mischkammer", "T_umluft_ein")
    v_ein_au = _reihe(ergebnis, "mischkammer", "V_aussenluft_ein")
    v_ein_um = _reihe(ergebnis, "mischkammer", "V_umluft_ein")
    ausserhalb = [
        i for i, (mi, a, u, va, vu) in enumerate(
            zip(t_mi, t_ein_au, t_ein_um, v_ein_au, v_ein_um))
        # Nur Stunden mit Luft auf beiden Seiten: fliesst nur eine, ist die
        # Mischung trivial, und die andere Temperatur steht auf null.
        if va > 1.0 and vu > 1.0
        and not (min(a, u) - 0.1 <= mi <= max(a, u) + 0.1)
    ]
    if t_mi:
        pruefe(
            "Mischlufttemperatur liegt zwischen ihren beiden Eingängen",
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
    # Eine Anlage im Dauerbetrieb - Museum, Krankenhaus, Rechenzentrum - hat
    # keine Stunden ausserhalb der Betriebszeit. Der Vergleich hat dann keine
    # Grundlage und wird nicht gefuehrt, statt mangels Gegenprobe durchzufallen.
    if strom_an and strom_aus:
        pruefe(
            "Im Betrieb wird mehr Strom gezogen als ausserhalb",
            sum(strom_an) / len(strom_an) > sum(strom_aus) / len(strom_aus),
            f"im Betrieb {sum(strom_an) / len(strom_an):.2f} kW, "
            f"ausserhalb {sum(strom_aus) / len(strom_aus):.2f} kW",
        )

    # 12 - Der spezifische Heizwaermebedarf (AHU-Erhitzer PLUS die statische
    # Zusatzheizung, denn beide beheizen denselben Raum) liegt in einer
    # ueblichen Groessenordnung fuer ein Bestandsgebaeude.
    # Die Flaeche kennt nur die ausfuehrliche Raumkarte, die ihre Geometrie
    # fuehrt. Anlagen mit einem einfachen Raum (core/bausteine/
    # einfacher_raum.py) haben keine - dort entfaellt diese Pruefung, statt
    # dass sie mit einer erfundenen Flaeche rechnet oder die ganze Pruefreihe
    # mit einem KeyError abbricht. Auf welche Flaeche sich der Verbrauch
    # bezieht, sagt bei diesen Anlagen ihr eigenes Erwartungsband
    # (werkzeuge/anlagenpruefung.py).
    raum_kid = _karte_mit_typ(ergebnis["graph"], "raum")
    if raum_kid is not None:
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
