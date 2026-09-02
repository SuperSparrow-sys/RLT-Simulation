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

  rand(von, nach) {
    /* Welche Kante einer Karte ein Pfeil beruehrt, richtet sich nach der
       Lage des Ziels: liegt es ueberwiegend rechts oder links, laufen die
       Pfeile wie in der Excel von rechts (Ausgang) nach links (Eingang);
       liegt es ueberwiegend darueber oder darunter (typisch fuer Regler direkt
       ueber oder unter dem Bauteil, das sie stellen), laufen sie von unten
       nach oben oder umgekehrt. Ohne diese Unterscheidung nahm jeder
       Pfeil - auch ein senkrechter oder ein rueckwaerts laufender wie
       Abluftventilator -> WRG - immer den rechten Rand als Start und den
       linken als Ziel und schlug dabei einen unnoetigen Bogen quer durch
       dazwischenliegende Karten (siehe Task-Beschreibung, Befund 5). */
    const vm = this.masse(von);
    const nm = this.masse(nach);
    const vMitteX = von.pos_x + vm.b / 2;
    const vMitteY = von.pos_y + vm.h / 2;
    const nMitteX = nach.pos_x + nm.b / 2;
    const nMitteY = nach.pos_y + nm.h / 2;
    const dx = nMitteX - vMitteX;
    const dy = nMitteY - vMitteY;

    if (Math.abs(dx) >= Math.abs(dy)) {
      return dx >= 0
        ? { a: { x: von.pos_x + vm.b, y: vMitteY }, b: { x: nach.pos_x, y: nMitteY }, achse: "x" }
        : { a: { x: von.pos_x, y: vMitteY }, b: { x: nach.pos_x + nm.b, y: nMitteY }, achse: "x" };
    }
    return dy >= 0
      ? { a: { x: vMitteX, y: von.pos_y + vm.h }, b: { x: nMitteX, y: nach.pos_y }, achse: "y" }
      : { a: { x: vMitteX, y: von.pos_y }, b: { x: nMitteX, y: nach.pos_y + nm.h }, achse: "y" };
  },

  /* Baut die Bezierbahn passend zur in rand() gewaehlten Achse: bei einer
     ueberwiegend waagrechten Verbindung liegen die Kontrollpunkte auf halber
     Breite (ein S in x), bei einer ueberwiegend senkrechten auf halber Hoehe
     (ein S in y) - sonst wuerde eine senkrechte Verbindung (Regler direkt
     ueber/unter seinem Bauteil) unnoetig seitlich ausholen. */
  bahnPunkte(a, b, achse) {
    if (achse === "y") {
      const mitteY = (a.y + b.y) / 2;
      return `M ${a.x} ${a.y} C ${a.x} ${mitteY}, ${b.x} ${mitteY}, ${b.x} ${b.y}`;
    }
    const mitteX = (a.x + b.x) / 2;
    return `M ${a.x} ${a.y} C ${mitteX} ${a.y}, ${mitteX} ${b.y}, ${b.x} ${b.y}`;
  },

  // Dieselben vier Energierollen wie core/bausteine/basis.py ENERGIEROLLEN -
  // sie fuehren an der Bilanzkarte zusammen und werden darum eigens
  // gekennzeichnet, statt wie jedes andere Signal auszusehen (siehe
  // static/css/style.css, .pfeil-energie).
  ENERGIEROLLEN: ["strom", "waerme", "kaelte", "wasser"],

  artDesPfeils(pfeil, anlage) {
    /* Traegt der Pfeil mindestens eine Luftverbindung, wird er dick gezeichnet. */
    const ports = new Map();
    for (const karte of anlage.karten) {
      for (const port of karte.ports) ports.set(port.id, port);
    }
    const hatLuft = pfeil.verbindungen.some(
      (v) => (ports.get(v.von_port_id) || {}).art === "luft"
    );
    if (hatLuft) return "luft";
    const hatEnergie = pfeil.verbindungen.some((v) =>
      this.ENERGIEROLLEN.includes((ports.get(v.von_port_id) || {}).rolle)
    );
    return hatEnergie ? "energie" : "signal";
  },

  zeichneAlle(anlage) {
    const ebene = document.getElementById("pfeile");
    ebene.textContent = "";
    const NSS = "http://www.w3.org/2000/svg";

    for (const pfeil of anlage.pfeile) {
      const von = anlage.karten.find((k) => k.id === pfeil.von_karte_id);
      const nach = anlage.karten.find((k) => k.id === pfeil.nach_karte_id);
      if (!von || !nach) continue;

      const { a, b, achse } = this.rand(von, nach);
      const bahn = document.createElementNS(NSS, "path");
      bahn.setAttribute("d", this.bahnPunkte(a, b, achse));
      const klassen = ["pfeil", `pfeil-${this.artDesPfeils(pfeil, anlage)}`];
      if (pfeil.mehrdeutig) klassen.push("pfeil-mehrdeutig");
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
