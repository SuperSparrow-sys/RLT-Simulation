/* Wetterseite: die Datensaetze verwalten und neue holen (Online-Abruf oder
   eigene TRY-Dateien).

   Die Liste selbst steht fertig in der Seite (templates/wetter.html, gefuellt
   in routes/pages.py: wetter()) - dieses Modul verdrahtet nur Umbenennen und
   Loeschen daran und bedient die beiden Formulare zum Hinzufuegen.

   Bis zum Umbau der Oberflaeche steckte all das im gemeinsamen start.js, das
   beide Seiten in voller Laenge luden: Die Wetterseite bekam die
   Projektdialoge mitgeliefert, die Startseite die Ordnerauswertung - zusammen
   44 kB, von denen jede Seite gut die Haelfte nie anfasste. zeigeFehler(),
   htmlSicher() und die beiden Dialoge stehen in static/js/dialoge.js. */

// Erstes Jahr, das die Open-Meteo Archive-API anbietet (core/wetter/openmeteo.py:
// FRUEHESTES_JAHR) - hier dupliziert, weil die Grenze rein in der Oberflaeche
// gebraucht wird und dafuer keine eigene Schnittstelle lohnt.
const WETTER_FRUEHESTES_JAHR = 1940;

// Endungen, die der Server lesen kann (core/wetter/einlesen.py: ENDUNGEN).
// Wonach hier nicht gefiltert wird, geht auch nicht ueber die Leitung - der
// Ordner eines Testreferenzjahrs enthaelt neben den Daten ein Handbuch von
// rund zwei Megabyte, das auf dem Rechner des Nutzers bleiben soll.
const WETTER_ENDUNGEN = [".dat", ".xls", ".xlsx", ".xlsm", ".csv"];

// Art des TRY aus dem Kuerzel im Dateinamen (Handbuch Kap. 2, AAAA) - dieselbe
// Zuordnung wie in core/wetter/try_dat.py: ARTEN. Hier nur fuer die
// Beschriftung der Ankreuzliste; verbindlich benannt wird auf dem Server.
const TRY_ARTEN = {
  jahr: "mittleres Jahr",
  somm: "extremer Sommer",
  wint: "extremer Winter",
};
const TRY_NAMENSMUSTER = /^TR[YJ](\d{4})_[^_]*_(Jahr|Somm|Wint)/i;


// Archive werden bewusst nicht ausgepackt (core/wetter/einlesen.py:
// ARCHIVENDUNGEN). Sie werden hier trotzdem erkannt, damit ein Nutzer, der ein
// heruntergeladenes Zip waehlt, erfaehrt, was er tun soll - statt vor einer
// leeren Liste zu stehen.
const WETTER_ARCHIVENDUNGEN = [".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2"];

const ARCHIV_HINWEIS =
  "Archive werden nicht ausgepackt. Bitte das Archiv entpacken und den " +
  "entpackten Ordner auswählen – die Dateien darin werden dann gefunden, " +
  "auch in Unterordnern.";

function wetterIstArchiv(dateiname) {
  const klein = dateiname.toLowerCase();
  return WETTER_ARCHIVENDUNGEN.some((endung) => klein.endsWith(endung));
}

function wetterEndungErlaubt(dateiname) {
  const klein = dateiname.toLowerCase();
  return WETTER_ENDUNGEN.some((endung) => klein.endsWith(endung));
}

// "TRY2015_510881137633_Somm.dat" -> "2015 - extremer Sommer". Alles, was nicht
// auf die Konvention passt, behaelt seinen Dateinamen: raten waere schlechter
// als zeigen, was dasteht.
function wetterBeschriftung(dateiname) {
  const treffer = TRY_NAMENSMUSTER.exec(dateiname);
  if (!treffer) return dateiname;
  const art = TRY_ARTEN[treffer[2].toLowerCase()];
  return art ? `${treffer[1]} – ${art}` : dateiname;
}

// Schluesseljahr aus dem Dateinamen, oder null.
function wetterSchluesseljahr(dateiname) {
  const treffer = TRY_NAMENSMUSTER.exec(dateiname);
  return treffer ? Number(treffer[1]) : null;
}

// Ein Zukunfts-TRJ beruht auf Klimamodellen fuer einen Zeitraum, der noch
// bevorsteht (derzeit 2031-2060, Schluesseljahr 2045). Es wird seltener
// gebraucht als das Gegenwarts-TRJ und darum nicht vorgehakt - man soll es
// bewusst dazunehmen.
//
// Verglichen wird mit dem laufenden Jahr statt mit der festen Zahl 2045:
// liefert der DWD spaeter einen weiteren Zukunftsdatensatz unter einem anderen
// Schluesseljahr, greift die Regel weiterhin.
function wetterIstZukunftsjahr(dateiname) {
  const jahr = wetterSchluesseljahr(dateiname);
  return jahr !== null && jahr > new Date().getFullYear();
}

// Der oberste Ordnername der Auswahl - beim Ordner-Upload der Standort.
// webkitRelativePath sieht bei einer Ordnerwahl so aus:
// "Dresden_Industriegelaende/TRY_510881137633/TRY2015_..._Jahr.dat".
function wetterStandortRaten(dateien) {
  for (const datei of dateien) {
    const pfad = datei.webkitRelativePath || "";
    const teile = pfad.split("/").filter(Boolean);
    if (teile.length > 1) return teile[0];
  }
  return "";
}

const Wetter = {
  // Die im Ordner gefundenen und im Formular angekreuzten Dateien.
  wetterAuswahl: [],
  // Mitgewaehlte Archive - nur, um sie erklaeren zu koennen.
  wetterArchive: [],

  /* Die Wetterliste steht schon im HTML (templates/wetter.html, gefuellt in
     routes/pages.py: wetter()) - dieses Skript baut sie nicht mehr, es haengt
     nur seine Handlungen an die fertigen Zeilen. Vorher holte es sie nach dem
     Laden ueber /api/wetter nach: bis die Antwort da war, zeigte die Seite,
     deren einziger Inhalt diese Liste ist, eine leere Flaeche - und auf keinem
     Abzug der Seite war sie zu sehen.

     Nach einer Aenderung wird die Seite neu geladen, wie bei der Projektliste
     der Startseite (bindeProjekte). */
  bindeWetter() {
    document.querySelectorAll("#start-wetter-liste tbody tr[data-id]").forEach((zeile) => {
      const datensatz = {
        id: Number(zeile.dataset.id),
        name: zeile.dataset.name,
        stunden: Number(zeile.dataset.stunden),
      };
      zeile.querySelector(".wetter-umbenennen").addEventListener("click", () =>
        this.wetterUmbenennenDialog(datensatz)
      );
      zeile.querySelector(".wetter-loeschen").addEventListener("click", () =>
        this.wetterLoeschenDialog(datensatz)
      );
    });
  },

  async wetterUmbenennenDialog(datensatz) {
    const neuerName = await textEingabeDialog("Wetterdatensatz umbenennen", datensatz.name);
    if (neuerName === null) return;
    let antwort;
    try {
      antwort = await fetch(`/api/wetter/${datensatz.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: neuerName }),
      });
    } catch {
      zeigeFehler("Wetterdatensatz konnte nicht umbenannt werden.");
      return;
    }
    if (!antwort.ok) {
      zeigeFehler("Wetterdatensatz konnte nicht umbenannt werden.");
      return;
    }
    await this._wetterListeAktualisieren(
      "Umbenannt, die Liste konnte aber nicht aktualisiert werden."
    );
  },

  // Der Loeschknopf ist bei einem verwendeten Datensatz schon deaktiviert
  // (templates/wetter.html) - dieser Zweig greift nur bei einem inzwischen
  // veralteten Stand (z.B. ein zweiter, offener Tab hat gerade einen Lauf
  // gestartet), nicht als erster Weg dorthin.
  async wetterLoeschenDialog(datensatz) {
    const bestaetigt = await bestaetigenDialog(
      "Wetterdatensatz löschen",
      `Wetterdatensatz "${htmlSicher(datensatz.name)}" (${datensatz.stunden} Stunden) ` +
        "wirklich löschen?"
    );
    if (!bestaetigt) return;
    let antwort;
    try {
      antwort = await fetch(`/api/wetter/${datensatz.id}`, { method: "DELETE" });
    } catch {
      zeigeFehler("Wetterdatensatz konnte nicht gelöscht werden.");
      return;
    }
    if (!antwort.ok) {
      let text = "Wetterdatensatz konnte nicht gelöscht werden.";
      try {
        const daten = await antwort.json();
        if (daten.fehler) text = daten.fehler;
      } catch {
        /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */
      }
      zeigeFehler(text);
      return;
    }
    await this._wetterListeAktualisieren(
      "Gelöscht, die Liste konnte aber nicht aktualisiert werden."
    );
  },

  // Sammelt die Auswahl aus beiden Dateifeldern (Ordner und Einzeldateien),
  // wirft alles Unlesbare weg und baut daraus die Ankreuzliste.
  //
  // Gefiltert wird hier und nicht erst auf dem Server, damit das Handbuch-PDF
  // aus einem TRY-Ordner den Rechner gar nicht erst verlaesst.
  wetterDateiAktualisieren() {
    const ordnerFeld = document.getElementById("feld-wetter-ordner");
    const dateiFeld = document.getElementById("feld-wetter-datei");
    const ortFeld = document.getElementById("feld-wetter-ort");

    const ordnerDateien = Array.from(ordnerFeld?.files || []);
    const einzelDateien = Array.from(dateiFeld?.files || []);
    const alle = [...ordnerDateien, ...einzelDateien];
    const lesbare = alle.filter((d) => wetterEndungErlaubt(d.name));
    this.wetterArchive = alle.filter((d) => wetterIstArchiv(d.name));

    this.wetterAuswahl = lesbare.map((datei) => ({
      datei,
      pfad: datei.webkitRelativePath || datei.name,
      beschriftung: wetterBeschriftung(datei.name),
      angehakt: !wetterIstZukunftsjahr(datei.name),
    }));

    const ordnerName = wetterStandortRaten(ordnerDateien);
    if (ordnerName && ortFeld && !ortFeld.value.trim()) ortFeld.value = ordnerName;

    const ordnerAnzeige = document.getElementById("feld-wetter-ordnername");
    if (ordnerAnzeige) {
      ordnerAnzeige.textContent = ordnerName
        ? `${ordnerName} (${ordnerDateien.length} Dateien)`
        : "Kein Ordner ausgewählt";
    }
    const dateiAnzeige = document.getElementById("feld-wetter-dateiname");
    if (dateiAnzeige) {
      dateiAnzeige.textContent =
        einzelDateien.length === 0
          ? "Keine Datei ausgewählt"
          : einzelDateien.map((d) => d.name).join(", ");
    }

    this.zeichneWetterAuswahl(alle.length - lesbare.length);
  },

  // Die Ankreuzliste unter den Dateifeldern. Sie zeigt auch, wie viele Dateien
  // aussortiert wurden - sonst wirkt ein Ordner mit Handbuch, als haette das
  // Programm etwas verschluckt.
  zeichneWetterAuswahl(uebersprungen) {
    const bereich = document.getElementById("wetter-auswahl-liste");
    if (!bereich) return;
    bereich.textContent = "";

    // Ein Archiv erklaeren wir auch dann, wenn sonst nichts gefunden wurde -
    // sonst bliebe der Kasten leer und der Nutzer ratlos.
    if (!this.wetterAuswahl.length && !this.wetterArchive.length) {
      bereich.hidden = true;
      return;
    }
    bereich.hidden = false;

    if (this.wetterArchive.length) {
      const archivHinweis = document.createElement("p");
      archivHinweis.className = "wetter-auswahl-hinweis wetter-auswahl-warnung";
      archivHinweis.textContent = ARCHIV_HINWEIS;
      bereich.appendChild(archivHinweis);
    }

    const liste = document.createElement("ul");
    liste.className = "wetter-auswahl-liste";
    this.wetterAuswahl.forEach((eintrag, nummer) => {
      const zeile = document.createElement("li");
      const marke = document.createElement("label");

      const haken = document.createElement("input");
      haken.type = "checkbox";
      haken.checked = eintrag.angehakt;
      haken.addEventListener("change", () => {
        this.wetterAuswahl[nummer].angehakt = haken.checked;
      });

      const titel = document.createElement("span");
      titel.className = "wetter-auswahl-titel";
      titel.textContent = eintrag.beschriftung;

      const pfad = document.createElement("span");
      pfad.className = "wetter-auswahl-pfad";
      pfad.textContent = eintrag.pfad;

      marke.append(haken, titel, pfad);
      zeile.appendChild(marke);
      liste.appendChild(zeile);
    });
    bereich.appendChild(liste);

    if (uebersprungen > 0) {
      const hinweis = document.createElement("p");
      hinweis.className = "wetter-auswahl-hinweis";
      hinweis.textContent =
        uebersprungen === 1
          ? "Eine weitere Datei im Ordner ist keine Wetterdatei und bleibt liegen."
          : `${uebersprungen} weitere Dateien im Ordner sind keine Wetterdaten und bleiben liegen.`;
      bereich.appendChild(hinweis);
    }
  },

  async wetterHochladen(ereignis) {
    ereignis.preventDefault();
    const ordnerFeld = document.getElementById("feld-wetter-ordner");
    const dateiFeld = document.getElementById("feld-wetter-datei");
    const ortFeld = document.getElementById("feld-wetter-ort");
    const nameFeld = document.getElementById("feld-wetter-name");
    const knopf = document.getElementById("btn-wetter-hochladen");

    const gewaehlt = this.wetterAuswahl.filter((e) => e.angehakt);
    if (!gewaehlt.length) {
      let meldung = "Bitte einen Ordner oder eine Datei auswählen.";
      if (this.wetterAuswahl.length) meldung = "Bitte mindestens eine Datei ankreuzen.";
      else if (this.wetterArchive.length) meldung = ARCHIV_HINWEIS;
      zeigeFehler(meldung);
      return;
    }

    const formular = new FormData();
    gewaehlt.forEach((eintrag) => formular.append("datei", eintrag.datei));
    if (ortFeld?.value.trim()) formular.append("ort", ortFeld.value.trim());
    // Eine eigene Bezeichnung kann nur fuer eine einzelne Datei gelten - bei
    // mehreren hiessen sonst alle Datensaetze gleich (routes/wetter.py).
    if (gewaehlt.length === 1 && nameFeld.value.trim()) {
      formular.append("name", nameFeld.value.trim());
    }

    const urspruenglicherText = knopf.textContent;
    knopf.disabled = true;
    knopf.textContent =
      gewaehlt.length === 1
        ? "Wird hochgeladen …"
        : `Wird hochgeladen (${gewaehlt.length}) …`;

    const zuruecksetzen = () => {
      knopf.disabled = false;
      knopf.textContent = urspruenglicherText;
    };

    let antwort;
    try {
      antwort = await fetch("/api/wetter/upload", { method: "POST", body: formular });
    } catch {
      zeigeFehler("Die Wetterdaten konnten nicht hochgeladen werden.");
      zuruecksetzen();
      return;
    }
    if (!antwort.ok) {
      let text = "Die Wetterdaten konnten nicht hochgeladen werden.";
      try {
        const daten = await antwort.json();
        if (daten.fehler) text = daten.fehler;
      } catch {
        /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */
      }
      zeigeFehler(text);
      zuruecksetzen();
      return;
    }

    // Ein Teilerfolg ist der Regelfall wert, gemeldet zu werden: wer sechs
    // Jahre hochlaedt und fuenf bekommt, soll nicht raten muessen, welches
    // fehlt.
    try {
      const daten = await antwort.json();
      if (daten.dateifehler?.length) {
        zeigeFehler(
          `Nicht gelesen: ${daten.dateifehler
            .map((f) => `${f.datei} (${f.fehler})`)
            .join("; ")}`
        );
      }
    } catch {
      /* Antwort war kein JSON - der Upload hat trotzdem geklappt. */
    }

    this.wetterArchive = [];
    if (ordnerFeld) ordnerFeld.value = "";
    if (dateiFeld) dateiFeld.value = "";
    if (ortFeld) ortFeld.value = "";
    nameFeld.value = "";
    this.wetterAuswahl = [];
    this.wetterDateiAktualisieren();
    zuruecksetzen();

    await this._wetterListeAktualisieren(
      "Die Daten wurden hochgeladen, die Liste konnte aber nicht aktualisiert werden."
    );
  },

  /* Nach einem Upload, Abruf, Umbenennen oder Loeschen die Seite neu laden,
     statt die Liste im Browser nachzuziehen: EINE Anfrage, und sie kann nicht
     von dem abweichen, was der Server ohnehin liefert. Die mitgegebene Meldung
     wird gebraucht, wenn schon das Neuladen scheitert - der Vorgang selbst ist
     dann durch, nur die Anzeige haengt hinterher. */
  async _wetterListeAktualisieren(fehlerBeiFehlschlag) {
    try {
      window.location.reload();
    } catch {
      zeigeFehler(fehlerBeiFehlschlag);
    }
  },

  // Fuellt das Jahr-Mehrfachauswahlfeld mit allen abgeschlossenen
  // Kalenderjahren, die die Open-Meteo Archive-API anbietet (1940 bis zum
  // Vorjahr) - neuestes zuerst, weil das der haeufigste Wunsch ist. So kann
  // die Oberflaeche gar nicht erst ein unzulaessiges Jahr anbieten, statt den
  // Benutzer erst beim Absenden auf den Fehler laufen zu lassen.
  wetterAbrufJahreFuellen() {
    const feld = document.getElementById("feld-wetter-abruf-jahre");
    if (!feld) return;
    const letztesVollstaendigesJahr = new Date().getFullYear() - 1;
    feld.textContent = "";
    for (let jahr = letztesVollstaendigesJahr; jahr >= WETTER_FRUEHESTES_JAHR; jahr--) {
      const option = document.createElement("option");
      option.value = String(jahr);
      option.textContent = String(jahr);
      feld.appendChild(option);
    }
    // Bequemer Einstieg: das juengste verfuegbare Jahr ist vorausgewaehlt.
    if (feld.options.length) feld.options[0].selected = true;
  },

  // Zeigt/versteckt die Koordinatenfelder, je nachdem ob ein vorbelegter Ort
  // oder "Eigene Koordinaten" gewaehlt ist.
  wetterAbrufOrtGewaehlt() {
    const auswahl = document.getElementById("feld-wetter-abruf-ort");
    const koordinatenBereich = document.getElementById("wetter-abruf-koordinaten");
    koordinatenBereich.hidden = auswahl.value !== "eigene";
  },

  async wetterAbrufen(ereignis) {
    ereignis.preventDefault();

    const ortAuswahl = document.getElementById("feld-wetter-abruf-ort");
    const jahreFeld = document.getElementById("feld-wetter-abruf-jahre");
    const nameFeld = document.getElementById("feld-wetter-abruf-name");
    const knopf = document.getElementById("btn-wetter-abrufen");

    let ort;
    let breite;
    let laenge;
    if (ortAuswahl.value === "eigene") {
      const breiteFeld = document.getElementById("feld-wetter-abruf-breite");
      const laengeFeld = document.getElementById("feld-wetter-abruf-laenge");
      const ortsnameFeld = document.getElementById("feld-wetter-abruf-ortsname");
      breite = parseFloat(breiteFeld.value);
      laenge = parseFloat(laengeFeld.value);
      if (!Number.isFinite(breite) || !Number.isFinite(laenge)) {
        zeigeFehler("Bitte Breite und Länge als Zahl eingeben.");
        return;
      }
      ort = ortsnameFeld.value.trim() || `${breite}, ${laenge}`;
    } else {
      const gewaehlteOption = ortAuswahl.selectedOptions[0];
      breite = parseFloat(gewaehlteOption.dataset.breite);
      laenge = parseFloat(gewaehlteOption.dataset.laenge);
      ort = ortAuswahl.value;
    }

    const jahre = Array.from(jahreFeld.selectedOptions).map((o) => parseInt(o.value, 10));
    if (!jahre.length) {
      zeigeFehler("Bitte mindestens ein Jahr auswählen.");
      return;
    }

    const eigenerName = nameFeld.value.trim();
    const urspruenglicherText = knopf.textContent;
    knopf.disabled = true;

    // Ein Abruf je Jahr, hintereinander statt parallel - der Server schickt
    // pro Jahr bereits fuenf parallele Teilabfragen an Open-Meteo los,
    // mehrere Jahre gleichzeitig wuerden das unnoetig vervielfachen. Fehler
    // bei einem Jahr sollen die uebrigen Jahre nicht verhindern.
    const fehlgeschlagen = [];
    let erfolge = 0;
    for (let i = 0; i < jahre.length; i++) {
      const jahr = jahre[i];
      knopf.textContent =
        jahre.length > 1 ? `Wird abgerufen … (${i + 1}/${jahre.length})` : "Wird abgerufen …";

      const name = eigenerName ? (jahre.length > 1 ? `${eigenerName} ${jahr}` : eigenerName) : "";

      let antwort;
      try {
        antwort = await fetch("/api/wetter/abrufen", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ breite, laenge, jahr, ort, name }),
        });
      } catch {
        fehlgeschlagen.push(`${jahr}: Wetterdaten konnten nicht abgerufen werden`);
        continue;
      }
      if (!antwort.ok) {
        let text = "Wetterdaten konnten nicht abgerufen werden";
        try {
          const daten = await antwort.json();
          if (daten.fehler) text = daten.fehler;
        } catch {
          /* Antwort war kein JSON - bei der Vorgabemeldung bleiben. */
        }
        fehlgeschlagen.push(`${jahr}: ${text}`);
        continue;
      }
      erfolge++;
    }

    knopf.disabled = false;
    knopf.textContent = urspruenglicherText;

    if (fehlgeschlagen.length) {
      zeigeFehler(
        erfolge
          ? `${erfolge} von ${jahre.length} Jahren abgerufen. Fehlgeschlagen: ${fehlgeschlagen.join("; ")}`
          : `Abruf fehlgeschlagen: ${fehlgeschlagen.join("; ")}`
      );
    }

    if (erfolge) {
      nameFeld.value = "";
      await this._wetterListeAktualisieren(
        "Die Wetterdaten wurden abgerufen, die Liste konnte aber nicht aktualisiert werden."
      );
    }
  },
};

function verdrahte(kennung, ereignis, was) {
  const element = document.getElementById(kennung);
  if (element) element.addEventListener(ereignis, was);
}

window.addEventListener("DOMContentLoaded", () => {
  verdrahte("form-wetter-upload", "submit", (e) => Wetter.wetterHochladen(e));
  for (const kennung of ["feld-wetter-ordner", "feld-wetter-datei"]) {
    verdrahte(kennung, "change", () => Wetter.wetterDateiAktualisieren());
  }
  Wetter.wetterAbrufJahreFuellen();
  verdrahte("feld-wetter-abruf-ort", "change", () => Wetter.wetterAbrufOrtGewaehlt());
  verdrahte("form-wetter-abruf", "submit", (e) => Wetter.wetterAbrufen(e));

  // Die Wetterliste steht schon da - sie wird nur verdrahtet.
  Wetter.bindeWetter();
});
