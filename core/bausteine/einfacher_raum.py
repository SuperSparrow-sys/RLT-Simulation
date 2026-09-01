"""Einfacher Raum: stationaere Mischbilanz ohne Speicher.

Formeln aus Anlage!AH45 bis AH50. Die Excel setzt Volumenstroeme, die null sind,
auf 0,001 - das verhindert eine Division durch null und wird hier uebernommen.
"""

from core.bausteine.basis import (
    ABLUFT, AUSGANG, EINGANG, LUFT, MESSWERT, SIGNAL, ZAHL, ZULUFT,
    Baustein, Luft, Param, Port, registriere,
)

MINDESTVOLUMEN = 0.001
LUFT_WAERMEKAPAZITAET = 1.2 * 1.007  # kJ/(m³ K), wie in der Excel


@registriere
class EinfacherRaum(Baustein):
    KENNUNG = "einfacher_raum"
    NAME = "Einfacher Raum"
    GRUPPE = "Räume"
    SYMBOL = "einfacher_raum.svg"

    PARAMETER = [
        Param("spez_transmission", "spez. Transmission", "kW/K", 0.5, darstellung=ZAHL, dezimalstellen=2),
        Param("sollwert_stat", "Sollwert für stat. Hzg", "°C", 15.0, darstellung=ZAHL, dezimalstellen=1),
    ]

    PORTS = [
        Port("zuluft_ein", LUFT, EINGANG, ZULUFT, dynamisch=True),
        Port("abluft_aus", LUFT, AUSGANG, ABLUFT, dynamisch=True),
        Port("T_AU", SIGNAL, EINGANG, MESSWERT),
        Port("F_AU", SIGNAL, EINGANG, MESSWERT),
        Port("waermelast", SIGNAL, EINGANG, MESSWERT),
        Port("feuchtelast", SIGNAL, EINGANG, MESSWERT),
        Port("T_Raum", SIGNAL, AUSGANG, MESSWERT),
        Port("F_Raum", SIGNAL, AUSGANG, MESSWERT),
        Port("QH_stat", SIGNAL, AUSGANG, MESSWERT),
    ]

    AUSGABEN = ["T_Raum", "F_Raum", "T_frei", "QH_stat"]
    AUSGABE_LABEL = {
        "T_Raum": "Raumtemperatur", "F_Raum": "Raumfeuchte",
        "QH_stat": "stat. Heizleistung",
    }

    def berechne(self, ein, p, zustand):
        zuluft = [
            (s, w) for s, w in ein.items()
            if s.startswith("zuluft_ein") and isinstance(w, Luft)
        ]
        abluft = [
            (s, w) for s, w in ein.items()
            if s.startswith("abluft_aus") and isinstance(w, Luft)
        ]

        T_AU = float(ein.get("T_AU", 0.0))
        F_AU = float(ein.get("F_AU", 0.0))
        Q_i = float(ein.get("waermelast", 0.0))
        M_i = float(ein.get("feuchtelast", 0.0))
        k = p["spez_transmission"]

        V_zu = [max(w.V, MINDESTVOLUMEN) for _, w in zuluft] or [MINDESTVOLUMEN]
        V_ab = [max(w.V, MINDESTVOLUMEN) for _, w in abluft] or [MINDESTVOLUMEN]
        summe_zu = sum(V_zu)
        summe_ab = sum(V_ab)

        C_zu = summe_zu / 3600.0 * LUFT_WAERMEKAPAZITAET
        waerme_zuluft = sum(
            V * w.T for V, (_, w) in zip(V_zu, zuluft)
        ) / 3600.0 * LUFT_WAERMEKAPAZITAET

        # Die Fallunterscheidung wird EINMAL getroffen und danach nur noch
        # benutzt. Ueberwiegt die Abluft, stroemt die Differenz als Infiltration
        # von aussen nach; das schlaegt gleichermassen auf Temperatur, Feuchte
        # und Heizbedarf durch. Bei Gleichstand ist C_inf null und beide Zweige
        # gehen ineinander ueber.
        abluft_ueberwiegt = summe_ab > summe_zu
        C_inf = 0.0
        bezug = summe_zu
        if abluft_ueberwiegt:
            C_inf = (summe_ab - summe_zu) / 3600.0 * LUFT_WAERMEKAPAZITAET
            bezug = summe_ab

        T_frei = (C_inf * T_AU + waerme_zuluft + Q_i + k * T_AU) / (C_inf + C_zu + k)
        T_Raum = max(T_frei, p["sollwert_stat"])

        feuchte_zuluft = sum(V * w.x for V, (_, w) in zip(V_zu, zuluft))
        feuchte_mischung = (
            feuchte_zuluft + F_AU * (summe_ab - summe_zu if abluft_ueberwiegt else 0.0)
        ) / bezug
        F_Raum = min(feuchte_mischung + M_i * 1000.0 / bezug / 1.2, 99.9)

        QH_stat = 0.0
        if p["sollwert_stat"] > T_frei:
            QH_stat = k * (p["sollwert_stat"] - T_AU) - Q_i
            QH_stat -= sum(
                V / 3600.0 * LUFT_WAERMEKAPAZITAET * (w.T - p["sollwert_stat"])
                for V, (_, w) in zip(V_zu, zuluft)
            )
            if abluft_ueberwiegt:
                QH_stat -= (summe_ab - summe_zu) / 3600.0 * LUFT_WAERMEKAPAZITAET * (
                    T_AU - p["sollwert_stat"]
                )

        aus = {
            "T_Raum": T_Raum, "F_Raum": F_Raum, "T_frei": T_frei,
            "QH_stat": QH_stat, "bezugsvolumen": bezug,
        }
        for schluessel, w in abluft:
            aus[schluessel] = Luft(V=w.V, T=T_Raum, x=F_Raum, dp=0.0)
        return aus, zustand

    def bedarf(self, aus_bedarf, p):
        return {}
