"""Lee y escribe fuentes u8g2 (formato comprimido que usa el Flipper Zero)."""
import re


def extraer_arreglo(texto_c, nombre):
    m = re.search(r"const uint8_t " + re.escape(nombre) + r"\[(\d+)\][^=]*=\s*((?:\s*\"(?:[^\"\\]|\\.)*\")+)\s*;", texto_c)
    if not m:
        raise KeyError(nombre)
    partes = re.findall(r"\"((?:[^\"\\]|\\.)*)\"", m.group(2))
    datos = bytearray()
    for p in partes:
        i = 0
        while i < len(p):
            c = p[i]
            if c == "\\":
                n = p[i + 1]
                if n in "01234567":
                    j = i + 1
                    while j < len(p) and j < i + 4 and p[j] in "01234567":
                        j += 1
                    datos.append(int(p[i + 1:j], 8)); i = j; continue
                datos.append({"n": 10, "t": 9, "r": 13, "\\": 92, '"': 34, "'": 39, "?": 63}[n]); i += 2; continue
            datos.append(ord(c)); i += 1
    assert len(datos) + 1 == int(m.group(1)), (nombre, len(datos), m.group(1))  # +1: NUL final de la cadena C
    return bytes(datos)


class Lector:
    def __init__(self, data, pos):
        self.d, self.p, self.bit = data, pos, 0

    def u(self, n):
        v, desp = 0, 0
        while n:
            b = (self.d[self.p] >> self.bit) & 1
            v |= b << desp; desp += 1; n -= 1; self.bit += 1
            if self.bit == 8:
                self.bit, self.p = 0, self.p + 1
        return v

    def s(self, n):
        return self.u(n) - (1 << (n - 1))


CAMPOS = ["cnt", "bbx_mode", "b0", "b1", "bw", "bh", "bx", "by", "bdx", "max_w", "max_h", "x_off", "y_off",
          "asc_A", "desc_g", "asc_p", "desc_p"]


def _s8(v):
    return v - 256 if v > 127 else v


def decodificar(data):
    h = {k: data[i] for i, k in enumerate(CAMPOS)}
    for k in ("x_off", "y_off", "asc_A", "desc_g", "asc_p", "desc_p"):
        h[k] = _s8(h[k])
    glifos = {}
    pos = 23
    while True:
        enc, salto = data[pos], data[pos + 1]
        if salto == 0:
            break
        r = Lector(data, pos + 2)
        w, ht = r.u(h["bw"]), r.u(h["bh"])
        x, y, dx = r.s(h["bx"]), r.s(h["by"]), r.s(h["bdx"])
        pix = []
        total = w * ht
        while len(pix) < total:
            a, b = r.u(h["b0"]), r.u(h["b1"])
            while True:
                pix += [0] * a + [1] * b
                if r.u(1) == 0:
                    break
        filas = [pix[i * w:(i + 1) * w] for i in range(ht)] if w else []
        glifos[enc] = {"w": w, "h": ht, "x": x, "y": y, "dx": dx, "filas": filas}
        pos += salto
    return h, glifos


class Escritor:
    def __init__(self):
        self.b, self.bit = bytearray([0]), 0

    def u(self, v, n):
        for i in range(n):
            self.b[-1] |= ((v >> i) & 1) << self.bit
            self.bit += 1
            if self.bit == 8:
                self.b.append(0); self.bit = 0

    def fin(self):
        return bytes(self.b[:-1] if self.bit == 0 else self.b)


def _bits_u(v):
    return max(1, v.bit_length())


def _bits_s(vals):
    n = 1
    while not all(-(1 << (n - 1)) <= v < (1 << (n - 1)) for v in vals):
        n += 1
    return n


def _corridas(g):
    pix = [p for f in g["filas"] for p in f]
    runs, i = [], 0
    while i < len(pix):
        a = 0
        while i < len(pix) and pix[i] == 0:
            a += 1; i += 1
        b = 0
        while i < len(pix) and pix[i] == 1:
            b += 1; i += 1
        runs.append((a, b))
    return runs


def _recortar(g):
    """Ajusta la caja del glifo a sus píxeles (como hace bdfconv)."""
    f = g["filas"]
    if not f or not any(any(r) for r in f):
        return {**g, "w": 0, "h": 0, "filas": [], "x": g["x"], "y": g["y"]}
    top = next(i for i, r in enumerate(f) if any(r))
    bot = max(i for i, r in enumerate(f) if any(r))
    izq = min(r.index(1) for r in f if any(r))
    der = max(len(r) - 1 - r[::-1].index(1) for r in f if any(r))
    nf = [r[izq:der + 1] for r in f[top:bot + 1]]
    return {"w": der - izq + 1, "h": bot - top + 1, "x": g["x"] + izq, "y": g["y"] + (g["h"] - 1 - bot),
            "dx": g["dx"], "filas": nf}


def _codificar_glifo(g, b0, b1, bw, bh, bx, by, bdx):
    e = Escritor()
    e.u(g["w"], bw); e.u(g["h"], bh)
    e.u(g["x"] + (1 << (bx - 1)), bx); e.u(g["y"] + (1 << (by - 1)), by); e.u(g["dx"] + (1 << (bdx - 1)), bdx)
    pix = [p for f in g["filas"] for p in f]
    i = 0
    while i < len(pix):
        a = 0
        while i < len(pix) and pix[i] == 0 and a < (1 << b0) - 1:
            a += 1; i += 1
        b = 0
        if not (i < len(pix) and pix[i] == 0):
            while i < len(pix) and pix[i] == 1 and b < (1 << b1) - 1:
                b += 1; i += 1
        e.u(a, b0); e.u(b, b1); e.u(0, 1)
    return e.fin()


def codificar(h, glifos):
    glifos = {k: _recortar(v) for k, v in sorted(glifos.items())}
    assert all(k < 256 for k in glifos)
    bw = _bits_u(max(g["w"] for g in glifos.values()))
    bh = _bits_u(max(g["h"] for g in glifos.values()))
    bx = _bits_s([g["x"] for g in glifos.values()])
    by = _bits_s([g["y"] for g in glifos.values()])
    bdx = _bits_s([g["dx"] for g in glifos.values()])
    mejor = None
    for b0 in range(2, 7):
        for b1 in range(2, 7):
            cs = {k: _codificar_glifo(g, b0, b1, bw, bh, bx, by, bdx) for k, g in glifos.items()}
            tam = sum(len(c) for c in cs.values())
            if mejor is None or tam < mejor[0]:
                mejor = (tam, b0, b1, cs)
    _, b0, b1, cs = mejor
    cab = bytearray(23)
    vals = dict(h, cnt=len(glifos), b0=b0, b1=b1, bw=bw, bh=bh, bx=bx, by=by, bdx=bdx)
    for i, k in enumerate(CAMPOS):
        cab[i] = vals[k] & 0xFF
    cuerpo = bytearray()
    pos_A = pos_a = 0
    for enc, c in cs.items():
        assert len(c) + 2 < 256
        if enc == ord("A"):
            pos_A = len(cuerpo)
        if enc == ord("a"):
            pos_a = len(cuerpo)
        cuerpo += bytes([enc, len(c) + 2]) + c
    cuerpo += b"\x00\x00"  # fin de la tabla de 8 bits
    pos_uni = len(cuerpo)
    cuerpo += b"\x00\x00\xff\xff"  # tabla unicode vacía
    cab[17:19] = pos_A.to_bytes(2, "big"); cab[19:21] = pos_a.to_bytes(2, "big"); cab[21:23] = pos_uni.to_bytes(2, "big")
    return bytes(cab + cuerpo)


def a_c(nombre, data):
    lineas, linea = [], ""
    for b in data:
        c = chr(b)
        if 32 <= b < 127 and c not in '\\"?':
            t = c
        else:
            t = "\\%03o" % b
        if len(linea) + len(t) > 72:
            lineas.append(linea); linea = ""
        linea += t
    lineas.append(linea)
    cuerpo = "\n".join('  "%s"' % l for l in lineas)  # octales siempre de 3 dígitos
    return "const uint8_t %s[%d] U8G2_FONT_SECTION(\"%s\") =\n%s;\n" % (nombre, len(data) + 1, nombre, cuerpo)
