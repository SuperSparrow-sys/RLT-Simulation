/* Rechte Spalte: die Parameter der gewaehlten Karte, erzeugt aus ihrer
   Typdeklaration. Jede Aenderung wird sofort gespeichert. */

const Panel = {
  karte: null,

  leeren() {
    this.karte = null;
    document.getElementById("panel").innerHTML =
      '<p class="leerhinweis">Karte auswählen, um ihre Parameter zu sehen.</p>';
  },

  zeige(karte) {
    this.karte = karte;
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

    for (const feld of karte.felder) {
      const wert = karte.parameter[feld.schluessel];
      if (Array.isArray(wert) || (wert && typeof wert === "object")) {
        panel.appendChild(this.zeileListe(feld, wert));
        continue;
      }
      if (feld.auswahl && feld.auswahl.length) {
        panel.appendChild(this.zeileAuswahl(feld, wert));
      } else {
        panel.appendChild(this.zeileZahl(feld, wert));
      }
    }

    const ports = document.createElement("div");
    ports.className = "panel-ports";
    ports.innerHTML = "<h3>Anschlüsse</h3>";
    for (const port of karte.ports) {
      const zeile = document.createElement("div");
      zeile.className = `port-zeile port-zeile-${port.art}`;
      zeile.textContent =
        `${port.richtung === "ein" ? "◀" : "▶"} ${port.schluessel} · ${port.rolle}`;
      ports.appendChild(zeile);
    }
    panel.appendChild(ports);
  },

  _huelle(beschriftung, eingabe, einheit) {
    const zeile = document.createElement("label");
    zeile.className = "panel-zeile";
    const text = document.createElement("span");
    text.className = "panel-label";
    text.textContent = einheit ? `${beschriftung} [${einheit}]` : beschriftung;
    zeile.appendChild(text);
    zeile.appendChild(eingabe);
    return zeile;
  },

  zeileText(beschriftung, wert, beiAenderung) {
    const eingabe = document.createElement("input");
    eingabe.type = "text";
    eingabe.value = wert;
    eingabe.addEventListener("change", () => beiAenderung(eingabe.value));
    return this._huelle(beschriftung, eingabe, "");
  },

  zeileZahl(feld, wert) {
    const eingabe = document.createElement("input");
    eingabe.type = "number";
    eingabe.step = "any";
    eingabe.value = wert;
    eingabe.addEventListener("change", async () => {
      const zahl = Number(eingabe.value);
      this.karte.parameter[feld.schluessel] = zahl;
      await this.speichere({ parameter: { [feld.schluessel]: zahl } });
    });
    return this._huelle(feld.label, eingabe, feld.einheit);
  },

  zeileAuswahl(feld, wert) {
    const eingabe = document.createElement("select");
    for (const moeglichkeit of feld.auswahl) {
      const option = document.createElement("option");
      option.value = moeglichkeit;
      option.textContent = moeglichkeit;
      if (moeglichkeit === wert) option.selected = true;
      eingabe.appendChild(option);
    }
    eingabe.addEventListener("change", async () => {
      this.karte.parameter[feld.schluessel] = eingabe.value;
      await this.speichere({ parameter: { [feld.schluessel]: eingabe.value } });
    });
    return this._huelle(feld.label, eingabe, feld.einheit);
  },

  zeileListe(feld, wert) {
    /* Listen und Tabellen - Zeitplaene, Lastgaenge, Ferien - als JSON-Feld.
       Bewusst schlicht: die Werte sind selten und die Struktur ist sichtbar. */
    const eingabe = document.createElement("textarea");
    eingabe.rows = 4;
    eingabe.value = JSON.stringify(wert);
    eingabe.addEventListener("change", async () => {
      try {
        const gelesen = JSON.parse(eingabe.value);
        this.karte.parameter[feld.schluessel] = gelesen;
        await this.speichere({ parameter: { [feld.schluessel]: gelesen } });
        eingabe.classList.remove("fehlerhaft");
      } catch (fehler) {
        eingabe.classList.add("fehlerhaft");
      }
    });
    return this._huelle(feld.label, eingabe, feld.einheit);
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
      return;
    }
    if (!antwort.ok) zeigeFehler("Änderung konnte nicht gespeichert werden.");
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
