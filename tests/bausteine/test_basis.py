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


def test_hole_meldet_unbekannten_typ():
    with pytest.raises(KeyError, match="gibt es nicht"):
        basis.hole("kein_baustein")


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
