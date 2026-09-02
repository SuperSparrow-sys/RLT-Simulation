"""Baut eine kleine Anlage ueber die Speicherschicht und rechnet sie durch.

Kein Test, sondern ein Handgriff zum Nachsehen: Er zeigt jede Verdrahtung, die beim
Ziehen der Pfeile entsteht, und rechnet die Anlage anschliessend 24 Stunden. Damit
faellt auf, wenn ein Pfeil etwas anderes verbindet als gemeint - so wurde die zu
grobe Rolle MESSWERT gefunden.
"""

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))


def main():
    import core.config as cfg

    cfg.DB_PATH = Path(tempfile.mkdtemp()) / "durchstich.db"

    from app import create_app
    from core import anlagen, database, solver

    app = create_app()
    with app.app_context():
        database.init_db()
        projekt = anlagen.projekt_anlegen("Durchstich")
        anlage = anlagen.anlage_anlegen(projekt, "Kleine Anlage")

        def karte(typ, x, y, **p):
            return anlagen.karte_anlegen(anlage, typ, x, y, p)

        wetter = karte("wetter", 0, 0)
        aussen = karte("aussenluft", 150, 0)
        erhitzer = karte("erhitzer", 300, 0, V_nenn=8200.0, QH_max=100.0, dp_nenn=50.0)
        zuluft = karte("ventilator", 450, 0, V_max=8200.0, PE_max=4.9, regelart="F")
        raum = karte("einfacher_raum", 600, 0,
                     spez_transmission=0.5, sollwert_stat=-50.0)
        abluft = karte("ventilator", 600, 200, rolle="abluft",
                       V_max=8200.0, PE_max=3.0, regelart="F")
        fort = karte("fortluft", 150, 200)
        regler = karte("p_regler", 300, 320, xp_2=5.0, sollwert_2=20.0)
        bilanz = karte("bilanz", 800, 200)

        namen = {k["id"]: k["name"] for k in anlagen.als_json(anlage)["karten"]}
        for von, nach in [
            (wetter, aussen), (aussen, erhitzer), (erhitzer, zuluft),
            (zuluft, raum), (raum, abluft), (abluft, fort), (wetter, raum),
            (regler, erhitzer), (zuluft, bilanz), (abluft, bilanz), (erhitzer, bilanz),
        ]:
            pfeil = anlagen.pfeil_anlegen(anlage, von, nach)
            verbindungen = ", ".join(
                f"{v['von_schluessel']} -> {v['nach_schluessel']}"
                for v in pfeil["verbindungen"]
            )
            print(f"{namen[von]:24} -> {namen[nach]:24} {verbindungen}")

        graph = anlagen.lade_graph(anlage)
        beginn = datetime(2024, 1, 15)
        stunden = [
            {
                "zeitpunkt": beginn + timedelta(hours=i), "t_au": 0.0, "x_au": 4.0,
                "str_s": 0.0, "str_o": 0.0, "str_w": 0.0, "str_n": 0.0, "str_h": 0.0,
            }
            for i in range(24)
        ]
        lauf = solver.Solver(graph).starte(stunden)

        print(f"\n{len(lauf.stunden)} Stunden gerechnet, "
              f"{len(lauf.warnungen)} Warnungen")
        print(f"Temperatur nach dem Erhitzer: "
              f"{lauf.stunden[0][erhitzer]['T_aus']:.2f} °C (Sollwert 20)")
        print(f"Raumtemperatur:               "
              f"{lauf.stunden[0][raum]['T_Raum']:.2f} °C")
        print("Bilanz ueber 24 Stunden:      " + ", ".join(
            f"{name} {wert:.2f}" for name, wert in lauf.bilanz.items()))


if __name__ == "__main__":
    main()
