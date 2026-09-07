# proyecto2-trafico

Simulación del impacto del cierre de una vía principal sobre el tráfico de las
**zonas 10, 15 y 16 de la Ciudad de Guatemala**.

**CC2017 — Modelación y Simulación · Ciclo 2, 2026 · Universidad del Valle de Guatemala**

---

## Qué hace

Se genera tráfico sintético sobre la red vial real de OpenStreetMap, se enruta
con una instancia local de OSRM, y se mide cuánto empeoran los tiempos de viaje
al cerrar una vía. El resultado se reporta como **cambio porcentual** respecto
al escenario sin cierre.

Los tiempos de OSRM son de flujo libre y no son predicciones del tiempo real de
viaje. Lo que sí es defendible es el cociente entre dos escenarios del mismo
modelo, porque los sesgos comunes se cancelan. La afirmación del proyecto no es
*"el viaje toma 23 minutos"* sino *"cerrar esta vía lo encarece un 34 %"*.
El razonamiento completo está en
[estructura-proyecto.md §2](estructura-proyecto.md).

## Los dos escenarios

| Escenario | Vía | Ways | Segmentos | Hipótesis |
|---|---|---|---|---|
| Crítico | `Boulevard Vista Hermosa` (z15) | 23 | 408 | Espina encajonada entre barrancos, pocas paralelas → **Δ% grande** |
| Redundante | `Avenida Reforma` (z10) | 36 | 162 | Retícula densa y carriles auxiliares intactos → **Δ% pequeño** |

El contraste entre los dos es el hallazgo central: la misma metodología
distingue un eslabón crítico de uno redundante.

## Cómo correrlo

### 1. Entorno

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

### 2. Red vial y servidor OSRM

Requiere Docker corriendo. El notebook 01 descarga el extracto de Guatemala
(131 MB) y guía el resto:

```bash
.venv/bin/jupyter notebook notebooks/01_red_y_osrm.ipynb
```

O directo desde la terminal, una vez descargado el `.pbf`:

```bash
./osrm/construir.sh
docker compose -f osrm/docker-compose.yml up -d
```

`construir.sh` se corre **una sola vez** — tarda varios minutos. Después, cada
cambio de escenario cuesta segundos:

```bash
./osrm/cerrar.sh data/derivados/cierre_vista_hermosa.csv
./osrm/cerrar.sh                                          # volver a la base
```

### 3. Notebooks

| Notebook | Contenido | Estado |
|---|---|---|
| [`01_red_y_osrm.ipynb`](notebooks/01_red_y_osrm.ipynb) | Descarga del extracto, grafo OSRM, validación de la red, mapa del área | listo |
| [`02_linea_base_y_cierres.ipynb`](notebooks/02_linea_base_y_cierres.ipynb) | Matriz O-D base, generación de los CSV de cierre, verificación de que el cierre funciona | listo |
| `03_generadores.ipynb` | Generadores de variables aleatorias y su validación | pista B |
| `04_simulacion.ipynb` | Motor de simulación y corridas | pista C |
| `05_analisis_y_figuras.ipynb` | Δ%, intervalos y figuras del informe | pista C |

## Estructura

```
src/config.py     zonas, escenarios, semilla, paleta — la única fuente de verdad
src/osrm.py       cliente OSRM (route, table, nearest)
src/red.py        Overpass y generación de los archivos de cierre
osrm/             pipeline Docker
data/derivados/   csv y json pequeños (sí van al repo)
data/osm/         pbf y grafo compilado (ignorados por git)
```

Ninguna coordenada, semilla ni parámetro se escribe dos veces: todo vive en
`src/config.py` y los notebooks lo importan.

## Documentación

- **[estructura-proyecto.md](estructura-proyecto.md)** — el plan completo:
  modelo, fuentes de aleatoriedad, métodos de generación comparados, criterios,
  división del trabajo y mapeo a la rúbrica. Es la referencia del proyecto.
- **[Proyecto_1_Modelacion_y_Simulacion.md](../Proyecto_1_Modelacion_y_Simulacion.md)** — enunciado del curso.
