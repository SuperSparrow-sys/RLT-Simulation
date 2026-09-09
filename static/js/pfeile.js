/* Pfeile zwischen Karten. Ein Pfeil verbindet KARTEN, nicht Ports - der Server
   ordnet die passenden Anschluesse selbst zu. */

const Pfeile = {
  editor: null,

  binde(editor) {
    this.editor = editor;
    const leinwand = document.getElementById("leinwand");

    /* editor.js' karteGreifen() laesst einen Umschalt-Klick ausdruecklich
       durch (siehe dort), statt seine Ausbreitung zu stoppen - deshalb reicht
       hier ein gewoehnlicher Bubble-Phase-Listener auf der Leinwand. */
    leinwand.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || !e.shiftKey) return;
      const kartenElement = e.target.closest(".karte");
      if (!kartenElement) return;
      e.stopPropagation();
      const id = Number(kartenElement.dataset.id);
      this.ziehenStarten(editor.karteNach(id), e);
    });

    leinwand.addEventListener("dblclick", (e) => {
      const pfeilElement = e.target.closest(".pfeil");
      if (!pfeilElement) return;
      this.loeschen(Number(pfeilElement.dataset.id));
    });
  },

  // Kartenmasse: editor.js traegt die tatsaechliche (durch Textumbruch
  // gewachsene) Breite/Hoehe jeder Karte als karte._breite/_hoehe ein, sobald
  // sie gezeichnet ist - siehe dortiger Kommentar bei zeichneKarte(). Diese
  // Datei liest sie nur, mit Rueckfallwerten fuer den (nie eintretenden, aber
  // billig abzusichernden) Fall, dass eine Karte noch nicht gezeichnet wurde.
  masse(karte) {
    return { b: karte._breite || 190, h: karte._hoehe || 96 };
  },

  /* Aus jeder Kante zeigt eine Richtung nach draussen. Sie bestimmt beides:
     wohin die Bahn die Karte verlaesst und aus welcher Richtung sie an der
     Zielkarte ankommt - und damit, wohin die Pfeilspitze zeigt. */
  NORMALE: {
    rechts: { x: 1, y: 0 },
    links: { x: -1, y: 0 },
    unten: { x: 0, y: 1 },
    oben: { x: 0, y: -1 },
  },

  kanten(von, nach) {
    /* Welche Kante einer Karte ein Pfeil beruehrt, richtet sich nach der
       Lage des Ziels: liegt es ueberwiegend rechts oder links, laufen die
       Pfeile wie in der Excel von rechts (Ausgang) nach links (Eingang);
       liegt es ueberwiegend darueber oder darunter (typisch fuer Regler direkt
       ueber oder unter dem Bauteil, das sie stellen), laufen sie von unten
       nach oben oder umgekehrt. Ohne diese Unterscheidung nahm jeder
       Pfeil - auch ein senkrechter oder ein rueckwaerts laufender wie
       Abluftventilator -> WRG - immer den rechten Rand als Start und den
       linken als Ziel und schlug dabei einen unnoetigen Bogen quer durch
       dazwischenliegende Karten. */
    const vm = this.masse(von);
    const nm = this.masse(nach);
    const dx = (nach.pos_x + nm.b / 2) - (von.pos_x + vm.b / 2);
    const dy = (nach.pos_y + nm.h / 2) - (von.pos_y + vm.h / 2);

    if (Math.abs(dx) >= Math.abs(dy)) {
      return dx >= 0
        ? { kanteVon: "rechts", kanteNach: "links" }
        : { kanteVon: "links", kanteNach: "rechts" };
    }
    return dy >= 0
      ? { kanteVon: "unten", kanteNach: "oben" }
      : { kanteVon: "oben", kanteNach: "unten" };
  },

  // Laenge einer Kante: bei oben/unten die Breite der Karte, sonst ihre Hoehe.
  kantenlaenge(karte, kante) {
    const m = this.masse(karte);
    return kante === "oben" || kante === "unten" ? m.b : m.h;
  },

  /* Ein Punkt auf einer Kante, 'versatz' Punkte vom oberen bzw. linken Ende
     der Kante entfernt. */
  punktAufKante(karte, kante, versatz) {
    const m = this.masse(karte);
    if (kante === "rechts") return { x: karte.pos_x + m.b, y: karte.pos_y + versatz };
    if (kante === "links") return { x: karte.pos_x, y: karte.pos_y + versatz };
    if (kante === "unten") return { x: karte.pos_x + versatz, y: karte.pos_y + m.h };
    return { x: karte.pos_x + versatz, y: karte.pos_y };
  },

  /* Wo auf der Kante sitzt der i-te von n Pfeilen?

     Vorher endeten ALLE Pfeile einer Karte im selben Punkt - der Mitte ihrer
     Kante. An der Waermerueckgewinnung der AX_SIM 2.1 laufen dort sieben
     Wege zusammen; sie lagen als Buendel uebereinander, und wo zwei sich
     kurz vor der Karte kreuzten, sah es aus wie ein Knick. Jetzt faechern
     sie auf: fester Abstand von 16 Punkten um die Mitte herum, gedeckelt
     durch die Kantenlaenge, damit auch acht Pfeile noch auf der Karte
     bleiben. Zwei Pfeile sehen dadurch nicht "auseinandergezogen" aus (sie
     stehen 16 Punkte auseinander), acht ordnen sich sichtbar. */
  ABSTAND_AUF_KANTE: 16,

  versatz(karte, kante, index, anzahl) {
    const laenge = this.kantenlaenge(karte, kante);
    const abstand = Math.min(this.ABSTAND_AUF_KANTE, laenge / (anzahl + 1));
    return laenge / 2 + (index - (anzahl - 1) / 2) * abstand;
  },

  /* Die Bahn verlaesst beide Karten SENKRECHT zu ihrer Kante.

     Vorher lagen die Kontrollpunkte auf halber Strecke der Hauptachse. Bei
     zwei Karten fast untereinander ergab das eine Bahn, die schraeg aus der
     Karte trat und kurz vor dem Ziel wieder einschwenkte - der Knick, der
     auf dem Schema als Fehler gelesen wurde. Senkrecht heraus und senkrecht
     hinein ist ausserdem die Lesart, die ein Anlagenbauer von einem Schema
     erwartet: Ein Weg verlaesst ein Bauteil an einem Anschluss, nicht
     irgendwo an seiner Flanke.

     Der "Zug" (wie weit die Kontrollpunkte hinausreichen) waechst mit dem
     Abstand, bleibt aber zwischen 36 und 120 Punkten: darunter wird die
     Bahn eckig, darueber schlaegt sie einen Bogen, der mehr Platz braucht
     als der Weg lang ist. */
  bahnPunkte(a, b, normaleVon, normaleNach) {
    const strecke = Math.hypot(b.x - a.x, b.y - a.y);
    const zug = Math.max(36, Math.min(120, strecke * 0.45));
    const c1 = { x: a.x + normaleVon.x * zug, y: a.y + normaleVon.y * zug };
    const c2 = { x: b.x + normaleNach.x * zug, y: b.y + normaleNach.y * zug };
    return `M ${a.x} ${a.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${b.x} ${b.y}`;
  },

  /* Die Spitze am Ziel - eine offene Winkelform, kein gefuelltes Dreieck:
     Sie wird gestrichen wie die Bahn selbst und nimmt damit deren Farbe an,
     ohne dass es je Kombination aus Luftart und Wegart eine eigene
     Fuellregel braeuchte.

     Ohne sie war einem Pfeil nicht anzusehen, wohin er zeigt - bei einem
     Regelweg (wer stellt wen?) und bei Zu-/Abluft ist das aber gerade die
     Auskunft, auf die es ankommt. */
  /* Die Groesse richtet sich nach der Strichstaerke der Bahn - und die steht
     im Stylesheet (.pfeil-luft 3,5 Punkte, .pfeil-protokoll 1,2). Eine feste
     Groesse liess die Spitze eines Luftwegs zu einem Querbalken verschmelzen:
     Bei 3,5 Punkten Strich und 7 Punkten Schenkellaenge liegen die beiden
     Schenkel praktisch aufeinander. Ausgelesen statt in zwei Dateien
     gepflegt - sonst laufen Strichstaerke und Spitze auseinander, sobald
     eine von beiden angefasst wird. */
  SPITZE_JE_STRICH: 3.6,
  SPITZE_MIN: 7,
  SPITZE_MAX: 14,
  /* Rund 36 Grad zu jeder Seite - ein offener Winkel wie am Vor-/Zurueck-Pfeil
     eines Browsers. Enger gestellt legen sich die beiden Schenkel bei einem
     3,5 Punkte dicken Luftweg fast aufeinander und die Spitze wird zu einem
     Querbalken. */
  SPITZENWINKEL: 0.62,

  /* Die Strichstaerke je Klassenkombination - einmal gemessen, dann gemerkt.

     Gemessen wird an einer leeren Probebahn, weil die Zahl allein im
     Stylesheet steht. Ohne das Gedaechtnis waere es eine Stilabfrage je
     Pfeil: Beim Ziehen einer Karte werden ALLE Pfeile in jedem Bild neu
     gezeichnet (editor-auswahl.js), bei der AX_SIM 2.1 also 52 Abfragen
     mitten im Aufbauen - jede erzwingt einen Stilabgleich. Die Kombinationen
     sind ueberschaubar (Luftart mal Wegart, keine zehn), und aendern kann
     sich eine Strichstaerke zur Laufzeit nicht. */
  _strichstaerken: new Map(),

  strichstaerke(klassen, ebene, NSS) {
    const schluessel = klassen.join(" ");
    if (this._strichstaerken.has(schluessel)) {
      return this._strichstaerken.get(schluessel);
    }
    const probe = document.createElementNS(NSS, "path");
    probe.setAttribute("class", schluessel);
    ebene.appendChild(probe);
    const wert = parseFloat(window.getComputedStyle(probe).strokeWidth) || 2;
    probe.remove();
    this._strichstaerken.set(schluessel, wert);
    return wert;
  },

  spitzenlaenge(strich) {
    return Math.max(
      this.SPITZE_MIN,
      Math.min(this.SPITZE_MAX, strich * this.SPITZE_JE_STRICH)
    );
  },

  spitzePunkte(b, normaleNach, s) {
    // Ankunftsrichtung: entgegen der nach aussen zeigenden Normalen.
    const rx = -normaleNach.x;
    const ry = -normaleNach.y;
    const w = this.SPITZENWINKEL;
    const cos = Math.cos(w);
    const sin = Math.sin(w);
    // Zwei um +-w zurueckgedrehte Schenkel, beide am Ziel zusammenlaufend.
    const l = { x: b.x - s * (rx * cos - ry * sin), y: b.y - s * (rx * sin + ry * cos) };
    const r = { x: b.x - s * (rx * cos + ry * sin), y: b.y - s * (-rx * sin + ry * cos) };
    return `M ${l.x} ${l.y} L ${b.x} ${b.y} L ${r.x} ${r.y}`;
  },

  /* Die Bahn laeuft bis in die Spitze hinein, nicht bis kurz davor.

     Zuerst hatte ich sie ein Stueck vorher enden lassen, damit die offene
     Spitze nicht auf der eigenen Linie liegt. Das Ergebnis war ein Winkel,
     der neben seinem Strich schwebte - Strich und Spitze passten nicht
     zusammen. Beim Vor-/Zurueck-Pfeil eines Browsers laeuft der Schaft bis
     zwischen die Schenkel; genau das ergibt mit derselben Strichstaerke und
     runden Enden EINE Form statt zweier Teile. */

  // Dieselben vier Energierollen wie core/bausteine/basis.py ENERGIEROLLEN -
  // sie fuehren an der Bilanzkarte zusammen und werden darum eigens
  // gekennzeichnet, statt wie jedes andere Signal auszusehen (siehe
  // static/css/style.css, .pfeil-energie).
  ENERGIEROLLEN: ["strom", "waerme", "kaelte", "wasser"],

  /* Welche Luft fuehrt dieser Weg? Die Anschluesse wissen es laengst
     (core/bausteine/basis.py: AUSSENLUFT, FORTLUFT, UMLUFT, ABLUFT, ZULUFT,
     dazu LUFTWEG fuer neutrale Bauteile wie einen Erhitzer) - gezeichnet
     wurde es bisher nicht, alle Luftwege sahen gleich aus.

     Die Reihenfolge ist die Rangfolge: von den beiden Anschluessen eines
     Weges gewinnt die aussagekraeftigere Rolle, und die Enden der Kette
     (Aussenluft, Fortluft) sind aussagekraeftiger als ihre Mitte. So wird
     aus 'abluft -> fortluft' ein Fortluftweg und aus 'aussenluft ->
     zuluft' ein Aussenluftweg - beides das, was ein Anlagenbauer auf dem
     Schema erwartet. Bleiben BEIDE Enden neutral (luftweg), bleibt der Weg
     der neutrale, blaue Luftweg wie bisher; gemessen an den drei echten
     Anlagen des Benutzers kommt das bei keiner einzigen der 44
     Luftverbindungen vor. */
  LUFTROLLEN: ["aussenluft", "fortluft", "umluft", "abluft", "zuluft"],

  klassenDesPfeils(pfeil, anlage) {
    const ports = new Map();
    for (const karte of anlage.karten) {
      for (const port of karte.ports) ports.set(port.id, port);
    }

    const luftrollen = new Set();
    let hatLuft = false;
    let hatEnergie = false;
    let hatProtokoll = false;
    for (const v of pfeil.verbindungen) {
      const von = ports.get(v.von_port_id) || {};
      const nach = ports.get(v.nach_port_id) || {};
      if (von.art === "luft") {
        hatLuft = true;
        luftrollen.add(von.rolle);
        luftrollen.add(nach.rolle);
      }
      if (this.ENERGIEROLLEN.includes(von.rolle)) hatEnergie = true;
      // Meldeweg: was nur zum Mitschreiben an einen Datenlogger geht
      // (Rolle 'protokoll' am Ziel-Anschluss).
      if (nach.rolle === "protokoll") hatProtokoll = true;
    }

    /* Traegt der Pfeil mindestens eine Luftverbindung, wird er dick
       gezeichnet - und traegt zusaetzlich die Klasse seiner Luftart. */
    if (hatLuft) {
      const rolle = this.LUFTROLLEN.find((r) => luftrollen.has(r));
      return rolle ? ["pfeil-luft", `pfeil-luft-${rolle}`] : ["pfeil-luft"];
    }
    // Energie- und Meldewege sind Buchhaltung, kein Regelkreis: sie
    // bekommen eine eigene Klasse, damit sie zurueckhaltender gezeichnet
    // und gemeinsam ausgeblendet werden koennen (siehe style.css,
    // .leinwand-ohne-meldewege).
    if (hatEnergie) return ["pfeil-energie", "pfeil-meldeweg"];
    if (hatProtokoll) return ["pfeil-protokoll", "pfeil-meldeweg"];
    return ["pfeil-signal"];
  },

  /* Wer teilt sich welche Kante?

     Zwei Durchgaenge, weil der Platz eines Pfeils auf einer Kante davon
     abhaengt, wieviele andere dieselbe Kante benutzen - das steht erst fest,
     wenn alle Kanten bestimmt sind. Innerhalb einer Kante werden sie nach
     der Lage des jeweils ANDEREN Endes sortiert: So kreuzen sich zwei Wege
     nicht schon auf den letzten Punkten vor der Karte, nur weil sie in der
     Reihenfolge der Datenbank gezeichnet wurden. */
  belegungBerechnen(wege) {
    const belegung = new Map();
    const eintragen = (karte, kante, weg, ende) => {
      const schluessel = `${karte.id}:${kante}`;
      if (!belegung.has(schluessel)) belegung.set(schluessel, []);
      belegung.get(schluessel).push({ weg, ende });
    };
    for (const weg of wege) {
      eintragen(weg.von, weg.kanteVon, weg, "von");
      eintragen(weg.nach, weg.kanteNach, weg, "nach");
    }

    for (const [schluessel, liste] of belegung) {
      const kante = schluessel.split(":")[1];
      const laengs = kante === "oben" || kante === "unten" ? "pos_x" : "pos_y";
      liste.sort((p, q) => {
        const andereP = p.ende === "von" ? p.weg.nach : p.weg.von;
        const andereQ = q.ende === "von" ? q.weg.nach : q.weg.von;
        return andereP[laengs] - andereQ[laengs];
      });
      liste.forEach((eintrag, i) => {
        const feld = eintrag.ende === "von" ? "platzVon" : "platzNach";
        eintrag.weg[feld] = { index: i, anzahl: liste.length };
      });
    }
  },

  zeichneAlle(anlage) {
    const ebene = document.getElementById("pfeile");
    ebene.textContent = "";
    const NSS = "http://www.w3.org/2000/svg";

    const wege = [];
    for (const pfeil of anlage.pfeile) {
      const von = anlage.karten.find((k) => k.id === pfeil.von_karte_id);
      const nach = anlage.karten.find((k) => k.id === pfeil.nach_karte_id);
      if (!von || !nach) continue;
      wege.push({ pfeil, von, nach, ...this.kanten(von, nach) });
    }
    this.belegungBerechnen(wege);

    for (const weg of wege) {
      const { pfeil, von, nach, kanteVon, kanteNach } = weg;

      const a = this.punktAufKante(
        von, kanteVon,
        this.versatz(von, kanteVon, weg.platzVon.index, weg.platzVon.anzahl)
      );
      const b = this.punktAufKante(
        nach, kanteNach,
        this.versatz(nach, kanteNach, weg.platzNach.index, weg.platzNach.anzahl)
      );
      const normaleVon = this.NORMALE[kanteVon];
      const normaleNach = this.NORMALE[kanteNach];

      const klassen = ["pfeil", ...this.klassenDesPfeils(pfeil, anlage)];
      if (pfeil.mehrdeutig) klassen.push("pfeil-mehrdeutig");

      // Die Spitze richtet sich nach der Strichstaerke der Bahn.
      const s = this.spitzenlaenge(this.strichstaerke(klassen, ebene, NSS));

      const bahn = document.createElementNS(NSS, "path");
      bahn.setAttribute("d", this.bahnPunkte(a, b, normaleVon, normaleNach));
      bahn.setAttribute("class", klassen.join(" "));
      bahn.setAttribute("data-id", pfeil.id);

      const hinweis = document.createElementNS(NSS, "title");
      hinweis.textContent =
        `${von.name} → ${nach.name} (${pfeil.verbindungen.length} Verbindungen)` +
        (pfeil.mehrdeutig
          ? " – mehrdeutig: es gab mehr als eine passende Zuordnung, bitte prüfen"
          : "");
      bahn.appendChild(hinweis);

      // "Pruefen einer bestehenden Verbindung": beim Ueberfahren des Pfeils
      // leuchten genau die zwei Anschluesse auf, die er tatsaechlich
      // verbindet - nicht der ganze Portkranz beider Karten. So bleibt die
      // Antwort auf "welche Anschluesse genau?" auffindbar, ohne dass die
      // Grundansicht dafuer staendig alle Anschluesse zeigen muss.
      const portIds = pfeil.verbindungen.flatMap((v) => [v.von_port_id, v.nach_port_id]);
      const beteiligtePorts = portIds
        .map((id) => document.querySelector(`[data-port="${id}"]`))
        .filter(Boolean);
      bahn.addEventListener("pointerenter", () => {
        beteiligtePorts.forEach((p) => p.classList.add("port-in-pruefung"));
      });
      bahn.addEventListener("pointerleave", () => {
        beteiligtePorts.forEach((p) => p.classList.remove("port-in-pruefung"));
      });

      ebene.appendChild(bahn);

      /* Die Spitze traegt dieselben Artklassen wie die Bahn und damit deren
         Farbe und Strichstaerke; .pfeil-spitze nimmt ihr nur das Strichmuster
         (siehe editor.css) - ein gestrichelter Winkel waere kaum als Spitze
         zu erkennen. Sie faengt keine Zeiger ab: getroffen wird die Bahn. */
      const spitze = document.createElementNS(NSS, "path");
      spitze.setAttribute("d", this.spitzePunkte(b, normaleNach, s));
      spitze.setAttribute("class", [...klassen, "pfeil-spitze"].join(" "));
      spitze.setAttribute("data-id", pfeil.id);
      ebene.appendChild(spitze);
    }
  },

  ziehenStarten(karte, ereignis) {
    const NSS = "http://www.w3.org/2000/svg";
    const leinwand = document.getElementById("leinwand");

    // Auf schmalem Hochformat mit Finger (siehe editor.js,
    // seitenbereichSchmal()) haengt das Parameterfenster als Schublade offen
    // ueber der Leinwand, sobald die Quellkarte ausgewaehlt wurde (genau der
    // Zustand, aus dem heraus ueberhaupt gezogen wird) - eine Zielkarte
    // koennte darunter liegen und waere fuer den Zug unerreichbar. Beide
    // Seitenbereiche schliessen, bevor die Zielsuche beginnt, gibt der
    // ganzen Leinwand den Platz zurueck.
    if (this.editor.seitenbereichSchmal()) {
      this.editor.seitenbereichSchliessen("palette");
      this.editor.seitenbereichSchliessen("panel");
    }

    const vorschau = document.createElementNS(NSS, "path");
    vorschau.setAttribute("class", "pfeil pfeil-vorschau");
    document.getElementById("pfeile").appendChild(vorschau);

    const quellElement = document.querySelector(`.karte[data-id="${karte.id}"]`);
    // Waehrend des Ziehens bleibt der Anknuepfpunkt der Quellkarte sichtbar
    // (statt nach dem ersten Pointerdown wieder unter :hover zu verschwinden,
    // sobald der Zeiger die Karte verlaesst) - siehe .karte.verbindet-von in
    // style.css. leinwand traegt dieselbe Markierung fuer den Cursor.
    if (quellElement) quellElement.classList.add("verbindet-von");
    leinwand.classList.add("verbindet-aktiv");

    const vm = this.masse(karte);
    const mitteX = karte.pos_x + vm.b / 2;
    const mitteY = karte.pos_y + vm.h / 2;
    const sicht = this.editor.sicht;

    const aufraeumen = () => {
      window.removeEventListener("pointermove", bewegen);
      window.removeEventListener("pointerup", loslassen);
      window.removeEventListener("pointercancel", abgebrochen);
      window.removeEventListener("keydown", beiEscape);
      vorschau.remove();
      if (quellElement) quellElement.classList.remove("verbindet-von");
      leinwand.classList.remove("verbindet-aktiv");
      document.querySelectorAll(".karte.ziel").forEach((g) =>
        g.classList.remove("ziel")
      );
    };
    const beiEscape = (e) => {
      if (e.key === "Escape") aufraeumen();
    };

    const bewegen = (e) => {
      const kasten = leinwand.getBoundingClientRect();
      const x = (e.clientX - kasten.left - sicht.x) / sicht.zoom;
      const y = (e.clientY - kasten.top - sicht.y) / sicht.zoom;

      // Der Anfangspunkt der Vorschau folgt dem Zeiger an den Rand der
      // Quellkarte, die er gerade verlaesst - so startet die Linie sichtbar
      // an der Karte, egal auf welcher Seite das Ziel liegt, statt immer
      // starr am rechten Rand zu kleben (siehe rand() weiter oben, dieselbe
      // Idee fuer fertige Pfeile).
      const dx = x - mitteX, dy = y - mitteY;
      const start = Math.abs(dx) >= Math.abs(dy)
        ? { x: karte.pos_x + (dx >= 0 ? vm.b : 0), y: mitteY }
        : { x: mitteX, y: karte.pos_y + (dy >= 0 ? vm.h : 0) };
      vorschau.setAttribute("d", `M ${start.x} ${start.y} L ${x} ${y}`);

      const ziel = document.elementFromPoint(e.clientX, e.clientY);
      document.querySelectorAll(".karte.ziel").forEach((g) =>
        g.classList.remove("ziel")
      );
      const zielKarte = ziel && ziel.closest(".karte");
      if (zielKarte && Number(zielKarte.dataset.id) !== karte.id) {
        zielKarte.classList.add("ziel");
      }
    };

    const loslassen = async (e) => {
      aufraeumen();

      const ziel = document.elementFromPoint(e.clientX, e.clientY);
      const zielKarte = ziel && ziel.closest(".karte");
      if (!zielKarte) return;
      const zielId = Number(zielKarte.dataset.id);
      if (zielId === karte.id) return;

      let antwort;
      try {
        antwort = await fetch("/api/pfeile", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            anlage_id: this.editor.anlage.id,
            von_karte_id: karte.id,
            nach_karte_id: zielId,
          }),
        });
      } catch {
        zeigeFehler("Pfeil konnte nicht angelegt werden.");
        return;
      }

      if (!antwort.ok) {
        let text = "Verbindung nicht möglich";
        try {
          const fehler = await antwort.json();
          if (fehler.fehler) text = fehler.fehler;
        } catch {
          /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */
        }
        zeigeFehler(text);
        return;
      }
      await this.editor.laden(this.editor.anlage.id);
    };

    // pointercancel: derselbe Grund wie bei karteGreifen() in editor.js
    // (siehe dortiger Kommentar) - iOS kann eine Beruehrungsfolge mitten in
    // der Geste abbrechen. Hier gibt es keine sinnvolle "Loslassen"-Stelle
    // mehr (kein echter Zeiger mehr da, an dem eine Zielkarte zu ermitteln
    // waere) - deshalb nur aufraeumen() statt loslassen(): die Vorschau
    // verschwindet sauber, ohne einen Pfeil an eine zufaellige letzte
    // Position anzulegen.
    const abgebrochen = () => aufraeumen();
    window.addEventListener("pointermove", bewegen);
    window.addEventListener("pointerup", loslassen);
    window.addEventListener("pointercancel", abgebrochen);
    window.addEventListener("keydown", beiEscape);
  },

  async loeschen(pfeilId) {
    let antwort;
    try {
      antwort = await fetch(`/api/pfeile/${pfeilId}`, { method: "DELETE" });
    } catch {
      zeigeFehler("Pfeil konnte nicht gelöscht werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Pfeil konnte nicht gelöscht werden.");
      return;
    }
    await this.editor.laden(this.editor.anlage.id);
  },
};
