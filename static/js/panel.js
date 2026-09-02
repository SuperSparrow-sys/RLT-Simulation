/* Rechte Spalte: die Parameter der gewaehlten Karte, erzeugt aus ihrer
   Typdeklaration. Jede Aenderung wird gespeichert, sobald das Feld verlassen
   wird (Zahl/Uhrzeit) oder sich der Wert aendert (Auswahl, Monat, Text).

   Die Karte liefert je Parameter eine Darstellungsangabe (feld.darstellung)
   und die Anzeige-Genauigkeit (feld.dezimalstellen) - dieses Skript liest sie
   und richtet sich danach. Kein Sonderfall fuer einen bestimmten Kartentyp:
   jede der neun Darstellungsarten hat GENAU einen Renderer, den jede Karte
   gleichermassen bekommt, wenn sie einen Parameter dieser Art deklariert.

   Wichtig fuer die Genauigkeit: ein Zahlenfeld zeigt den gerundeten Wert nur,
   waehrend es NICHT den Fokus hat. Beim Hineinklicken erscheint der volle,
   ungerundete Wert - sonst wuerde ein Pfeiltasten-Klick oder ein Tippfehler
   auf der gerundeten Anzeige aufsetzen und den gespeicherten Wert stillschwei-
   gend kappen. Erst ein tatsaechlich geaenderter Wert wird gespeichert. */

const MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];

// Tagesanteil (0..1, wie core/bausteine/basis.py rechnet) <-> "HH:MM". Muss
// mit basis.uhrzeit_anzeigen()/uhrzeit_einlesen() uebereinstimmen - siehe dort.
function uhrzeitAnzeigen(tagesanteil) {
  const normiert = ((Number(tagesanteil) || 0) % 1 + 1) % 1;
  const minutenGesamt = Math.round(normiert * 24 * 60) % (24 * 60);
  const stunden = Math.floor(minutenGesamt / 60);
  const minuten = minutenGesamt % 60;
  return `${String(stunden).padStart(2, "0")}:${String(minuten).padStart(2, "0")}`;
}
function uhrzeitEinlesen(text) {
  const [stunden, minuten] = String(text).split(":").map(Number);
  return ((stunden || 0) * 60 + (minuten || 0)) / (24 * 60);
}

// Anzeige-Rundung. Der Rueckgabewert ist ein reiner String fuers Feld - der
// tatsaechliche, ungerundete Wert lebt weiter in karte.parameter[...] und wird
// nur beim Fokussieren wieder eingeblendet (siehe zeileZahl()).
function formatZahl(wert, dezimalstellen) {
  const zahl = Number(wert);
  if (!Number.isFinite(zahl)) return "0";
  return zahl.toFixed(Math.max(0, dezimalstellen == null ? 1 : dezimalstellen));
}

// TT.MM.-Zeitraumtexte (siehe core/bausteine/ferien.py, _als_tagesnummer) in
// ihre beiden Zahlen zerlegen und wieder zusammensetzen.
function zeitraumTeile(text) {
  const teile = String(text || "").replace(/\.+$/, "").split(".");
  const tag = parseInt(teile[0], 10);
  const monat = parseInt(teile[1], 10);
  return { tag: Number.isFinite(tag) ? tag : 1, monat: Number.isFinite(monat) ? monat : 1 };
}
function zeitraumText(tag, monat) {
  return `${String(tag).padStart(2, "0")}.${String(monat).padStart(2, "0")}.`;
}

const Panel = {
  karte: null,
  // Schuetzt vor einem veralteten Messwerte-Ergebnis: wird eine Karte
  // angeklickt, waehrend fuer die vorige noch die Messwerte-Liste unterwegs
  // ist, darf die spaete Antwort nicht mehr das inzwischen gezeigte Panel
  // ueberschreiben.
  _anfrage: 0,

  // Ein fokussiertes Eingabefeld verliert beim Abriss des Panels (innerHTML-
  // bzw. textContent-Ersetzung in leeren()/zeige() unten) nicht in jedem Fall
  // zuverlaessig synchron den Fokus, bevor der Knoten verschwindet - das vom
  // DOM eigentlich verlangte "blur" beim Entfernen eines fokussierten
  // Elements feuert hier nachweislich NICHT immer (per Netzwerkmitschnitt
  // geprueft: Leinwand anklicken nach dem Tippen in "Bezeichnung" loeste
  // keine PATCH-Anfrage aus). zeileText()/zeileUhrzeit() speichern beim
  // Verlassen des Feldes ("blur") - ohne dieses ausdrueckliche blur() vorher
  // ginge ein gerade getippter Wert beim Wegklicken oder Kartenwechsel
  // verloren. explizites .blur() ist (anders als das implizite Verhalten
  // beim Entfernen) garantiert synchron.
  _commitAktivesFeld() {
    const panel = document.getElementById("panel");
    const aktiv = document.activeElement;
    if (panel && aktiv && panel.contains(aktiv) && typeof aktiv.blur === "function") {
      aktiv.blur();
    }
  },

  leeren() {
    this._commitAktivesFeld();
    this.karte = null;
    document.getElementById("panel").innerHTML =
      '<p class="leerhinweis">Karte auswählen, um ihre Parameter zu sehen.</p>';
  },

  async zeige(karte) {
    this._commitAktivesFeld();
    this.karte = karte;
    const anfrage = ++this._anfrage;
    const panel = document.getElementById("panel");
    panel.textContent = "";

    const kopf = document.createElement("h2");
    kopf.className = "panel-kopf";
    kopf.textContent = karte.name;
    panel.appendChild(kopf);

    const namensfeld = this.zeileText("Bezeichnung", karte.name, async (wert) => {
      karte.name = wert;
      await this.speichere({ name: wert });
      Editor.zeichne();
    });
    panel.appendChild(namensfeld);

    const regelkreise = this.ermittleRegelkreise(karte);
    let messwerte = [];
    if (regelkreise.length) {
      messwerte = await this.ladeMesswerte();
      // Zwischenzeitlich eine andere Karte gewaehlt? Dann diese veraltete
      // Antwort verwerfen, statt das falsche Panel zu vervollstaendigen.
      if (anfrage !== this._anfrage || this.karte !== karte) return;
    }

    // Parameter, die zu einem Regelungseingang gehoeren (Sollwert/Istwert),
    // stehen unten im eigenen Abschnitt - nicht zusaetzlich hier oben, das
    // waere doppelt und ohne den Verbindungszusammenhang unklar.
    const regelSchluessel = new Set();
    for (const gruppe of regelkreise) {
      for (const eintrag of gruppe.eintraege) {
        if (eintrag.feld) regelSchluessel.add(eintrag.feld.schluessel);
      }
    }
    this.zeigeParameterliste(panel, karte, regelSchluessel);

    if (regelkreise.length) {
      panel.appendChild(this.baueRegelungsabschnitt(karte, regelkreise, messwerte));
    }

    panel.appendChild(this.bauePortliste(karte));
  },

  zeigeParameterliste(panel, karte, regelSchluessel) {
    const restliche = karte.felder.filter((f) => !regelSchluessel.has(f.schluessel));
    const textlisten = restliche.filter((f) => f.darstellung === "textliste");
    const sonstige = restliche.filter((f) => f.darstellung !== "textliste");
    for (const feld of sonstige) panel.appendChild(this.feldZeile(karte, feld));
    if (textlisten.length) panel.appendChild(this.zeileTextlisten(karte, textlisten));
  },

  // Ein Parameter samt seinem Erklaersatz. Der Hinweis kommt von der Karte
  // (core/bausteine/basis.py: Param.hinweis) und steht unter dem Eingabefeld -
  // hier und nicht in den einzelnen Renderern, damit er unabhaengig von der
  // Darstellungsart immer an derselben Stelle erscheint.
  feldZeile(karte, feld) {
    const zeile = this.feldEingabe(karte, feld);
    if (!feld.hinweis) return zeile;
    // In die Zeile hinein, nicht um sie herum: .panel-zeile ist eine
    // Flex-Spalte mit 4px Abstand, der Hinweis rueckt damit direkt unter das
    // Eingabefeld und noch vor dessen Abstand zum naechsten Parameter.
    const hinweis = document.createElement("p");
    hinweis.className = "panel-hinweis";
    hinweis.textContent = feld.hinweis;
    zeile.appendChild(hinweis);
    return zeile;
  },

  // Verteilt jeden Parameter an GENAU einen Renderer, allein anhand seiner
  // Darstellungsangabe - keine Fallunterscheidung nach Kartentyp.
  feldEingabe(karte, feld) {
    const wert = karte.parameter[feld.schluessel];
    if (feld.ueberschrieben_von) return this.zeileUeberschrieben(feld);
    switch (feld.darstellung) {
      case "uhrzeit": return this.zeileUhrzeit(karte, feld, wert);
      case "prozent": return this.zeileZahl(karte, feld, wert, true, false);
      case "auswahl": return this.zeileAuswahl(karte, feld, wert);
      case "zeitreihe": return this.zeileZeitreihe(karte, feld, wert);
      case "monatswerte": return this.zeileMonatswerte(karte, feld, wert);
      case "zeitraeume": return this.zeileZeitraeume(karte, feld, wert);
      case "anteile": return this.zeileAnteile(karte, feld, wert);
      default: return this.zeileZahl(karte, feld, wert, false, false);
    }
  },

  _huelle(beschriftung, eingabe, einheit) {
    const zeile = document.createElement("label");
    zeile.className = "panel-zeile";
    const text = document.createElement("span");
    text.className = "panel-label";
    // "-" ist der Platzhalter fuer Auswahlfelder ohne echte Einheit
    // (etwa dampfart, pumpenart) - ihn anzuzeigen ergaebe Beschriftungen
    // wie "E-/Fremddampf [-]".
    const zeigeEinheit = einheit && einheit !== "-";
    text.textContent = zeigeEinheit ? `${beschriftung} [${einheit}]` : beschriftung;
    zeile.appendChild(text);
    zeile.appendChild(eingabe);
    return zeile;
  },

  // "blur" statt "change": ein Klick auf die Leinwand oder eine andere Karte
  // raeumt das Panel sofort leer (panelLeeren()/Panel.zeige() setzen
  // panel.innerHTML/.textContent synchron zurueck, noch im selben
  // Pointerdown-Handler) - das fokussierte Feld verschwindet dabei aus dem
  // DOM. Ein Browser MUSS beim Entfernen eines fokussierten Elements
  // synchron "blur" nachliefern (die Fokus-Invariante des DOM verlangt das),
  // "change" ist dagegen nur eine Ableitung davon, die einzelne Engines in
  // genau diesem erzwungenen Fall unterschiedlich behandeln koennen. "blur"
  // ist deshalb die einzige Stelle, an der ein getippter Wert garantiert
  // ankommt - dasselbe Muster wie ueberall sonst im Parameterfenster
  // (zeileZahl, zeileUhrzeit, zeileZeitraeume, zeileTextlisten, ...).
  zeileText(beschriftung, wert, beiAenderung) {
    const eingabe = document.createElement("input");
    eingabe.type = "text";
    eingabe.value = wert;
    let aktuell = wert;
    eingabe.addEventListener("keydown", (e) => { if (e.key === "Enter") eingabe.blur(); });
    eingabe.addEventListener("blur", () => {
      if (eingabe.value === aktuell) return;
      aktuell = eingabe.value;
      beiAenderung(eingabe.value);
    });
    return this._huelle(beschriftung, eingabe, "");
  },

  // Zahl UND Prozent - "istProzent" haengt nur ein "%"-Zeichen statt der
  // eckigen Einheit an. "nurEingabe" laesst die aeussere Beschriftungszeile
  // weg, weil der Regelungsabschnitt (siehe unten) die Beschriftung selbst
  // schon zeigt ("Istwert"/"Sollwert").
  zeileZahl(karte, feld, wert, istProzent, nurEingabe) {
    const eingabe = document.createElement("input");
    eingabe.type = "number";
    eingabe.step = "any";
    let voll = Number(wert) || 0;
    eingabe.value = formatZahl(voll, feld.dezimalstellen);

    eingabe.addEventListener("focus", () => { eingabe.value = String(voll); });
    eingabe.addEventListener("keydown", (e) => { if (e.key === "Enter") eingabe.blur(); });
    eingabe.addEventListener("blur", async () => {
      const zahl = Number(eingabe.value);
      if (Number.isFinite(zahl) && zahl !== voll) {
        const ergebnis = await this.speichereParameter(feld.schluessel, zahl);
        if (ergebnis.ok) {
          voll = zahl;
          karte.parameter[feld.schluessel] = zahl;
        } else if (ergebnis.feldfehler[feld.schluessel]) {
          // Abgelehnt (siehe zeigeFehler in speichere() fuer die Meldung) -
          // der alte, gueltige Wert bleibt stehen statt des unzulaessigen.
          this.markiereFeldFehler(eingabe);
        }
      }
      eingabe.value = formatZahl(voll, feld.dezimalstellen);
    });

    let inhalt = eingabe;
    if (istProzent) {
      const wrapper = document.createElement("div");
      wrapper.className = "panel-prozent-huelle";
      wrapper.appendChild(eingabe);
      const suffix = document.createElement("span");
      suffix.textContent = "%";
      wrapper.appendChild(suffix);
      inhalt = wrapper;
    }

    if (nurEingabe) return inhalt;
    return this._huelle(feld.label, inhalt, istProzent ? "" : feld.einheit);
  },

  zeileUhrzeit(karte, feld, wert) {
    const eingabe = document.createElement("input");
    eingabe.type = "time";
    eingabe.value = uhrzeitAnzeigen(wert);
    let aktuell = eingabe.value;
    // "blur" statt "change" - siehe Begruendung bei zeileText() oben.
    eingabe.addEventListener("blur", async () => {
      if (!eingabe.value || eingabe.value === aktuell) return;
      aktuell = eingabe.value;
      const tagesanteil = uhrzeitEinlesen(eingabe.value);
      karte.parameter[feld.schluessel] = tagesanteil;
      await this.speichereParameter(feld.schluessel, tagesanteil);
    });
    return this._huelle(feld.label, eingabe, "");
  },

  // feld.auswahl kommt fertig als Liste von {wert, label} von der Karte
  // (core/bausteine/basis.py: Param.auswahl, gefuellt ueber wahl()) - das
  // Fenster kennt keine kartenspezifischen Kuerzel, es zeigt nur, was die
  // Karte mitgibt.
  zeileAuswahl(karte, feld, wert) {
    const eingabe = document.createElement("select");
    let aktuell = wert;
    for (const moeglichkeit of feld.auswahl) {
      const option = document.createElement("option");
      option.value = moeglichkeit.wert;
      option.textContent = moeglichkeit.label;
      if (moeglichkeit.wert === wert) option.selected = true;
      eingabe.appendChild(option);
    }
    eingabe.addEventListener("change", async () => {
      const neu = eingabe.value;
      const ergebnis = await this.speichereParameter(feld.schluessel, neu);
      if (!ergebnis.ok) {
        // Das Auswahlfeld bietet ohnehin nur zulaessige Werte an - eine
        // Ablehnung kann hier praktisch nur ueber einen fremden Aufruf der
        // Schnittstelle entstehen. Sicherheitshalber trotzdem auf den zuletzt
        // gueltigen Wert zurueckstellen statt die Ablehnung zu ignorieren.
        if (ergebnis.feldfehler[feld.schluessel]) this.markiereFeldFehler(eingabe);
        eingabe.value = aktuell;
        return;
      }
      aktuell = neu;
      karte.parameter[feld.schluessel] = neu;
      // Die Ventilator-Rolle (Zuluft/Abluft) aendert, welche Ports die Karte
      // hat - ohne Neuladen zeigte das Panel danach veraltete Anschluesse.
      await this.neuLadenUndAnzeigen();
    });
    return this._huelle(feld.label, eingabe, "");
  },

  // Ein Parameter, dessen gleichnamiger Anschluss gerade belegt ist: der
  // Zahlenwert daneben ist wirkungslos, solange die Verbindung steht. Das
  // Feld sieht deshalb bewusst NICHT wie ein normales Eingabefeld aus.
  zeileUeberschrieben(feld) {
    const zeile = document.createElement("div");
    zeile.className = "panel-zeile";
    const text = document.createElement("span");
    text.className = "panel-label";
    text.textContent = feld.label;
    zeile.appendChild(text);

    const badge = document.createElement("div");
    badge.className = "panel-ueberschrieben";
    badge.textContent =
      `kommt von: ${feld.ueberschrieben_von.von_karte_name} → ${feld.ueberschrieben_von.von_label}`;
    zeile.appendChild(badge);

    const loesen = document.createElement("button");
    loesen.type = "button";
    loesen.className = "panel-knopf-klein";
    loesen.textContent = "Verbindung lösen";
    loesen.addEventListener("click", () => this.loeseVerbindung(feld.ueberschrieben_von.pfeil_id));
    zeile.appendChild(loesen);

    return zeile;
  },

  // 24 Werte, ein Wert je Stunde (Tageslastprofil & Co.): eine kleine
  // Balkenreihe fuer den Verlauf auf einen Blick, darunter jede Stunde als
  // eigenes, beschriftetes Zahlenfeld - kein rohes JSON.
  zeileZeitreihe(karte, feld, wert) {
    const werte = Array.isArray(wert) ? wert.slice() : new Array(24).fill(0);

    const huelle = document.createElement("div");
    huelle.className = "panel-block";
    const titel = document.createElement("span");
    titel.className = "panel-label";
    titel.textContent = feld.einheit && feld.einheit !== "-" ? `${feld.label} [${feld.einheit}]` : feld.label;
    huelle.appendChild(titel);

    const balken = document.createElement("div");
    balken.className = "panel-zeitreihe-balken";
    huelle.appendChild(balken);

    const zeichneBalken = () => {
      balken.textContent = "";
      const max = Math.max(1e-9, ...werte.map((w) => Math.abs(Number(w) || 0)));
      for (const w of werte) {
        const saeule = document.createElement("div");
        saeule.className = "panel-balken-saeule";
        saeule.style.height = `${Math.max(2, Math.round((Math.abs(Number(w) || 0) / max) * 28))}px`;
        balken.appendChild(saeule);
      }
    };
    zeichneBalken();

    const gitter = document.createElement("div");
    gitter.className = "panel-zeitreihe-gitter";
    werte.forEach((wertJeStunde, stunde) => {
      const zelle = document.createElement("label");
      zelle.className = "panel-zeitreihe-zelle";
      const stundenText = document.createElement("span");
      stundenText.textContent = String(stunde).padStart(2, "0");
      zelle.appendChild(stundenText);

      const eingabe = document.createElement("input");
      eingabe.type = "number";
      eingabe.step = "any";
      let voll = Number(wertJeStunde) || 0;
      eingabe.value = formatZahl(voll, feld.dezimalstellen);
      eingabe.addEventListener("focus", () => { eingabe.value = String(voll); });
      eingabe.addEventListener("keydown", (e) => { if (e.key === "Enter") eingabe.blur(); });
      eingabe.addEventListener("blur", async () => {
        const zahl = Number(eingabe.value);
        if (Number.isFinite(zahl) && zahl !== voll) {
          voll = zahl;
          werte[stunde] = zahl;
          karte.parameter[feld.schluessel] = werte;
          await this.speichereParameter(feld.schluessel, werte);
          zeichneBalken();
        }
        eingabe.value = formatZahl(voll, feld.dezimalstellen);
      });
      zelle.appendChild(eingabe);
      gitter.appendChild(zelle);
    });
    huelle.appendChild(gitter);

    return huelle;
  },

  // 12 Werte, einer je Monat (Monatsprofil): Umschaltknoepfe statt Checkbox-
  // Liste - lesbar auf einen Blick, welche Monate an sind.
  zeileMonatswerte(karte, feld, wert) {
    const werte = Array.isArray(wert) ? wert.slice() : new Array(12).fill(true);

    const huelle = document.createElement("div");
    huelle.className = "panel-block";
    const titel = document.createElement("span");
    titel.className = "panel-label";
    titel.textContent = feld.label;
    huelle.appendChild(titel);

    const gitter = document.createElement("div");
    gitter.className = "panel-monat-gitter";
    werte.forEach((an, i) => {
      const knopf = document.createElement("button");
      knopf.type = "button";
      knopf.className = "panel-monat-knopf";
      knopf.textContent = MONATE[i];
      knopf.setAttribute("aria-pressed", String(!!an));
      knopf.classList.toggle("aktiv", !!an);
      knopf.addEventListener("click", async () => {
        werte[i] = !werte[i];
        knopf.classList.toggle("aktiv", werte[i]);
        knopf.setAttribute("aria-pressed", String(werte[i]));
        karte.parameter[feld.schluessel] = werte;
        await this.speichereParameter(feld.schluessel, werte);
      });
      gitter.appendChild(knopf);
    });
    huelle.appendChild(gitter);

    return huelle;
  },

  // Zeitraeume mit Datum (Ferien): je Zeitraum eine Bezeichnung plus Tag/Monat
  // fuer von und bis - genau das Format, das core/bausteine/ferien.py liest
  // (Tag.Monat, ohne Jahr - ein Zeitraum gilt in jedem Wetterjahr).
  zeileZeitraeume(karte, feld, wert) {
    const eintraege = Array.isArray(wert)
      ? wert.map((e) => ({ name: e.name || "", von: e.von || "01.01.", bis: e.bis || "01.01." }))
      : [];

    const huelle = document.createElement("div");
    huelle.className = "panel-block";
    const titel = document.createElement("span");
    titel.className = "panel-label";
    titel.textContent = feld.label;
    huelle.appendChild(titel);

    const liste = document.createElement("div");
    liste.className = "panel-zeitraeume";
    huelle.appendChild(liste);

    const speichern = async () => {
      karte.parameter[feld.schluessel] = eintraege;
      await this.speichereParameter(feld.schluessel, eintraege);
    };

    const datumsFeld = (eintrag, schluessel, beschriftung) => {
      const gruppe = document.createElement("span");
      gruppe.className = "panel-zeitraum-datum";
      const label = document.createElement("span");
      label.textContent = beschriftung;
      gruppe.appendChild(label);

      const teile = zeitraumTeile(eintrag[schluessel]);
      const tag = document.createElement("input");
      tag.type = "number"; tag.min = 1; tag.max = 31; tag.title = "Tag";
      tag.value = teile.tag;
      const punkt = document.createElement("span");
      punkt.textContent = ".";
      const monat = document.createElement("input");
      monat.type = "number"; monat.min = 1; monat.max = 12; monat.title = "Monat";
      monat.value = teile.monat;

      const aktualisieren = () => {
        eintrag[schluessel] = zeitraumText(Number(tag.value) || 1, Number(monat.value) || 1);
        speichern();
      };
      tag.addEventListener("blur", aktualisieren);
      monat.addEventListener("blur", aktualisieren);

      gruppe.appendChild(tag);
      gruppe.appendChild(punkt);
      gruppe.appendChild(monat);
      return gruppe;
    };

    const zeichne = () => {
      liste.textContent = "";
      eintraege.forEach((eintrag, i) => {
        const zeile = document.createElement("div");
        zeile.className = "panel-zeitraum-zeile";

        const name = document.createElement("input");
        name.type = "text";
        name.placeholder = "Bezeichnung (z. B. Weihnachten)";
        name.value = eintrag.name;
        name.addEventListener("blur", () => { eintrag.name = name.value; speichern(); });
        zeile.appendChild(name);

        const daten = document.createElement("div");
        daten.className = "panel-zeitraum-daten";
        daten.appendChild(datumsFeld(eintrag, "von", "von"));
        daten.appendChild(datumsFeld(eintrag, "bis", "bis"));
        zeile.appendChild(daten);

        const entfernen = document.createElement("button");
        entfernen.type = "button";
        entfernen.className = "panel-knopf-klein panel-entfernen";
        entfernen.textContent = "Entfernen";
        entfernen.addEventListener("click", () => {
          eintraege.splice(i, 1);
          zeichne();
          speichern();
        });
        zeile.appendChild(entfernen);

        liste.appendChild(zeile);
      });
    };
    zeichne();

    const hinzufuegen = document.createElement("button");
    hinzufuegen.type = "button";
    hinzufuegen.className = "panel-knopf-klein";
    hinzufuegen.textContent = "+ Zeitraum";
    hinzufuegen.addEventListener("click", () => {
      eintraege.push({ name: "", von: "01.01.", bis: "01.01." });
      zeichne();
      speichern();
    });
    huelle.appendChild(hinzufuegen);

    return huelle;
  },

  // Anteile einer Aufteilung (Verteiler): ein Eingabefeld je tatsaechlichem
  // Luftausgang der Karte, mit dem Ziel, an dem er (falls schon verbunden)
  // haengt - "greift nur, solange ein Gang selbst keinen Bedarf meldet"
  // steht dazu, weil sonst unklar bliebe, wann die Zahl ueberhaupt wirkt.
  zeileAnteile(karte, feld, wert) {
    const anteile = wert && typeof wert === "object" ? { ...wert } : {};
    const ziele = karte.ports.filter((p) => p.art === "luft" && p.richtung === "aus");

    const huelle = document.createElement("div");
    huelle.className = "panel-block";
    const titel = document.createElement("span");
    titel.className = "panel-label";
    titel.textContent = `${feld.label} — greift nur, wenn ein Gang keinen eigenen Bedarf meldet`;
    huelle.appendChild(titel);

    if (!ziele.length) {
      const hinweis = document.createElement("p");
      hinweis.className = "panel-hinweis";
      hinweis.textContent = "Noch kein Gang angeschlossen.";
      huelle.appendChild(hinweis);
      return huelle;
    }

    for (const ziel of ziele) {
      const zeile = document.createElement("div");
      zeile.className = "panel-anteil-zeile";

      const beschriftung = document.createElement("span");
      beschriftung.className = "panel-anteil-ziel";
      // Noch unverbundene Gaenge zeigten ihren rohen Schluessel ("luft_aus_3").
      // Stattdessen die Beschriftung des Anschlusses samt laufender Nummer -
      // dieselbe Schreibweise wie im Abschnitt "Anschlüsse" unten.
      const nummer = (ziel.schluessel.match(/_(\d+)$/) || [])[1];
      const eigenname = nummer ? `${ziel.label} ${nummer}` : ziel.label;
      beschriftung.textContent =
        this.zielBeschriftung(ziel.id) || `${eigenname} – nicht verbunden`;
      zeile.appendChild(beschriftung);

      const wrapper = document.createElement("div");
      wrapper.className = "panel-prozent-huelle";
      const eingabe = document.createElement("input");
      eingabe.type = "number";
      eingabe.step = "any";
      eingabe.min = 0;
      let voll = Number(anteile[ziel.schluessel]) || 0;
      eingabe.value = formatZahl(voll, feld.dezimalstellen);
      eingabe.addEventListener("focus", () => { eingabe.value = String(voll); });
      eingabe.addEventListener("keydown", (e) => { if (e.key === "Enter") eingabe.blur(); });
      eingabe.addEventListener("blur", async () => {
        const zahl = Number(eingabe.value);
        if (Number.isFinite(zahl) && zahl !== voll) {
          voll = zahl;
          anteile[ziel.schluessel] = zahl;
          karte.parameter[feld.schluessel] = anteile;
          await this.speichereParameter(feld.schluessel, anteile);
        }
        eingabe.value = formatZahl(voll, feld.dezimalstellen);
      });
      wrapper.appendChild(eingabe);
      const prozent = document.createElement("span");
      prozent.textContent = "%";
      wrapper.appendChild(prozent);
      zeile.appendChild(wrapper);

      huelle.appendChild(zeile);
    }
    return huelle;
  },

  // Mehrere gleich lange Textlisten (Datenlogger: Spaltennamen + Einheiten)
  // als EINE Tabelle nebeneinander - Zeile i der einen gehoert zu Zeile i der
  // anderen, das soll man sehen, nicht zaehlen muessen. Generisch ueber die
  // Laenge entschieden, nicht ueber den Kartentyp: passen die Laengen nicht
  // zusammen, bekommt jede Liste ihre eigene, einfache Spalte.
  zeileTextlisten(karte, felder) {
    const huelle = document.createElement("div");
    huelle.className = "panel-block";

    const laengen = felder.map((f) => (Array.isArray(karte.parameter[f.schluessel]) ? karte.parameter[f.schluessel].length : 0));
    const gemeinsam = felder.length > 1 && laengen.every((l) => l === laengen[0]) ? laengen[0] : null;

    if (gemeinsam === null) {
      for (const feld of felder) huelle.appendChild(this.zeileEinzelTextliste(karte, feld));
      return huelle;
    }

    const titel = document.createElement("span");
    titel.className = "panel-label";
    titel.textContent = felder.map((f) => f.label).join(" / ");
    huelle.appendChild(titel);

    const werteJeFeld = felder.map((f) => (karte.parameter[f.schluessel] || []).slice());
    const spalten = `20px repeat(${felder.length}, 1fr)`;

    const tabelle = document.createElement("div");
    tabelle.className = "panel-textlisten-tabelle";

    const kopf = document.createElement("div");
    kopf.className = "panel-textlisten-zeile panel-textlisten-kopf";
    kopf.style.gridTemplateColumns = spalten;
    kopf.appendChild(document.createElement("span"));
    for (const feld of felder) {
      const spalte = document.createElement("span");
      spalte.textContent = feld.label;
      kopf.appendChild(spalte);
    }
    tabelle.appendChild(kopf);

    for (let i = 0; i < gemeinsam; i++) {
      const zeile = document.createElement("div");
      zeile.className = "panel-textlisten-zeile";
      zeile.style.gridTemplateColumns = spalten;
      const nummer = document.createElement("span");
      nummer.className = "panel-textlisten-nummer";
      nummer.textContent = String(i + 1);
      zeile.appendChild(nummer);
      felder.forEach((feld, spaltenIndex) => {
        const eingabe = document.createElement("input");
        eingabe.type = "text";
        eingabe.value = werteJeFeld[spaltenIndex][i] || "";
        eingabe.addEventListener("blur", async () => {
          werteJeFeld[spaltenIndex][i] = eingabe.value;
          karte.parameter[feld.schluessel] = werteJeFeld[spaltenIndex];
          await this.speichereParameter(feld.schluessel, werteJeFeld[spaltenIndex]);
        });
        zeile.appendChild(eingabe);
      });
      tabelle.appendChild(zeile);
    }
    huelle.appendChild(tabelle);
    return huelle;
  },

  zeileEinzelTextliste(karte, feld) {
    const werte = Array.isArray(karte.parameter[feld.schluessel]) ? karte.parameter[feld.schluessel].slice() : [];
    const huelle = document.createElement("div");
    huelle.className = "panel-block";
    const titel = document.createElement("span");
    titel.className = "panel-label";
    titel.textContent = feld.label;
    huelle.appendChild(titel);
    werte.forEach((wertI, i) => {
      const zeile = document.createElement("label");
      zeile.className = "panel-textliste-zeile";
      const nummer = document.createElement("span");
      nummer.textContent = String(i + 1);
      zeile.appendChild(nummer);
      const eingabe = document.createElement("input");
      eingabe.type = "text";
      eingabe.value = wertI || "";
      eingabe.addEventListener("blur", async () => {
        werte[i] = eingabe.value;
        karte.parameter[feld.schluessel] = werte;
        await this.speichereParameter(feld.schluessel, werte);
      });
      zeile.appendChild(eingabe);
      huelle.appendChild(zeile);
    });
    return huelle;
  },

  // -- "Regelt auf": woher der Soll-/Istwert eines Reglers kommt -----------
  //
  // Gruppiert alle Sollwert-/Istwert-Eingaenge einer Karte nach ihrer
  // Nummer im Schluessel (istwert_1/sollwert_1 gehoeren zusammen, istwert_2/
  // sollwert_2 zum zweiten Regelkreis - siehe core/bausteine/p_regler.py).
  // Ports ohne Nummer (die meisten Regler haben nur einen Kreis) bilden eine
  // einzelne, unbetitelte Gruppe. Die Ueberschrift einer nummerierten Gruppe
  // kommt vom zugehoerigen Xp-Parameter, dem der Groessenname vorne
  // abgeschnitten wird ("Xp (Proportionalbereich) Regler 1 (schnell)" ->
  // "Regler 1 (schnell)") - existiert er nicht, faellt sie auf
  // "Regelkreis <Nummer>" zurueck. Rein strukturell, kein Kartentyp-Name im
  // Code.
  ermittleRegelkreise(karte) {
    const eingaenge = karte.ports.filter(
      (p) => p.richtung === "ein" && (p.rolle === "istwert" || p.rolle === "sollwert")
    );
    if (!eingaenge.length) return [];

    const gruppen = new Map();
    for (const port of eingaenge) {
      const treffer = port.schluessel.match(/^(?:sollwert|istwert)(?:_(\d+))?$/);
      const nummer = treffer ? treffer[1] : undefined;
      const schluesselGruppe = nummer || "_";
      if (!gruppen.has(schluesselGruppe)) {
        let titel = null;
        if (nummer) {
          const xp = karte.felder.find((f) => f.schluessel === `xp_${nummer}`);
          titel = xp
            ? xp.label.replace(/^Xp\s*(\([^)]*\)\s*)?/i, "")
            : `Regelkreis ${nummer}`;
        }
        gruppen.set(schluesselGruppe, { titel, eintraege: [] });
      }
      const feld = karte.felder.find((f) => f.schluessel === port.schluessel) || null;
      gruppen.get(schluesselGruppe).eintraege.push({ port, feld });
    }
    return [...gruppen.values()];
  },

  async ladeMesswerte() {
    let antwort;
    try {
      antwort = await fetch(`/api/anlagen/${Editor.anlage.id}/messwerte`);
    } catch {
      zeigeFehler("Messwerte der Anlage konnten nicht geladen werden.");
      return [];
    }
    if (!antwort.ok) {
      zeigeFehler("Messwerte der Anlage konnten nicht geladen werden.");
      return [];
    }
    return antwort.json();
  },

  baueRegelungsabschnitt(karte, regelkreise, messwerte) {
    const abschnitt = document.createElement("div");
    abschnitt.className = "panel-regelung";
    const kopf = document.createElement("h3");
    kopf.textContent = "Regelt auf";
    abschnitt.appendChild(kopf);

    const mehrereGruppen = regelkreise.length > 1;
    for (const gruppe of regelkreise) {
      const kasten = document.createElement("div");
      kasten.className = "panel-regelkreis";
      if (mehrereGruppen && gruppe.titel) {
        const titel = document.createElement("div");
        titel.className = "panel-regelkreis-titel";
        titel.textContent = gruppe.titel;
        kasten.appendChild(titel);
      }
      for (const eintrag of gruppe.eintraege) {
        kasten.appendChild(this.regelungseingangZeile(karte, eintrag, messwerte));
      }
      abschnitt.appendChild(kasten);
    }
    return abschnitt;
  },

  regelungseingangZeile(karte, eintrag, messwerte) {
    const { port, feld } = eintrag;
    const zeile = document.createElement("div");
    zeile.className = "panel-regeleingang";

    const basisName = port.rolle === "istwert" ? "Istwert" : "Sollwert";
    const bezeichnung = document.createElement("span");
    bezeichnung.className = "panel-regeleingang-label";
    if (feld) {
      bezeichnung.textContent = feld.label.replace(/\s*\(fest\)\s*$/i, "");
    } else if (port.label && port.label !== basisName) {
      // Der Anschluss traegt eine eigene Beschriftung von seiner Karte
      // (core.bausteine.basis.port_label) - frueher stand hier stattdessen der
      // rohe Schluessel, also "Istwert (T_Raum)" statt "Istwert: Raumtemperatur".
      bezeichnung.textContent = `${basisName}: ${port.label}`;
    } else {
      bezeichnung.textContent = basisName;
    }
    zeile.appendChild(bezeichnung);

    const verbindung = this.findeVerbindungAn(port.id);
    if (verbindung) {
      const quelle = this.findePort(verbindung.vonPortId);
      const messwertEintrag = messwerte.find((m) => m.port_id === verbindung.vonPortId);
      const quellName = quelle ? quelle.karte.name : "unbekannt";
      const quellLabel = messwertEintrag
        ? messwertEintrag.label
        : (quelle ? quelle.port.schluessel : "unbekannt");

      const badge = document.createElement("div");
      badge.className = "panel-ueberschrieben";
      badge.textContent = `kommt von: ${quellName} → ${quellLabel}`;
      zeile.appendChild(badge);

      const loesen = document.createElement("button");
      loesen.type = "button";
      loesen.className = "panel-knopf-klein";
      loesen.textContent = "Verbindung lösen";
      loesen.addEventListener("click", () => this.loeseVerbindung(verbindung.pfeilId));
      zeile.appendChild(loesen);
      return zeile;
    }

    // Nicht verbunden: der feste Wert (wenn die Karte einen hat) bleibt
    // wirksam und ist hier direkt aenderbar; daneben steht die Auswahl, ihn
    // stattdessen an einen Messwert der Anlage zu haengen.
    if (feld) {
      zeile.appendChild(this.zeileZahl(karte, feld, karte.parameter[feld.schluessel], feld.darstellung === "prozent", true));
    } else {
      const hinweis = document.createElement("p");
      hinweis.className = "panel-hinweis";
      hinweis.textContent = "nicht verbunden – ohne Verbindung gilt 0";
      zeile.appendChild(hinweis);
    }

    const auswahl = document.createElement("select");
    const platzhalter = document.createElement("option");
    platzhalter.value = "";
    platzhalter.textContent = "— aus Anlage wählen —";
    auswahl.appendChild(platzhalter);

    const nachKarte = new Map();
    for (const m of messwerte) {
      if (!nachKarte.has(m.karte_name)) nachKarte.set(m.karte_name, []);
      nachKarte.get(m.karte_name).push(m);
    }
    for (const [name, eintraege] of nachKarte) {
      const gruppeEl = document.createElement("optgroup");
      gruppeEl.label = name;
      for (const m of eintraege) {
        const option = document.createElement("option");
        option.value = m.port_id;
        option.textContent = m.label;
        gruppeEl.appendChild(option);
      }
      auswahl.appendChild(gruppeEl);
    }
    auswahl.addEventListener("change", async () => {
      if (!auswahl.value) return;
      await this.verbinde(Number(auswahl.value), port.id);
    });
    zeile.appendChild(auswahl);

    return zeile;
  },

  async verbinde(vonPortId, nachPortId) {
    let antwort;
    try {
      antwort = await fetch("/api/verbindungen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ anlage_id: Editor.anlage.id, von_port_id: vonPortId, nach_port_id: nachPortId }),
      });
    } catch {
      zeigeFehler("Verbindung konnte nicht angelegt werden.");
      return;
    }
    if (!antwort.ok) {
      let text = "Verbindung konnte nicht angelegt werden.";
      try {
        const fehler = await antwort.json();
        if (fehler.fehler) text = fehler.fehler;
      } catch { /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */ }
      zeigeFehler(text);
      return;
    }
    await this.neuLadenUndAnzeigen();
  },

  async loeseVerbindung(pfeilId) {
    let antwort;
    try {
      antwort = await fetch(`/api/pfeile/${pfeilId}`, { method: "DELETE" });
    } catch {
      zeigeFehler("Verbindung konnte nicht gelöst werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Verbindung konnte nicht gelöst werden.");
      return;
    }
    await this.neuLadenUndAnzeigen();
  },

  // Nach einer Verdrahtungs-Aenderung: Anlage komplett neu laden (die
  // Leinwand muss den neuen/verschwundenen Pfeil zeigen) und, falls noch
  // dieselbe Karte gewaehlt ist, das Panel mit den frischen Daten neu bauen.
  async neuLadenUndAnzeigen() {
    const karteId = this.karte ? this.karte.id : null;
    await Editor.laden(Editor.anlage.id);
    if (karteId == null) return;
    const frisch = Editor.karteNach(karteId);
    if (frisch) this.zeige(frisch);
  },

  // -- Verbindungen finden (ohne eigenes Wissen ueber die Datenbank - allein
  // aus dem schon geladenen Editor.anlage, wie es palette.js/pfeile.js auch
  // schon fuer andere Auskuenfte tun). --------------------------------------
  findeVerbindungAn(nachPortId) {
    for (const pfeil of Editor.anlage.pfeile) {
      for (const v of pfeil.verbindungen) {
        if (v.nach_port_id === nachPortId) return { pfeilId: pfeil.id, vonPortId: v.von_port_id };
      }
    }
    return null;
  },

  findeVerbindungVon(vonPortId) {
    for (const pfeil of Editor.anlage.pfeile) {
      for (const v of pfeil.verbindungen) {
        if (v.von_port_id === vonPortId) return { pfeilId: pfeil.id, nachPortId: v.nach_port_id };
      }
    }
    return null;
  },

  findePort(portId) {
    for (const k of Editor.anlage.karten) {
      const p = k.ports.find((pp) => pp.id === portId);
      if (p) return { karte: k, port: p };
    }
    return null;
  },

  zielBeschriftung(vonPortId) {
    const treffer = this.findeVerbindungVon(vonPortId);
    if (!treffer) return null;
    const ziel = this.findePort(treffer.nachPortId);
    return ziel ? `→ ${ziel.karte.name}` : null;
  },

  // Anschluesse ohne Sollwert/Istwert - die stehen schon oben im
  // Regelungsabschnitt, hier noch einmal waeren sie doppelt zu sehen.
  //
  // Jeder Anschluss kommt vom Server schon mit einer lesbaren Beschriftung
  // (karte.ports[].label - core.anlagen._port_label: AUSGABE_LABEL, sonst ein
  // gleichnamiger Parameter, sonst die uebersetzte Rolle), genau wie "Regelt
  // auf" oben schon vorgemacht hat ("kommt von: <Karte> → <Label>") statt
  // technischer Schluessel wie "ausgang_2 · stellgroesse". Teilen sich mehrere
  // Anschluesse dieselbe Beschriftung (mehrere Stellgroessen, mehrere
  // Protokollspalten), haengt hier - und nur hier, wo die Mehrdeutigkeit
  // sichtbar wird - die laufende Nummer aus dem Schluessel an.
  bauePortliste(karte) {
    const ports = document.createElement("div");
    ports.className = "panel-ports";
    const kopf = document.createElement("h3");
    kopf.textContent = "Anschlüsse";
    ports.appendChild(kopf);
    const uebrige = karte.ports.filter((p) => p.rolle !== "istwert" && p.rolle !== "sollwert");

    // Gruppiert nach Beschriftung UND Richtung - ein Eingang und ein Ausgang
    // mit demselben Label (luft_ein/luft_aus -> beide "Zuluft") sind durch den
    // Pfeil (◀/▶) schon eindeutig unterschieden und brauchen keine Nummer.
    const vorkommen = new Map();
    for (const port of uebrige) {
      const schluesselGruppe = `${port.richtung}|${port.label}`;
      vorkommen.set(schluesselGruppe, (vorkommen.get(schluesselGruppe) || 0) + 1);
    }

    for (const port of uebrige) {
      const zeile = document.createElement("div");
      zeile.className = `port-zeile port-zeile-${port.art}`;
      let beschriftung = port.label;
      if (vorkommen.get(`${port.richtung}|${port.label}`) > 1) {
        const treffer = port.schluessel.match(/_(\d+)$/);
        beschriftung += ` ${treffer ? treffer[1] : port.schluessel}`;
      }
      zeile.textContent = `${port.richtung === "ein" ? "◀" : "▶"} ${beschriftung}`;
      zeile.title = port.schluessel;
      ports.appendChild(zeile);
    }
    return ports;
  },

  // Rueckgabe: { ok, feldfehler } - "ok" allein reicht Aufrufern wie dem
  // Bezeichnungsfeld, die keinen konkreten Parameter treffen koennen;
  // Zahlen-/Auswahlfelder (siehe zeileZahl/zeileAuswahl) werten "feldfehler"
  // zusaetzlich aus, um GENAU das abgelehnte Feld zu markieren statt nur
  // irgendeine Fehlermeldung zu zeigen (core.bausteine.basis.pruefe_parameter
  // liefert diese Zuordnung schon vor).
  async speichereParameter(schluessel, wert) {
    return this.speichere({ parameter: { [schluessel]: wert } });
  },

  async speichere(felder) {
    let antwort;
    try {
      antwort = await fetch(`/api/karten/${this.karte.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(felder),
      });
    } catch {
      zeigeFehler("Änderung konnte nicht gespeichert werden.");
      return { ok: false, feldfehler: {} };
    }
    if (!antwort.ok) {
      let text = "Änderung konnte nicht gespeichert werden.";
      let feldfehler = {};
      try {
        const daten = await antwort.json();
        if (daten.fehler) text = daten.fehler;
        if (daten.feldfehler) feldfehler = daten.feldfehler;
      } catch { /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */ }
      zeigeFehler(text);
      return { ok: false, feldfehler };
    }
    return { ok: true, feldfehler: {} };
  },

  // Markiert ein abgelehntes Eingabefeld sichtbar (roter Rahmen) - die
  // Fehlermeldung selbst steht schon, verstaendlich und auf Deutsch, in der
  // Fehlerleiste (zeigeFehler in speichere() oben); hier geht es nur darum,
  // dass erkennbar bleibt, WELCHES Feld gemeint war. Verschwindet von selbst
  // nach kurzer Zeit oder sobald das Feld erneut geaendert wird.
  markiereFeldFehler(eingabe) {
    eingabe.classList.add("panel-feld-fehler");
    eingabe.setAttribute("aria-invalid", "true");
    window.clearTimeout(eingabe._feldFehlerTimer);
    eingabe._feldFehlerTimer = window.setTimeout(() => {
      eingabe.classList.remove("panel-feld-fehler");
      eingabe.removeAttribute("aria-invalid");
    }, 5000);
  },

  zeigeWerte(werteJeKarte) {
    /* Traegt nach einem Lauf die wichtigsten Groessen in die Karten ein -
       so wie die farbigen Felder in der Excel. */
    for (const karte of Editor.anlage.karten) {
      const ziel = document.querySelector(`[data-werte="${karte.id}"]`);
      if (!ziel) continue;
      const werte = werteJeKarte[karte.id] || {};
      const teile = [];
      if ("T_aus" in werte) teile.push(`${werte.T_aus.toFixed(1)} °C`);
      if ("F_aus" in werte) teile.push(`${werte.F_aus.toFixed(1)} g/kg`);
      if ("T_Raum" in werte) teile.push(`Raum ${werte.T_Raum.toFixed(1)} °C`);
      if ("QH" in werte) teile.push(`${werte.QH.toFixed(1)} kW`);
      if ("QK" in werte) teile.push(`${werte.QK.toFixed(1)} kW`);
      if ("PE" in werte) teile.push(`${werte.PE.toFixed(2)} kW`);
      ziel.textContent = teile.join("  ·  ");
    }
  },
};
