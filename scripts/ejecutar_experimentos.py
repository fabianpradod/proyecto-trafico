"""Reproduce corrida principal, sensibilidad de demanda y criterio 5 sin OSRM."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import argparse
from dataclasses import asdict
import hashlib
import json
import numpy as np
import pandas as pd
import config as c
from simulacion import Motor, Parametros, cargar_cache, experimento, resumir


def main(replicas=c.REPLICAS):
    motor = Motor(cargar_cache()); grupos = []; matrices = None
    for fuente,metodo in c.GENERADORES:
        print('generador',fuente,metodo,flush=True)
        principal = (fuente,metodo)==c.GENERADORES[0]
        f,m,d = experimento(motor,replicas,fuente,metodo,guardar_vehiculos=principal)
        grupos.append(f)
        if principal:
            matrices = m
            np.savez_compressed(c.DERIVADOS/'04_vehiculos.npz',**{k:d[k].to_numpy() for k in d})
    for demanda in c.FACTORES_DEMANDA:
        if demanda == 1: continue
        print('demanda',demanda,flush=True)
        f,_,_ = experimento(motor,replicas,demanda=demanda)
        grupos.append(f)
    filas = pd.concat(grupos,ignore_index=True)
    filas.to_csv(c.DERIVADOS/'04_replicas.csv',index=False)
    matrices.to_csv(c.DERIVADOS/'04_matrices.csv',index=False)
    resumen = resumir(filas)
    resultado = {'parametros':asdict(Parametros()),'capacidad_por_carril':c.CAPACIDAD_POR_CARRIL,
                 'semilla':c.SEMILLA,'replicas':replicas,'bootstrap_replicas':c.BOOTSTRAP_REPLICAS,
                 'nivel_confianza':c.NIVEL_CONFIANZA,'resumen':resumen,
                 'cache_sha256':hashlib.sha256((c.DERIVADOS/'04_rutas.json.gz').read_bytes()).hexdigest(),
                 'fuentes_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (c.RAIZ/'src').glob('*.py') if p.name != 'analisis.py'},
                 'modelo':'BPR una pasada, cohortes de salida, pool finito, parámetros no calibrados'}
    (c.DERIVADOS/'04_resultados.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2,allow_nan=False))
    print(pd.DataFrame([x for x in resumen if x['fuente']=='pcg64' and x['metodo']=='polar' and x['demanda']==1])[
        ['escenario','metrica','delta_pct','ic_pareado','delta_libre_pct','reduccion_ancho_pct']].to_string(index=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--replicas',type=int,default=c.REPLICAS)
    main(parser.parse_args().replicas)
