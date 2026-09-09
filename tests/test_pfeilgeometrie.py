"""Die Geometrie der Pfeile - gerechnet, nicht am Wortlaut geprueft.

static/js/pfeile.js rechnet aus Kartenlagen die Bahn eines Pfeils aus. Das
laesst sich nicht sinnvoll am Quelltext ablesen: Ob eine Bahn eine Karte
senkrecht verlaesst oder ob sich acht Pfeile auf einer Kante auffaechern, ist
eine Aussage ueber Zahlen. Diese Tests fuehren die reinen Rechenfunktionen
deshalb in node aus und pruefen ihre Ergebnisse.

node ist kein Erfordernis des Projekts (die Anwendung laeuft im Browser) -
fehlt es, werden diese Tests uebersprungen. Der Rest der Reihe deckt die
Oberflaeche weiter ueber das ausgelieferte HTML und den Wortlaut der Skripte
ab, wie an anderer Stelle beschrieben.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
PFEILE_JS = Path(__file__).resolve().parent.parent / "static" / "js" / "pfeile.js"

pytestmark = pytest.mark.skipif(NODE is None, reason="node ist nicht vorhanden")


def rechne(auftrag):
    """Fuehrt pfeile.js in node aus und wertet 'auftrag' darin aus.

    Die Datei legt nur ein Objekt an und ruft beim Laden nichts auf; sie
    braucht also weder ein Fenster noch ein Dokument, solange nur die
    Rechenfunktionen benutzt werden.
    """
    skript = (
        PFEILE_JS.read_text(encoding="utf-8")
        + "\n;(function () {\n"
        + auftrag
        + "\n})();\n"
    )
    fertig = subprocess.run(
        [NODE, "--input-type=commonjs", "-e", skript],
        capture_output=True, text=True, timeout=30,
    )
    assert fertig.returncode == 0, fertig.stderr
    return json.loads(fertig.stdout)


KARTE = "{ id: %d, pos_x: %d, pos_y: %d, _breite: 190, _hoehe: 96 }"


def test_die_kante_richtet_sich_nach_der_lage_des_ziels():
    """Liegt das Ziel rechts, geht der Pfeil rechts hinaus und links hinein;
    liegt es darunter, unten hinaus und oben hinein. Ohne diese Unterscheidung
    schlug jeder Pfeil einen Bogen quer durch die Karten dazwischen."""
    ergebnis = rechne(f"""
      const a = {KARTE % (1, 0, 0)};
      const rechts = {KARTE % (2, 400, 10)};
      const unten  = {KARTE % (3, 10, 400)};
      const links  = {KARTE % (4, -400, 10)};
      const oben   = {KARTE % (5, 10, -400)};
      console.log(JSON.stringify({{
        rechts: Pfeile.kanten(a, rechts),
        unten: Pfeile.kanten(a, unten),
        links: Pfeile.kanten(a, links),
        oben: Pfeile.kanten(a, oben),
      }}));
    """)
    assert ergebnis["rechts"] == {"kanteVon": "rechts", "kanteNach": "links"}
    assert ergebnis["unten"] == {"kanteVon": "unten", "kanteNach": "oben"}
    assert ergebnis["links"] == {"kanteVon": "links", "kanteNach": "rechts"}
    assert ergebnis["oben"] == {"kanteVon": "oben", "kanteNach": "unten"}


def test_pfeile_auf_derselben_kante_faechern_auf():
    """Vorher endeten ALLE Pfeile einer Karte im selben Punkt - der Mitte
    ihrer Kante. An der Waermerueckgewinnung der AX_SIM 2.1 laufen dort sieben
    Wege zusammen; sie lagen als Buendel uebereinander."""
    ergebnis = rechne(f"""
      const k = {KARTE % (1, 0, 0)};
      const werte = {{}};
      for (const anzahl of [1, 2, 3, 7]) {{
        werte[anzahl] = [];
        for (let i = 0; i < anzahl; i++) {{
          werte[anzahl].push(Pfeile.versatz(k, "oben", i, anzahl));
        }}
      }}
      console.log(JSON.stringify(werte));
    """)
    # Ein einzelner Pfeil sitzt genau in der Mitte der 190 Punkte breiten Karte.
    assert ergebnis["1"] == [95.0]
    for anzahl in ("2", "3", "7"):
        werte = ergebnis[anzahl]
        assert len(set(werte)) == len(werte), (anzahl, werte)          # alle verschieden
        assert werte == sorted(werte), (anzahl, werte)                 # der Reihe nach
        assert all(0 <= w <= 190 for w in werte), (anzahl, werte)      # auf der Karte
        mitte = sum(werte) / len(werte)
        assert abs(mitte - 95.0) < 1e-9, (anzahl, mitte)               # um die Mitte


def test_die_bahn_verlaesst_beide_karten_senkrecht():
    """Vorher lagen die Kontrollpunkte auf halber Strecke der Hauptachse: Die
    Bahn trat schraeg aus der Karte und schwenkte kurz vor dem Ziel wieder
    ein - der Knick, der auf dem Schema als Fehler gelesen wurde."""
    ergebnis = rechne("""
      const a = { x: 100, y: 50 };
      const b = { x: 120, y: 400 };
      const d = Pfeile.bahnPunkte(a, b, Pfeile.NORMALE.unten, Pfeile.NORMALE.oben);
      const zahlen = d.match(/-?\\d+(\\.\\d+)?/g).map(Number);
      console.log(JSON.stringify(zahlen));
    """)
    ax, ay, c1x, c1y, c2x, c2y, bx, by = ergebnis
    assert (ax, ay) == (100, 50) and (bx, by) == (120, 400)
    # Erster Kontrollpunkt senkrecht unter dem Start, zweiter senkrecht ueber
    # dem Ziel - dieselbe x-Lage wie ihr jeweiliger Endpunkt.
    assert c1x == ax and c1y > ay
    assert c2x == bx and c2y < by


def test_die_spitze_steht_am_ziel_und_zeigt_hinein():
    """Ohne sie war einem Pfeil nicht anzusehen, wohin er zeigt - bei einem
    Regelweg (wer stellt wen?) ist das gerade die Auskunft, auf die es
    ankommt."""
    ergebnis = rechne("""
      const b = { x: 300, y: 200 };
      const d = Pfeile.spitzePunkte(b, Pfeile.NORMALE.links, 10);
      console.log(JSON.stringify(d.match(/-?\\d+(\\.\\d+)?/g).map(Number)));
    """)
    lx, ly, sx, sy, rx, ry = ergebnis
    # Die Spitze selbst sitzt auf dem Zielpunkt.
    assert (sx, sy) == (300, 200)
    # Die Karte liegt rechts (Kante "links"), der Pfeil kommt also von links:
    # beide Schenkel liegen links vom Ziel und symmetrisch darueber/darunter.
    assert lx < sx and rx < sx
    assert abs((ly - sy) + (ry - sy)) < 1e-9
    assert abs(ly - ry) > 4      # eine sichtbare Oeffnung, kein Strich


def test_die_spitze_waechst_mit_der_strichstaerke():
    """Eine feste Groesse liess die Spitze eines Luftwegs (3,5 Punkte Strich)
    zu einem Querbalken verschmelzen, waehrend sie an einem Meldeweg (1,2)
    ueberdimensioniert wirkte."""
    ergebnis = rechne("""
      console.log(JSON.stringify({
        duenn: Pfeile.spitzenlaenge(1.2),
        mittel: Pfeile.spitzenlaenge(2),
        dick: Pfeile.spitzenlaenge(3.5),
        absurd: Pfeile.spitzenlaenge(20),
      }));
    """)
    assert ergebnis["duenn"] < ergebnis["dick"]
    assert ergebnis["duenn"] >= 7      # darunter nicht mehr als Spitze erkennbar
    assert ergebnis["absurd"] <= 14    # und nie groesser als eine halbe Karte


def test_die_bahn_laeuft_bis_in_die_spitze():
    """Zuerst endete die Bahn ein Stueck vor der Karte, damit die offene
    Spitze nicht auf der eigenen Linie liegt. Das Ergebnis war ein Winkel, der
    neben seinem Strich schwebte - Strich und Spitze passten nicht zusammen.
    Wie beim Vor-/Zurueck-Pfeil eines Browsers laeuft der Schaft jetzt bis
    zwischen die Schenkel."""
    quelle = PFEILE_JS.read_text(encoding="utf-8")
    assert "spitzenluecke" not in quelle, "die Luecke ist wieder da"

    ergebnis = rechne("""
      const a = { x: 100, y: 50 };
      const b = { x: 100, y: 400 };
      const d = Pfeile.bahnPunkte(a, b, Pfeile.NORMALE.unten, Pfeile.NORMALE.oben);
      const zahlen = d.match(/-?\\d+(\\.\\d+)?/g).map(Number);
      const spitze = Pfeile.spitzePunkte(b, Pfeile.NORMALE.oben, 10);
      console.log(JSON.stringify({
        ende: zahlen.slice(-2),
        spitze: spitze.match(/-?\\d+(\\.\\d+)?/g).map(Number).slice(2, 4),
      }));
    """)
    # Das Ende der Bahn und die Spitze der Spitze sind derselbe Punkt.
    assert ergebnis["ende"] == ergebnis["spitze"] == [100, 400]


def test_die_belegung_zaehlt_beide_enden_einer_kante():
    """Der Platz eines Pfeils auf einer Kante haengt davon ab, wieviele andere
    dieselbe Kante benutzen - das steht erst fest, wenn alle Kanten bestimmt
    sind. Deshalb zwei Durchgaenge."""
    ergebnis = rechne(f"""
      const ziel = {KARTE % (9, 400, 200)};
      const wege = [];
      for (const [i, y] of [[1, 0], [2, 200], [3, 400]].entries()) {{
        const von = {{ id: y[0], pos_x: 0, pos_y: y[1], _breite: 190, _hoehe: 96 }};
        wege.push({{ von, nach: ziel, ...Pfeile.kanten(von, ziel) }});
      }}
      Pfeile.belegungBerechnen(wege);
      console.log(JSON.stringify(wege.map((w) => ({{
        kanteVon: w.kanteVon, kanteNach: w.kanteNach,
        platzVon: w.platzVon, platzNach: w.platzNach,
      }}))));
    """)
    # Alle drei laufen auf dieselbe Kante der Zielkarte - jeder bekommt dort
    # einen eigenen Platz, und alle wissen, dass sie zu dritt sind.
    assert [w["platzNach"]["anzahl"] for w in ergebnis] == [3, 3, 3]
    assert sorted(w["platzNach"]["index"] for w in ergebnis) == [0, 1, 2]
    # An ihren eigenen Karten haengt jeder allein.
    assert all(w["platzVon"] == {"index": 0, "anzahl": 1} for w in ergebnis)
