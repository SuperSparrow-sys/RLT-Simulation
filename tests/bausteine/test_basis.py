import pytest

from core.bausteine import basis


def test_luft_hat_vorgabewerte():
    luft = basis.Luft()
    assert (luft.V, luft.T, luft.x, luft.dp) == (0.0, 0.0, 0.0, 0.0)


def test_registrierung_findet_baustein():
    @basis.registriere
    class Testbaustein(basis.Baustein):
        KENNUNG = "test_dummy"
        NAME = "Testbaustein"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = [basis.Param("a", "A", "kW", 1.0)]
        PORTS = [basis.Port("luft_ein", basis.LUFT, basis.EINGANG, basis.ZULUFT)]
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    assert basis.hole("test_dummy") is Testbaustein
    assert Testbaustein in basis.alle()


def test_doppelte_kennung_wird_gemeldet():
    """Eine doppelt vergebene Kennung darf nicht stillschweigend ueberschreiben."""

    @basis.registriere
    class Erster(basis.Baustein):
        KENNUNG = "test_doppelt"
        NAME = "Erster"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = []
        PORTS = []
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    with pytest.raises(ValueError, match="schon von Erster belegt"):

        @basis.registriere
        class Zweiter(basis.Baustein):
            KENNUNG = "test_doppelt"
            NAME = "Zweiter"
            GRUPPE = "Test"
            SYMBOL = "test.svg"
            PARAMETER = []
            PORTS = []
            AUSGABEN = []

            def berechne(self, ein, p, zustand):
                return {}, zustand


def test_wegwerfbausteine_lecken_nicht_zwischen_tests():
    """Die conftest-Vorrichtung stellt das Register nach jedem Test wieder her."""
    assert "test_dummy" not in {k.KENNUNG for k in basis.alle()}


def test_hole_meldet_unbekannten_typ():
    with pytest.raises(KeyError, match="gibt es nicht"):
        basis.hole("kein_baustein")


def test_vorgabeparameter_teilen_keine_veraenderlichen_werte():
    """Listen und Tabellen muessen je Karte eigene Objekte sein."""

    @basis.registriere
    class MitListe(basis.Baustein):
        KENNUNG = "test_liste"
        NAME = "Mit Liste"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = [
            basis.Param("plan", "Plan", "-", [1.0, 2.0]),
            basis.Param("anteile", "Anteile", "%", {}),
        ]
        PORTS = []
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    erste = MitListe.vorgabeparameter()
    zweite = MitListe.vorgabeparameter()
    erste["plan"].append(3.0)
    erste["anteile"]["luft_aus_1"] = 70.0

    assert zweite["plan"] == [1.0, 2.0]
    assert zweite["anteile"] == {}
    assert MitListe.PARAMETER[0].vorgabe == [1.0, 2.0]


def test_vorgabeparameter_werden_aus_der_deklaration_gebildet():
    @basis.registriere
    class MitVorgabe(basis.Baustein):
        KENNUNG = "test_vorgabe"
        NAME = "Mit Vorgabe"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = [
            basis.Param("V_nenn", "V_nenn", "m³/h", 8200.0),
            basis.Param("art", "Art", "-", "F", auswahl=("F", "D", "-")),
        ]
        PORTS = []
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    assert MitVorgabe.vorgabeparameter() == {"V_nenn": 8200.0, "art": "F"}


def test_druckverlust_steigt_quadratisch():
    """Anlage!S135 - dp_nenn * (V / V_nenn)^2."""
    assert basis.druckverlust(8200.0, 8200.0, 240.0) == pytest.approx(240.0)
    assert basis.druckverlust(4100.0, 8200.0, 240.0) == pytest.approx(60.0)


# -- pruefe_wert()/pruefe_parameter() -------------------------------------

def test_pruefe_wert_lehnt_unbekannten_auswahlwert_ab():
    feld = basis.Param(
        "pumpenart", "Ventil/FU/HD", "-", "H",
        auswahl=(basis.wahl("V", "Ventil (V)"), basis.wahl("F", "FU (F)")),
        darstellung=basis.AUSWAHL,
    )
    meldung = basis.pruefe_wert(feld, "Q")
    assert meldung is not None
    assert "Ventil/FU/HD" in meldung
    assert "V, F" in meldung


def test_pruefe_wert_erlaubt_bekannten_auswahlwert():
    feld = basis.Param(
        "pumpenart", "Ventil/FU/HD", "-", "H",
        auswahl=(basis.wahl("V", "Ventil (V)"), basis.wahl("F", "FU (F)")),
        darstellung=basis.AUSWAHL,
    )
    assert basis.pruefe_wert(feld, "V") is None


def test_pruefe_wert_lehnt_negativen_wert_unter_minimum_ab():
    feld = basis.Param("V_nenn", "V_nenn", "m³/h", 8200.0, minimum=0.0)
    meldung = basis.pruefe_wert(feld, -1.0)
    assert meldung is not None
    assert "V_nenn" in meldung
    assert "0" in meldung


def test_pruefe_wert_lehnt_wert_ueber_maximum_ab():
    feld = basis.Param(
        "absalzverlust", "Absalzverlust", "%", 10.0,
        darstellung=basis.PROZENT, minimum=0.0, maximum=100.0,
    )
    assert basis.pruefe_wert(feld, 150.0) is not None
    assert basis.pruefe_wert(feld, 100.0) is None
    assert basis.pruefe_wert(feld, 0.0) is None


def test_pruefe_wert_lehnt_nicht_numerischen_wert_ab():
    feld = basis.Param("V_nenn", "V_nenn", "m³/h", 8200.0, minimum=0.0)
    meldung = basis.pruefe_wert(feld, "viel")
    assert meldung is not None
    assert "Zahl" in meldung


def test_pruefe_wert_ohne_grenzen_laesst_alles_durch():
    """Wo es keine sinnvolle Grenze gibt (z.B. eine Preisangabe), wird keine
    erfunden - dort ist jeder Wert zulaessig."""
    feld = basis.Param("preis_waerme", "Wärme", "EUR/MWh", 50.0)
    assert basis.pruefe_wert(feld, -500.0) is None
    assert basis.pruefe_wert(feld, 1e9) is None


def test_pruefe_parameter_prueft_nur_uebergebene_und_bekannte_schluessel():
    @basis.registriere
    class TestPruefung(basis.Baustein):
        KENNUNG = "test_pruefung"
        NAME = "Testpruefung"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = [
            basis.Param("V_nenn", "V_nenn", "m³/h", 100.0, minimum=0.0),
            basis.Param("bezeichnung", "Bezeichnung", "-", "x"),
        ]
        PORTS = []
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    # Gueltig -> kein Fehler.
    assert basis.pruefe_parameter(TestPruefung, {"V_nenn": 50.0}) == {}
    # Ungueltig -> genau der betroffene Schluessel steht im Ergebnis.
    fehler = basis.pruefe_parameter(TestPruefung, {"V_nenn": -1.0})
    assert set(fehler) == {"V_nenn"}
    # Ein der Karte unbekannter Schluessel wird nicht geprueft (kein KeyError).
    assert basis.pruefe_parameter(TestPruefung, {"unbekannt": 1}) == {}
    # Ein Feld ohne Grenzen bleibt unbeanstandet, auch bei einem Fehler daneben.
    fehler = basis.pruefe_parameter(TestPruefung, {"V_nenn": -1.0, "bezeichnung": "irgendwas"})
    assert set(fehler) == {"V_nenn"}


def test_druckverlust_ohne_nennvolumenstrom_ist_null():
    assert basis.druckverlust(5000.0, 0.0, 240.0) == 0.0


def test_bedarf_reicht_volumenstrom_standardmaessig_durch():
    @basis.registriere
    class Durchreiche(basis.Baustein):
        KENNUNG = "test_durchreiche"
        NAME = "Durchreiche"
        GRUPPE = "Test"
        SYMBOL = "test.svg"
        PARAMETER = []
        PORTS = [
            basis.Port("luft_ein", basis.LUFT, basis.EINGANG, basis.ZULUFT),
            basis.Port("luft_aus", basis.LUFT, basis.AUSGANG, basis.ZULUFT),
        ]
        AUSGABEN = []

        def berechne(self, ein, p, zustand):
            return {}, zustand

    assert Durchreiche().bedarf({"luft_aus": 5000.0}, {}) == {"luft_ein": 5000.0}


# -- Darstellung ------------------------------------------------------------
#
# Der Bugreport: 05:00 Uhr stand im Parameterfenster als 0,20833333333333334 -
# der rohe Tagesanteil der Excel, ungefiltert durchgereicht. Diese Tests
# sichern zweierlei ab: dass uhrzeit_anzeigen()/uhrzeit_einlesen() korrekt und
# zueinander invers sind, und dass keine der beiden Richtungen den
# gespeicherten Wert veraendert - nur die ANZEIGE wird gerundet.

def test_uhrzeit_anzeigen_formatiert_den_bugreport_fall():
    assert basis.uhrzeit_anzeigen(5.0 / 24.0) == "05:00"
    assert basis.uhrzeit_anzeigen(22.0 / 24.0) == "22:00"


def test_uhrzeit_anzeigen_rundet_auf_die_minute():
    assert basis.uhrzeit_anzeigen(0.0) == "00:00"
    assert basis.uhrzeit_anzeigen(0.5) == "12:00"
    assert basis.uhrzeit_anzeigen(23.98 / 24.0) == "23:59"
    # Rundet ueber Mitternacht hinweg statt auf "24:00" zu laufen.
    assert basis.uhrzeit_anzeigen(23.999 / 24.0) == "00:00"


def test_uhrzeit_einlesen_ist_die_kehrfunktion():
    assert basis.uhrzeit_einlesen("05:00") == pytest.approx(5.0 / 24.0)
    assert basis.uhrzeit_einlesen("22:00") == pytest.approx(22.0 / 24.0)
    assert basis.uhrzeit_einlesen("00:00") == 0.0


def test_uhrzeit_hin_und_zurueck_ist_auf_die_minute_verlustfrei():
    for text in ("00:00", "05:00", "12:34", "22:00", "23:59"):
        assert basis.uhrzeit_anzeigen(basis.uhrzeit_einlesen(text)) == text


def test_uhrzeit_anzeigen_veraendert_den_uebergebenen_wert_nicht():
    """Anzeige-Rundung darf den Aufrufer nie ueberraschen: derselbe Tagesanteil
    liefert vorher wie nachher exakt denselben Wert."""
    wert = 5.0 / 24.0
    vorher = wert
    basis.uhrzeit_anzeigen(wert)
    assert wert == vorher
    assert wert == 5.0 / 24.0  # keine Gleitkomma-Verschiebung durch den Aufruf


def test_wochenzeitplan_speichert_den_exakten_tagesanteil():
    """Die Vorgabe eines Uhrzeit-Parameters bleibt der volle Excel-Bruch - die
    siebzehn Nachkommastellen aus dem Bugreport sind der GESPEICHERTE Wert und
    duerfen sich durch die Darstellungsangabe nicht aendern."""
    from core.bausteine.wochenzeitplan import Wochenzeitplan

    vorgaben = Wochenzeitplan.vorgabeparameter()
    assert vorgaben["von_montag"] == 5.0 / 24.0
    assert vorgaben["bis_montag"] == 22.0 / 24.0
    # Die Kartendeklaration selbst sagt, dass es sich um eine Uhrzeit handelt.
    feld = next(p for p in Wochenzeitplan.PARAMETER if p.schluessel == "von_montag")
    assert feld.darstellung == basis.UHRZEIT


def test_alle_parameter_deklarieren_eine_darstellung_und_ganzzahlige_dezimalstellen():
    """Jeder der 136 Parameter muss eine gueltige Darstellungsangabe tragen -
    sonst weiss das Parameterfenster nicht, wie es ihn zeigen soll."""
    from core.bausteine import lade_alle

    lade_alle()
    gueltig = {
        basis.ZAHL, basis.PROZENT, basis.UHRZEIT, basis.AUSWAHL,
        basis.TEXTLISTE, basis.ZEITREIHE, basis.MONATSWERTE,
        basis.ZEITRAEUME, basis.ANTEILE,
    }
    anzahl = 0
    for klasse in basis.alle():
        for p in klasse.PARAMETER:
            anzahl += 1
            assert p.darstellung in gueltig, f"{klasse.KENNUNG}.{p.schluessel}"
            assert isinstance(p.dezimalstellen, int)
    assert anzahl == 136


def test_alle_auswahl_parameter_tragen_wert_und_label():
    """Jeder Auswahlparameter deklariert seine Kuerzel SELBST mit lesbarer
    Beschriftung (wahl()) - das Parameterfenster liest nur noch feld.auswahl
    und braucht kein Sonderwissen ueber einzelne Kartentypen mehr."""
    from core.bausteine import lade_alle

    lade_alle()
    gefunden = 0
    for klasse in basis.alle():
        for p in klasse.PARAMETER:
            if p.darstellung != basis.AUSWAHL:
                continue
            assert p.auswahl, f"{klasse.KENNUNG}.{p.schluessel} hat keine Auswahl"
            for eintrag in p.auswahl:
                gefunden += 1
                assert set(eintrag) == {"wert", "label"}, (
                    f"{klasse.KENNUNG}.{p.schluessel}: {eintrag!r}"
                )
                assert eintrag["wert"] and eintrag["label"]
    assert gefunden == 10  # 2 (Dampfart) + 3 (Pumpenart) + 3 (Regelart) + 2 (Rolle)


def test_wahl_erzeugt_ein_json_taugliches_dict():
    assert basis.wahl("E", "Elektrisch (E)") == {"wert": "E", "label": "Elektrisch (E)"}


def test_pumpenart_hd_heisst_hochdruck():
    """Anlage!AA12 beschriftet die drei Werte 'Ventil/FU/HD' in dieser
    Reihenfolge - H steht fuer Hochdruck, nicht geraten."""
    from core.bausteine.luftwaescher import Luftwaescher

    feld = next(p for p in Luftwaescher.PARAMETER if p.schluessel == "pumpenart")
    beschriftungen = {e["wert"]: e["label"] for e in feld.auswahl}
    assert beschriftungen == {
        "V": "Ventil (V)",
        "F": "Frequenzumrichter (F)",
        "H": "HD (Hochdruck)",
    }


def test_auswahlwerte_stimmen_mit_dem_erlaubten_bereich_der_berechnung_ueberein():
    """Jeder in der Karte erlaubte Wert (auswahl) muss auch tatsaechlich einer
    der Werte sein, den berechne() unterscheidet - sonst waere eine Auswahl im
    Fenster moeglich, die die Karte gar nicht kennt."""
    from core.bausteine.dampfbefeuchter import Dampfbefeuchter
    from core.bausteine.luftwaescher import Luftwaescher
    from core.bausteine.ventilator import Ventilator

    def werte(klasse, schluessel):
        feld = next(p for p in klasse.PARAMETER if p.schluessel == schluessel)
        return {e["wert"] for e in feld.auswahl}

    assert werte(Dampfbefeuchter, "dampfart") == {"E", "F"}
    assert werte(Luftwaescher, "pumpenart") == {"V", "F", "H"}
    assert werte(Ventilator, "regelart") == {"F", "D", "-"}
    assert werte(Ventilator, "rolle") == {"zuluft", "abluft"}


# -- Verstaendliche Beschriftungen -----------------------------------------
#
# Ziel des Programms ist, dass jemand ohne Vorkenntnisse damit eine
# Lueftungsanlage auslegen kann. Die Karten stammen aber aus einer
# Excel-Mappe und trugen deren Kuerzel (V_nenn, QH_max, Xp, T_KW_mittel) und
# teils gar keine Einheit. Die folgenden Tests halten fest, was dabei
# herausgekommen ist - inhaltlich, nicht als Wortlautprotokoll.


def test_jeder_parameter_nennt_seine_einheit_oder_sagt_dimensionslos():
    """Ein leeres Einheitenfeld laesst offen, ob 0,4 nun 0,4 % oder 40 % sind -
    genau daran ist das Tageslastprofil aufgefallen. Zulaessig leer bleibt die
    Einheit nur dort, wo die Darstellungsart sie selbst mitbringt: eine Uhrzeit
    (HH:MM), Monatsschalter, Zeitraeume und freie Textfelder. Auswahlfelder
    tragen weiter den Platzhalter "-", den das Fenster ausblendet."""
    from core.bausteine import lade_alle

    lade_alle()
    ohne_eigene_einheit = {
        basis.UHRZEIT, basis.MONATSWERTE, basis.ZEITRAEUME, basis.TEXTLISTE,
    }
    for klasse in basis.alle():
        for p in klasse.PARAMETER:
            if p.darstellung in ohne_eigene_einheit:
                continue
            if p.darstellung == basis.AUSWAHL:
                assert p.einheit == "-", f"{klasse.KENNUNG}.{p.schluessel}"
                continue
            assert p.einheit and p.einheit != "-", (
                f"{klasse.KENNUNG}.{p.schluessel} hat keine Einheit"
            )


def test_lastgang_ist_als_anteil_gekennzeichnet():
    """Der Anlass der ganzen Durchsicht: 72 Felder mit Werten wie 0,4 und 1,0,
    ohne jede Einheit. Dass das Anteile der Nennlast sind, muss dranstehen."""
    from core.bausteine.tageslastprofil import Tageslastprofil

    for schluessel in ("lastgang_1", "lastgang_2", "lastgang_3"):
        feld = next(p for p in Tageslastprofil.PARAMETER if p.schluessel == schluessel)
        assert feld.einheit == "Anteil 0–1"
    erster = next(p for p in Tageslastprofil.PARAMETER if p.schluessel == "lastgang_1")
    assert "Nennlast" in erster.hinweis


def test_keine_beschriftung_ist_nur_ein_kuerzel_aus_der_mappe():
    """Die Kuerzel duerfen als Gedaechtnisstuetze in Klammern stehenbleiben,
    aber nie allein die ganze Beschriftung sein."""
    from core.bausteine import lade_alle

    lade_alle()
    kuerzel = {
        "V_nenn", "V_max", "dp_nenn", "dp_max", "dp_konst", "dp_WRG_nenn",
        "dp_Byp_nenn", "QH_max", "QH_nenn", "QK_nenn", "T_KW_mittel", "PE_max",
        "Xp", "WWB", "Nennbel.", "Zirk_PU", "Zirk. VL-RL", "Speichervol.",
        "sp. Leistung", "max. Bef.Leist", "Dampftemp.", "min. T_Raum",
        "max. T_Raum", "bei T_AU", "min. T_ZU", "max. T_ZU", "Strom Leist.",
        "HT von", "HT bis", "Ventil/FU/HD", "FU/DD/-", "E-/Fremddampf",
        "Wärmeüberg.", "Nennbel", "Strom HT", "Strom NT",
    }
    treffer = [
        f"{klasse.KENNUNG}.{p.schluessel}: {p.label!r}"
        for klasse in basis.alle()
        for p in klasse.PARAMETER
        if p.label in kuerzel
    ]
    assert treffer == []


def test_gleichartige_anschluesse_einer_karte_sind_unterscheidbar():
    """Ein Raum hat zehn Signaleingaenge mit der Rolle 'Messwert'. Ohne eigene
    Beschriftung stuenden im Parameterfenster zehn gleichlautende Zeilen, und
    niemand koennte den Pfeil fuer die Aussentemperatur von dem fuer die
    Suedstrahlung unterscheiden. Ausgenommen sind Anschluesse, deren
    Unterscheidung ohnehin eine laufende Nummer ist: dynamische Gruppen
    (dynamisch=True) und durchnummerierte Anschluesse wie die zehn Spalten des
    Datenloggers - das Parameterfenster haengt dort die Nummer aus dem
    Schluessel an (static/js/panel.js, bauePortliste)."""
    import re

    from core.bausteine import lade_alle

    lade_alle()
    for klasse in basis.alle():
        gesehen = {}
        for port in klasse.PORTS:
            if port.dynamisch or re.search(r"_\d+$", port.schluessel):
                continue
            label = basis.port_label(klasse, port.schluessel, port.rolle)
            assert label != port.schluessel, (
                f"{klasse.KENNUNG}.{port.schluessel} zeigt seinen rohen Schlüssel"
            )
            schluessel = (port.richtung, port.art, label)
            assert schluessel not in gesehen, (
                f"{klasse.KENNUNG}: {port.schluessel} und {gesehen.get(schluessel)} "
                f"heißen beide „{label}“"
            )
            gesehen[schluessel] = port.schluessel


def test_parameter_ohne_wirkung_sind_als_solche_gekennzeichnet():
    """Fuenf Parameter stehen an ihrer Karte, gehen aber in keine Formel ein -
    sie stammen aus der Excel-Mappe, die sie ebenfalls nur danebenstellt.
    Solange sie da sind, muessen sie das Merkmal `ohne_wirkung` tragen: das
    Parameterfenster zeigt sie daraufhin als festen Wert statt als
    Eingabefeld (static/js/panel.js, zeileOhneWirkung). Ein beschreibbares
    Feld ohne Wirkung laedt dazu ein, etwas einzutragen und auf eine
    Aenderung zu warten, die nie kommt - dann sucht ein Anfaenger den Fehler
    bei sich.

    Die Liste ist zugleich die vollstaendige: kommt ein sechster hinzu oder
    wird einer davon doch gerechnet, faellt es hier auf.

    * beleuchtung.nennbeleuchtung  - Anlage!AK134 rechnet nur mit AK132*AH115
    * raum.aw_anteil_e             - geometrie() kennt nur die Seiten a bis d
    * sequenzregler.xp             - Anlage!T140 teilt fest durch 10
    * kaskade.xp                   - Anlage!Q140 teilt fest durch 3
    * bilanz.preis_strom_leistung  - core.ergebnisse.BILANZ kennt ihn nicht
    """
    from core.bausteine import lade_alle

    lade_alle()
    erwartet = {
        ("beleuchtung", "nennbeleuchtung"),
        ("raum", "aw_anteil_e"),
        ("sequenzregler", "xp"),
        ("kaskade", "xp"),
        ("bilanz", "preis_strom_leistung"),
    }
    gefunden = {
        (klasse.KENNUNG, p.schluessel)
        for klasse in basis.alle()
        for p in klasse.PARAMETER
        if p.ohne_wirkung
    }
    assert gefunden == erwartet

    # Ein fester Wert ohne Begruendung waere nur raetselhaft - jeder von ihnen
    # sagt im Hinweis, was stattdessen gerechnet wird.
    for kennung, schluessel in sorted(erwartet):
        feld = next(
            p for p in basis.hole(kennung).PARAMETER if p.schluessel == schluessel
        )
        assert feld.hinweis.startswith("Wird nicht gerechnet:"), f"{kennung}.{schluessel}"


def test_hinweise_sind_kurze_saetze_und_nicht_ueberall():
    """Der Hinweis traegt nur, solange er die Ausnahme bleibt: stuende an jedem
    der 136 Parameter einer, laese ihn niemand mehr. Und er gehoert unter ein
    Eingabefeld, nicht in einen Absatz."""
    from core.bausteine import lade_alle

    lade_alle()
    alle = [p for klasse in basis.alle() for p in klasse.PARAMETER]
    mit_hinweis = [p for p in alle if p.hinweis]
    assert 0 < len(mit_hinweis) < len(alle) / 2
    for p in mit_hinweis:
        assert len(p.hinweis) <= 320, f"{p.schluessel}: {len(p.hinweis)} Zeichen"


def test_port_label_zieht_die_karte_der_rolle_vor():
    """Die Reihenfolge der Quellen - erst was die Karte selbst sagt, zuletzt
    die allgemeine Rolle."""
    from core.bausteine import lade_alle

    lade_alle()
    raum = basis.hole("raum")
    # PORT_LABEL vor der Rolle
    assert basis.port_label(raum, "QH_S", basis.MESSWERT) == "Sonneneinstrahlung Süd (W/m²)"
    # AUSGABE_LABEL, wo kein PORT_LABEL steht
    assert basis.port_label(raum, "T_Raum", basis.MESSWERT) == "Raumtemperatur (°C)"
    # gleichnamiger Parameter
    hysterese = basis.hole("hysterese_regler")
    assert basis.port_label(hysterese, "istwert", basis.ISTWERT) == "Istwert (fest)"
    # zuletzt die Rolle
    ventilator = basis.hole("ventilator")
    assert basis.port_label(ventilator, "luft_ein", basis.ZULUFT) == "Zuluft"
