# Proyecto de tráfico — zonas 10, 15 y 16

**CC2017 · Modelación y Simulación · UVG · 2026**

El proyecto mide cómo cambia la movilidad al cerrar Boulevard Vista Hermosa o
la calzada principal de Avenida Reforma. Usa la red real de OpenStreetMap,
rutas OSRM y tráfico sintético reproducible. La pista C está implementada,
ejecutada y acompañada de figuras, pruebas y resultados guardados.

## Qué hace el proyecto completo

1. **Construye la red y los escenarios.** Descarga el extracto vial de Guatemala,
   compila OSRM con Docker, ancla puntos a calles y genera archivos de cierre.
   Reforma conserva sus carriles auxiliares. Comprueba cierres mediante pares
   de nodos consecutivos, monotonía y especificidad de los tiempos.
2. **Genera y valida variables aleatorias.** PCG64, LCG propio y RANDU; normales
   por polar y rechazo exponencial; lognormal, exponencial, Erlang, categórica,
   normal truncada, Poisson homogéneo por dos métodos y NHPP por adelgazamiento.
   Incluye pruebas estadísticas, colas, tripletas, QQ y tiempos de generación.
3. **Simula tráfico.** Sortea llegadas de 16:00 a 19:00, origen/destino,
   multiplicadores de velocidad, capacidad por segmento y demora en semáforos.
   Aplica BPR una sola vez sobre las rutas de cada escenario.
4. **Compara escenarios.** Reutiliza exactamente el mismo tráfico y los mismos
   campos aleatorios entre base y cierres. Calcula cambios de mediana, p95,
   tiempo total, conectividad y matriz 3×3, con IC bootstrap por réplica.
5. **Evalúa robustez.** Contrasta cuatro combinaciones de generador y demanda
   ×0,5, ×1, ×1,5 y ×2. Compara incertidumbre pareada/no pareada y descompone
   el efecto de velocidad, BPR y esperas adicionales.
6. **Presenta resultados.** Notebooks ejecutados, figuras SVG/PNG, datos CSV/JSON/NPZ
   y un mapa interactivo autónomo con los 552 pares O-D y selector de escenario.

## Resultados ejecutados de C

PCG64 + polar, demanda ×1, 30 réplicas, media de 5.090,9 vehículos/réplica.
IC de 95% mediante 2.000 remuestreos de réplicas completas.

| Cierre | Δ mediana | IC 95% mediana | Δ p95 | Δ tiempo total | Sin ruta |
|---|---:|---:|---:|---:|---:|
| Vista Hermosa | +55,40% | [54,96%; 55,82%] | +45,42% | +41,72% | 0% |
| Reforma | −0,68% | [−0,77%; −0,59%] | +1,86% | +0,0025% | 0% |

**Vista Hermosa es el corredor más crítico bajo estos supuestos.** El pequeño
signo negativo de Reforma aparece al agregar las esperas semafóricas: sin ese
componente, BPR/velocidad da +0,64% en la mediana. No demuestra una mejora real.

El +16,97% histórico de Vista Hermosa corresponde a 552 pares equiponderados en
flujo libre. Con los mismos vehículos y pesos de C, su contrafactual de flujo
libre es +47,79%; comparar directamente 55,40% con 16,97% confunde composición
de viajes con congestión. [Resultados y decisiones metodológicas](PISTA_C.md).

## Abrir y reproducir

El [mapa interactivo](figuras/10_mapa_interactivo.html) se abre directamente en
un navegador, incluso sin conexión. Los notebooks 04 y 05 usan rutas cacheadas;
no requieren Docker ni internet después de instalar las dependencias.

Desde la raíz del proyecto:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m ipykernel install --sys-prefix --name trafico --display-name 'Python (tráfico)'
.venv/bin/jupyter notebook notebooks/04_simulacion.ipynb
```

`requirements-lock.txt` registra las versiones probadas con Python 3.9/macOS
Apple Silicon; `requirements.txt` permite resolver paquetes para otros entornos.

Para recalcular todo C desde las rutas incluidas:

```bash
.venv/bin/python scripts/ejecutar_experimentos.py
.venv/bin/python scripts/analizar_componentes.py
.venv/bin/python scripts/ejecutar_notebooks.py 04_simulacion.ipynb 05_analisis_y_figuras.ipynb
.venv/bin/pytest -q
```

`--replicas 10` en `ejecutar_experimentos.py` permite una corrida abreviada;
para regenerar el paquete entregado se utiliza el valor predeterminado de 30.
Los notebooks también verifican una réplica recalculándola contra el NPZ.

## Reconstruir la red y las rutas

Esta parte sí necesita internet, Docker y el extracto PBF:

```bash
.venv/bin/jupyter notebook notebooks/01_red_y_osrm.ipynb
# Tras descargar data/osm/guatemala-latest.osm.pbf:
bash osrm/construir.sh
docker compose -f osrm/docker-compose.yml up -d
.venv/bin/python scripts/preparar_rutas.py
```

OSRM sirve en `127.0.0.1:5001`. `preparar_rutas.py` verifica **todos** los pares
contra ambos cierres y restaura la base al terminar, también ante excepciones.
Extrae clases, carriles y semáforos del **mismo PBF** que el grafo, incluidos
tramos fuera del BBOX. `red.metadatos_overpass()` ofrece además una consulta
conjunta cacheable para explorar esos metadatos vía Overpass.

```bash
bash osrm/cerrar.sh data/derivados/cierre_vista_hermosa.csv
bash osrm/cerrar.sh  # restaura la base original
```

**Corrección de infraestructura:** omitir el CSV en `osrm-customize` no basta
para deshacer velocidades anteriores. `construir.sh` guarda `base_original/`
y `cerrar.sh` restaura ese snapshot antes de cada escenario. Las instalaciones
anteriores deben reconstruir una vez para generar el respaldo. El script
bloquea cambios concurrentes y detiene el servidor mientras reemplaza archivos.

## Notebooks y archivos

| Notebook | Contenido | Estado |
|---|---|---|
| [01](notebooks/01_red_y_osrm.ipynb) | Red, OSRM y área de estudio | existente |
| [02](notebooks/02_linea_base_y_cierres.ipynb) | Línea base y cierres | referencia histórica |
| [03](notebooks/03_generadores.ipynb) | Pista B, validación y figuras 5–7 | reejecutado |
| [04](notebooks/04_simulacion.ipynb) | Corridas, IC, criterio 5 y convergencia | ejecutado |
| [05](notebooks/05_analisis_y_figuras.ipynb) | Análisis y figuras 2, 3, 4, 8, 9, 10 | ejecutado |

- `src/config.py`: parámetros compartidos; `generadores.py`: pista B conservada.
- `src/osrm.py`, `src/red.py`: rutas, cierres y metadatos OSM.
- `src/simulacion.py`: motor, estimadores y bootstrap.
- `src/analisis.py`: figuras y mapa autónomo.
- `data/derivados/04_*`: cache, procedencia, réplicas, vehículos y resultados.
- `tests/`: unidades de flujo, BPR, giros, CRN, conectividad y bootstrap.
- `estructura-proyecto.md`: diseño original; [PISTA_C.md](PISTA_C.md): implementación final.

## Alcance de las conclusiones

Son resultados **condicionales al modelo**, no predicciones de tráfico real.
Se usan 24 puntos fijos (8 por zona), 20% de viajes intrazonales, pesos supuestos,
capacidades sin calibrar y carriles imputados cuando falta la etiqueta OSM.
Los discos de muestreo son proxies, no polígonos administrativos oficiales.
BPR usa cohortes de salida de 15 minutos: no hay propagación de colas,
reasignación iterativa, spillback ni equilibrio de Wardrop. El IC mide sólo
variabilidad Monte Carlo; formar cocientes no garantiza cancelar todo sesgo.

El siguiente paso útil es calibrar demanda/capacidades y ampliar el pool O-D.
