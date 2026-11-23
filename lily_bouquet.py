#!/usr/bin/env python3
"""lily_bouquet.py - genera scene.js: ramo de lirios paramétrico y animable en ASCII.
Solo librería estándar.  Uso:
    python lily_bouquet.py [--seed 7] [--scale 0.85] [--step 0.45] [--particles 170] [--json]

Cada celda: [col, fila, caracter, color, luminancia, tipo, id, a, b]
  tipo 0 pétalo   (id = flor,  a,b = posición de la celda cuando es brote)
  tipo 1 tallo    (id = flor,  a   = u, avance 0..1 desde la base)
  tipo 2 partícula
  tipo 3 hoja     (id = hoja)
  tipo 4 estambre (id = flor,  a,b = centro de la flor)
La línea de tiempo (segundos) también sale de aquí: ver TIMELINE.
"""
import argparse, json, math, random
from dataclasses import dataclass, asdict

ASPECT = 0.5                 # ancho/alto de una celda de texto: fila = y_mundo * ASPECT
RAMP = " .:-=+*#%@"          # DENSIDAD: de menos a más denso (editable)
STEP = 0.45                  # paso de muestreo en celdas (menor = más fino y más lento)

# TIEMPOS (segundos): ventanas aleatorias (mín, máx) por flor
TIMELINE = dict(stem_start=(0.0, 1.2), stem_dur=(3.2, 4.0),      # tallos crecen
                open_start=(6.5, 9.5), open_dur=3.5,              # brotes se abren
                particles=(9.5, 14.0))                            # aparecen las partículas

# PALETA: (centro, medio, punta) - degradado desde el centro hacia las puntas
PALETTES = {
    "rojo":     ("#f7e27a", "#e5262d", "#7d0c18"),
    "magenta":  ("#f4e08a", "#e04fc0", "#7a2380"),
    "morado":   ("#f0e7a0", "#b04fd8", "#4f2490"),
    "amarillo": ("#fff3a0", "#f2c230", "#c78a12"),
    "blanco":   ("#d8e68a", "#f8f2ea", "#c2b8aa"),
    "durazno":  ("#f8e69a", "#f2a574", "#c8642e"),
}
GREEN = ("#2f7a2a", "#6cc04a", "#c4ef7a")      # tallos y hojas (oscuro, medio, claro)

# COMPOSICIÓN Y TAMAÑO: (col, fila, radio_en_columnas, paleta, rotación°, inclinación, z)
FLOWERS = [
    (32, 26, 22, "blanco",   8, .90, 0.0),
    (84, 24, 22, "amarillo", 25, .85, 0.1),
    (58, 14, 15, "durazno",   0, .80, 0.2),
    (58, 32, 27, "rojo",     15, .90, 2.0),
    (90, 42, 19, "morado",    5, .85, 1.0),
    (20, 48, 19, "amarillo", 20, .85, 1.5),
    (36, 52, 27, "magenta",   0, .90, 3.0),
    (68, 56, 28, "blanco",   30, .85, 4.0),
    (52, 68, 24, "durazno",  12, .90, 5.0),
    (94, 66, 15, "rojo",     40, .80, 1.2),
]
GATHER = (58, 94)            # punto donde nacen los tallos


def h2r(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def hexc(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in c)


def grad(stops, t):
    """Degradado de 3 paradas (centro -> medio -> punta), t en [0, 1]."""
    c, m, p = (h2r(s) for s in stops)
    return mix(c, m, t / .45) if t < .45 else mix(m, p, (t - .45) / .55)


def hash2(x, y):
    return ((int(x * 3) * 73856093) ^ (int(y * 5) * 19349663)) % 1000 / 1000


class Canvas:
    """Z-buffer sobre la rejilla. Hay uno por grupo (flores, tallos, hojas) para que
    una flor no borre las celdas del tallo que quedan debajo cuando aún es un brote."""
    def __init__(self):
        self.buf = {}

    def put(self, x, y, z, rgb, l, kind, ident, ch=None, ex=(0, 0)):
        k = (round(x), round(y))
        old = self.buf.get(k)
        if old is None or z >= old[0]:
            if ch is None:
                i = int(l * (len(RAMP) - 1) + (hash2(x, y) - .5) * 1.2)   # variedad de caracteres
                ch = RAMP[max(2, min(len(RAMP) - 1, i))]
            self.buf[k] = (z, ch, rgb, l, kind, ident, ex)


def blade(cv, x0, y0, ang, L, W, color, z, kind, ident, bend=0., phi=0., tilt=1.,
          lum=0., ruf=0., asym=0., curl=0., bud=None, seed=0.):
    """Hoja alargada y puntiaguda (pétalos y hojas).
    t = largo [0,1], s = ancho [-1,1].  Toques orgánicos: borde ondulado (ruf), un lado más
    ancho (asym), punta que se enrolla (curl) y vista en perspectiva (phi, tilt).
    bud = (ángulo, largo, ancho): dónde cae la misma celda cuando la flor es un brote."""
    nt = int(L / STEP * 1.3) + 2
    ns = int(W * 2 / STEP * 1.3) + 2
    ca, sa = math.cos(ang), math.sin(ang)
    cp, sp = math.cos(phi), math.sin(phi)
    for i in range(nt + 1):
        t = i / nt
        prof = math.sin(math.pi * t ** .7) ** .85              # base fina, punta aguda
        edge = 1 + ruf * math.sin(t * 13 + seed)               # borde ondulado
        for j in range(ns + 1):
            s = -1 + 2 * j / ns
            a = t * L
            b = s * W * prof * edge * (1 + asym * s) + bend * L * t * t + curl * L * 3 * max(0., t - .62) ** 2
            wx, wy = a * ca - b * sa, a * sa + b * ca
            rx, ry = wx * cp + wy * sp, (-wx * sp + wy * cp) * tilt   # perspectiva: aplasta un eje
            x, y = x0 + rx * cp - ry * sp, y0 + (rx * sp + ry * cp) * ASPECT
            l = .5 + .4 * (1 - s * s) + lum + .1 * math.cos(ang + 2.4) + (hash2(x, y) - .5) * .14
            if abs(s) < .08:
                l *= .8                                         # nervio central
            elif abs(s) > .85:
                l += .08                                        # borde más claro
            ex = (0, 0)
            if bud:
                th, Lb, Wb = bud
                ab, bb = t * Lb, s * Wb * prof
                ex = (x0 + ab * math.cos(th) - bb * math.sin(th),
                      y0 + (ab * math.sin(th) + bb * math.cos(th)) * ASPECT)
            cv.put(x, y, z, color(t, s, x, y), max(0., min(1., l)), kind, ident, None, ex)


def petal_color(pal):
    def f(t, s, x, y):
        c = grad(pal, t)
        if abs(s) < .1 and t > .1:
            c = mix(c, (255, 255, 255), .15)
        if .12 < t < .6 and abs(s) < .85 and hash2(x, y) < .07:
            c = mix(c, h2r(pal[2]), .7)                         # pecas del lirio
        return c
    return f


def leaf_color(t, s, x, y):
    return mix(h2r(GREEN[0]), h2r(GREEN[2]), min(1, t ** .8 * .8 + (1 - abs(s)) * .2))


def stamens(cv, fid, cx, cy, R, phi, tilt, z, rnd):
    cp, sp = math.cos(phi), math.sin(phi)
    for k in range(6):
        a, ln = k * math.pi / 3 + rnd.uniform(-.3, .3) + .5, R * rnd.uniform(.45, .62)
        for i in range(21):
            t = i / 20
            wx, wy = ln * t * math.cos(a), ln * t * math.sin(a) - R * .1 * t * t
            rx, ry = wx * cp + wy * sp, (-wx * sp + wy * cp) * tilt
            x, y = cx + rx * cp - ry * sp, cy + (rx * sp + ry * cp) * ASPECT
            cv.put(x, y, z + .05, (222, 196, 120), .7, 4, fid, ".", (cx, cy))
        for dx, ch in ((-1, "#"), (0, "@"), (1, "#")):          # antera
            cv.put(x + dx, y, z + .06, (196, 98, 30), .9, 4, fid, ch, (cx, cy))
    cv.put(cx, cy, z + .05, (150, 190, 70), .8, 4, fid, "*", (cx, cy))


def bez(p0, p1, p2, u):
    """Bézier cuadrática: punto y tangente en u."""
    v = 1 - u
    return (v * v * p0[0] + 2 * v * u * p1[0] + u * u * p2[0],
            v * v * p0[1] + 2 * v * u * p1[1] + u * u * p2[1],
            2 * v * (p1[0] - p0[0]) + 2 * u * (p2[0] - p1[0]),
            2 * v * (p1[1] - p0[1]) + 2 * u * (p2[1] - p1[1]))


def stem(cv, p0, p1, p2, fid):
    """Tallo que se afina hacia la punta; guarda u para poder hacerlo crecer."""
    n = 260
    for i in range(n + 1):
        u = i / n
        x, y, dx, dy = bez(p0, p1, p2, u)
        vx = dx * ASPECT
        ch = "|" if abs(vx) < .38 * abs(dy) else ("\\" if vx * dy > 0 else "/")
        w = .65 * (1 - .55 * u)
        for off in (-w, w):
            cv.put(x + off, y, -1, mix(h2r(GREEN[0]), h2r(GREEN[2]), .2 + .3 * (off > 0) + .2 * u),
                   .5, 1, fid, ch, (round(u, 2), 0))


@dataclass
class Bounds:
    xmin: int
    xmax: int
    ymin: int
    ymax: int
    maxw: int          # ancho máximo de una fila


def compute_bounds(keys):
    """Límites espaciales (xmin, xmax, ymin, ymax, maxw) de todas las celdas ocupadas."""
    rows = {}
    for x, y in keys:
        lo, hi = rows.get(y, (x, x))
        rows[y] = (min(lo, x), max(hi, x))
    xs, ys = [k[0] for k in keys], [k[1] for k in keys]
    return Bounds(min(xs), max(xs), min(ys), max(ys), max(h - l + 1 for l, h in rows.values()))


def build(seed, scale, particles):
    rnd = random.Random(seed)
    cvF, cvS, cvL = Canvas(), Canvas(), Canvas()
    TL = TIMELINE
    T = lambda x, y: (55 + (x - 55) * scale, 50 + (y - 50) * scale)
    gx, gy = T(*GATHER)
    flowers, leaves, geo = [], [], []

    for idx, (x, y, R, name, rot, tilt, z) in enumerate(FLOWERS):
        cx, cy = T(x, y)
        R *= scale
        base = (gx + rnd.uniform(-4, 4), gy)
        ctrl = (base[0] + (cx - base[0]) * .35 + rnd.uniform(-5, 5), base[1] + (cy - base[1]) * .6)
        ts, td = rnd.uniform(*TL["stem_start"]), rnd.uniform(*TL["stem_dur"])
        to = rnd.uniform(*TL["open_start"])
        flowers.append([cx, cy, round(rnd.uniform(0, 6.28), 2), round(ts, 2), round(td, 2), round(to, 2), TL["open_dur"]])
        geo.append((base, ctrl, (cx, cy), ts, td))
        stem(cvS, base, ctrl, (cx, cy), idx)

        _, _, dx, dy = bez(base, ctrl, (cx, cy), 1)
        theta = math.atan2(dy / ASPECT, dx)                     # hacia dónde apunta el brote
        pal, color = PALETTES[name], petal_color(PALETTES[name])
        r0 = math.radians(rot + rnd.uniform(-10, 10))
        phi, tl = rnd.uniform(0, math.pi), tilt * rnd.uniform(.9, 1.05)
        for k in range(6):                                      # capa trasera, más oscura
            blade(cvF, cx, cy, r0 + math.pi / 6 + k * math.pi / 3 + rnd.uniform(-.08, .08),
                  R * rnd.uniform(.72, .85), R * .27, color, z, 0, idx, rnd.uniform(-.12, .12), phi, tl,
                  -.2, .05, rnd.uniform(-.2, .2), rnd.uniform(-.3, .3),
                  (theta + ((k % 3) - 1) * .2, R * .45, R * .1), rnd.uniform(0, 6))
        for k in range(6):                                      # 3 externos + 3 internos (más anchos)
            inner = k % 2
            blade(cvF, cx, cy, r0 + k * math.pi / 3 + rnd.uniform(-.1, .1),
                  R * rnd.uniform(.92, 1.05) * (.95 if inner else 1), R * (.34 if inner else .26) * rnd.uniform(.9, 1.1),
                  color, z + .01 + .01 * inner, 0, idx, rnd.choice((-.14, -.08, .08, .14)), phi, tl,
                  .08 * inner, .06, rnd.uniform(-.25, .25), rnd.uniform(.2, .6),
                  (theta + ((k % 3) - 1) * .14, R * (.55 if inner else .6), R * .12), rnd.uniform(0, 6))
        stamens(cvF, idx, cx, cy, R, phi, tl, z, rnd)

    def add_leaf(ox, oy, ang, L, W, bend, ts, td):
        lid = len(leaves)
        leaves.append([ox, oy, round(ts, 2), round(td, 2)])
        blade(cvL, ox, oy, ang, L, W, leaf_color, -.5, 3, lid, bend=bend, ruf=.03, curl=.2, seed=rnd.uniform(0, 6))

    for _ in range(9):                                          # hojas anchas de la base
        side = rnd.choice((-1, 1))
        add_leaf(gx + rnd.uniform(-5, 5), gy - rnd.uniform(0, 6), -math.pi / 2 + side * rnd.uniform(.45, 1.25),
                 rnd.uniform(30, 46) * scale, 3.4 * scale, side * .22, rnd.uniform(.6, 3), 3.5)
    for _ in range(10):                                         # hojas finas que nacen de los tallos
        base, ctrl, c, ts, td = rnd.choice(geo)
        u = rnd.uniform(.25, .65)
        px, py, dx, dy = bez(base, ctrl, c, u)
        side = rnd.choice((-1, 1))
        add_leaf(px, py, math.atan2(dy / ASPECT, dx) + side * rnd.uniform(.45, .85),
                 rnd.uniform(22, 34) * scale, 2.2 * scale, -side * .1, ts + u * td + .3, 2.5)

    keys = set(cvF.buf) | set(cvS.buf) | set(cvL.buf)
    b = compute_bounds(keys)
    pad = 4
    dx, dy = pad - b.xmin, pad - b.ymin                         # recentra con margen
    cols, rows = b.xmax - b.xmin + 1 + 2 * pad, b.ymax - b.ymin + 1 + 2 * pad

    def emit(cv, shift):
        out = []
        for (px, py), (z, ch, rgb, l, kind, ident, ex) in sorted(cv.buf.items(), key=lambda kv: kv[1][0]):
            a, bb = (round(ex[0] + dx, 1), round(ex[1] + dy, 1)) if shift else (ex[0], ex[1])
            out.append([px + dx, py + dy, ch, hexc(rgb), round(l, 2), kind, ident, a, bb])
        return out

    taken = {(k[0] + dx, k[1] + dy) for k in keys}
    stars = []
    while len(stars) < particles:                               # partículas de fondo
        c, r = rnd.randrange(cols), rnd.randrange(rows)
        if (c, r) in taken:
            continue
        taken.add((c, r))
        v = rnd.randint(70, 170)
        stars.append([c, r, rnd.choice(".,'`*+"), hexc((v, v, v * 1.1)), .3, 2, -1, 0, 0])
    back = stars + emit(cvL, False) + emit(cvS, False)
    cells = back + emit(cvF, True)
    total = max(max(f[5] + f[6] for f in flowers), max(l[2] + l[3] for l in leaves)) + .5
    return dict(cols=cols, rows=rows, aspect=ASPECT, bounds=asdict(b), fstart=len(back),
                timeline=dict(total=round(total, 2), particles=list(TL["particles"])),
                flowers=[[f[0] + dx, f[1] + dy] + f[2:] for f in flowers],
                leaves=[[l[0] + dx, l[1] + dy] + l[2:] for l in leaves], cells=cells)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--scale", type=float, default=0.85, help="tamaño del ramo")
    ap.add_argument("--step", type=float, default=0.45, help="paso de muestreo (menor = más denso)")
    ap.add_argument("--particles", type=int, default=170)
    ap.add_argument("--json", action="store_true", help="escribe también scene.json")
    a = ap.parse_args()
    STEP = a.step
    scene = build(a.seed, a.scale, a.particles)
    data = json.dumps(scene, separators=(",", ":"))
    open("scene.js", "w", encoding="utf-8").write("window.SCENE=" + data + ";")
    if a.json:
        open("scene.json", "w", encoding="utf-8").write(data)
    print("scene.js listo:", len(scene["cells"]), "celdas,", scene["cols"], "x", scene["rows"], scene["bounds"])
