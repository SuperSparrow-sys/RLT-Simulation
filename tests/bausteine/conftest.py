"""Haelt das Bausteinregister zwischen den Tests sauber.

Mehrere Tests melden Wegwerf-Bausteine an. Ohne Wiederherstellung blieben sie
fuer den Rest des Testlaufs im Register und taeuchten in jeder spaeteren
Auswertung von basis.alle() oder basis.nach_gruppen() auf.
"""

import pytest

from core.bausteine import basis


@pytest.fixture(autouse=True)
def register_zuruecksetzen():
    vorher = dict(basis._REGISTER)
    yield
    basis._REGISTER.clear()
    basis._REGISTER.update(vorher)
