# Estructura del proyecto

**CC2017 — Modelación y Simulación · Ciclo 2, 2026 · Universidad del Valle de Guatemala**

Simulación del impacto del cierre de una vía principal sobre el tráfico de las
zonas 10, 15 y 16 de la Ciudad de Guatemala.

Este documento es la referencia única del proyecto. Define qué se modela, con
qué distribuciones, con qué métodos de generación, cómo se compara y quién hace
qué. Si algo se decide en una conversación y no queda escrito aquí, no está
decidido.

---

## 1. El proyecto en un párrafo

Se simula el tráfico vehicular de un área acotada de la Ciudad de Guatemala y se
mide **cuánto empeora** cuando se cierra una vía principal. La red vial real se
obtiene de OpenStreetMap y se enruta con una instancia local de OSRM; los
cierres se implementan poniendo a cero la velocidad de los segmentos de la calle
cerrada. La aleatoriedad — llegadas de vehículos, elección de origen y destino,
velocidad de cada conductor, demoras en intersecciones — se genera con los
métodos vistos en el curso, y el proyecto **compara tres pares de métodos de
generación** bajo criterios propios. El resultado se reporta como **cambio
porcentual** respecto al escenario sin cierre, nunca como minutos absolutos.

---

## 2. Por qué porcentajes y no minutos

Es la decisión metodológica más importante del proyecto y hay que poder
defenderla en la presentación.

OSRM devuelve tiempos de **flujo libre**: asume que cada vía se recorre a la
velocidad que su clasificación permite, sin semáforos, sin cola, sin hora pico.
Un tiempo OSRM de 14 minutos entre la UVG y la Zona Viva no es una predicción
del tiempo real de viaje a las 5 de la tarde, y presentarlo como tal sería
falso. Calibrar tiempos absolutos exigiría datos de aforo vehicular y de
tiempos de recorrido observados que no tenemos.

Lo que sí es defendible es el **cociente**. Al comparar el mismo modelo consigo
mismo bajo dos configuraciones de red — abierta y cerrada — los sesgos comunes
al numerador y al denominador se cancelan:

$$\Delta\% \;=\; \frac{T_{\text{cerrado}} - T_{\text{abierto}}}{T_{\text{abierto}}}\times 100$$

Si el modelo subestima uniformemente el tiempo real por un factor $k$, ese $k$
desaparece del cociente. La afirmación del proyecto no es *"el viaje toma 23
minutos"* sino *"cerrar el Boulevard Vista Hermosa encarece el viaje promedio
en un 34 %"*, que es una afirmación mucho más robusta y, para la pregunta de
planificación urbana que interesa, mucho más útil.

**Consecuencia de diseño:** toda cantidad reportada es un cociente, un cambio
relativo o una probabilidad. Ninguna tabla de resultados lleva minutos como
conclusión; los minutos aparecen solo como insumo intermedio.

---

## 3. Descripción del sistema *(rúbrica: 5 pts)*

### 3.1 Frontera

| Elemento | Definición |
|---|---|
| Área | Zonas 10, 15 y 16 de la Ciudad de Guatemala |
| Caja delimitadora | `(14.575, -90.530, 14.630, -90.455)` — (sur, oeste, norte, este) |
| Entidades | Vehículos particulares que hacen un viaje origen→destino dentro del área |
| Horizonte | Una hora pico de la tarde, 16:00–19:00 (3 h simuladas) |
| Recurso escaso | Capacidad de cada segmento vial |
| Evento externo | Cierre total de una vía principal |

La caja encierra **5 512 ways y 744.9 km** de vía conducible, de los cuales
97.2 km son estructurantes (`trunk` + `primary`). Medido en el notebook 01.

Quedan **fuera** del modelo: transporte público, motocicletas con
comportamiento de filtrado entre carriles, peatones, estacionamiento en vía,
y todo viaje con un extremo fuera de la caja. Son simplificaciones conscientes
y hay que enunciarlas en el informe, no esconderlas.

### 3.2 Las tres zonas

| Zona | Carácter | Centro (lat, lon) | Peso como destino |
|---|---|---|---|
| 10 | Zona Viva / Oakland — comercio y oficinas | 14.5990, −90.5120 | 0.40 |
| 15 | Vista Hermosa — residencial + UVG | 14.6047, −90.4896 | 0.35 |
| 16 | Cayalá / Landívar — comercio nuevo + universidad | 14.6084, −90.4865 | 0.25 |

Los pesos son un supuesto declarado: la zona 10 concentra la mayor atracción de
viajes en la tarde. Su efecto se examina en el análisis de sensibilidad (§9.3).

### 3.3 Los dos escenarios de cierre

Ambos verificados contra Overpass; los nombres son literalmente los de la
etiqueta `name` de OpenStreetMap.

| Escenario | Nombre OSM | Ways | km | Nodos únicos | Segmentos dirigidos | Clase |
|---|---|---|---|---|---|---|
| Crítico | `Boulevard Vista Hermosa` | 23 | 8.68 | 206 | 408 | `primary`, `oneway=yes` |
| Redundante | `Avenida Reforma` | 36 | 4.60 | 84 | 162 | `primary`/`tertiary`, `oneway=yes` |

Medido con el notebook 01. Los *nodos únicos* son los que forman el conjunto
contra el que se verifica el cierre (§12.1); los *segmentos dirigidos* son las
líneas del CSV que consume `osrm-customize`.

**Contexto que salió de la validación:** el rodeo mediano entre los puntos
ancla es de **2.6×** la línea recta, y el peor par (UVG → Los Próceres) es de
**4.0×** — 2.36 km en línea recta contra 9.46 km por calle. No es un defecto de
la red: son los barrancos que separan la zona 15 de la zona 10 y obligan a pasar
por unos pocos cruces. La red ya opera con muy poca holgura, que es precisamente
la condición bajo la cual un cierre duele.

**El contraste entre los dos es el hallazgo central del proyecto**, no un
detalle. Vista Hermosa es la espina de la zona 15, encajonada entre barrancos y
con pocas paralelas: cerrarla obliga a rodeos largos. La Avenida Reforma corre
dentro de una retícula densa y **conserva sus carriles auxiliares**, que en OSM
llevan otro nombre (`Carril Auxiliar Avenida Reforma`) y por eso el escenario
deliberadamente **no** los cierra. Se espera que el mismo método produzca un
Δ% grande en un caso y pequeño en el otro. Eso convierte el proyecto de
*"cerrar una calle es malo"* en *"aquí está la medida de qué tan crítico es
cada eslabón de la red"*, que es un resultado con contenido.

Ambas vías están mapeadas como calzadas separadas por sentido (`oneway=yes`),
así que "cerrar la calle" significa cerrar los ways de los dos sentidos. La
selección por nombre ya los captura todos.

---

## 4. Fuentes de aleatoriedad *(rúbrica: Modelo, 5 pts)*

El enunciado exige que la generación aleatoria esté fundamentada. Cada fila de
esta tabla debe poder justificarse en la defensa.

| # | Fuente | Variable | Distribución | Método de generación | Justificación |
|---|---|---|---|---|---|
| A | Llegadas de vehículos a la red | Tiempos entre llegadas | Exponencial → **proceso de Poisson no homogéneo** | Transformada inversa + **adelgazamiento (thinning)** | Llegadas independientes de muchos conductores que deciden por separado: el límite natural es Poisson. La intensidad no es constante — hay un pico de salida de oficinas — así que se usa $\lambda(t)$ variable, exactamente el ejercicio 7 de la Práctica 2 |
| B | Zona de origen y de destino | Par (O, D) discreto | Categórica sobre 3×3 zonas | Transformada inversa discreta sobre la acumulada | Es una elección entre pocas categorías con probabilidades dadas; la inversa discreta cuesta un uniforme y es exacta |
| C | Punto exacto dentro de la zona | Coordenada (lat, lon) | Uniforme sobre la zona, anclada a la vía más cercana | Uniforme + `nearest` de OSRM | Sin datos de manzana, la uniforme es el supuesto de máxima entropía; el anclaje evita orígenes en un techo |
| D | Velocidad relativa del conductor | Multiplicador $s$ sobre la velocidad de flujo libre | **Lognormal** $(\mu,\sigma)$, mediana 1.0 | **Polar (Marsaglia)** vs. **aceptación-rechazo con envolvente exponencial** | Positiva por construcción y asimétrica a la derecha: hay conductores mucho más lentos que el promedio, pero nadie va al triple. Se obtiene exponenciando una normal, y la normal es justo donde el curso ofrece dos métodos competidores |
| E | Demora en intersección semaforizada | Segundos de espera | **Erlang(k=2)** = suma de dos exponenciales | Convolución de inversas | Espera de semáforo más despeje de cola: dos etapas secuenciales. La Erlang tiene menos masa cerca de cero que la exponencial, que es el comportamiento correcto — casi nunca se cruza un semáforo con demora exactamente nula |
| F | Capacidad efectiva del segmento | Vehículos/hora | Normal truncada alrededor del nominal por carril | Polar + truncamiento por rechazo | Recoge la variabilidad no modelada: un bus detenido, una entrega en doble fila |

Las fuentes A y B son las que el enunciado señala explícitamente
(*"se espera el uso de un proceso de Poisson o generación de tiempos entre
llegadas vía distribución exponencial"*). Las demás son las que hacen que la
simulación tenga algo que decir.

---

## 5. Modelo *(rúbrica: 5 pts)*

### 5.1 Llegadas: proceso de Poisson no homogéneo

La intensidad de la hora pico se modela con una función suave con máximo cerca
de las 17:30:

$$\lambda(t) \;=\; \lambda_{\min} \;+\; (\lambda_{\max}-\lambda_{\min})\,
\exp\!\left(-\frac{(t-t_{\text{pico}})^2}{2\tau^2}\right)$$

con $t$ en horas desde las 16:00. Se genera por **adelgazamiento**: se simula un
Poisson homogéneo de tasa $\lambda^\* = \max_t \lambda(t)$ y se conserva cada
llegada con probabilidad $\lambda(t)/\lambda^\*$. La eficiencia del
adelgazamiento — fracción de candidatos aceptados — es una de las cantidades
que se reportan.

### 5.2 Elección de origen y destino

$P(O=i, D=j) = p_i^{\text{orig}} \cdot p_j^{\text{dest}}$ con la restricción
$i \neq j$ renormalizada, más una fracción de viajes intrazonales. Se sortea con
inversa discreta sobre la acumulada aplanada de las 9 celdas.

### 5.3 Tiempo de viaje: OSRM más congestión

OSRM entrega, por ruta, la lista de segmentos con su distancia $d_a$ y su
duración de flujo libre $t^0_a$. Sobre eso se monta una función de demora
dependiente del flujo (BPR, la estándar en ingeniería de transporte):

$$t_a(v_a) \;=\; \frac{t^0_a}{s}\left[1 + \alpha\left(\frac{v_a}{c_a}\right)^{\beta}\right]$$

- $v_a$: vehículos que usaron el segmento $a$ en la ventana de tiempo (lo cuenta la simulación)
- $c_a$: capacidad del segmento (fuente F)
- $s$: multiplicador del conductor (fuente D)
- $\alpha = 0.15$, $\beta = 4$: valores clásicos del *Bureau of Public Roads*

A esto se suma la demora en intersecciones (fuente E) por cada nodo
semaforizado de la ruta.

El tiempo total de un vehículo es $T = \sum_{a \in \text{ruta}} t_a(v_a) + \sum_{\text{int}} D_{\text{int}}$.

### 5.4 Realimentación de congestión

Los flujos $v_a$ dependen de las rutas, y las rutas dependen de los tiempos, que
dependen de los flujos. Se resuelve con **iteración de promedios sucesivos**:
se corre la asignación, se promedian los flujos con los de la iteración previa
con peso $1/k$, y se repite hasta que el cambio relativo de flujos baje del 1 %
o se agoten 10 iteraciones. No es un equilibrio de Wardrop exacto y no hay que
afirmar que lo sea; es una aproximación razonable y se declara como tal.

### 5.5 La métrica

Por escenario se estima:

| Símbolo | Cantidad | Por qué |
|---|---|---|
| $\Delta\%_{\text{med}}$ | Cambio en el tiempo **mediano** de viaje | Resumen robusto, poco sensible a la cola |
| $\Delta\%_{95}$ | Cambio en el percentil 95 | El viaje que arruina el día; suele moverse mucho más que la mediana |
| $\Delta\%_{\text{red}}$ | Cambio en la demora total de la red $\sum_i T_i$ | Costo social agregado |
| $P_{\text{sin ruta}}$ | Fracción de pares O-D que quedan desconectados | Si el cierre aísla algo, hay que decirlo, no promediarlo |
| $\Delta\%_{ij}$ | Matriz de cambio por par de zonas | Donde se ve la asimetría: no todos sufren igual |

`OSRM` devolviendo `NoRoute` **no es un error del programa**: es un resultado
del experimento y alimenta $P_{\text{sin ruta}}$.

### 5.6 Números aleatorios comunes

Los escenarios abierto y cerrado se corren con **la misma semilla y la misma
secuencia de vehículos**: mismos tiempos de llegada, mismos pares O-D, mismos
multiplicadores de conductor. Lo único que cambia es la red.

Esto convierte la comparación en **pareada**, y la varianza de la diferencia cae
de $\operatorname{Var}(A)+\operatorname{Var}(B)$ a
$\operatorname{Var}(A)+\operatorname{Var}(B)-2\operatorname{Cov}(A,B)$. Como la
covarianza es fuertemente positiva — es el mismo tráfico en casi la misma red —
el intervalo de confianza del Δ% se estrecha muchísimo con el mismo número de
corridas. Es reducción de varianza gratis y hay que reportar cuánto se ganó
(comparar el ancho del IC pareado contra el no pareado).

El IC del Δ% se obtiene por **bootstrap** sobre las diferencias pareadas,
porque el cociente de dos medias no tiene una fórmula cerrada cómoda.

---

## 6. Arquitectura técnica

### 6.1 Por qué OSRM local y no el servidor público

El servidor demo `router.project-osrm.org` **rechaza el parámetro `exclude`**
(verificado: devuelve `{"code":"InvalidValue","message":"Exclude flag
combination is not supported."}`). No hay forma de cerrar una calle contra él.
Las alternativas de "pedir rutas alternativas y descartar las que pasan por la
calle" son metodológicamente pobres: OSRM suele devolver una sola alternativa, y
el desvío verdadero casi nunca está entre ellas.

Con una instancia local se cierra la calle **en el grafo**, y OSRM recalcula el
óptimo real sobre la red mutilada. Es la diferencia entre medir el desvío y
adivinarlo.

### 6.2 El truco que hace esto barato

El pipeline MLD de OSRM separa la compilación del grafo de la asignación de
velocidades:

```
osrm-extract    (minutos)  ─┐
osrm-partition  (minutos)   ├── una sola vez, nunca se repite
osrm-customize  (segundos) ─┘ ← SOLO esto se repite por escenario
```

`osrm-customize --segment-speed-file cierre.csv` acepta un CSV de
`nodo_origen,nodo_destino,velocidad_kmh`. Poniendo `0` en los segmentos de la
calle, quedan intransitables. Cambiar de escenario cuesta **segundos**, no
minutos, y por eso el proyecto puede permitirse decenas de escenarios y un
análisis de sensibilidad en vez de dos corridas.

El CSV se genera desde Overpass: se piden los ways con el `name` exacto, se
toman sus nodos consecutivos y se escriben los pares en ambos sentidos.

### 6.3 Datos

| Recurso | Tamaño | Origen |
|---|---|---|
| `guatemala-latest.osm.pbf` | 131 MB | Geofabrik (verificado) |
| Grafo OSRM compilado | 519 MB | generado localmente (medido) |
| CSV de cierre | pocos KB | Overpass |

Los dos primeros están en `.gitignore` y se regeneran con el notebook 01. Al
repositorio solo van los derivados pequeños (`data/derivados/`).

---

## 7. Métodos de generación y su comparación *(rúbrica: Método de simulaciones, 5 pts)*

El enunciado pide **al menos dos** métodos comparados con criterio propio y
justificado. Se comparan **tres pares**, cada uno respondiendo una pregunta
distinta.

### Par 1 — Normales: polar (Marsaglia) vs. aceptación-rechazo exponencial

Es el par principal, porque alimenta la fuente D, que es la que más vehículos
toca.

- **Polar:** se sortean $V_1,V_2$ uniformes en $[-1,1]$ hasta caer dentro del
  círculo unitario ($S=V_1^2+V_2^2\le 1$, se acepta con probabilidad
  $\pi/4 \approx 0.785$) y se devuelven dos normales
  $V_i\sqrt{-2\ln S / S}$. Sin senos ni cosenos.
- **Rechazo con envolvente exponencial** (Ejemplo 5f de Ross, ejercicio 5 de la
  Práctica 2): genera $|Z|$ con envolvente $g(x)=e^{-x}$ y constante
  $c=\sqrt{2e/\pi}\approx 1.3155$, tasa de aceptación $1/c \approx 0.760$.

### Par 2 — Poisson: transformada inversa de exponenciales vs. condicionamiento en $N(T)$

- **A:** acumular $-\ln(U)/\lambda$ hasta pasar $T$.
- **B:** sortear $N \sim \text{Poisson}(\lambda T)$ y colocar $N$ uniformes
  ordenadas en $[0,T]$.

Ambos son exactos y la comparación es de costo y de conveniencia — B necesita
conocer $T$ de antemano, A sirve en línea.

### Par 3 — La fuente de uniformes: LCG propio vs. PCG64 de NumPy

- **LCG propio:** $x_{n+1} = (a x_n + c) \bmod m$ con los parámetros de
  *Numerical Recipes* ($a=1664525$, $c=1013904223$, $m=2^{32}$).
- **RANDU** ($a=65539$, $c=0$, $m=2^{31}$) como control negativo deliberado.
- **PCG64**, el generador por defecto de NumPy.

RANDU está ahí a propósito: sus tripletas consecutivas caen en 15 planos en el
cubo unitario, y graficarlas produce la figura más contundente de toda la
presentación. Es la demostración visual de por qué la validación de un
generador no es un trámite.

### Criterios de comparación

Cada criterio va acompañado de números o gráficas, nunca de una afirmación
suelta.

| # | Criterio | Cómo se mide |
|---|---|---|
| 1 | **Costo computacional** | Nanosegundos por variable generada, `timeit` con ≥ 10⁶ variables, 7 repeticiones, se reporta la mediana |
| 2 | **Eficiencia del rechazo** | Uniformes consumidos por variable aceptada; se contrasta contra el valor teórico ($4/\pi$ para el polar, $c=\sqrt{2e/\pi}$ para el rechazo) |
| 3 | **Calidad estadística** | Kolmogórov–Smirnov y chi-cuadrado contra la distribución objetivo; QQ-plots; para las uniformes además prueba de rachas, prueba del hueco y autocorrelación serial |
| 4 | **Comportamiento en la cola** | Cociente entre la frecuencia empírica y la teórica más allá de $3\sigma$ — importa porque $\Delta\%_{95}$ es una métrica de cola y un generador que falla ahí sesga justo el resultado que interesa |
| 5 | **Impacto sobre la conclusión** | **El criterio propio del proyecto.** Se corre la simulación completa con cada generador y se comprueba si el Δ% estimado cambia más allá del error Monte Carlo |
| 6 | **Facilidad de implementación** | Líneas de código, dependencias, y cuántos casos borde hay que cuidar |

El criterio 5 es el que hay que subrayar en la defensa. Los criterios 1–4 miden
el generador; el 5 mide **si la elección del generador importa para la pregunta
que el proyecto quiere responder**. El resultado esperado es que polar y rechazo
den el mismo Δ% dentro del error — y demostrarlo tiene más valor que
asumirlo. El resultado interesante es que **RANDU sí lo mueva**: eso cierra el
argumento de por qué se valida.

### Resultados medidos *(notebook 03, ya ejecutado)*

Criterios 1, 2, 4 y 6. El 3 lo cubre §8 y el 5 depende del notebook 04.

| Par | Medición | Resultado |
|---|---|---|
| 1 | Costo por normal (PCG64) | polar 59.6 ns · rechazo 68.2 ns |
| 1 | Uniformes por normal | polar 1.2757 (teoría 1.2732) · rechazo 3.6362 (teoría 3.6310) |
| 1 | Cola a 3σ, razón empírica/teórica | polar 0.990 · rechazo 0.972 |
| 1 | Líneas de código | polar 20 · rechazo 19 |
| 2 | Distribución de *N(T)* | KS de dos muestras p = 0.90: los dos coinciden |
| 3 | Costo por uniforme | PCG64 3.3 ns · LCG propio 12.6 ns · RANDU 11.9 ns |

Los tiempos son de la máquina donde se corrió el notebook y cambian entre
corridas; el consumo de uniformes no, porque es propiedad del algoritmo.

Los dos métodos del par 1 son exactos y no se distinguen en calidad, así que la
elección se puede hacer por costo. El polar gana en las dos cosas medidas —más
rápido y 2.85× menos uniformes— y es el que usa el proyecto; el rechazo queda
documentado como competidor.

RANDU, por su parte, pasó las cinco pruebas de §8 y está roto igual: sus
tripletas caen sobre 15 planos, verificado con aritmética entera. Es el
argumento de por qué §8 existe, y está en la figura 5.

### Parámetros que la pista B fijó

Estaban sin definir y ahora viven en `src/config.py`:

| Parámetro | Valor | Criterio |
|---|---|---|
| σ de la lognormal (fuente D) | 0.20 | el 90 % central conduce entre 0.72× y 1.39× |
| Media de la Erlang(k=2) (fuente E) | 30 s | demora típica de semáforo urbano |
| λ_min, λ_max | 800, 2 300 veh/h | dan 5 091.6 vehículos por réplica (el «~5 000» de §9.1) |
| t_pico, τ | 1.5 h (17:30), 0.75 h | pico de salida de oficinas |

La eficiencia del adelgazamiento sale 0.7379 teórica contra 0.7380 medida sobre
400 réplicas, que es lo que §5.1 pide reportar.

---

## 8. Validación estadística

| Objeto | Pruebas |
|---|---|
| Uniformes del LCG | KS contra U(0,1); chi-cuadrado con 100 clases; rachas; hueco; autocorrelación a rezagos 1–20; dispersión 3-D de tripletas |
| Normales | KS; Shapiro–Wilk sobre submuestras; QQ-plot; contraste de momentos 1–4 |
| Exponenciales | KS; media y varianza contra $1/\lambda$ y $1/\lambda^2$ |
| Proceso de Poisson | $N(T)\sim\text{Poisson}(\lambda T)$ por chi-cuadrado; tiempos entre eventos exponenciales por KS; para el NHPP, conteos por intervalo contra $\int\lambda(t)dt$ |
| Simulación completa | Convergencia del estimador con $n$; ancho del IC; el IC pareado contra el no pareado |

Toda prueba se reporta con su estadístico y su valor $p$. Un valor $p$ alto no
"prueba" que el generador es bueno y no hay que escribir eso; lo que se dice es
que no hay evidencia para rechazarlo al nivel elegido.

---

## 9. Experimentos

### 9.0 Resultado preliminar ya validado

El notebook 02 corrió los tres escenarios contra el OSRM local y las tres
verificaciones de §12 pasaron. Estos son tiempos de **flujo libre sobre 552
pares origen-destino**, sin tráfico todavía: es el desvío puramente geométrico
que impone la red, y por lo tanto el **piso** del efecto.

| Escenario | Δ% mediana | Δ% p95 | Δ% red total | Pares sin ruta |
|---|---|---|---|---|
| Boulevard Vista Hermosa | **+16.97 %** | **+36.31 %** | **+31.61 %** | 0 % |
| Avenida Reforma | **0.00 %** | +0.71 % | +0.74 % | 0 % |

**La hipótesis del §3.3 se confirma con un margen enorme: 17 % contra 0 %.** La
misma metodología, aplicada a dos vías `primary` de porte parecido, distingue
un eslabón crítico de uno redundante. La Reforma no mueve la mediana ni un
punto porque sus carriles auxiliares —4.2 km que el escenario deja abiertos a
propósito— absorben el tráfico a media cuadra de distancia.

Δ% de la mediana por par de zonas, cierre de Vista Hermosa:

| origen \ destino | z10 | z15 | z16 |
|---|---|---|---|
| **z10** | 0.0 | **+69.8** | **+43.2** |
| **z15** | +36.2 | 0.0 | 0.0 |
| **z16** | +22.8 | 0.0 | 0.0 |

Dos cosas que hay que explotar en el análisis:

1. **El daño es direccional.** z10 → z15 sufre +69.8 % y el sentido contrario
   solo +36.2 %. Las calzadas están mapeadas por separado y las alternativas no
   son simétricas. Un promedio sobre toda la red escondería esto por completo.
2. **Los viajes intrazonales no se enteran.** Todos los pares dentro de una
   misma zona quedan en 0.0 %. El cierre no degrada la movilidad local: rompe
   la conexión *entre* zonas, que es una conclusión mucho más específica que
   "aumenta el tráfico".

Con congestión el efecto debe crecer, y no en proporción: la BPR tiene
exponente 4, así que un desvío que además satura la ruta alterna se paga mucho
más caro que en flujo libre. **Contrastar el Δ% final del notebook 04 contra
este piso es uno de los resultados del proyecto**, porque separa cuánto del daño
es geometría y cuánto es congestión.

### 9.1 Corridas principales

| Escenario | Réplicas | Vehículos/réplica | Salida |
|---|---|---|---|
| Base (sin cierre) | 30 | ~5 000 | Distribución de referencia |
| Cierre Vista Hermosa | 30 | ~5 000 | Δ% vs. base, pareado |
| Cierre Avenida Reforma | 30 | ~5 000 | Δ% vs. base, pareado |

Las 30 réplicas usan semillas `SEMILLA + r`, y la réplica $r$ del escenario
cerrado usa la misma semilla que la réplica $r$ del base (§5.6).

### 9.2 Cruce de generadores

La corrida de Vista Hermosa se repite con polar, con rechazo y con RANDU como
fuente de uniformes: alimenta el criterio 5 de §7.

### 9.3 Sensibilidad

| Parámetro | Barrido | Pregunta |
|---|---|---|
| $\lambda_{\max}$ | ×0.5, ×1, ×1.5, ×2 | ¿El Δ% crece con la demanda? Debería, y de forma no lineal por la $\beta=4$ de la BPR |
| Velocidad del cierre | 0, 5, 15 km/h | Cierre total vs. carril reducido vs. paso restringido |
| Pesos de destino | ±20 % | ¿Cambia la conclusión si la zona 10 atrae menos? |
| $\alpha,\beta$ de la BPR | valores alternos | ¿Cuánto del resultado lo pone la función de demora? |

---

## 10. Estructura de archivos

```
proyecto/
├── README.md                       cómo correrlo
├── estructura-proyecto.md          este documento
├── requirements.txt
├── src/
│   ├── config.py                   zonas, escenarios, semilla, paleta   [listo]
│   ├── osrm.py                     cliente OSRM                          [listo]
│   ├── red.py                      Overpass y archivos de cierre         [listo]
│   ├── generadores.py              métodos de generación                 [listo]
│   └── simulacion.py               motor de simulación                [pista C]
├── notebooks/
│   ├── 01_red_y_osrm.ipynb         red, servidor, validación             [listo]
│   ├── 02_linea_base_y_cierres.ipynb  rutas base y cierres               [listo]
│   ├── 03_generadores.ipynb        generación y validación               [listo]
│   ├── 04_simulacion.ipynb         corridas y Δ%                      [pista C]
│   └── 05_analisis_y_figuras.ipynb resultados y figuras              [pista C]
├── osrm/
│   ├── construir.sh                pipeline MLD, una sola vez
│   ├── cerrar.sh                   aplica un escenario
│   └── docker-compose.yml
├── data/
│   ├── osm/                        pbf y grafo         [ignorado por git]
│   └── derivados/                  csv y json chicos       [sí van al repo]
└── figuras/                        salidas para el informe
```

**Regla de oro:** ninguna coordenada, semilla ni parámetro se escribe dos veces.
Todo vive en `src/config.py` y los notebooks lo importan. Un número duplicado es
un número que tarde o temprano deja de coincidir con su copia.

---

## 11. División del trabajo — 3 personas

Las tres pistas están diseñadas para correr **en paralelo** desde el primer
momento. La pista B no necesita que OSRM esté levantado y la pista C puede
desarrollarse contra rutas de prueba.

### Pista A — Red y escenarios
`src/config.py`, `src/osrm.py`, `src/red.py`, `notebooks/01`, `notebooks/02`, `osrm/`

- Levantar OSRM local y dejar documentado el procedimiento
- Extraer la red del área y validarla contra el servidor público
- Construir los CSV de cierre y **verificar que efectivamente cierran** (§12)
- Entregar a las otras pistas una función estable `ruta(origen, destino) → {distancia, duración, nodos}`

### Pista B — Generación de variables aleatorias
`src/generadores.py`, `notebooks/03`

- LCG propio, RANDU y el envoltorio sobre PCG64
- Polar y rechazo exponencial para normales; lognormal por exponenciación
- Exponencial, Erlang, Poisson homogéneo y NHPP por adelgazamiento
- Toda la batería de validación de §8
- El banco de tiempos de §7, criterios 1–4

### Pista C — Simulación y análisis
`src/simulacion.py`, `notebooks/04`, `notebooks/05`

- Motor: generar vehículos, asignar rutas, contar flujos, aplicar BPR, iterar
- Números aleatorios comunes entre escenarios
- Estimadores, bootstrap, intervalos de confianza
- Todas las figuras y el criterio 5 de §7

### Interfaces entre pistas — acordar antes de escribir código

```python
# A entrega a C
ruta(origen, destino) -> {"distancia_m": float, "duracion_s": float, "nodos": list[int]} | None

# B entrega a C
class Generador:
    def uniformes(self, n) -> np.ndarray
    def exponenciales(self, n, lam) -> np.ndarray
    def normales(self, n, metodo="polar") -> np.ndarray
    def lognormales(self, n, mu, sigma) -> np.ndarray
    def erlang(self, n, k, lam) -> np.ndarray
    def poisson_nh(self, T, lam_func, lam_max) -> np.ndarray
```

Si una interfaz cambia, se avisa al grupo antes de hacer *push*. Es la única
regla de proceso que importa.

### Cronograma comprimido

| Bloque | A | B | C |
|---|---|---|---|
| 1 | Descargar pbf, construir grafo, levantar servidor | LCG, uniformes, validación | Esqueleto del motor con rutas de prueba |
| 2 | CSV de cierre y verificación | Normales por ambos métodos | Asignación de flujos y BPR |
| 3 | Matrices O-D de los tres escenarios | Exponencial, Erlang, NHPP | Réplicas con números comunes |
| 4 | — | Banco de tiempos y pruebas | Δ%, bootstrap, sensibilidad |
| 5 | Revisión conjunta | Revisión conjunta | Figuras e informe |

**Mínimo viable** si el tiempo aprieta: escenario de Vista Hermosa solamente,
par de generadores 1 y 3, sin realimentación de congestión (BPR de una sola
pasada), 10 réplicas. Eso ya satisface el enunciado completo. **Lo primero que
se recorta** es el análisis de sensibilidad de §9.3; **lo último** es la
validación estadística de §8, que es donde está la mitad de la nota.

---

## 12. Cómo se comprueba que un cierre realmente cerró

Es el punto donde un proyecto así falla en silencio: el CSV se escribe, OSRM lo
acepta, y las rutas no cambian porque los IDs de nodo no correspondían. Tres
verificaciones obligatorias antes de creerle a cualquier Δ%:

1. **Segmentos ausentes.** Ninguna ruta del escenario cerrado debe **recorrer**
   un segmento de la calle cerrada, donde "segmento" es un par de nodos
   consecutivos.

   > **Por nodo NO sirve, y este es el error fácil de cometer.** Una ruta puede
   > compartir un nodo con la calle cerrada sin circular por ella: ese nodo es
   > una intersección, y el tráfico transversal la cruza con todo derecho.
   > Medido en la Avenida Reforma: **7 de 60 rutas comparten nodos** con la
   > avenida cerrada y **ninguna recorre un segmento suyo**. Verificar por nodo
   > daría siete falsos positivos y mandaría al grupo a buscar un error que no
   > existe. La comprobación vive en `red.recorre_cerrados`.
2. **El tiempo sube o no hay ruta.** Para todo par O-D,
   $T_{\text{cerrado}} \ge T_{\text{abierto}}$. Cerrar calles nunca acelera un
   viaje. Un solo par que baje significa que algo está mal.
3. **Cambia lo que tiene que cambiar.** Los pares O-D cuya ruta base no
   circulaba por la calle cerrada deben conservar exactamente el mismo tiempo. Si cambian,
   el CSV está cerrando de más.

Estas tres van como aserciones en el notebook 02 y se vuelven a correr cada vez
que se agrega un escenario.

---

## 13. Entregables y mapeo a la rúbrica

| Componente | Pts | Dónde se sustenta |
|---|---|---|
| Descripción del sistema | 5 | §3 del informe, notebook 01 con el mapa del área |
| Modelo utilizado | 5 | §4 y §5: tabla de fuentes con su justificación |
| Método de simulaciones | 5 | §7: tres pares comparados, seis criterios |
| Objetivos | 5 | §2 y §5.5: por qué Δ% y qué se estima |
| Resultados obtenidos | 5 | §9, notebook 05 |
| Análisis de resultados | 5 | Contraste crítico/redundante, sensibilidad, criterio 5 |
| Representación visual | 5 | §14 |
| Soporte multimedia | 5 | Mapa interactivo con el antes y el después |
| Presentación oral | 5 | Ensayada, con tiempos por sección |
| Presentación visual | 5 | Paleta consistente, figuras vectoriales |

**Requisito de aprobación:** la simulación tiene que correr el día de la
presentación. Concretamente: el grafo OSRM ya construido en la máquina que se
lleva, el contenedor levantado y probado **antes** de salir, y un notebook de
respaldo con todos los resultados ya ejecutados por si la red o Docker fallan.
No se depende de internet durante la defensa.

---

## 14. Figuras

| # | Figura | Qué muestra |
|---|---|---|
| 1 | Mapa del área con las tres zonas y las dos vías candidatas | Contexto |
| 2 | Rutas antes y después, superpuestas | El desvío, visualmente |
| 3 | Histogramas de tiempo de viaje, base vs. cierre | El desplazamiento de la distribución |
| 4 | Δ% por par de zonas (mapa de calor 3×3) | Quién sufre y quién no |
| 5 | Dispersión 3-D de tripletas de RANDU | Los 15 planos |
| 6 | QQ-plots de normales por ambos métodos | Calidad de los generadores |
| 7 | Tiempo por variable generada, por método | Criterio 1 |
| 8 | Δ% vs. demanda | No linealidad de la BPR |
| 9 | Ancho del IC pareado vs. no pareado | La ganancia de los números comunes |
| 10 | Mapa interactivo con selector de escenario | Demostración en vivo |

Paleta única en todo el proyecto: `NAVY #003865`, `ORANGE #FC4C02`,
`GREY #696969`, `YELLOW #FDB92E`. Definida en `src/config.py`; nadie elige
colores por su cuenta.

---

## 15. Riesgos

| Riesgo | Señal | Plan B |
|---|---|---|
| La imagen de OSRM no corre en la máquina | `docker pull` falla | `ghcr.io/project-osrm/osrm-backend:latest` **sí trae build nativo `linux/arm64`** (verificado en Apple Silicon), así que no hace falta emular. Si aun así falla: `export PLATAFORMA="--platform linux/amd64"` |
| `osrm-extract` se queda sin memoria | El contenedor muere | Recortar el pbf al área con `osmium extract` antes de procesarlo |
| Overpass no responde | Timeout | `src/red.py` ya rota entre dos espejos; en el peor caso, cachear los ways en `data/derivados/` |
| El cierre no cambia las rutas | Falla la verificación §12.1 | Revisar que los IDs sean de nodo OSM y no de way; confirmar que se escribieron ambos sentidos |
| La simulación tarda demasiado | Las réplicas no terminan | Bajar vehículos por réplica antes que réplicas: el IC depende más del número de réplicas |
| Docker no arranca el día de la presentación | — | Notebook de respaldo con resultados ya ejecutados y salidas guardadas |
| El contenedor no puede enlazar el puerto | `address already in use` | En macOS el 5000 lo ocupa el receptor de AirPlay (`ControlCenter`). El proyecto ya usa el **5001**; si también estuviera tomado, cambiarlo en `src/config.py` y en `docker-compose.yml` a la vez |

---

## 16. Convenciones

- **Idioma:** contenido en español (notebooks, informe, comentarios); mensajes
  de *commit* en inglés, como en las prácticas anteriores del curso.
- **Commits:** `tipo: descripción corta en minúscula`, con `tipo` ∈
  `feat`, `docs`, `chore`, `fix`, `test`. Un commit por unidad de trabajo con
  sentido propio.
- **Semilla:** `SEMILLA = 20_172_026` en `src/config.py`. Ningún notebook define
  la suya.
- **Notebooks:** se entregan **ejecutados, con salidas**. Un notebook sin
  salidas es un notebook que nadie puede verificar.
- **Aserciones:** todo resultado numérico que tenga un valor de referencia se
  contrasta con `assert`. Es la costumbre de la Práctica 2 y aquí también
  aplica.
- **Entorno:** `.venv` en la raíz, dependencias en `requirements.txt`.
