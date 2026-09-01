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
