"""Haelt das Bausteinregister zwischen den Tests sauber.

Mehrere Tests melden Wegwerf-Bausteine an. Ohne Wiederherstellung blieben sie
fuer den Rest des Testlaufs im Register und tauchten in jeder spaeteren
Auswertung von basis.alle() oder basis.nach_gruppen() auf.

Die Bausteinbibliothek wird dafuer schon hier geladen, nicht erst im ersten
Test, der sie braucht. Der Grund ist die Reihenfolge: Die Vorrichtung sichert
das Register VOR dem Test und stellt es danach wieder her. Waere die Bibliothek
zu diesem Zeitpunkt noch nicht geladen, sicherte sie ein leeres Register - der
erste Test, der lade_alle() aufruft, fuellte es, und die Wiederherstellung
raeumte es danach wieder ab. Ein zweites lade_alle() bringt es nicht zurueck,
weil Python die einmal importierten Module zwischenspeichert und der
Registrierungs-Dekorator daher kein zweites Mal laeuft. Der Rest der Datei sah
dann ein halb leeres Register.

Beim Lauf der ganzen Testreihe fiel das nicht auf, weil andere Testmodule die
Bibliothek vorher importiert hatten - der Fehler zeigte sich nur, wenn man
tests/bausteine/ allein aufrief. Genau dann, wenn man an den Bausteinen
arbeitet.
"""

import pytest

from core.bausteine import basis, lade_alle

lade_alle()


@pytest.fixture(autouse=True)
def register_zuruecksetzen():
    vorher = dict(basis._REGISTER)
    yield
    basis._REGISTER.clear()
    basis._REGISTER.update(vorher)
