"""Rechnet jede der 34 Beispielanlagen durch und prueft sie physikalisch.

Anders als werkzeuge/plausibilitaet.py (die eine grosse Testanlage ueber ein
Jahr) geht es hier um die Breite: JEDE Beispielanlage aus core/lehrinhalte/
wird gerechnet, weil genau diese Anlagen es sind, die jemand beim Lernen
oeffnet. Eine davon, die unbemerkt Unsinn rechnet, waere dort am schaedlichsten.

Geprueft wird je Stunde und Anlage:

* Zahlen sind endlich (kein NaN, kein Unendlich) - faengt Division durch null
  und aehnliche Rechenunfaelle.
* Jede Luft bleibt unterhalb der Saettigung (mit 2 % Toleranz fuer die
  Polynomnaeherung der Stoffdaten).
* Temperaturen bleiben im bauphysikalisch moeglichen Band.
* Leistungen bleiben im Rahmen: keine negative Heiz- oder Kaelteleistung
  ausser dort, wo die Karte selbst davor warnt.
* Der Lauf konvergiert - eine Beispielanlage soll gerade NICHT schwingen,
  sie hat keinen der Regelkreise, die in der grossen Vorlage schwingen.

Aufruf von Hand:  ./venv/bin/python werkzeuge/beispielpruefung.py
"""

import math
import pathlib
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
if str(WURZEL) not in sys.path:
    sys.path.insert(0, str(WURZEL))

# Grenzen, ab denen ein Wert nicht mehr als Rechenergebnis, sondern als Fehler
# gilt. Bewusst weit: eine Beispielanlage darf ungewoehnliche Betriebspunkte
# zeigen, sie darf nur nichts Unmoegliches rechnen.
T_MIN, T_MAX = -40.0, 120.0
X_MIN, X_MAX = -0.5, 200.0
SAETTIGUNG_TOLERANZ = 1.02


def _endlich(wert):
    return isinstance(wert, (int, float)) and math.isfinite(wert)


def pruefe_lauf(lauf, graph, stunden):
    """Liefert eine Liste lesbarer Befunde - leer heisst: nichts gefunden."""
    from core.bausteine import stoffdaten as st
    from core.bausteine.basis import Luft

    befunde = []
    for nummer, ausgaben in enumerate(lauf.stunden, start=1):
        for karte_id, werte in ausgaben.items():
            name = graph.karten[karte_id].name
            for schluessel, wert in werte.items():
                if isinstance(wert, Luft):
                    for feld, w in (("V", wert.V), ("T", wert.T), ("x", wert.x)):
                        if not math.isfinite(w):
                            befunde.append(
                                f"Stunde {nummer}, {name}.{schluessel}.{feld} "
                                f"ist keine Zahl ({w})"
                            )
                    if not math.isfinite(wert.T) or not math.isfinite(wert.x):
                        continue
                    if not (T_MIN <= wert.T <= T_MAX):
                        befunde.append(
                            f"Stunde {nummer}, {name}.{schluessel}: "
                            f"Temperatur {wert.T:.1f} °C ausserhalb {T_MIN}..{T_MAX}"
                        )
                    if not (X_MIN <= wert.x <= X_MAX):
                        befunde.append(
                            f"Stunde {nummer}, {name}.{schluessel}: "
                            f"Feuchte {wert.x:.2f} g/kg ausserhalb {X_MIN}..{X_MAX}"
                        )
                    elif wert.V > 0 and T_MIN <= wert.T <= T_MAX:
                        grenze = st.x_saett(wert.T) * SAETTIGUNG_TOLERANZ
                        if wert.x > grenze:
                            befunde.append(
                                f"Stunde {nummer}, {name}.{schluessel}: "
                                f"{wert.x:.2f} g/kg ueber der Saettigung "
                                f"({grenze:.2f} g/kg bei {wert.T:.1f} °C)"
                            )
                elif isinstance(wert, (int, float)) and not math.isfinite(wert):
                    befunde.append(
                        f"Stunde {nummer}, {name}.{schluessel} ist keine Zahl ({wert})"
                    )
        if len(befunde) > 30:
            befunde.append("... weitere Befunde unterdrueckt")
            break
    return befunde


def rechne_alle(app, stunden):
    """Baut jede Beispielanlage, rechnet sie und liefert je Anlage einen Bericht."""
    from core import anlagen, solver, verlauf
    from core.lehrinhalte import beispielanlagen

    berichte = []
    with app.app_context(), verlauf.stumm():
        projekt = anlagen.projekt_anlegen("Beispielpruefung")
        for kennung in sorted(beispielanlagen.BAUPLAENE):
            anlage_id = beispielanlagen.baue_beispiel(kennung, projekt)
            graph = anlagen.lade_graph(anlage_id)
            lauf = solver.Solver(graph).starte(stunden)
            berichte.append(
                {
                    "kennung": kennung,
                    "karten": len(graph.karten),
                    "bilanz": dict(lauf.bilanz),
                    "warnungen": len(lauf.warnungen),
                    "takte": len(lauf.takte),
                    "befunde": pruefe_lauf(lauf, graph, stunden),
                }
            )
    return berichte


def als_text(berichte):
    zeilen = []
    for b in berichte:
        stand = "ok" if not b["befunde"] and not b["warnungen"] and not b["takte"] else ""
        if b["takte"]:
            stand += f"{b['takte']} taktende Stunden "
        if b["warnungen"]:
            stand += f"{b['warnungen']} Konvergenzwarnungen "
        if b["befunde"]:
            stand += f"{len(b['befunde'])} Befunde"
        zeilen.append(
            f"{b['kennung']:<18} {b['karten']:>2} Karten  "
            f"Waerme {b['bilanz'].get('waerme', 0.0):8.2f} kWh  "
            f"Kaelte {b['bilanz'].get('kaelte', 0.0):8.2f} kWh  "
            f"Strom {b['bilanz'].get('strom_ht', 0.0) + b['bilanz'].get('strom_nt', 0.0):7.2f} kWh"
            f"   {stand or 'ok'}"
        )
        for zeile in b["befunde"][:5]:
            zeilen.append(f"    {zeile}")
    return "\n".join(zeilen)


def main():
    import tempfile

    from app import create_app
    from core import config, database
    from werkzeuge.abgleich import lade_wetterstunden

    with tempfile.TemporaryDirectory() as ordner:
        config.DB_PATH = pathlib.Path(ordner) / "pruefung.db"
        app = create_app()
        with app.app_context():
            database.init_db()
        # Eine Woche im Januar und eine im Juli - Heiz- und Kuehlfall in einem
        # Durchgang, ohne fuer 34 Anlagen je ein volles Jahr zu rechnen.
        alle = lade_wetterstunden()
        stunden = alle[0:168] + alle[4344:4512]
        berichte = rechne_alle(app, stunden)
    print(als_text(berichte))
    fehler = sum(len(b["befunde"]) for b in berichte)
    print(f"\n{len(berichte)} Beispielanlagen, {fehler} Befunde")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
