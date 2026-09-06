"""Kein Luftzustand in der ganzen Kette darf übersättigt sein.

Luft kann nicht mehr Wasser tragen als ihre Sättigungsmenge - alles darüber
fällt als Nebel oder Kondensat aus. Geprüft wurde das bisher nur für die
Raumluft (werkzeuge/plausibilitaet.py, Prüfung 4). Zwischen Befeuchter und
Ventilator, hinter der Mischkammer oder nach der Wärmerückgewinnung konnte
eine Anlage übersättigte Luft führen, ohne dass es auffiel - und genau dort
entsteht sie: ein Befeuchter, der zu viel einträgt, ein Kühler, dessen
Entfeuchtung nicht greift, eine Mischung zweier Zustände dicht an der
Sättigungslinie.
"""

import pytest

from core.bausteine import lade_alle, stoffdaten as st
from core.bausteine.basis import Luft

lade_alle()


def test_saettigungsgrenze_ist_temperaturabhaengig():
    """Grundlage der Prüfung - warme Luft trägt mehr."""
    assert st.x_saett(30.0) > st.x_saett(20.0) > st.x_saett(10.0)


def test_die_pruefung_findet_einen_uebersaettigten_zustand():
    from werkzeuge import plausibilitaet

    # 20 °C tragen rund 14,7 g/kg; 25 g/kg sind unmöglich.
    zustaende = [{1: {"luft_aus": Luft(V=1000.0, T=20.0, x=25.0)}}]
    treffer = plausibilitaet.uebersaettigte_zustaende(zustaende)
    assert treffer, "eine unmögliche Luft wurde nicht gefunden"
    assert treffer[0]["stunde"] == 1


def test_moegliche_zustaende_werden_nicht_gemeldet():
    from werkzeuge import plausibilitaet

    zustaende = [
        {1: {"luft_aus": Luft(V=1000.0, T=20.0, x=10.0)}},
        {1: {"luft_aus": Luft(V=1000.0, T=5.0, x=5.0)}},
        # Genau auf der Sättigungslinie - Nebelgrenze, noch möglich.
        {1: {"luft_aus": Luft(V=1000.0, T=15.0, x=st.x_saett(15.0))}},
    ]
    assert plausibilitaet.uebersaettigte_zustaende(zustaende) == []


def test_ein_leerer_lauf_meldet_nichts_und_prueft_auch_nichts():
    """Die Kehrseite: Eine Prüfung auf einer leeren Reihe besteht immer -
    wer sie benutzt, muss wissen, dass sie dann nichts aussagt."""
    from werkzeuge import plausibilitaet

    assert plausibilitaet.uebersaettigte_zustaende([]) == []
