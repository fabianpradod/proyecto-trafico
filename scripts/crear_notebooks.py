"""Construye los notebooks entregables; ejecutar después con nbclient."""
from pathlib import Path
import nbformat as nb
RAIZ=Path(__file__).resolve().parents[1]

def md(s):return nb.v4.new_markdown_cell(s)
def code(s):return nb.v4.new_code_cell(s)
setup='''import sys, json
from pathlib import Path
RAIZ = Path.cwd() if (Path.cwd() / 'src').exists() else Path.cwd().parent
sys.path.insert(0, str(RAIZ / 'src'))
import numpy as np
import pandas as pd
import config as c
from IPython.display import display, Image, IFrame
pd.set_option('display.max_columns', 20)
'''

def escribir(nombre,celdas):
    n=nb.v4.new_notebook(cells=celdas)
    n.metadata['kernelspec']={'display_name':'Python (tráfico)','language':'python','name':'trafico'}
    nb.write(n,RAIZ/'notebooks'/nombre)

escribir('04_simulacion.ipynb',[
md('''# 04 · Simulación del cierre de vías
**Modelo ejecutado:** una pasada BPR sobre rutas OSRM fijas por escenario. 30 réplicas por combinación, semilla global + índice de réplica. Comparaciones con números comunes entre escenarios.

Se reutilizan los 24 puntos anclados del notebook 02: la fuente espacial es uniforme discreta dentro del pool de cada zona, no un nuevo punto continuo por vehículo. Los centros y discos son proxies del estudio, no límites administrativos oficiales. Los parámetros de capacidad, demanda y demora son supuestos no calibrados.

Cada vehículo pertenece a una cohorte de salida de 15 minutos. Su contribución se cuenta en todos los segmentos de su ruta dentro de esa cohorte, y se divide entre su duración en horas para obtener veh/h. No se propagan colas, ocupación, cruces de ventana ni spillback. La capacidad de cada arco se sortea una vez por réplica. La espera Erlang es **adicional** al costo base OSRM, que ya puede incluir penalizaciones de intersección.'''),
code(setup+'''from dataclasses import asdict
from simulacion import Motor, Parametros, cargar_cache, intervalo
'''),
code('''cache=cargar_cache();motor=Motor(cache)
print('Rutas por escenario:', {k:len(v) for k,v in cache['rutas'].items()})
display(pd.DataFrame(cache['manifiesto']['validacion']).T)
display(pd.Series(asdict(Parametros()),name='Valor'))
print('Capacidades nominales supuestas (veh/h/carril):',c.CAPACIDAD_POR_CARRIL)
print('Segmentos:',len(motor.arcos),'Semáforos:',len(motor.semaforos))
print('Carriles imputados:',sum(v['carriles_imputados'] for v in cache['metadatos']['segmentos'].values()))
'''),
md('''Los escenarios de cierre se validaron contra todos los pares: ausencia de segmentos bloqueados, monotonía y especificidad de los tiempos de flujo libre. `cerrar.sh` restaura un snapshot original para evitar que las velocidades de un cierre persistan en el siguiente. Los derivados guardan hashes del PBF, CSV e imagen OSRM.

Para reconstruir las corridas completas desde este notebook, active la siguiente opción. Las rutas y los metadatos están incluidos; esta etapa no necesita Docker ni internet.'''),
code('''REEJECUTAR = False
if REEJECUTAR:
    import subprocess
    subprocess.run([sys.executable,str(RAIZ/'scripts/ejecutar_experimentos.py')],check=True,cwd=RAIZ)
resultado=json.loads((c.DERIVADOS/'04_resultados.json').read_text())
filas=pd.read_csv(c.DERIVADOS/'04_replicas.csv')
vehiculos=dict(np.load(c.DERIVADOS/'04_vehiculos.npz'))
from analisis import principales
resumen=principales(resultado)
display(resumen[['escenario','metrica','delta_pct','ic_pareado','delta_libre_pct','p_sin_ruta']])
'''),
code('''# Validación ejecutable: recomputar una réplica completa y cotejar sus vehículos.
tr=motor.trafico(c.SEMILLA)
mask=vehiculos['replica']==0
np.testing.assert_array_equal(tr['origen'],vehiculos['origen'][mask])
np.testing.assert_array_equal(tr['destino'],vehiculos['destino'][mask])
for esc in c.ESCENARIOS:
    nuevo=motor.simular(tr,esc)
    np.testing.assert_allclose(nuevo['tiempos_s'],vehiculos[esc][mask],rtol=1e-12,equal_nan=True)
print('Reproducción exacta de la réplica 0 en los tres escenarios: OK')
base=filas[(filas.fuente=='pcg64')&(filas.metodo=='polar')&(filas.demanda==1)&(filas.escenario=='base')]
print('Vehículos por réplica:',base.vehiculos.min(), 'a',base.vehiculos.max(),'; media:',base.vehiculos.mean())
print('Aceptación de adelgazamiento:',base.aceptacion_nh.mean())
'''),
md('''**Estimador:** para cada réplica se calcula la mediana, p95 y suma de tiempos en los vehículos con ruta en ambos escenarios. El titular es `100 × (media de estadísticas cerradas / media de estadísticas base − 1)`. No es la media de los cocientes ni el cambio en la mediana de todas las réplicas concatenadas. Los intervalos de 95% se obtienen con 2.000 remuestreos de réplicas completas. La suma de red es condicional a conectividad común; se reporta por separado P(sin ruta), sin convertir viajes desconectados en tiempos cero.

La comparación de flujo libre utiliza exactamente los mismos vehículos y pesos que la simulación. El +16,97% histórico usa 552 pares equiponderados: se conserva como referencia histórica, no como contrafactual directamente comparable ni cota inferior garantizada.'''),
code('''# Criterio 5: fuente de uniformes y método de normales.
comparacion=pd.DataFrame([r for r in resultado['resumen'] if r['demanda']==1 and r['escenario']=='vista_hermosa'])
display(comparacion[['fuente','metodo','metrica','delta_pct','ic_pareado']])
# Convergencia por número de réplicas, estadística mediana.
g=filas[(filas.fuente=='pcg64')&(filas.metodo=='polar')&(filas.demanda==1)&(filas.escenario=='vista_hermosa')].sort_values('replica')
display(pd.DataFrame([dict(n=n,**intervalo(g.mediana_base.iloc[:n],g.mediana_escenario.iloc[:n])) for n in sorted(set(min(n,len(g)) for n in (5,10,20,30)))]))
'''),
md('''Los cambios entre generadores se interpretan junto al error Monte Carlo. El solapamiento de IC es orientativo, no una prueba formal de equivalencia; RANDU puede fallar en dependencia multivariada sin mover este estimador. Ningún resultado debe forzarse para favorecer la hipótesis original.''')])

escribir('05_analisis_y_figuras.ipynb',[
md('''# 05 · Resultados, análisis y figuras
Este notebook regenera las figuras 2, 3, 4, 8, 9 y 10 a partir de los derivados auditables. Los gráficos estáticos se guardan en SVG y PNG. El mapa interactivo contiene sus propias geometrías y JavaScript; funciona sin red ni servicios externos.'''),
code(setup+'''from simulacion import cargar_cache
from analisis import figuras, principales
cache=cargar_cache()
resultado=json.loads((c.DERIVADOS/'04_resultados.json').read_text())
vehiculos=dict(np.load(c.DERIVADOS/'04_vehiculos.npz'))
matrices=pd.read_csv(c.DERIVADOS/'04_matrices.csv')
tablas=figuras(cache,resultado,vehiculos,matrices)
resumen=principales(resultado)
display(resumen[['escenario','metrica','delta_pct','ic_pareado','delta_libre_pct','reduccion_ancho_pct','p_sin_ruta']])
'''),
code('''for nombre in ('02_rutas_antes_despues','03_histogramas','04_matriz_zonas','08_sensibilidad_demanda','09_intervalos_pareados'):
    display(Image(filename=str(c.FIGURAS/f'{nombre}.png')))
'''),
code('''# Lectura numérica sin imponer el signo esperado del efecto de congestión.
for r in resumen.itertuples():
    diferencia=r.delta_pct-r.delta_libre_pct
    print(f'{r.escenario} / {r.metrica}: Δ {r.delta_pct:+.2f}%; flujo libre con la misma demanda {r.delta_libre_pct:+.2f}%; diferencia {diferencia:+.2f} pp.')
    print(f'  IC 95% pareado [{r.ic_pareado[0]:.2f}, {r.ic_pareado[1]:.2f}]%; reducción de ancho vs. no pareado {r.reduccion_ancho_pct:.1f}%.')
print('Mayor impacto O-D por escenario:')
for esc,m in tablas.items():
    i,j=np.unravel_index(np.nanargmax(m),m.shape)
    print(esc,list(c.ZONAS)[i],'→',list(c.ZONAS)[j],f'{m[i,j]:+.2f}%')
'''),
code("""componentes=pd.read_csv(c.DERIVADOS/'04_componentes.csv')
g=componentes.groupby(['escenario','etapa'])[['mediana','p95','red_total']].mean()
from simulacion import cociente
for esc in ('vista_hermosa','reforma'):
    print(esc)
    display(pd.DataFrame(cociente(g.loc['base'],g.loc[esc]),index=g.loc[esc].index,columns=g.columns).round(3))
"""),
md("""**Por qué Reforma tiene una mediana ligeramente negativa:** con BPR y velocidades, pero sin demora adicional de semáforos, el cambio es +0,640%. Al sumar las esperas en los nodos de cada ruta pasa a −0,678%. El cambio de signo proviene de este componente del modelo; no es evidencia de que cerrar Reforma mejore el tráfico real. En Vista Hermosa, BPR/velocidad da +44,588% y el modelo completo +55,402%."""),
md('''La diferencia frente al contrafactual de flujo libre combina BPR, velocidades y demora adicional; no identifica causalmente el aporte exclusivo de congestión. La sensibilidad varía sólo la intensidad de llegadas, manteniendo el resto de supuestos. Las bandas son incertidumbre Monte Carlo condicional al modelo: no incluyen incertidumbre de parámetros, geografía muestreada ni datos OSM.

**Limitaciones:** pool pequeño, pesos supuestos, carriles imputados cuando faltan etiquetas, capacidad sin calibración, semáforos incompletos en OSM, rutas fijas y cohortes estáticas. No hay equilibrio de tráfico, medición de la hora pico real ni demostración de causalidad urbana. Los cocientes pueden retener sesgos que difieran entre escenarios. El siguiente paso de mayor valor es calibrar demanda/capacidades y ampliar el pool, antes de añadir más complejidad al motor.'''),
code('''display(IFrame(src='../figuras/10_mapa_interactivo.html',width='100%',height=950))
print('Abrir para la defensa:',c.FIGURAS/'10_mapa_interactivo.html')
''')])
