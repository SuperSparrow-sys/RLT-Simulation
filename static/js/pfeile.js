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

  rand(von, nach) {
    /* Ausgang rechts, Eingang links - so laufen die Pfeile wie in der Excel. */
    return {
      a: { x: von.pos_x + 150, y: von.pos_y + 48 },
      b: { x: nach.pos_x, y: nach.pos_y + 48 },
    };
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

      const { a, b } = this.rand(von, nach);
      const mitteX = (a.x + b.x) / 2;
      const bahn = document.createElementNS(NSS, "path");
      bahn.setAttribute(
        "d",
        `M ${a.x} ${a.y} C ${mitteX} ${a.y}, ${mitteX} ${b.y}, ${b.x} ${b.y}`
      );
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

      ebene.appendChild(bahn);
    }
  },

  ziehenStarten(karte, ereignis) {
    const NSS = "http://www.w3.org/2000/svg";
    const leinwand = document.getElementById("leinwand");
    const vorschau = document.createElementNS(NSS, "path");
    vorschau.setAttribute("class", "pfeil pfeil-vorschau");
    document.getElementById("pfeile").appendChild(vorschau);

    const start = { x: karte.pos_x + 150, y: karte.pos_y + 48 };
    const sicht = this.editor.sicht;

    const bewegen = (e) => {
      const kasten = leinwand.getBoundingClientRect();
      const x = (e.clientX - kasten.left - sicht.x) / sicht.zoom;
      const y = (e.clientY - kasten.top - sicht.y) / sicht.zoom;
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
      window.removeEventListener("pointermove", bewegen);
      window.removeEventListener("pointerup", loslassen);
      vorschau.remove();
      document.querySelectorAll(".karte.ziel").forEach((g) =>
        g.classList.remove("ziel")
      );

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

    window.addEventListener("pointermove", bewegen);
    window.addEventListener("pointerup", loslassen);
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
