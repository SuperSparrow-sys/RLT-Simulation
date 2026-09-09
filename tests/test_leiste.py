"""Die Kopfleiste des Schreibtischs raeumt ihre Knoepfe um - hin UND zurueck.

static/js/editor-leiste.js verschiebt Knoepfe zwischen der Leiste und dem
Ausweichmenue. Das Hinschieben war leicht zu sehen, das Zurueckholen nicht:
Es geschieht erst bei einer Groessenaenderung NACH dem ersten Einraeumen, und
am Schreibtisch aendert sich nach dem Laden nichts mehr. Auf dem iPad genuegt
das Ein- und Ausfahren der Safari-Leiste - dort brach der Umbau mitten drin
ab, und ein Knopf stand als runder Knopf ohne Wort im Menue.

Geprueft wird deshalb der ganze Weg, an einem winzigen nachgebauten
Dokument: einraeumen, ausraeumen, wieder einraeumen. Ein Nachbau statt eines
Browsers, weil genau die Reihenfolge der Knotenverschiebungen zaehlt - nicht,
wie das Ergebnis aussieht.

node ist kein Erfordernis des Projekts; fehlt es, werden diese Tests
uebersprungen.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which("node")
LEISTE_JS = Path(__file__).resolve().parent.parent / "static" / "js" / "editor-leiste.js"

pytestmark = pytest.mark.skipif(NODE is None, reason="node ist nicht vorhanden")


# Ein Dokument, das genau die Handgriffe kann, die editor-leiste.js benutzt -
# und insertBefore genauso streng nimmt wie ein Browser: Ein Bezugsknoten, der
# kein Kind des Ziels ist, ist ein Fehler. Genau daran ist der erste Anlauf
# gescheitert.
NACHBAU = r"""
class Knoten {
  constructor(name, id) {
    this.nodeName = name;
    this.id = id || "";
    this.kinder = [];
    this.parentElement = null;
    this.dataset = {};
    this.klassen = new Set();
    this.hidden = false;
    this.open = false;
    this.eigenbreite = 0;
  }
  get children() { return this.kinder.filter((k) => k.nodeName !== "#comment"); }
  get classList() {
    const s = this.klassen;
    return {
      add: (c) => s.add(c),
      remove: (c) => s.delete(c),
      contains: (c) => s.has(c),
    };
  }
  get offsetWidth() {
    if (this.hidden) return 0;
    if (this.eigenbreite) return this.eigenbreite;
    return this.children.reduce((s, k) => s + k.offsetWidth, 0);
  }
  getClientRects() { return this.hidden ? [] : [{}]; }
  get nextElementSibling() {
    if (!this.parentElement) return null;
    const g = this.parentElement.children;
    return g[g.indexOf(this) + 1] || null;
  }
  _loesen(k) {
    const alt = k.parentElement;
    if (alt) alt.kinder = alt.kinder.filter((x) => x !== k);
    k.parentElement = null;
  }
  appendChild(k) { this._loesen(k); k.parentElement = this; this.kinder.push(k); return k; }
  insertBefore(k, bezug) {
    if (bezug && bezug.parentElement !== this) {
      throw new Error("NotFoundError: Bezugsknoten ist kein Kind dieses Knotens");
    }
    this._loesen(k);
    k.parentElement = this;
    const i = bezug ? this.kinder.indexOf(bezug) : this.kinder.length;
    this.kinder.splice(i, 0, k);
    return k;
  }
  addEventListener() {}
  alleMit(pruefung, gefunden) {
    for (const k of this.kinder) {
      if (pruefung(k)) gefunden.push(k);
      if (k.alleMit) k.alleMit(pruefung, gefunden);
    }
    return gefunden;
  }
  querySelectorAll(auswahl) {
    if (auswahl !== "[data-weicht]") throw new Error("nicht nachgebaut: " + auswahl);
    return this.alleMit((k) => k.dataset && k.dataset.weicht, []);
  }
  get pfad() {
    return (this.parentElement ? this.parentElement.pfad + "/" : "") + (this.id || this.nodeName);
  }
}

function knopf(id, weicht, breite) {
  const k = new Knoten("button", id);
  k.dataset.weicht = weicht;
  k.eigenbreite = breite;
  return k;
}

const leiste = new Knoten("header", "leiste");
const ort = new Knoten("div", "ort");
ort.eigenbreite = 200;
const verlauf = new Knoten("div", "verlauf");
const ansicht = new Knoten("div", "ansicht");
const ergebnis = new Knoten("div", "ergebnis");
const menue = new Knoten("details", "werkzeugmenue");
const inhalt = new Knoten("div", "werkzeugmenue-inhalt");
const simulieren = new Knoten("button", "btn-simulieren");
simulieren.eigenbreite = 100;

const zurueck = knopf("btn-zurueck", "gesammelt", 44);
const vor = knopf("btn-vor", "gesammelt", 44);
const einpassen = knopf("btn-einpassen", "gesammelt", 44);
const bericht = knopf("link-bericht", "knapp", 80);

menue.appendChild(inhalt);
menue.eigenbreite = 44;
verlauf.appendChild(zurueck);
verlauf.appendChild(vor);
ansicht.appendChild(einpassen);
ergebnis.appendChild(bericht);
ergebnis.appendChild(menue);
ergebnis.appendChild(simulieren);
leiste.appendChild(ort);
leiste.appendChild(verlauf);
leiste.appendChild(ansicht);
leiste.appendChild(ergebnis);

const nachId = { werkzeugmenue: menue, "werkzeugmenue-inhalt": inhalt };
globalThis.document = {
  querySelector: () => leiste,
  getElementById: (id) => nachId[id] || null,
  createComment: (text) => {
    const k = new Knoten("#comment", "");
    k.text = text;
    return k;
  },
};
globalThis.window = {
  addEventListener: () => {},
  getComputedStyle: () => ({
    columnGap: "10px", gap: "10px", paddingLeft: "8px", paddingRight: "8px",
  }),
};

function bericht_stand() {
  return {
    stufe: leiste.dataset.stufe,
    imMenue: inhalt.children.map((k) => k.id),
    klassen: {
      zurueck: [...zurueck.klassen],
      vor: [...vor.klassen],
      einpassen: [...einpassen.klassen],
    },
    eltern: {
      zurueck: zurueck.parentElement.id,
      vor: vor.parentElement.id,
      einpassen: einpassen.parentElement.id,
      bericht: bericht.parentElement.id,
    },
    reihenfolgeVerlauf: verlauf.children.map((k) => k.id),
  };
}
"""


def spiele(auftrag):
    skript = LEISTE_JS.read_text(encoding="utf-8")
    # Die Datei haengt sich beim Laden an DOMContentLoaded - der Nachbau
    # schluckt das (window.addEventListener tut nichts).
    voll = NACHBAU + "\n" + skript + "\n;(function () {\n" + auftrag + "\n})();\n"
    fertig = subprocess.run(
        [NODE, "--input-type=commonjs", "-e", voll],
        capture_output=True, text=True, timeout=30,
    )
    assert fertig.returncode == 0, fertig.stderr
    return json.loads(fertig.stdout)


def test_die_knoepfe_finden_ihren_platz_wieder():
    """Der Fehler, den dieser Test haelt: Beim Zurueckholen merkte sich jeder
    Knopf den NACHBARN, vor dem er wieder einzusetzen sei. Beim ersten
    Ausraeumen stand dieser Nachbar aber noch im Menue - insertBefore warf,
    die Schleife brach ab, und der erste Knopf blieb ohne seine Klasse im
    Menue stehen: ein runder Knopf ohne Wort."""
    ergebnis = spiele("""
      const stand = [];
      leiste.clientWidth = 300;          // eng: alles muss ins Menue
      Leiste.starte();
      stand.push(bericht_stand());
      leiste.clientWidth = 900;          // weit: alles kommt zurueck
      Leiste.pruefe();
      stand.push(bericht_stand());
      leiste.clientWidth = 300;          // und wieder hinein
      Leiste.pruefe();
      stand.push(bericht_stand());
      console.log(JSON.stringify(stand));
    """)
    eng, weit, wieder_eng = ergebnis

    # Eng: alle vier im Menue, jeder mit seiner Klasse.
    assert eng["imMenue"] == ["btn-zurueck", "btn-vor", "btn-einpassen", "link-bericht"]
    assert all("im-menue" in k for k in eng["klassen"].values())

    # Weit: alle wieder an ihrem Platz - und in ihrer alten Reihenfolge.
    assert weit["stufe"] == "voll"
    assert weit["imMenue"] == []
    assert weit["eltern"] == {
        "zurueck": "verlauf", "vor": "verlauf",
        "einpassen": "ansicht", "bericht": "ergebnis",
    }
    assert weit["reihenfolgeVerlauf"] == ["btn-zurueck", "btn-vor"]
    assert all("im-menue" not in k for k in weit["klassen"].values())

    # Und der zweite Weg hinein fuehrt zum selben Ergebnis wie der erste.
    assert wieder_eng["imMenue"] == eng["imMenue"]
    assert wieder_eng["klassen"] == eng["klassen"]


def test_das_menue_verschwindet_wenn_es_leer_ist():
    """Ein leeres Menue ist ein Knopf, hinter dem nichts steht."""
    ergebnis = spiele("""
      leiste.clientWidth = 300;
      Leiste.starte();
      const eng = menue.hidden;
      leiste.clientWidth = 900;
      Leiste.pruefe();
      console.log(JSON.stringify({ eng, weit: menue.hidden }));
    """)
    assert ergebnis["eng"] is False
    assert ergebnis["weit"] is True


def test_die_stufe_wird_gemessen_nicht_geraten():
    """Die Leiste bekommt probeweise die hoechste Stufe und geht eine tiefer,
    solange ihr Inhalt breiter ist als sie selbst."""
    ergebnis = spiele("""
      const stufen = {};
      for (const breite of [900, 480, 380, 260]) {
        leiste.clientWidth = breite;
        if (!Leiste.leiste) Leiste.starte(); else Leiste.pruefe();
        stufen[breite] = leiste.dataset.stufe;
      }
      console.log(JSON.stringify(stufen));
    """)
    # Je enger, desto tiefer - und nie wieder hinauf, ohne dass Platz da ist.
    reihe = ["voll", "zeichen", "gesammelt", "knapp"]
    gewaehlt = [ergebnis[str(b)] for b in (900, 480, 380, 260)]
    assert gewaehlt == sorted(gewaehlt, key=reihe.index), gewaehlt
    assert gewaehlt[0] == "voll"
    assert gewaehlt[-1] == "knapp"
