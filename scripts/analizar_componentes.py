"""Descompone el modelo manteniendo exactamente los mismos vehículos de C."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import json
import numpy as np
import pandas as pd
import config as c
from simulacion import Motor,cargar_cache,estadisticas,cociente,METRICAS
motor=Motor(cargar_cache());filas=[]
replicas=json.loads((c.DERIVADOS/'04_resultados.json').read_text())['replicas']
for rep in range(replicas):
    tr=motor.trafico(c.SEMILLA+rep)
    for esc in motor.redes:
        sal=motor.simular(tr,esc)
        dem=np.asarray(motor.redes[esc]['senales'][tr['par']].multiply(tr['demora']).sum(axis=1)).ravel()
        componentes={'OSRM':sal['libre_s'],'OSRM / velocidad':sal['libre_s']/tr['velocidad'],
                     'BPR / velocidad':sal['tiempos_s']-dem,'BPR / velocidad + semáforos':sal['tiempos_s']}
        for etapa,t in componentes.items():
            filas.append({'replica':rep,'escenario':esc,'etapa':etapa,
                           **dict(zip(METRICAS,estadisticas(t))),'demora_semaforos_total_s':float(dem.sum())})
f=pd.DataFrame(filas);f.to_csv(c.DERIVADOS/'04_componentes.csv',index=False)
g=f.groupby(['escenario','etapa'])[list(METRICAS)].mean()
for esc in ('vista_hermosa','reforma'):
    print(esc);print(pd.DataFrame(cociente(g.loc['base'],g.loc[esc]),index=g.loc[esc].index,columns=METRICAS).round(3))
