/* Erklärbereich (/bausteine): lädt die Kartentypen samt Erklärtext von
   /api/lehre/bausteine und zeigt sie gruppiert an. Ein Klick auf "Beispiel-
   anlage öffnen" legt über /api/lehre/bausteine/<kennung>/anlage eine neue
   Anlage an und wechselt in den Editor.

   Eigenständiges Modul, wie schon start.js: diese Seite lädt weder editor.js
   noch panel.js noch pfeile.js, ein stiller Aufruf einer nur dort
   vorhandenen Funktion wäre ein Fehler, der erst beim Klicken auffiele. */

function zeigeFehler(nachricht) {
  const leiste = document.getElementById("fehlermeldung");
  if (!leiste) return;
  leiste.textContent = nachricht;
  leiste.hidden = false;
  window.clearTimeout(zeigeFehler.timer);
  zeigeFehler.timer = window.setTimeout(() => { leiste.hidden = true; }, 5000);
}

const ART_LABEL = { luft: "Luft", signal: "Signal" };
const RICHTUNG_LABEL = { ein: "Eingang", aus: "Ausgang" };

function anschlussZeile(port) {
  const li = document.createElement("li");
  const punkt = document.createElement("span");
  punkt.className = `baustein-anschluss-art ${port.art}`;
  li.appendChild(punkt);
  const art = ART_LABEL[port.art] || port.art;
  const richtung = RICHTUNG_LABEL[port.richtung] || port.richtung;
  li.appendChild(document.createTextNode(`${port.schluessel} – ${art}, ${richtung}`));
  return li;
}

function parameterZeile(feld) {
  const li = document.createElement("li");
  const einheit = feld.einheit && feld.einheit !== "-" ? ` (${feld.einheit})` : "";
  li.textContent = `${feld.label}${einheit}`;
  return li;
}

function detailsBlock(titel, elemente) {
  const block = document.createElement("div");
  block.className = "baustein-details-block";
  const kopf = document.createElement("p");
  kopf.className = "baustein-details-titel";
  kopf.textContent = titel;
  block.appendChild(kopf);
  const liste = document.createElement("ul");
  if (!elemente.length) {
    const li = document.createElement("li");
    li.textContent = "– keine –";
    liste.appendChild(li);
  } else {
    elemente.forEach((el) => liste.appendChild(el));
  }
  block.appendChild(liste);
  return block;
}

async function beispielanlageAnlegen(kennung, knopf, statusfeld) {
  knopf.disabled = true;
  statusfeld.textContent = "Wird angelegt …";
  try {
    const antwort = await fetch(`/api/lehre/bausteine/${kennung}/anlage`, { method: "POST" });
    if (!antwort.ok) throw new Error();
    const daten = await antwort.json();
    window.location.href = `/anlage/${daten.id}`;
  } catch {
    statusfeld.textContent = "";
    knopf.disabled = false;
    zeigeFehler("Beispielanlage konnte nicht angelegt werden.");
  }
}

function bausteinKarteElement(baustein) {
  const div = document.createElement("div");
  div.className = "baustein-karte";
  div.id = `baustein-${baustein.kennung}`;

  const kopf = document.createElement("div");
  kopf.className = "baustein-kopf";
  const name = document.createElement("span");
  name.className = "baustein-name";
  name.textContent = baustein.name;
  kopf.appendChild(name);
  const kennung = document.createElement("span");
  kennung.className = "baustein-kennung";
  kennung.textContent = baustein.kennung;
  kopf.appendChild(kennung);
  div.appendChild(kopf);

  const beschreibung = document.createElement("p");
  beschreibung.className = "baustein-beschreibung";
  beschreibung.textContent = baustein.beschreibung;
  div.appendChild(beschreibung);

  if (baustein.hinweis) {
    const hinweis = document.createElement("p");
    hinweis.className = "baustein-hinweis";
    hinweis.textContent = baustein.hinweis;
    div.appendChild(hinweis);
  }

  const details = document.createElement("div");
  details.className = "baustein-details";
  details.appendChild(
    detailsBlock("Anschlüsse", baustein.ports.map(anschlussZeile))
  );
  details.appendChild(
    detailsBlock("Parameter", baustein.parameter.map(parameterZeile))
  );
  div.appendChild(details);

  const fuss = document.createElement("div");
  fuss.className = "baustein-fuss";
  const knopf = document.createElement("button");
  knopf.className = "baustein-beispiel-knopf";
  knopf.textContent = "Beispielanlage öffnen";
  const statusfeld = document.createElement("span");
  statusfeld.className = "baustein-beispiel-status";
  if (baustein.beispiel_verfuegbar) {
    knopf.addEventListener("click", () =>
      beispielanlageAnlegen(baustein.kennung, knopf, statusfeld)
    );
  } else {
    knopf.disabled = true;
    statusfeld.textContent = "Noch keine Beispielanlage";
  }
  fuss.append(knopf, statusfeld);
  div.appendChild(fuss);

  return div;
}

function gruppenAnker(gruppe) {
  return `gruppe-${gruppe.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

async function laden() {
  const bereich = document.getElementById("lehre-gruppen");
  const inhalt = document.getElementById("lehre-inhalt");
  let bausteine;
  try {
    const antwort = await fetch("/api/lehre/bausteine");
    if (!antwort.ok) throw new Error();
    bausteine = await antwort.json();
  } catch {
    bereich.textContent = "";
    zeigeFehler("Bausteine konnten nicht geladen werden.");
    return;
  }

  const gruppen = new Map();
  for (const b of bausteine) {
    if (!gruppen.has(b.gruppe)) gruppen.set(b.gruppe, []);
    gruppen.get(b.gruppe).push(b);
  }

  bereich.textContent = "";
  inhalt.textContent = "";

  for (const [gruppe, liste] of gruppen) {
    const link = document.createElement("a");
    link.href = `#${gruppenAnker(gruppe)}`;
    link.textContent = `${gruppe} (${liste.length})`;
    inhalt.appendChild(link);

    const abschnitt = document.createElement("div");
    abschnitt.className = "lehre-gruppe";
    abschnitt.id = gruppenAnker(gruppe);
    const titel = document.createElement("h2");
    titel.className = "lehre-gruppe-titel";
    titel.textContent = gruppe;
    abschnitt.appendChild(titel);
    liste.forEach((b) => abschnitt.appendChild(bausteinKarteElement(b)));
    bereich.appendChild(abschnitt);
  }
}

laden();
