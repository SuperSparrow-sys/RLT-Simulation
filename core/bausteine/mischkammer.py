"""Mischkammer aus Aussenluft und Umluft. Formeln aus Anlage!M132 bis M134."""

from core.bausteine.basis import (
    AUSGANG, AUSSENLUFT, EINGANG, LUFT, MESSWERT, PROZENT, SIGNAL,
    STELLGROESSE, UMLUFT, ZULUFT, Baustein, Luft, Param, Port, registriere,
)


@registriere
class Mischkammer(Baustein):
    KENNUNG = "mischkammer"
    NAME = "Mischkammer"
    GRUPPE = "Luftbehandlung"
    SYMBOL = "mischkammer.svg"

    PARAMETER = [
        Param("max_umluft", "Höchster Umluftanteil", "%", 80.0,
              darstellung=PROZENT, dezimalstellen=1, minimum=0.0, maximum=100.0,
              hinweis="Obergrenze für die Stellgröße: Auch wenn der Regler mehr "
                      "fordert, wird nie mehr Umluft beigemischt. Der Rest bleibt "
                      "Außenluft - das sichert die Frischluftmenge im Raum.")
    ]

    PORTS = [
        Port("aussenluft_ein", LUFT, EINGANG, AUSSENLUFT),
        Port("umluft_ein", LUFT, EINGANG, UMLUFT),
        Port("luft_aus", LUFT, AUSGANG, ZULUFT),
        Port("umluftanteil", SIGNAL, EINGANG, STELLGROESSE),
        # Der tatsaechlich gefahrene Anteil als Messwert. Ohne ihn liess
        # sich die Klappenstellung weder protokollieren noch als Istwert
        # fuer einen zweiten Regelkreis abgreifen - die Mischkammer war
        # die einzige Karte, die ihre Ausgabe nicht auch herausgab.
        # Anderer Schluessel als der Eingang, weil eine Karte denselben
        # Namen nicht zweimal fuehren kann.
        Port("umluftanteil_ist", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["T_MI", "F_MI", "umluftanteil", "umluftanteil_soll"]
    AUSGABE_LABEL = {
        "T_MI": "Mischtemperatur (°C)",
        "F_MI": "Mischfeuchte, absolut (g/kg)",
        "umluftanteil": "wirksamer Umluftanteil (%)",
        "umluftanteil_soll": "angeforderter Umluftanteil (%)",
    }
    # Der gleichnamige Eingang traegt den GEFORDERTEN Anteil; wirksam wird er
    # erst nach der Begrenzung auf max_umluft - deshalb hier ein eigener Name
    # statt der Beschriftung des Ausgabewerts.
    PORT_LABEL = {"umluftanteil": "geforderter Umluftanteil (0–100 %)"}

    def berechne(self, ein, p, zustand):
        au = ein.get("aussenluft_ein", Luft())
        um = ein.get("umluft_ein", Luft())
        anteil = min(float(ein.get("umluftanteil", 0.0)), p["max_umluft"])

        # Wieviel stromabwaerts abgenommen wird - der Solver legt es am
        # eigenen Luftausgang ab (core/solver.py, _eingaenge). DIESE Menge
        # verlaesst die Mischkammer, nicht die Summe dessen, was an ihren
        # beiden Eingaengen angeboten wird: Was durch eine Mischkammer
        # stroemt, bestimmt der Ventilator dahinter; die beiden Klappen
        # teilen diesen einen Strom nur auf. Vorher stand hier
        # V = au.V + um.V, und das Angebot beider Seiten addierte sich - in
        # core/vorlagen/testanlage.py kamen so 7000 m³/h heraus, wo der
        # Ventilator 5000 forderte. Erhitzer, Kuehler und Befeuchter davor
        # rechneten dann mit 40 Prozent zu viel Luft, und der Ventilator
        # setzte die Menge anschliessend still wieder auf seine eigene.
        V_soll = float(ein.get("luft_aus", Luft()).V)

        # Die Umluftklappe kann nur beimischen, was die Abluftseite anbietet.
        # Fehlt etwas, holt die Aussenluftklappe den Rest - so wie eine echte
        # Mischkammer, deren beide Klappen gegenlaeufig laufen.
        V_um = min(um.V, anteil / 100.0 * V_soll)
        V_au = max(0.0, V_soll - V_um)

        if V_soll > 0:
            T = (V_au * au.T + V_um * um.T) / V_soll
            x = (V_au * au.x + V_um * um.x) / V_soll
        else:
            T, x = au.T, au.x

        # Der WIRKSAME Anteil, nicht der geforderte: er sagt, was die
        # Mischkammer tatsaechlich beigemischt hat.
        wirksam = V_um / V_soll * 100.0 if V_soll > 0 else 0.0

        return (
            {
                "luft_aus": Luft(V=V_soll, T=T, x=x, dp=0.0),
                "T_MI": T, "F_MI": x,
                "umluftanteil": wirksam,
                "umluftanteil_ist": wirksam,
                # Getrennt vom wirksamen Anteil, weil bedarf_gestellt() genau
                # DIESEN braucht: Wuerde dort der wirksame stehen, forderte die
                # Kammer nur noch das an, was sie ohnehin schon bekommt, und
                # naehme jeden zu kleinen Wert als neue Vorgabe - sie schnuerte
                # sich selbst ein. Nachgestellt: In
                # core/vorlagen/testanlage.py blieb sie so bei 40 Prozent
                # stehen, obwohl 60 angefordert waren.
                "umluftanteil_soll": anteil,
            },
            zustand,
        )

    def bedarf(self, aus_bedarf, p):
        """Nennbedarf: die ganze Menge ueber die Aussenluftseite.

        Das ist der Auslegungsfall - bei geschlossener Umluftklappe muss die
        Aussenluftseite den vollen Strom tragen. Wieviel im Betrieb
        tatsaechlich von welcher Seite kommt, entscheidet berechne() anhand
        der Klappenstellung; hier geht es nur um die Groesse der Kanaele.
        """
        gesamt = sum(aus_bedarf.values())
        return {"aussenluft_ein": gesamt, "umluft_ein": 0.0}

    def bedarf_gestellt(self, aus_bedarf, p, werte):
        """Gestellter Bedarf - was die Mischkammer in DIESER Stunde abnimmt.

        Ohne diese Aufteilung fordert die Umluftseite dauerhaft null, und der
        Verteiler davor schickt seinen Strom nach seinem eigenen Schluessel
        statt nach dem, was die Mischkammer braucht. Mit ihr zieht die
        Umluftklappe genau ihren Anteil, und der Rest der Abluft geht dorthin,
        wo er hingehoert - zur Fortluft.
        """
        gesamt = sum(aus_bedarf.values())
        anteil = min(
            float(werte.get("umluftanteil_soll", 0.0)), p["max_umluft"]
        ) / 100.0
        return {
            "aussenluft_ein": gesamt * (1.0 - anteil),
            "umluft_ein": gesamt * anteil,
        }
