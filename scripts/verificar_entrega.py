"""Audita derivados, trazabilidad, notebooks y reproducción de resultados sin red."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import hashlib
import json
import numpy as np
import pandas as pd
import nbformat
import config as c
from simulacion import cargar_cache,resumir
cache=cargar_cache()
r=json.loads((c.DERIVADOS/'04_resultados.json').read_text())
assert hashlib.sha256((c.DERIVADOS/'04_rutas.json.gz').read_bytes()).hexdigest()==r['cache_sha256']
for nombre,huella in r['fuentes_sha256'].items():
    assert hashlib.sha256((c.RAIZ/'src'/nombre).read_bytes()).hexdigest()==huella, nombre
filas=pd.read_csv(c.DERIVADOS/'04_replicas.csv')
assert len(filas)==7*r['replicas']*len(c.ESCENARIOS)
recalculados=resumir(filas)
assert len(recalculados)==len(r['resumen'])
for nuevo,guardado in zip(recalculados,r['resumen']):
    for key in ('fuente','metodo','demanda','escenario','metrica'):
        assert nuevo[key]==guardado[key], key
    for key in ('delta_pct','ic_pareado','ic_no_pareado','delta_libre_pct','reduccion_ancho_pct'):
        np.testing.assert_allclose(nuevo[key],guardado[key],atol=1e-10,rtol=1e-10)
for nombre in ('03_generadores.ipynb','04_simulacion.ipynb','05_analisis_y_figuras.ipynb'):
    n=nbformat.read(c.RAIZ/'notebooks'/nombre,as_version=4);nbformat.validate(n)
    codigos=[x for x in n.cells if x.cell_type=='code']
    assert all(x.execution_count is not None for x in codigos),nombre
    assert all(o.output_type!='error' for x in codigos for o in x.outputs),nombre
for nombre in ('02_rutas_antes_despues','03_histogramas','04_matriz_zonas','08_sensibilidad_demanda','09_intervalos_pareados'):
    for ext in ('svg','png'):assert (c.FIGURAS/f'{nombre}.{ext}').stat().st_size>1000
html=(c.FIGURAS/'10_mapa_interactivo.html').read_text()
assert 'src="http' not in html and 'href="http' not in html
assert len(cache['rutas']['base'])==len(cache['manifiesto']['puntos'])*(len(cache['manifiesto']['puntos'])-1)
print(f'OK: hashes, {len(filas)} réplicas, estimadores, notebooks ejecutados y seis figuras de C.')
