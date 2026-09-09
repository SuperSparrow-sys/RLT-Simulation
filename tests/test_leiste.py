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
      toggle: (c, an) => (an ? s.add(c) : s.delete(c)),
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
  contains(k) {
    for (let n = k; n; n = n.parentElement) if (n === this) return true;
    return false;
  }
  closest() { return null; }   // die Leiste fragt nur, OB es die Methode gibt
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

// Die Legende "Verbindungen" ist die zweite Klappe der Leiste. Sie steht in
// der Ansichtsgruppe, direkt neben "Einpassen".
const legende = new Knoten("details", "legende");
legende.dataset.weicht = "gesammelt";   // sie wandert wie die uebrigen
legende.eigenbreite = 44;
const legendeInhalt = new Knoten("div", "legende-inhalt");
legende.appendChild(legendeInhalt);
ansicht.appendChild(legende);

// Etwas ausserhalb der Leiste, worauf sich tippen laesst.
const leinwand = new Knoten("svg", "leinwand");

const nachId = { werkzeugmenue: menue, "werkzeugmenue-inhalt": inhalt };
const lauscher = { dokument: {}, fenster: {} };
globalThis.document = {
  querySelector: () => leiste,
  getElementById: (id) => nachId[id] || null,
  querySelectorAll: (auswahl) => {
    if (auswahl === ".werkzeugmenue, .legende") return [menue, legende];
    throw new Error("nicht nachgebaut: " + auswahl);
  },
  addEventListener: (typ, fn) => { lauscher.dokument[typ] = fn; },
  createComment: (text) => {
    const k = new Knoten("#comment", "");
    k.text = text;
    return k;
  },
};
globalThis.window = {
  addEventListener: (typ, fn) => { lauscher.fenster[typ] = fn; },
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
    assert eng["imMenue"] == [
        "btn-zurueck", "btn-vor", "btn-einpassen", "legende", "link-bericht"
    ]
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


def test_ein_tipp_daneben_schliesst_die_klappen():
    """Ein natives <details> bleibt offen, bis man seinen Knopf wieder
    antippt. Wer daneben tippt, liess es stehen - und die Klappe deckte die
    Leinwand zu, auf die er gerade zeigen wollte."""
    ergebnis = spiele("""
      leiste.clientWidth = 900;
      Leiste.starte();
      const tipp = lauscher.dokument.pointerdown;
      const stand = [];

      menue.open = true;
      legende.open = true;
      tipp({ target: leinwand });                  // daneben, auf die Leinwand
      stand.push({ menue: menue.open, legende: legende.open });

      menue.open = true;
      tipp({ target: inhalt });                    // in die Klappe hinein
      stand.push({ menue: menue.open, legende: legende.open });

      menue.open = true;
      legende.open = true;
      tipp({ target: legendeInhalt });   // in die eine, waehrend die andere offen ist
      stand.push({ menue: menue.open, legende: legende.open });

      // Auf schmalen Geraeten steht die Legende IM Menue - dann darf ein
      // Tipp in sie das Menue nicht mit zuklappen.
      leiste.clientWidth = 300;
      Leiste.pruefe();
      menue.open = true;
      legende.open = true;
      tipp({ target: legendeInhalt });
      stand.push({ menue: menue.open, legende: legende.open, drin: inhalt.children.includes(legende) });

      lauscher.fenster.keydown({ key: "Escape" }); // Escape schliesst beide
      stand.push({ menue: menue.open, legende: legende.open });

      console.log(JSON.stringify(stand));
    """)
    daneben, in_klappe, nebeneinander, ineinander, nach_escape = ergebnis

    assert daneben == {"menue": False, "legende": False}
    # Ein Tipp INNERHALB der Klappe laesst sie stehen - sonst waere kein
    # Eintrag darin zu treffen.
    assert in_klappe["menue"] is True
    # Stehen beide nebeneinander in der Leiste, schliesst ein Tipp in die eine
    # die andere - sie sind fuereinander "daneben".
    assert nebeneinander == {"menue": False, "legende": True}
    # Steckt die Legende im Menue, gehoert ein Tipp in sie auch zum Menue.
    assert ineinander["drin"] is True
    assert ineinander["menue"] is True and ineinander["legende"] is True
    assert nach_escape == {"menue": False, "legende": False}


def test_der_lauscher_haengt_in_der_erfassungsphase():
    """Die Leinwand faengt pointerdown ab (Karten schieben, Pfeile ziehen) und
    haelt es teilweise an - ein Lauscher in der Blasenphase kaeme dort nie
    an."""
    quelle = LEISTE_JS.read_text(encoding="utf-8")
    stelle = quelle.index('document.addEventListener(')
    block = quelle[stelle:stelle + 400]
    assert '"pointerdown"' in block
    assert "true" in block.split(")")[-3] or "true" in block


def test_die_leiste_schiebt_nur_wenn_es_nicht_mehr_passt():
    """Ein Ueberlaufbereich schneidet ab, ob geschoben wird oder nicht - und
    die Klappe "Verbindungen" haengt in der Leiste. Dauerhaft eingeschaltet
    war sie am Schreibtisch unsichtbar: aufgeklappt, aber abgeschnitten.
    Deshalb nur dann, wenn auch die knappste Stufe noch ueberlaeuft."""
    ergebnis = spiele("""
      const stand = {};
      leiste.clientWidth = 900;
      Leiste.starte();
      stand.weit = { stufe: leiste.dataset.stufe, schiebt: leiste.klassen.has("schiebt") };
      leiste.clientWidth = 200;      // enger als selbst die knappste Stufe
      Leiste.pruefe();
      stand.eng = { stufe: leiste.dataset.stufe, schiebt: leiste.klassen.has("schiebt") };
      leiste.clientWidth = 900;      // und wieder zurueck
      Leiste.pruefe();
      stand.wiederWeit = { stufe: leiste.dataset.stufe, schiebt: leiste.klassen.has("schiebt") };
      console.log(JSON.stringify(stand));
    """)
    assert ergebnis["weit"] == {"stufe": "voll", "schiebt": False}
    assert ergebnis["eng"]["stufe"] == "knapp"
    assert ergebnis["eng"]["schiebt"] is True
    # Wird wieder Platz frei, hoert das Schieben auf - sonst bliebe die
    # Legende dauerhaft abgeschnitten.
    assert ergebnis["wiederWeit"] == {"stufe": "voll", "schiebt": False}
