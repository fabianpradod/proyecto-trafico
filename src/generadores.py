"""Generación de variables aleatorias — pista B.

Todo lo que el proyecto sortea sale de `Generador.uniformes`; ningún método
llama a `np.random` por su cuenta. La fuente de uniformes y el método para
normales son parámetros del constructor, así que la pista C puede repetir la
simulación con otro generador sin tocar su código (criterio 5 de §7).

    g = Generador(config.SEMILLA)
    s = g.lognormales(5000, config.LOGN_MU, config.LOGN_SIGMA)
"""

from __future__ import annotations

import numpy as np

import config

# --------------------------------------------------------------------------
# Fuentes de números uniformes
# --------------------------------------------------------------------------


class FuenteLCG:
    """Generador congruencial lineal  x[n+1] = (a·x[n] + c) mod m.

    Se genera por bloques con salto adelante: f^k(x) = A·x + C, con A = a^k y
    C = c·(a^(k−1) + … + 1), ambos por exponenciación binaria. Así cada fila
    sale de la anterior con una operación de NumPy en vez de un bucle de
    Python, y el banco de tiempos mide el algoritmo. La sucesión es la misma
    que la del bucle ingenuo; el notebook 03 lo comprueba.
    """

    #: cuántos números se calculan de corrido antes de saltar a vectorizado
    BLOQUE = 4096

    def __init__(self, semilla: int, a: int, c: int, m: int, nombre: str = "lcg"):
        if m & (m - 1):
            raise ValueError("este LCG asume m potencia de dos (el módulo es una máscara)")
        self.a, self.c, self.m, self.nombre = int(a), int(c), int(m), nombre
        self._mascara = np.uint64(m - 1)

        estado = int(semilla) % m
        if self.c == 0:
            # RANDU: con semilla par pierde bits en cada paso, con 0 se clava.
            if estado % 2 == 0:
                estado += 1
            estado %= m
        self.estado = estado
        self.semilla = estado

    # -- salto adelante ----------------------------------------------------
    def _salto(self, k: int) -> tuple[int, int]:
        """Coeficientes (A, C) tales que x[n+k] = (A·x[n] + C) mod m."""
        A, C = 1, 0                       # identidad
        ba, bc = self.a, self.c           # f^1
        m = self.m
        while k:
            if k & 1:
                # aplicar (A,C) y después (ba,bc)
                A, C = (A * ba) % m, (ba * C + bc) % m
            ba, bc = (ba * ba) % m, (ba * bc + bc) % m
            k >>= 1
        return A, C

    def enteros(self, n: int) -> np.ndarray:
        """Los siguientes `n` estados de la sucesión, en orden."""
        if n <= 0:
            return np.empty(0, dtype=np.uint64)

        b = min(self.BLOQUE, n)
        # Primera fila: b pasos de corrido desde el estado actual.
        fila = np.empty(b, dtype=np.uint64)
        x, a, c, m = self.estado, self.a, self.c, self.m
        for j in range(b):
            x = (a * x + c) % m
            fila[j] = x

        n_filas = -(-n // b)  # techo de la división
        if n_filas == 1:
            salida = fila[:n]
        else:
            A, C = self._salto(b)
            A64, C64 = np.uint64(A), np.uint64(C)
            bloque = np.empty((n_filas, b), dtype=np.uint64)
            bloque[0] = fila
            for i in range(1, n_filas):
                # El desborde de uint64 es inofensivo: m divide a 2^64.
                bloque[i] = (bloque[i - 1] * A64 + C64) & self._mascara
            salida = bloque.reshape(-1)[:n]

        self.estado = int(salida[-1])
        return salida

    def uniformes(self, n: int) -> np.ndarray:
        """`n` uniformes en [0, 1). El 0 es alcanzable; el 1 no."""
        return self.enteros(n).astype(np.float64) / self.m


class FuentePCG64:
    """Envoltorio sobre el generador por defecto de NumPy, para que entre a la
    comparación por la misma puerta que el LCG propio y RANDU."""

    nombre = "pcg64"

    def __init__(self, semilla: int):
        self.semilla = int(semilla)
        self._rng = np.random.default_rng(self.semilla)

    def uniformes(self, n: int) -> np.ndarray:
        return self._rng.random(n)


def fuente(nombre: str, semilla: int):
    """Construye una fuente de uniformes por nombre."""
    nombre = nombre.lower()
    if nombre == "pcg64":
        return FuentePCG64(semilla)
    if nombre == "lcg":
        return FuenteLCG(semilla, config.LCG_A, config.LCG_C, config.LCG_M, "lcg")
    if nombre == "randu":
        return FuenteLCG(semilla, config.RANDU_A, config.RANDU_C, config.RANDU_M, "randu")
    raise ValueError(f"fuente desconocida: {nombre!r} (use pcg64, lcg o randu)")


FUENTES = ("pcg64", "lcg", "randu")
METODOS_NORMAL = ("polar", "rechazo")

#: Uniformes por normal aceptada, en teoría (criterio 2 de §7).
#:   polar   : 2 por intento, aceptación π/4, 2 normales por acierto -> 4/π
#:   rechazo : 2 por intento, aceptación 1/c, más 1 para el signo    -> 2c + 1
C_RECHAZO = np.sqrt(2.0 * np.e / np.pi)          # ≈ 1.31549
TEORICO_UNIFORMES_POR_NORMAL = {
    "polar": 4.0 / np.pi,                        # ≈ 1.27324
    "rechazo": 2.0 * C_RECHAZO + 1.0,            # ≈ 3.63099
}


# --------------------------------------------------------------------------
# Generador
# --------------------------------------------------------------------------


class Generador:
    """Punto único de acceso a la aleatoriedad del proyecto.

    `semilla` es la de la fuente; la pista C usa SEMILLA + r para la réplica r,
    la misma en el escenario abierto y en el cerrado (§5.6). `fuente_nombre` es
    "pcg64", "lcg" o "randu"; `metodo_normal`, "polar" o "rechazo" (par 1 de §7).

    `uniformes_consumidos` lleva la cuenta de lo que sale de la fuente, que es
    de donde se lee el criterio 2.
    """

    def __init__(self, semilla: int = config.SEMILLA, fuente_nombre: str = "pcg64",
                 metodo_normal: str = "polar"):
        if metodo_normal not in METODOS_NORMAL:
            raise ValueError(f"método normal desconocido: {metodo_normal!r}")
        self.semilla = int(semilla)
        self.fuente_nombre = fuente_nombre
        self.metodo_normal = metodo_normal
        self._fuente = fuente(fuente_nombre, semilla)
        self.uniformes_consumidos = 0
        self._sobrantes: dict[str, np.ndarray | None] = {m: None for m in METODOS_NORMAL}

    def __repr__(self) -> str:
        return (f"Generador(semilla={self.semilla}, fuente={self.fuente_nombre!r}, "
                f"metodo_normal={self.metodo_normal!r})")

    def reiniciar(self) -> None:
        """Vuelve al estado inicial: la secuencia se repite igual."""
        self._fuente = fuente(self.fuente_nombre, self.semilla)
        self.uniformes_consumidos = 0
        self._sobrantes = {m: None for m in METODOS_NORMAL}

    # -- uniformes ---------------------------------------------------------
    def uniformes(self, n: int) -> np.ndarray:
        """`n` uniformes en [0, 1)."""
        n = int(n)
        if n <= 0:
            return np.empty(0)
        self.uniformes_consumidos += n
        return self._fuente.uniformes(n)

    # -- exponencial y Erlang ---------------------------------------------
    def exponenciales(self, n: int, lam: float) -> np.ndarray:
        """Exponencial(λ) por transformada inversa.

        Se usa −ln(1 − U)/λ y no la forma de los libros −ln(U)/λ porque el LCG
        sí puede devolver un 0 exacto y −ln(0) es infinito. 1 − U nunca vale 0.
        """
        if lam <= 0:
            raise ValueError("λ debe ser positivo")
        u = self.uniformes(n)
        return -np.log1p(-u) / lam

    def erlang(self, n: int, k: int = config.ERLANG_K,
               lam: float = config.ERLANG_LAMBDA) -> np.ndarray:
        """Erlang(k, λ) como convolución de k exponenciales inversas.

        Media k/λ, varianza k/λ². Con k = 2 la densidad en el origen es nula,
        que es lo correcto para una demora de semáforo.
        """
        k = int(k)
        if k < 1:
            raise ValueError("k debe ser un entero ≥ 1")
        u = self.uniformes(n * k).reshape(n, k)
        return (-np.log1p(-u)).sum(axis=1) / lam

    # -- normales ----------------------------------------------------------
    def normales(self, n: int, metodo: str | None = None) -> np.ndarray:
        """`n` normales estándar por el método configurado (o el que se pida)."""
        metodo = metodo or self.metodo_normal
        if metodo == "polar":
            return self._normales_polar(n)
        if metodo == "rechazo":
            return self._normales_rechazo(n)
        raise ValueError(f"método normal desconocido: {metodo!r}")

    def _normales_polar(self, n: int) -> np.ndarray:
        """Método polar de Marsaglia.

        V1, V2 uniformes en [−1, 1] hasta caer en el círculo unitario
        (probabilidad π/4) y se devuelven dos normales V·√(−2·ln S / S), sin
        senos ni cosenos. Salen de dos en dos, así que lo que sobra se guarda
        para la llamada siguiente en vez de tirarse.
        """
        n = int(n)
        if n <= 0:
            return np.empty(0)

        salida = np.empty(n)
        i = self._tomar_sobrantes("polar", salida, 0)

        p = np.pi / 4.0                        # probabilidad de caer en el disco
        while i < n:
            faltan = n - i
            k = int(np.ceil(faltan / 2))       # pares que hacen falta
            # Media k/p más tres desviaciones: el exceso crece como √k, así
            # que el consumo medido converge al teórico.
            m = int(np.ceil(k / p + 3.0 * np.sqrt(k * (1.0 - p)) / p)) + 4
            v = self.uniformes(2 * m).reshape(m, 2) * 2.0 - 1.0
            s = (v**2).sum(axis=1)
            ok = (s > 0.0) & (s <= 1.0)        # el 0 se descarta: divide
            v, s = v[ok], s[ok]
            if v.size == 0:
                continue
            z = (v * np.sqrt(-2.0 * np.log(s) / s)[:, None]).reshape(-1)
            i = self._guardar_y_tomar("polar", z, salida, i)
        return salida

    # -- caché de normales sobrantes ---------------------------------------
    # Una caché por método: con una sola compartida, una llamada con `rechazo`
    # podría servirse de normales del `polar` y el par 1 de §7 dejaría de
    # comparar lo que dice.
    def _tomar_sobrantes(self, metodo: str, salida: np.ndarray, i: int) -> int:
        buf = self._sobrantes.get(metodo)
        if buf is None:
            return i
        toma = min(salida.size - i, buf.size)
        salida[i:i + toma] = buf[:toma]
        resto = buf[toma:]
        self._sobrantes[metodo] = resto if resto.size else None
        return i + toma

    def _guardar_y_tomar(self, metodo: str, z: np.ndarray,
                         salida: np.ndarray, i: int) -> int:
        toma = min(salida.size - i, z.size)
        salida[i:i + toma] = z[:toma]
        if z.size > toma:
            self._sobrantes[metodo] = z[toma:].copy()
        return i + toma

    def _normales_rechazo(self, n: int) -> np.ndarray:
        """Aceptación-rechazo con envolvente exponencial (Ross, ejemplo 5f).

        |Z| con densidad √(2/π)·e^(−x²/2) y envolvente g(x) = e^(−x). La cota
        es c = √(2e/π) ≈ 1.3155 (aceptación ≈ 0.760) y la condición se reduce
        a U ≤ e^(−(Y−1)²/2). El signo cuesta un uniforme más: de ahí los
        2c + 1 ≈ 3.63 por normal contra los 4/π ≈ 1.27 del polar.
        """
        n = int(n)
        if n <= 0:
            return np.empty(0)

        salida = np.empty(n)
        i = self._tomar_sobrantes("rechazo", salida, 0)

        p = 1.0 / C_RECHAZO                    # tasa de aceptación ≈ 0.760
        while i < n:
            k = n - i
            # Igual que en el polar.
            m = int(np.ceil(k / p + 3.0 * np.sqrt(k * (1.0 - p)) / p)) + 4
            u1 = self.uniformes(m)
            u2 = self.uniformes(m)
            y = -np.log1p(-u1)                 # |Z| candidato: Exp(1) por inversa
            y = y[u2 <= np.exp(-0.5 * (y - 1.0) ** 2)]
            if y.size == 0:
                continue
            # Un uniforme más por aceptada, para el signo.
            signo = np.where(self.uniformes(y.size) < 0.5, -1.0, 1.0)
            i = self._guardar_y_tomar("rechazo", signo * y, salida, i)
        return salida

    def lognormales(self, n: int, mu: float = config.LOGN_MU,
                    sigma: float = config.LOGN_SIGMA,
                    metodo: str | None = None) -> np.ndarray:
        """Lognormal(μ, σ) exponenciando una normal.

        Fuente D: el multiplicador de velocidad de cada conductor. Positiva por
        construcción y con cola a la derecha; con μ = 0 la mediana es 1.0.
        """
        return np.exp(mu + sigma * self.normales(n, metodo))

    def normales_truncadas(self, n: int, mu: float, sigma: float,
                           bajo: float = -np.inf, alto: float = np.inf,
                           metodo: str | None = None) -> np.ndarray:
        """Normal(μ, σ) truncada a [bajo, alto] por rechazo.

        Fuente F, la capacidad efectiva del segmento. Sin truncar saldrían
        capacidades negativas, que no significan nada.
        """
        if not bajo < alto:
            raise ValueError("el intervalo de truncamiento está vacío")
        from scipy.stats import norm

        # Probabilidad de caer dentro, para dimensionar la tanda.
        p = float(norm.cdf((alto - mu) / sigma) - norm.cdf((bajo - mu) / sigma))
        if p <= 0.0:
            raise ValueError("el truncamiento deja probabilidad cero")

        salida = np.empty(int(n))
        i = 0
        while i < salida.size:
            k = salida.size - i
            m = int(np.ceil(k / p + 3.0 * np.sqrt(k * (1.0 - p)) / p)) + 4
            x = mu + sigma * self.normales(m, metodo)
            x = x[(x >= bajo) & (x <= alto)]
            toma = min(k, x.size)
            if toma:
                salida[i:i + toma] = x[:toma]
                i += toma
        return salida

    # -- procesos de Poisson ----------------------------------------------
    def poisson_homogeneo(self, T: float, lam: float,
                          metodo: str = "inversa") -> np.ndarray:
        """Instantes de un Poisson homogéneo de tasa λ en [0, T]. Par 2 de §7.

        "inversa" acumula tiempos entre llegadas Exp(λ) hasta pasar T y sirve
        en línea. "condicional" sortea N ~ Poisson(λT) y coloca N uniformes
        ordenadas; necesita T de antemano. Los dos son exactos.
        """
        if metodo == "inversa":
            return self._poisson_inversa(T, lam)
        if metodo == "condicional":
            return self._poisson_condicional(T, lam)
        raise ValueError(f"método de Poisson desconocido: {metodo!r}")

    def _poisson_inversa(self, T: float, lam: float) -> np.ndarray:
        instantes: list[np.ndarray] = []
        acumulado, total = 0.0, 0.0
        while True:
            # Tanda del tamaño esperado que falta, más un margen de 6σ.
            faltan = max(T - acumulado, 0.0) * lam
            m = int(faltan + 6.0 * np.sqrt(faltan + 1.0)) + 16
            t = acumulado + np.cumsum(self.exponenciales(m, lam))
            dentro = t < T
            instantes.append(t[dentro])
            total += int(dentro.sum())
            if not dentro.all():
                break
            acumulado = float(t[-1])
        return np.concatenate(instantes) if instantes else np.empty(0)

    def _poisson_condicional(self, T: float, lam: float) -> np.ndarray:
        n = self.poisson_conteo(lam * T)
        return np.sort(self.uniformes(n) * T)

    def poisson_conteo(self, media: float) -> int:
        """Un entero Poisson(media) por transformada inversa.

        La recursión p[0] = e^(−media), p[k+1] = p[k]·media/(k+1) desborda por
        debajo: aquí media ≈ 6 900 y e^(−6900) es cero en punto flotante. Se
        evalúa la inversa sobre la CDF de SciPy, que trabaja en logaritmos.
        Sigue siendo inversa y sigue costando un uniforme.
        """
        from scipy.stats import poisson

        u = float(self.uniformes(1)[0])
        return int(poisson.ppf(u, media))

    def poisson_nh(self, T: float, lam_func, lam_max: float | None = None,
                   devolver_eficiencia: bool = False):
        """Poisson no homogéneo por adelgazamiento. Fuente A del modelo.

        Se simula un homogéneo de tasa λ* = max λ(t) y cada candidato se
        conserva con probabilidad λ(t)/λ*. `lam_func` recibe t en horas desde
        el inicio del horizonte y devuelve veh/h.

        Con `devolver_eficiencia` devuelve también la fracción aceptada, que
        §5.1 pide reportar.
        """
        if lam_max is None:
            malla = np.linspace(0.0, T, 2001)
            lam_max = float(np.max(lam_func(malla)))
        if not np.isfinite(T) or T <= 0 or not np.isfinite(lam_max) or lam_max <= 0:
            raise ValueError("horizonte y cota deben ser positivos")
        candidatos = self._poisson_inversa(T, lam_max)
        u = self.uniformes(candidatos.size)
        tasas = np.asarray(lam_func(candidatos), dtype=float)
        if not np.isfinite(tasas).all() or np.any(tasas < 0) or np.any(tasas > lam_max*(1+1e-12)):
            raise ValueError("lambda(t) fuera de la envolvente de adelgazamiento")
        acepta = u < tasas / lam_max
        instantes = candidatos[acepta]
        if devolver_eficiencia:
            ef = float(acepta.mean()) if candidatos.size else float("nan")
            return instantes, ef
        return instantes

    # -- categórica --------------------------------------------------------
    def categorica(self, n: int, probabilidades) -> np.ndarray:
        """`n` índices por transformada inversa discreta. Fuente B, el par
        origen-destino: con pocas categorías es exacta y cuesta un uniforme."""
        p = np.asarray(probabilidades, dtype=float)
        if np.any(p < 0):
            raise ValueError("hay probabilidades negativas")
        total = p.sum()
        if not np.isclose(total, 1.0):
            p = p / total
        acumulada = np.cumsum(p)
        acumulada[-1] = 1.0
        return np.searchsorted(acumulada, self.uniformes(n), side="right")


# --------------------------------------------------------------------------
# Pruebas de calidad — §8
# --------------------------------------------------------------------------
# Aquí y no en el notebook para que la pista C las pueda reusar.


def prueba_rachas(u: np.ndarray) -> dict:
    """Prueba de rachas ascendentes y descendentes.

    Cuenta los tramos monótonos. Bajo independencia E[R] = (2n − 1)/3 y
    Var[R] = (16n − 29)/90, y el estadístico normalizado es N(0,1). Detecta
    tendencias, que es lo que una prueba de bondad de ajuste no ve.
    """
    u = np.asarray(u)
    n = u.size
    if n < 3:
        raise ValueError("hacen falta al menos 3 observaciones")
    signos = np.sign(np.diff(u))
    signos = signos[signos != 0]           # los empates no rompen la racha
    r = 1 + int(np.count_nonzero(np.diff(signos)))
    m = len(signos) + 1
    esperado = (2.0 * m - 1.0) / 3.0
    var = (16.0 * m - 29.0) / 90.0
    z = (r - esperado) / np.sqrt(var)
    from scipy.stats import norm

    return {"rachas": r, "esperado": esperado, "z": float(z),
            "p": float(2 * norm.sf(abs(z)))}


def prueba_hueco(u: np.ndarray, alfa: float = 0.0, beta: float = 0.5,
                 max_hueco: int = 10) -> dict:
    """Prueba del hueco sobre el intervalo (alfa, beta).

    Cuántos valores pasan entre dos caídas consecutivas dentro del intervalo.
    Con independencia la longitud es geométrica de parámetro p = beta − alfa;
    se contrasta con chi-cuadrado agrupando los huecos ≥ max_hueco.
    """
    from scipy.stats import chisquare

    u = np.asarray(u)
    p = beta - alfa
    dentro = np.flatnonzero((u >= alfa) & (u < beta))
    if dentro.size < 2:
        raise ValueError("muy pocas caídas dentro del intervalo")
    huecos = np.diff(dentro) - 1
    obs = np.array([np.count_nonzero(huecos == k) for k in range(max_hueco)]
                   + [np.count_nonzero(huecos >= max_hueco)], dtype=float)
    prob = np.array([p * (1 - p) ** k for k in range(max_hueco)]
                    + [(1 - p) ** max_hueco])
    esp = obs.sum() * prob / prob.sum()
    est, pv = chisquare(obs, esp)
    return {"huecos": int(huecos.size), "chi2": float(est), "p": float(pv),
            "gl": int(obs.size - 1)}


def autocorrelacion(u: np.ndarray, rezagos: int = 20) -> dict:
    """Autocorrelación serial a los rezagos 1..`rezagos`.

    Cada r_k es aproximadamente N(0, 1/n), así que la banda del 95 % es
    ±1.96/√n.
    """
    u = np.asarray(u, dtype=float)
    n = u.size
    x = u - u.mean()
    den = float(x @ x)
    r = np.array([float(x[:-k] @ x[k:]) / den for k in range(1, rezagos + 1)])
    banda = 1.96 / np.sqrt(n)
    return {"r": r, "banda95": float(banda), "fuera": int(np.sum(np.abs(r) > banda))}


def razon_cola(z: np.ndarray, sigmas: float = 3.0) -> dict:
    """Criterio 4 de §7: frecuencia empírica contra la teórica más allá de kσ.

    Importa porque Δ%₉₅ es una métrica de cola y el KS es sensible al centro
    de la distribución, no a sus extremos.
    """
    from scipy.stats import norm

    z = np.asarray(z)
    emp = float(np.count_nonzero(np.abs(z) > sigmas)) / z.size
    teo = float(2 * norm.sf(sigmas))
    return {"sigmas": sigmas, "empirica": emp, "teorica": teo,
            "razon": emp / teo if teo else float("nan"),
            "casos": int(np.count_nonzero(np.abs(z) > sigmas))}


def lineas_de_codigo(objeto) -> int:
    """Líneas efectivas de una función, sin blancos, comentarios ni
    documentación (criterio 6 de §7)."""
    import inspect

    fuente_txt = inspect.getsource(objeto)
    lineas, en_doc, delim = [], False, None
    for cruda in fuente_txt.splitlines():
        s = cruda.strip()
        if not s or s.startswith("#"):
            continue
        if en_doc:
            if delim in s:
                en_doc = False
            continue
        if s.startswith(('"""', "'''")):
            delim = s[:3]
            if not (s.endswith(delim) and len(s) > 5):
                en_doc = True
            continue
        lineas.append(s)
    return len(lineas)
