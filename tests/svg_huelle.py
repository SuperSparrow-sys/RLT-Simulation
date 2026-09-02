"""Huelle der gezeichneten Geometrie eines Symbols, in Nutzerkoordinaten.

Hilfsmittel fuer tests/test_symbole.py - kein Test, deshalb ohne test_-Namen.

Kein vollstaendiger SVG-Leser: er versteht genau die Formen, die
static/symbole/ benutzt (rect, line, circle, polyline/polygon, path mit
M/L/H/V/C/Q/A/Z und rotate()). Kommt eine neue Form dazu, die er nicht kennt,
faellt sie stillschweigend aus der Huelle - deshalb prueft der Test
zusaetzlich, dass jede gezeichnete Form auch erfasst wurde.

Bei Kurven zaehlen die Kontrollpunkte mit. Die Kurve bleibt immer innerhalb
ihrer Kontrollpunkte, die Huelle ist also hoechstens zu gross - fuer eine
Grenzpruefung die sichere Seite.
"""
import math, re

_ZAHL = re.compile(r"-?\d*\.?\d+(?:e-?\d+)?")


def _zahlen(text):
    return [float(z) for z in _ZAHL.findall(text)]


def _pfadpunkte(d):
    punkte, x, y, start = [], 0.0, 0.0, (0.0, 0.0)
    for befehl, rest in re.findall(r"([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)", d):
        z = _zahlen(rest)
        rel = befehl.islower()
        b = befehl.upper()
        if b == "Z":
            x, y = start
            continue
        i = 0
        while i < len(z) or (b in "MLHVCSQT" and i == 0 and not z):
            if b in ("M", "L", "T"):
                nx, ny = z[i], z[i + 1]; i += 2
                x, y = (x + nx, y + ny) if rel else (nx, ny)
                if b == "M" and not punkte: start = (x, y)
                if b == "M": start = (x, y)
            elif b == "H":
                nx = z[i]; i += 1
                x = x + nx if rel else nx
            elif b == "V":
                ny = z[i]; i += 1
                y = y + ny if rel else ny
            elif b in ("C", "S", "Q", "A"):
                n = {"C": 6, "S": 4, "Q": 4, "A": 7}[b]
                teil = z[i:i + n]; i += n
                # Kontrollpunkte zaehlen mit: die Kurve bleibt in ihrer Huelle,
                # das ist die sichere Seite fuer eine Grenzpruefung.
                paare = [(teil[k], teil[k + 1]) for k in range(0, n - 1, 2)] if b != "A" else [(teil[5], teil[6])]
                for px, py in paare:
                    punkte.append((x + px, y + py) if rel else (px, py))
                lx, ly = paare[-1]
                x, y = (x + lx, y + ly) if rel else (lx, ly)
            else:
                break
            punkte.append((x, y))
            if not z: break
    return punkte


def huelle(svg):
    inhalt = svg[svg.index(">", svg.index("<svg")) + 1:]
    punkte = []
    for x, y, w, h in re.findall(r'<rect[^>]*x="([\d.-]+)"[^>]*y="([\d.-]+)"[^>]*width="([\d.-]+)"[^>]*height="([\d.-]+)"', inhalt):
        x, y, w, h = map(float, (x, y, w, h))
        punkte += [(x, y), (x + w, y + h)]
    for m in re.finditer(r'<line[^>]*x1="([\d.-]+)"[^>]*y1="([\d.-]+)"[^>]*x2="([\d.-]+)"[^>]*y2="([\d.-]+)"', inhalt):
        a, b, c, d = map(float, m.groups()); punkte += [(a, b), (c, d)]
    for m in re.finditer(r'<circle[^>]*cx="([\d.-]+)"[^>]*cy="([\d.-]+)"[^>]*r="([\d.-]+)"', inhalt):
        cx, cy, r = map(float, m.groups()); punkte += [(cx - r, cy - r), (cx + r, cy + r)]
    for m in re.finditer(r'<(?:polyline|polygon)[^>]*points="([^"]+)"', inhalt):
        z = _zahlen(m.group(1)); punkte += list(zip(z[0::2], z[1::2]))
    for m in re.finditer(r'<path[^>]*\sd="([^"]+)"([^>]*)>', inhalt):
        p = _pfadpunkte(m.group(1))
        dreh = re.search(r'rotate\(\s*([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s*\)', m.group(2))
        if dreh:
            a, cx, cy = (float(v) for v in dreh.groups())
            r = math.radians(a)
            p = [(cx + (px - cx) * math.cos(r) - (py - cy) * math.sin(r),
                  cy + (px - cx) * math.sin(r) + (py - cy) * math.cos(r)) for px, py in p]
        punkte += p
    xs = [p[0] for p in punkte]; ys = [p[1] for p in punkte]
    return min(xs), min(ys), max(xs), max(ys)
