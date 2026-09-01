"""Erklärbereich: eine Erklärung und eine lauffähige Beispielanlage je Kartentyp.

Zwei Module:

* erklaerungen.py  - der beschreibende Text je Kartentyp (Prosa, von Hand
  geschrieben, auf Grundlage der jeweiligen core/bausteine/<typ>.py-Datei).
  Parameter, Anschlüsse, Gruppe und Symbol werden NICHT hier dupliziert,
  sondern zur Anfragezeit aus der lebenden Bausteinklasse gelesen
  (core/bausteine/basis.py) - siehe routes/lehre.py. So kann ein Text nie
  von den tatsächlichen Feldern einer Karte abweichen.

* beispielanlagen.py - baut zu jedem Kartentyp eine kleine, rechenbare Anlage,
  direkt über core.anlagen (denselben Weg, den auch core/vorlagen/ax_sim_2_1.py
  nutzt).
"""
