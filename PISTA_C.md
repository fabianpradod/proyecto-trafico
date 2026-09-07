# Pista C: implementación, resultados y defensa

## Decisiones cerradas

- **BPR de una pasada.** OSRM elige rutas con costos estáticos del escenario;
  el motor calcula después la demora. No se presenta como asignación iterativa
  ni equilibrio de tráfico.
- **Pool finito reproducible.** Se preservan los 24 puntos del notebook 02,
  8 por zona, y sus 552 pares ordenados sin autoviajes. Cada vehículo sortea
  uniformemente dentro del pool condicionado a sus zonas O-D.
- **Metadatos coherentes.** Los 4.129 arcos utilizados y 95 nodos semaforizados
  se extraen del mismo PBF que alimenta OSRM. Esto incluye rutas fuera del BBOX.
  Hay 997 arcos sin etiqueta suficiente de carriles: se imputa un carril.
  En ways bidireccionales, `lanes` se distribuye por sentido; las etiquetas
  `lanes:forward/backward` tienen prioridad y permiten inferir el sentido faltante.
- **Conservación del tiempo base.** Se preservan las anotaciones por segmento
  y el residuo entre la duración total OSRM y su suma. Las anotaciones excluyen
  giros; el residuo no recibe BPR, pero sí el factor del conductor.
  Véase la [definición oficial de las anotaciones OSRM](https://project-osrm.org/docs/v5.24.0/api/#annotation-object).
- **Cierres independientes.** El grafo original se respalda tras construirlo;
  se restaura antes de cada escenario. No basta quitar el CSV: se observó
  persistencia de velocidades modificadas en `.geometry`, que contaminaba la base.
  Se comprobaron ausencia de segmentos cerrados, monotonía y especificidad
  sobre las 552 rutas de cada cierre, con tolerancia de redondeo de 0,2 segundos.

## Parámetros finales

Se conservan los parámetros entregados por B: horizonte 16–19 h; intensidad
mínima 800 y máxima 2.300 veh/h; pico a las 17:30 y ancho 0,75 h; lognormal
(μ=0, σ=0,20); espera Erlang(2) con media **adicional** de 30 segundos por nodo.

C agrega: ventanas de 0,25 h; 20% de viajes intrazonales; pesos de origen
(0,40; 0,35; 0,25); destinos conservan los pesos existentes. La masa interzonal
se obtiene renormalizando el producto de ambos pesos fuera de la diagonal,
y la masa intrazonal se reparte según los pesos de origen.

Capacidad nominal por carril en veh/h: motorway 2.000, trunk 1.800, primary
1.500, secondary 1.200, tertiary 1.000, residential 600, unclassified 800,
service/living_street 400. Los enlaces usan la clase madre. Se multiplica por
una normal N(1; 0,1²) truncada por rechazo a [0,5; 1,5]. Son hipótesis de
simulación, no capacidades observadas de Guatemala. α=0,15 y β=4.

El flujo se calcula como vehículos que recorren un arco por cohorte de salida,
divididos entre la duración de esa cohorte en horas. La última cohorte parcial
usa su duración real. El motor no actualiza la hora de entrada a cada segmento.

## Experimentos y estimador

Se ejecutaron 630 réplicas de escenario: siete configuraciones × 30 réplicas ×
tres escenarios. Las siete configuraciones son PCG64/polar con demanda ×0,5,
×1, ×1,5 y ×2; más PCG64/rechazo, LCG/polar y RANDU/polar a demanda ×1.

La corrida principal contiene **152.727 vehículos** reutilizados entre los
escenarios (4.956–5.357 por réplica, media 5.090,9). La aceptación media del
adelgazamiento fue 73,87%. No hubo viajes sin ruta en las corridas ejecutadas.

Para cada réplica se calcula la estadística en los vehículos con ruta tanto en
base como en cierre. El estimador es:

`Δ% = 100 × (media de estadísticas cerradas / media de estadísticas base − 1)`.

Se aplica a mediana, p95 y suma de tiempos. La matriz 3×3 usa medianas por
réplica para cada par de zonas. Los tiempos de viajes desconectados se conservan
como NaN y P(sin ruta) usa todos los vehículos; no se les asigna tiempo cero.
El total comparado es condicional al conjunto alcanzable común.

El bootstrap usa 2.000 muestras de **réplicas completas** y percentiles 2,5 y
97,5. El pareado remuestrea los mismos índices; el no pareado utiliza índices
independientes para representar la pérdida de covarianza. Se preservan entre
escenarios llegadas, pares O-D, conductor, capacidad por arco y demora por
vehículo/nodo con índices globales estables.

## Resultados principales

| Cierre | Métrica | Δ% | IC pareado 95% | Reducción del ancho del IC |
|---|---|---:|---|---:|
| Vista Hermosa | Mediana | +55,402 | [54,964; 55,821] | 52,68% |
| Vista Hermosa | p95 | +45,424 | [44,871; 45,975] | 10,50% |
| Vista Hermosa | Tiempo total | +41,723 | [41,535; 41,919] | 85,80% |
| Reforma | Mediana | −0,678 | [−0,766; −0,588] | 83,55% |
| Reforma | p95 | +1,865 | [1,682; 2,044] | 58,94% |
| Reforma | Tiempo total | +0,0025 | [−0,0381; 0,0424] | 95,66% |

Vista Hermosa afecta sobre todo z10 → z15: **+77,7%** de cambio mediano.
Su efecto mediano pasa de +54,81% a demanda ×0,5 a +64,49% a demanda ×2.
La respuesta no se impuso como condición del motor.

Las medianas para Vista Hermosa con PCG64/polar, PCG64/rechazo, LCG/polar y
RANDU/polar son, respectivamente, +55,402%, +55,520%, +55,443% y +55,304%.
No cambia la conclusión de corredor crítico en estas corridas. El solapamiento
de IC no prueba equivalencia, y RANDU mantiene sus defectos multivariados aun
cuando no desplace materialmente este estimador.

## Qué explica el resultado

La referencia histórica +16,97% de Vista Hermosa usa 552 pares equiponderados.
El contrafactual correcto con los vehículos de C tiene +47,788% en flujo libre:
la diferencia frente a 16,97% proviene de la composición de demanda, no de BPR.

La descomposición, manteniendo los mismos vehículos, da:

| Componentes activados | Vista Hermosa: Δ mediana | Reforma: Δ mediana |
|---|---:|---:|
| OSRM | +47,788% | +0,090% |
| OSRM / velocidad | +43,770% | +0,636% |
| BPR / velocidad | +44,588% | +0,640% |
| BPR / velocidad + demora semafórica | +55,402% | −0,678% |

La diferencia entre las dos últimas filas procede de sumar las demoras
semafóricas en las rutas correspondientes. Reforma cambia de signo porque
las alternativas atraviesan una combinación distinta de nodos con espera.
Es un efecto de este modelo, no evidencia de una mejora urbana real.

## Entregables y reproducción

- `src/simulacion.py`, `src/analisis.py` y notebooks 04–05 ejecutados.
- Figuras 2, 3, 4, 8 y 9 en SVG/PNG, más figura 10 HTML sin dependencias remotas.
- `04_rutas.json.gz`: respuestas OSRM y metadatos; `04_manifiesto_rutas.json`:
  hashes del PBF, cierres, imagen OSRM y puntos usados.
- `04_replicas.csv`, `04_matrices.csv`, `04_vehiculos.npz`, `04_resultados.json`
  y `04_componentes.csv`: resultados auditables sin consultar servidores.
- Pista B conservada y reejecutada; se agregó validación de la envolvente NHPP.
- Pruebas numéricas de BPR y sus unidades, residuo OSRM, última ventana parcial,
  CRN, ausencia de ruta, distribución O-D, momentos, bootstrap y metadatos.

Las instrucciones están en [README.md](README.md). Para la defensa, abrir el
[mapa autónomo](figuras/10_mapa_interactivo.html) y el notebook 05 ya ejecutado.

## Límites e interpretación

La aproximación es sensible al pool, a los pesos, a las capacidades y a las
esperas. Los discos de muestreo no garantizan pertenencia a zonas oficiales;
OSM puede omitir semáforos o carriles. OSRM ya incluye penalizaciones de giro o
intersección: la Erlang debe defenderse como espera **adicional**. No se modela
spillback, cola dinámica, congestión que modifique rutas ni equilibrio.
Los IC no incluyen incertidumbre de parámetros ni del mapa. Un cociente puede
retener sesgos diferentes entre escenarios. El flujo libre no es una cota
inferior matemática del cambio porcentual de una distribución congestionada.

La siguiente mejora de mayor valor es calibrar demanda, capacidad y espera con
observaciones, y ampliar el pool. La sensibilidad de velocidad de cierre,
pesos y α/β del plan original queda como extensión opcional.
