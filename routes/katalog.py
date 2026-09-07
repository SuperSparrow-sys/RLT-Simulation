"""Der Anlagenkatalog.

Eigenes Blueprint, wie routes/lehre.py: Die Seite gehoert weder zu den
Projekten (routes/anlagen.py) noch zu den allgemeinen Seiten (routes/pages.py),
sondern ist ein eigener Bereich - der einzige Ort, an dem die zwoelf
mitgelieferten Anlagen ueberhaupt sichtbar sind.

Die Seite wird SERVERSEITIG gefuellt, nicht ueber einen Abruf im Browser. Ihr
Inhalt steht fest, sobald das Programm laeuft: Es sind dieselben zwoelf
Vorlagen bei jedem Aufruf. Ein Abruf danach waere ein zweiter Weg zu
denselben Daten - er braucht einen zweiten Umlauf, zeigt bis dahin eine leere
Seite, und er laesst sich nicht pruefen, ohne einen Browser zu starten. Die
Suche bleibt im Browser (static/js/anlagen.js); sie kommt zu einer Seite
hinzu, die auch ohne sie vollstaendig ist.
"""

from flask import Blueprint, render_template

from core import vorlagen

bp = Blueprint("katalog", __name__)

#: Die Reihenfolge der Gruppen ist gesetzt, nicht alphabetisch: Wer eine
#: Anlage sucht, sucht meistens die gewoehnliche. Zuletzt stehen die beiden
#: Referenzanlagen, die keine Auslegung sind, sondern eine Nachbildung der
#: Excel-Mappe und ein Pruefstand.
GRUPPEN = (
    ("Komfortlüftung",
     "Der Regelfall: Menschen, Betriebszeiten, Wärmerückgewinnung."),
    ("Sonderbau",
     "Feuchte, Hygiene oder stoßweise Belegung bestimmen die Anlage."),
    ("Technik und Industrie",
     "Die Last kommt aus der Nutzung, nicht aus dem Wetter."),
    ("Referenz",
     "Kein Entwurf, sondern Vergleichsmaßstab: die nachgebaute Excel-Mappe "
     "und der Prüfstand, an dem jeder Kartentyp vorkommt."),
)

#: Wie die Erwartungsbänder heißen, wenn sie jemand liest.
BAND_LABEL = {
    "heizwaerme_kwh_m2a": ("Heizwärme", "kWh/(m²·a)"),
    "kaelte_kwh_m2a": ("Kälte", "kWh/(m²·a)"),
    "sfp_w_m3h": ("SFP", "W/(m³/h)"),
    "luftwechsel_1h": ("Luftwechsel", "1/h"),
}


@bp.route("/anlagen")
def seite():
    katalog = vorlagen.alle()
    bekannt = [name for name, _ in GRUPPEN]
    uebrige = sorted(
        {v["gruppe"] for v in katalog.values() if v["gruppe"] not in bekannt}
    )
    gruppen = list(GRUPPEN) + [(name, "") for name in uebrige]

    return render_template(
        "anlagen.html",
        gruppen=[
            (
                name,
                hinweis,
                sorted(
                    (
                        (kennung, v) for kennung, v in katalog.items()
                        if v["gruppe"] == name
                    ),
                    key=lambda paar: paar[1]["name"],
                ),
            )
            for name, hinweis in gruppen
        ],
        anzahl=len(katalog),
        band_label=BAND_LABEL,
    )
