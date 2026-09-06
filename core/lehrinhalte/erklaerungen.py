"""Erklärtexte je Kartentyp.

Jeder Eintrag ist eine kurze Beschreibung dessen, was der Baustein in einer
Lüftungsanlage ist, was er tut, wann man ihn braucht - und, wo es eine gibt,
eine Eigenheit, die man kennen muss, um ihn richtig anzuschließen. Grundlage
ist ausschließlich der Rechenweg in der jeweiligen core/bausteine/<typ>.py.

Parameter- und Anschlussnamen stehen NICHT hier, sondern werden von
routes/lehre.py zur Anfragezeit aus der Bausteinklasse selbst gelesen (siehe
core/lehrinhalte/__init__.py) - dieses Modul enthält nur den erklärenden Text.
"""

ERKLAERUNGEN = {
    # -- Quellen und Senken ------------------------------------------------
    "wetter": {
        "beschreibung": (
            "Liefert für jede Stunde des Jahres Außentemperatur, Außenfeuchte "
            "und die Sonneneinstrahlung auf die vier Himmelsrichtungen sowie "
            "horizontal, aus dem hochgeladenen oder abgerufenen "
            "Wetterdatensatz. Sie hat keinen Luftanschluss und speist andere "
            "Karten ausschließlich über Signale. Fast jede Anlage braucht "
            "genau eine Wetterkarte, meist verbunden mit der Außenluft und "
            "mit jedem Raum."
        ),
        "hinweis": (
            "Ohne Wetterdatensatz bleiben ihre Werte leer; ein Simulationslauf "
            "braucht sie als Startpunkt."
        ),
    },
    "aussenluft": {
        "beschreibung": (
            "Der Anschlusspunkt, an dem Außenluft in die Anlage eintritt. Sie "
            "übernimmt Temperatur und Feuchte von der Wetterkarte und liefert "
            "so viel Volumenstrom, wie stromabwärts angefordert wird - wie "
            "viel das ist, bestimmt letztlich der nächste Ventilator. Jede "
            "Anlage, die Frischluft ansaugt, beginnt hier."
        ),
    },
    "fortluft": {
        "beschreibung": (
            "Der Endpunkt eines Abluftwegs - hier verlässt die Luft die "
            "Anlage endgültig. Sie hat keinen eigenen Ausgang, sondern nimmt "
            "nur auf und zeigt Temperatur, Feuchte und Volumenstrom der "
            "austretenden Luft. Jeder Abluftstrang muss irgendwo enden, meist "
            "hinter der Wärmerückgewinnung."
        ),
    },
    # -- Luftbehandlung ------------------------------------------------------
    "erhitzer": {
        "beschreibung": (
            "Erwärmt einen Luftstrom mit einer Heizleistung, die über die "
            "Stellgröße zwischen 0 und der höchsten Heizleistung (QH_max) "
            "vorgegeben wird. Er sitzt zwischen zwei Luftanschlüssen im Zuluftstrang und "
            "braucht eine Stellgröße - meist von einem Regler, sonst bleibt "
            "er kalt."
        ),
        "hinweis": (
            "Nennvolumenstrom und Nenndruckverlust bestimmen nur den "
            "Druckverlust, nicht die Heizleistung; die folgt allein aus "
            "Stellgröße mal höchster Heizleistung."
        ),
    },
    "kuehler": {
        "beschreibung": (
            "Kühlt einen Luftstrom ab und entfeuchtet ihn nebenbei, sobald "
            "die rechnerische Oberflächentemperatur unter dem Taupunkt der "
            "Luft liegt. Die Kühlleistung folgt wie beim Erhitzer einer "
            "Stellgröße von 0 bis 100 Prozent. Die mittlere "
            "Kaltwassertemperatur begrenzt dabei, wie kalt die Luft "
            "überhaupt werden kann."
        ),
        "hinweis": (
            "Überschreitet die geforderte Leistung die Nennkälteleistung, meldet "
            "die Karte eine Warnung - begrenzt wird sie dadurch aber nicht."
        ),
    },
    "wrg": {
        "beschreibung": (
            "Überträgt Wärme - und wahlweise Feuchte - von der Abluft auf die "
            "Zuluft, bevor die Abluft die Anlage verlässt. Sie braucht vier "
            "Luftanschlüsse (Zuluft rein/raus, Abluft rein/raus) und eine "
            "Stellgröße, die den Wirkungsgrad zwischen 0 und der "
            "Rückwärmzahl steuert; ein zweiter Stellgrößeneingang öffnet "
            "einen Bypass."
        ),
        "hinweis": (
            "Ohne Stellgröße (0 %) läuft die gesamte Luft am Wärmetauscher "
            "vorbei, als wäre er nicht da."
        ),
    },
    "mischkammer": {
        "beschreibung": (
            "Mischt Außenluft mit zurückgeführter Umluft im Verhältnis, das "
            "die Stellgröße 'Umluftanteil' vorgibt, begrenzt durch den "
            "Parameter max_umluft. Sie braucht zwei Lufteingänge - Außenluft "
            "und Umluft - und einen gemeinsamen Luftausgang."
        ),
        "hinweis": "Ohne Stellgröße bleibt der Umluftanteil null, es strömt reine Außenluft durch.",
    },
    "dampfbefeuchter": {
        "beschreibung": (
            "Befeuchtet die Luft, indem er Dampf direkt einbläst - wahlweise "
            "elektrisch erzeugt oder aus einem Fremddampfnetz bezogen. Die "
            "Stellgröße bestimmt, wie viel von der maximalen "
            "Befeuchtungsleistung (max_leistung) genutzt wird."
        ),
        "hinweis": (
            "Die Karte meldet eine Übersättigungswarnung, wenn die Zielfeuchte "
            "über der Sättigung der Luft läge."
        ),
    },
    "luftwaescher": {
        "beschreibung": (
            "Befeuchtet adiabat durch Verdunstung von Wasser - die Luft kühlt "
            "sich dabei ab, während sie feuchter wird, bis maximal 90 Prozent "
            "des Sättigungszustands erreicht sind. Die Stellgröße legt fest, "
            "wie weit sich der Vorgang der Sättigung annähert; pumpenart "
            "bestimmt den Leistungsverlauf der Umwälzpumpe."
        ),
    },
    "ventilator": {
        "beschreibung": (
            "Treibt die Luft durch die Anlage und ist der einzige Baustein, "
            "der den Volumenstrom selbst festlegt - alle anderen richten "
            "sich danach. Die Rolle (Zuluft oder Abluft) bestimmt, an welche "
            "Luftwege er passt; regelart wählt zwischen Frequenzumrichter "
            "(F, Leistung sinkt mit dem Volumenstrom), Drallregler (D) und "
            "ungeregeltem Betrieb (-)."
        ),
        "hinweis": (
            "Ist der Stellgrößen-Anschluss nicht verbunden, gilt der feste "
            "Parameter 'Stellgröße (fest)'."
        ),
    },
    # -- Verteilung ----------------------------------------------------------
    "verteiler": {
        "beschreibung": (
            "Teilt einen Luftstrang auf mehrere Gänge auf, etwa wenn zwei "
            "getrennte Zonen aus derselben Vorbehandlung versorgt werden. Er "
            "hat einen Lufteingang; ein weiterer Luftausgang wächst von "
            "selbst nach, sobald der vorhandene durch einen Pfeil belegt "
            "wird."
        ),
        "hinweis": (
            "'Anteile je Gang' greift nur, wenn kein Gang stromabwärts einen "
            "Bedarf meldet - reicht der Volumenstrom nicht für alle Gänge, "
            "wird anteilig gekürzt und eine Warnung gesetzt."
        ),
    },
    "sammler": {
        "beschreibung": (
            "Führt mehrere Luftstränge wieder zu einem zusammen, "
            "volumenstromgewichtet gemischt. Er wächst ebenso wie der "
            "Verteiler an seinen Lufteingängen, sobald ein weiterer Pfeil "
            "ankommt, und hat genau einen Luftausgang."
        ),
    },
    # -- Räume -----------------------------------------------------------
    "einfacher_raum": {
        "beschreibung": (
            "Ein stark vereinfachter Raum ohne eigene Speichermasse: "
            "Temperatur und Feuchte ergeben sich als sofortige Mischbilanz "
            "aus Zuluft, Infiltration von außen und den eingespeisten "
            "Lasten. spez_transmission fasst alle Transmissionsverluste in "
            "einer Zahl zusammen, sollwert_stat ist die Mindesttemperatur, "
            "unter die der Raum wegen einer - hier nicht mitgerechneten - "
            "statischen Heizung nicht fällt."
        ),
        "hinweis": "Ohne Zuluftanschluss wirkt nur die Infiltration über die Außentemperatur.",
    },
    "statische_heizung": {
        "beschreibung": (
            "Nimmt die vom Raum gemeldete Unterdeckung (QH_stat) auf und "
            "begrenzt sie auf die eingestellte Nennleistung - die "
            "eigentliche Heizkörperheizung neben der Lüftungsanlage. Sie "
            "braucht einen Raum als Signalquelle für ihren einzigen "
            "Anschluss."
        ),
    },
    "statische_kuehlung": {
        "beschreibung": (
            "Das Gegenstück zur Statischen Heizung: Sie nimmt die vom Raum "
            "gemeldete Überdeckung (QK_stat) auf und begrenzt sie auf die "
            "eingestellte Nennleistung - die Kühldecke oder das Kühlsegel "
            "neben der Lüftungsanlage. Gebraucht wird sie überall dort, wo "
            "die Luftmenge nach Hygiene bemessen ist: Bei acht Kelvin "
            "Untertemperatur trägt ein Kubikmeter Luft nur wenig Wärme fort, "
            "und eine innere Last von 25 W/m² übersteigt das schnell. Sie "
            "braucht einen Raum als Signalquelle, und im Raum muss ein "
            "Sollwert der Kühlfläche stehen - sonst meldet er nie etwas."
        ),
    },
    "innere_lasten": {
        "beschreibung": (
            "Rechnet aus, was Menschen und Geräte in einen Raum eintragen, "
            "und zwar getrennt nach Wärme und Feuchte. Statt einer nackten "
            "Zahl stehen hier die Größen einer Auslegung: Personenzahl, "
            "Wärme- und Feuchteabgabe je Person, Geräteleistung je "
            "Quadratmeter. Der Eingang „Belegung“ nimmt einen Anteil zwischen "
            "0 und 1 entgegen, meist aus einem Tageslastprofil; die Dauerlast "
            "läuft unabhängig davon rund um die Uhr."
        ),
        "hinweis": (
            "Der Raum hat je einen Eingang für Wärme- und Feuchtelast. Was "
            "sonst noch hineingeht - allen voran die Beleuchtungswärme - "
            "hängt deshalb an dieser Karte und wird mitgezählt."
        ),
    },
    "raum": {
        "beschreibung": (
            "Der ausführliche Raum: Geometrie aus vier Wandabschnitten a bis "
            "d mit Fenstern, dazu Dach, Bodenplatte, Wärmebrücken, "
            "Sonneneintrag je Himmelsrichtung und ein Wandspeicher, der sich "
            "von Stunde zu Stunde träge nachführt. Er braucht Zuluft/Abluft, "
            "Außentemperatur/-feuchte und die fünf Strahlungssignale der "
            "Wetterkarte - ein einziger Pfeil von der Wetterkarte verbindet "
            "alle sieben auf einmal."
        ),
    },
    # -- Regelung --------------------------------------------------------
    "p_regler": {
        "beschreibung": (
            "Ein zweistufiger stetiger Regler mit zwei unabhängigen "
            "Ausgängen (schnell und träge), gedacht für Bauteile, die zwei "
            "Freiheitsgrade brauchen. Xp ist die Bandbreite: je kleiner, "
            "desto kräftiger reagiert der Regler auf eine Abweichung "
            "zwischen Ist- und Sollwert. Ist ein Sollwert- oder "
            "Istwert-Eingang nicht verbunden, gilt der feste Parameterwert. "
            "Wichtig zum Verständnis: Er verschiebt seine Stellgröße in jedem "
            "Rechendurchgang um Abweichung ÷ Xp und trifft am Ende einer "
            "Stunde genau den Sollwert - eine bleibende Regelabweichung, wie "
            "sie ein reiner P-Regler im Lehrbuch hinterlässt, bleibt hier "
            "nicht übrig. Xp bestimmt also, wie schnell er ankommt, nicht wie "
            "weit er daneben liegt. Der Name stammt aus der Excel-Vorlage."
        ),
        "hinweis": (
            "Ein einziger Pfeil vom Regler zum geregelten Bauteil genügt "
            "meist: er verdrahtet die Stellgröße vorwärts und holt sich den "
            "passenden Messwert automatisch als Istwert zurück."
        ),
    },
    "sequenzregler": {
        "beschreibung": (
            "Leitet aus einer Regelabweichung fünf gestaffelte Ausgänge ab - "
            "drei Heiz- und zwei Kühlstufen -, die nacheinander öffnen, je "
            "größer die Abweichung wird. Der obere und der untere Sollwert "
            "spannen die neutrale Zone auf, in der nichts geregelt wird. Der "
            "Proportionalbereich Xp dieser Karte geht - wie in der "
            "Excel-Vorlage - in keine Formel ein."
        ),
    },
    "hysterese_regler": {
        "beschreibung": (
            "Ein Zweipunktregler: Er vergleicht Istwert und Sollwert und "
            "schaltet den Ausgang auf 0 oder 100 Prozent - nichts "
            "dazwischen. Die Schaltdifferenz (Hysterese) verhindert, dass er "
            "am Umschaltpunkt ständig hin- und herflattert."
        ),
        "hinweis": (
            "In der mitgelieferten Beispielanlage steuert er den "
            "Luftwäscher mit vertauschter Wirkrichtung: Der Istwert ist eine "
            "feste Zahl (Parameter), der Sollwert die gemessene "
            "Raumfeuchte - dadurch schaltet er ein, wenn der Raum trockener "
            "als diese Zahl ist, statt umgekehrt. Deshalb werden Sollwert "
            "und Ausgang hier gezielt statt automatisch verbunden: ein "
            "gewöhnlicher Pfeil vom Regler zum Luftwäscher würde sonst "
            "versuchen, den Istwert automatisch mit der "
            "Luftwäscher-Austrittstemperatur zu belegen."
        ),
    },
    "kaskade": {
        "beschreibung": (
            "Ein gleitender, außentemperaturgeführter Raumsollwert, "
            "kombiniert mit einer Zulufttemperatur-Begrenzung und fünf "
            "Sequenzstufen wie beim Sequenzregler - nur mit vorgeschalteter "
            "Sollwertberechnung. Überschreitet oder unterschreitet die "
            "Zuluft ihre Grenzen, hat das Vorrang vor der Raumabweichung."
        ),
    },
    "maximalwert": {
        "beschreibung": (
            "Gibt den größten von beliebig vielen angeschlossenen "
            "Signalwerten weiter. Nützlich, wenn ein Bauteil von mehreren "
            "Reglern beeinflusst werden darf und der fordernde gewinnen "
            "soll - etwa ein Kühler, den sowohl ein Kühl- als auch ein "
            "Entfeuchtungsregler öffnen dürfen."
        ),
    },
    "faktor": {
        "beschreibung": (
            "Multipliziert ein Signal mit einem festen Faktor und begrenzt "
            "das Ergebnis auf 0 bis 100 Prozent. Damit lassen sich einfache "
            "Verriegelungen bauen, etwa 'läuft der Luftwäscher voll, öffne "
            "den Nachheizer auf die Hälfte'."
        ),
    },
    "umkehrglied": {
        "beschreibung": (
            "Spiegelt ein Signal an einem Bezugswert (Vorgabe 100) und "
            "begrenzt das Ergebnis auf 0 bis 100 Prozent - aus 30 Prozent "
            "werden 70. Nötig, wenn ein Regler eine Größe meldet, deren Sinn "
            "umgekehrt zu dem ist, was das nächste Bauteil erwartet."
        ),
    },
    # -- Zeit und Betrieb --------------------------------------------------
    "wochenzeitplan": {
        "beschreibung": (
            "Ein Betriebsfenster je Wochentag, angegeben als Von-Bis-Uhrzeit. "
            "Sein Signal ist 1, solange die aktuelle Stunde in das jeweilige "
            "Tagesfenster fällt, sonst 0 - ein typischer Zubringer für die "
            "Karte 'Anlagenbetrieb'."
        ),
    },
    "ferien": {
        "beschreibung": (
            "Eine Liste von Zeiträumen (Tag.Monat, ohne Jahr, gilt also für "
            "jedes Wetterjahr), in denen der Betrieb ausgesetzt wird - "
            "Weihnachten, Betriebsferien und Ähnliches. Ihr Signal ist 1 "
            "während eines Ferienzeitraums, sonst 0."
        ),
    },
    "monatsprofil": {
        "beschreibung": (
            "Schaltet zwölf Monate einzeln ein oder aus, etwa um eine Anlage "
            "nur in der Heizperiode laufen zu lassen. Sein Signal ist 1 in "
            "einem freigegebenen Monat, sonst 0."
        ),
    },
    "tageslastprofil": {
        "beschreibung": (
            "Ein Tagesgang aus 24 Werten zwischen 0 und 1 für bis zu drei "
            "Lastprofile, etwa um eine Anlage tagsüber auf voller und nachts "
            "auf abgesenkter Leistung fahren zu lassen. Anders als die "
            "übrigen Zeitkarten liefert sie keinen Ein/Aus-Wert, sondern "
            "einen Stellgrad."
        ),
    },
    "anlagenbetrieb": {
        "beschreibung": (
            "Verknüpft Zeitplan, Ferien und Tageslastprofil zu einem "
            "einzigen Betriebssignal und einem Stellgrad in Prozent - der "
            "zentrale Baustein, an dem Ventilatoren und Regler ihre "
            "Freigabe bekommen. Mehrere angeschlossene Zeitpläne wirken wie "
            "hintereinandergeschaltete Schalter: nur wenn alle freigeben, "
            "läuft die Anlage."
        ),
    },
    # -- Verbraucher ---------------------------------------------------------
    "heizungspumpen": {
        "beschreibung": (
            "Rechnet die elektrische Leistung der Heizkreispumpen aus fest "
            "eingestellten Werten für allgemeine Pumpen, Warmwasserbereitung "
            "und Kessel - jeweils nur, wenn die Karte 'in Betrieb' gemeldet "
            "bekommt. Kein Luftanschluss, ein reiner Stromverbraucher für "
            "die Bilanz."
        ),
    },
    "warmwasser": {
        "beschreibung": (
            "Rechnet den Wärmebedarf für Trinkwarmwasser aus einem "
            "Jahresverbrauch, gleichmäßig auf 8760 Stunden verteilt, "
            "zuzüglich eines von der Speichergröße abhängigen "
            "Bereitschaftsverlusts. Kein Luftanschluss, ein reiner "
            "Wärmeverbraucher für die Bilanz."
        ),
    },
    "zirkulation": {
        "beschreibung": (
            "Die Verlustwärme und der Pumpenstrom einer "
            "Warmwasser-Zirkulationsleitung, wirksam nur wenn die Karte 'in "
            "Betrieb' gemeldet bekommt."
        ),
    },
    "beleuchtung": {
        "beschreibung": (
            "Rechnet die elektrische Leistung einer Raumbeleuchtung aus "
            "spezifischer Leistung und Grundfläche; die abgegebene Wärme "
            "entspricht der aufgenommenen Leistung. Eine eigenständige "
            "Karte, damit unterschiedliche Räume unterschiedlich beleuchtet "
            "gerechnet werden können."
        ),
    },
    "enthalpierechner": {
        "beschreibung": (
            "Ein Hilfsbaustein, der aus Temperatur und absoluter Feuchte die "
            "Enthalpie und die relative Feuchte errechnet - nützlich, um "
            "einen Luftzustand lesbar zu machen, ohne die Simulation selbst "
            "zu beeinflussen."
        ),
    },
    "bilanz": {
        "beschreibung": (
            "Sammelt alles, was an ihre vier Eingänge - Strom, Wärme, Kälte, "
            "Wasser - angeschlossen wird, trennt Strom nach Hoch- und "
            "Niedertarif und weist am Jahresende die Kosten aus den "
            "hinterlegten Preisen aus. Fast jedes Bauteil mit "
            "Energieanschluss gehört hierher."
        ),
        "hinweis": (
            "Je Energieart dürfen beliebig viele Karten anschließen - ein "
            "Pfeil reicht, die Karte wächst dabei automatisch um weitere "
            "Eingänge."
        ),
    },
    "datenlogger": {
        "beschreibung": (
            "Zeichnet bis zu zehn beliebige Signalwerte über den ganzen Lauf "
            "auf und zeigt sie im Ergebnisprotokoll als eigene Spalte."
        ),
        "hinweis": (
            "Ein Anschluss wird erst sichtbar, sobald ihm im "
            "Parameterfenster ein Name gegeben wird; ohne Namen bleibt die "
            "Spalte leer und wird beim Verbinden nicht angeboten."
        ),
    },
}
