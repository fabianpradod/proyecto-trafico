"""Monte Carlo de tráfico: rutas OSRM fijas por escenario + una pasada BPR.

Flujos en veh/h por cohorte de salida, sin propagación temporal ni reasignación.
CRN: tráfico, conductores, capacidad por arco y demoras por vehículo/nodo se
sortean una sola vez, con índices globales estables para TODOS los escenarios.
"""
from __future__ import annotations
from dataclasses import dataclass
import gzip
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
import config as c
from generadores import Generador


@dataclass(frozen=True)
class Parametros:
    horizonte_h: float = c.HORIZONTE_H
    ventana_h: float = c.VENTANA_H
    lambda_min: float = c.LAMBDA_MIN
    lambda_max: float = c.LAMBDA_MAX
    pico_h: float = c.T_PICO_H
    tau_h: float = c.TAU_H
    intrazonal: float = c.FRACCION_INTRAZONAL
    pesos_origen: tuple = c.PESOS_ORIGEN
    velocidad_mu: float = c.LOGN_MU
    velocidad_sigma: float = c.LOGN_SIGMA
    alpha: float = c.ALFA_BPR
    beta: float = c.BETA_BPR
    capacidad_cv: float = c.CAPACIDAD_CV
    capacidad_min: float = c.CAPACIDAD_MIN_REL
    capacidad_max: float = c.CAPACIDAD_MAX_REL
    erlang_k: int = c.ERLANG_K
    erlang_lambda: float = c.ERLANG_LAMBDA

    def __post_init__(self):
        vals = [self.horizonte_h, self.ventana_h, self.lambda_max, self.tau_h,
                self.beta, self.capacidad_cv, self.erlang_lambda]
        if not all(np.isfinite(v) and v > 0 for v in vals): raise ValueError('parámetros positivos inválidos')
        if not 0 <= self.lambda_min <= self.lambda_max: raise ValueError('intensidad inválida')
        if not 0 <= self.intrazonal <= 1 or self.alpha < 0: raise ValueError('fracción/alpha inválidos')
        if self.capacidad_min <= 0 or self.capacidad_max <= self.capacidad_min: raise ValueError('capacidad inválida')
        if self.velocidad_sigma < 0: raise ValueError('sigma inválida')


def probabilidades_od(p):
    orig = np.array(p.pesos_origen, float)
    dest = np.array([z['peso'] for z in c.ZONAS.values()])
    if orig.shape != (len(c.ZONAS),) or not np.isfinite(orig).all() or (orig < 0).any() or orig.sum() <= 0:
        raise ValueError('pesos de origen inválidos')
    orig /= orig.sum(); dest /= dest.sum()
    tabla = np.outer(orig, dest); np.fill_diagonal(tabla, 0)
    tabla *= (1-p.intrazonal)/tabla.sum()
    np.fill_diagonal(tabla, p.intrazonal*orig)
    return tabla


def cargar_cache(archivo=None):
    archivo = archivo or c.DERIVADOS/'04_rutas.json.gz'
    if not archivo.exists(): raise FileNotFoundError('Ejecutar .venv/bin/python scripts/preparar_rutas.py con OSRM local')
    with gzip.open(archivo, 'rt') as f: datos = json.load(f)
    if datos['manifiesto']['version'] != 1: raise ValueError('versión de cache incompatible')
    puntos = json.loads((c.DERIVADOS/'02_linea_base.json').read_text())['puntos_od']
    if datos['manifiesto']['puntos'] != puntos: raise ValueError('cambiaron puntos O-D; regenerar cache')
    for esc, huella in datos['manifiesto']['cierres_sha256'].items():
        if hashlib.sha256((c.DERIVADOS/f'cierre_{esc}.csv').read_bytes()).hexdigest() != huella:
            raise ValueError('cambió CSV de cierre; regenerar cache')
    return datos


class Motor:
    def __init__(self, cache):
        self.cache = cache
        self.puntos = cache['manifiesto']['puntos']
        self.np = len(self.puntos)
        self.zonas = list(c.ZONAS)
        self.pool = [np.array([i for i,x in enumerate(self.puntos) if x['zona'] == z]) for z in self.zonas]
        if any(len(x) < 2 for x in self.pool): raise ValueError('cada zona requiere al menos dos puntos')
        meta = cache['metadatos']
        self.arcos = sorted(meta['segmentos'], key=lambda k: tuple(map(int,k.split(','))))
        self.ia = {a:i for i,a in enumerate(self.arcos)}
        self.semaforos = sorted(meta['semaforos']); self.ins = {n:i for i,n in enumerate(self.semaforos)}
        self.capacidad_nominal = np.array([
            c.CAPACIDAD_POR_CARRIL.get(meta['segmentos'][a]['highway'].replace('_link',''),
                                      c.CAPACIDAD_POR_CARRIL['unclassified']) * meta['segmentos'][a]['carriles']
            for a in self.arcos])
        self.redes = {esc:self._compilar(rs) for esc,rs in cache['rutas'].items()}

    def _compilar(self, rutas):
        filas, cols, dur, señales = [], [], [], []
        libre = np.full(self.np**2, np.nan); residuo = np.zeros(self.np**2)
        for par, r in rutas.items():
            i,j = map(int, par.split(',')); k = i*self.np+j
            if r is None: continue
            nd, ts = r['nodos'], r['duraciones_s']
            if len(nd) != len(ts)+1 or len(ts) != len(r['distancias_m']): raise ValueError('anotaciones desalineadas')
            if not np.isfinite(ts).all() or min(ts, default=0) < 0: raise ValueError('duraciones inválidas')
            libre[k] = r['duracion_s']; residuo[k] = libre[k] - sum(ts)
            for a,b,t in zip(nd, nd[1:], ts):
                filas.append(k); cols.append(self.ia[f'{a},{b}']); dur.append(t)
            # Se cuenta cada paso por un nodo, incluso si una ruta lo visita dos veces.
            señales.append((k, [self.ins[n] for n in nd if n in self.ins]))
        shape = (self.np**2, len(self.arcos))
        flujo = csr_matrix((np.ones(len(cols)), (filas,cols)), shape=shape)
        tiempos = csr_matrix((dur, (filas,cols)), shape=shape)
        sf, sc = [], []
        for k, ss in señales:
            sf.extend([k]*len(ss)); sc.extend(ss)
        senales = csr_matrix((np.ones(len(sc)), (sf,sc)), shape=(self.np**2,len(self.semaforos)))
        return {'flujo':flujo,'tiempos':tiempos,'libre':libre,'residuo':residuo,'senales':senales}

    def trafico(self, semilla, fuente='pcg64', metodo='polar', demanda=1., parametros=None):
        p = parametros or Parametros()
        if not np.isfinite(demanda) or demanda <= 0: raise ValueError('demanda debe ser positiva')
        g = Generador(semilla, fuente, metodo)
        tasa = lambda t: demanda*c.lambda_llegadas(t, p.lambda_min, p.lambda_max, p.pico_h, p.tau_h)
        llegadas, eficiencia = g.poisson_nh(p.horizonte_h, tasa, demanda*p.lambda_max, devolver_eficiencia=True)
        n = len(llegadas)
        od = g.categorica(n, probabilidades_od(p).ravel()); zo, zd = od//len(self.zonas), od%len(self.zonas)
        uo, ud = g.uniformes(n), g.uniformes(n)
        origen, destino = np.empty(n,int), np.empty(n,int)
        for z, pool in enumerate(self.pool):
            mask = zo == z; origen[mask] = pool[(uo[mask]*len(pool)).astype(int)]
        for i in range(n):
            pool = self.pool[zd[i]]
            if zo[i] == zd[i]: pool = pool[pool != origen[i]]
            destino[i] = pool[int(ud[i]*len(pool))]
        velocidad = g.lognormales(n, p.velocidad_mu, p.velocidad_sigma)
        capacidad = self.capacidad_nominal*g.normales_truncadas(len(self.arcos), mu=1., sigma=p.capacidad_cv,
                                                      bajo=p.capacidad_min,alto=p.capacidad_max)
        demora = g.erlang(n*len(self.semaforos), p.erlang_k, p.erlang_lambda).reshape(n,len(self.semaforos))
        return {'llegadas_h':llegadas,'origen':origen,'destino':destino,'zo':zo,'zd':zd,
                'par':origen*self.np+destino,'velocidad':velocidad,'capacidad':capacidad,'demora':demora,
                'aceptacion_nh':eficiencia}

    def simular(self, trafico, escenario, parametros=None):
        p = parametros or Parametros(); red = self.redes[escenario]
        par = trafico['par']; n = len(par)
        bins = np.floor(trafico['llegadas_h']/p.ventana_h).astype(int)
        nb = int(np.ceil(p.horizonte_h/p.ventana_h))
        anchos = np.minimum(p.ventana_h, p.horizonte_h - np.arange(nb)*p.ventana_h)
        conteo = np.zeros((nb,self.np**2)); np.add.at(conteo,(bins,par),1)
        flujos = np.asarray(red['flujo'].T.dot(conteo.T).T)/anchos[:,None]
        factor = 1 + p.alpha*(flujos/trafico['capacidad'])**p.beta
        por_par = np.asarray(red['tiempos'].dot(factor.T).T)+red['residuo'][None,:]
        tiempos = por_par[bins,par]/trafico['velocidad']
        if len(self.semaforos):
            tiempos += np.asarray(red['senales'][par].multiply(trafico['demora']).sum(axis=1)).ravel()
        tiempos[~np.isfinite(red['libre'][par])] = np.nan
        libre = red['libre'][par].copy()
        return {'tiempos_s':tiempos,'libre_s':libre,'vc_max':float((flujos/trafico['capacidad']).max(initial=0))}


def estadisticas(x):
    x = np.asarray(x); x = x[np.isfinite(x)]
    if not len(x): return np.full(3,np.nan)
    return np.array([np.median(x),np.percentile(x,95),x.sum()])


def cociente(a,b):
    a,b = np.asarray(a,float),np.asarray(b,float)
    return np.divide(100*(b-a), a, out=np.full(np.broadcast(a,b).shape,np.nan), where=a>0)


def intervalo(a,b, semilla=c.SEMILLA, n_boot=c.BOOTSTRAP_REPLICAS, nivel=c.NIVEL_CONFIANZA):
    """Cociente de medias de estadísticas por réplica, bootstrap por réplica.

    IC pareado remuestrea los mismos índices; no pareado rompe esa covarianza.
    No confundir con un bootstrap de vehículos ni con la media de los Δ%.
    """
    a,b = np.asarray(a,float),np.asarray(b,float)
    if a.shape != b.shape or a.ndim != 1: raise ValueError('vectores pareados requeridos')
    if n_boot < 2 or not 0 < nivel < 1: raise ValueError('bootstrap inválido')
    ok = np.isfinite(a)&np.isfinite(b)&(a>0); a,b = a[ok],b[ok]
    if len(a) < 2: return {'delta_pct':float(cociente(a.mean(),b.mean())) if len(a) else None,
                           'ic_pareado':None,'ic_no_pareado':None,'reduccion_ancho_pct':None,'replicas_validas':len(a)}
    rng = np.random.default_rng(semilla)
    idx = rng.integers(0,len(a),(n_boot,len(a))); jdx = rng.integers(0,len(a),(n_boot,len(a)))
    aa = a[idx].mean(axis=1)
    pareado = cociente(aa,b[idx].mean(axis=1)); independiente = cociente(aa,b[jdx].mean(axis=1))
    q = [(1-nivel)/2, 1-(1-nivel)/2]
    ip, ii = np.quantile(pareado,q),np.quantile(independiente,q)
    wp, wi = np.diff(ip)[0],np.diff(ii)[0]
    return {'delta_pct':float(cociente(a.mean(),b.mean())), 'ic_pareado':ip.tolist(),
            'ic_no_pareado':ii.tolist(),'reduccion_ancho_pct':float(100*(1-wp/wi)) if wi>0 else None,
            'replicas_validas':len(a)}


METRICAS = ('mediana','p95','red_total')


def experimento(motor, replicas=c.REPLICAS, fuente='pcg64', metodo='polar', demanda=1.,
                parametros=None, guardar_vehiculos=False):
    if replicas < 2: raise ValueError('se requieren al menos dos réplicas')
    filas, detalle, matrices = [], [], []
    escenarios = list(motor.redes)
    for rep in range(replicas):
        tr = motor.trafico(c.SEMILLA+rep,fuente,metodo,demanda,parametros)
        salidas = {esc:motor.simular(tr,esc,parametros) for esc in escenarios}
        for esc in escenarios:
            sal = salidas[esc]
            base = salidas['base']
            ok = np.isfinite(base['tiempos_s']) & np.isfinite(sal['tiempos_s'])
            fila = {'replica':rep,'escenario':esc,'fuente':fuente,'metodo':metodo,'demanda':demanda,
                    'vehiculos':len(ok),'comparables':int(ok.sum()),
                    'p_sin_ruta':float(np.mean(~np.isfinite(sal['tiempos_s']))) if len(ok) else np.nan,
                    'p_sin_ruta_base':float(np.mean(~np.isfinite(base['tiempos_s']))) if len(ok) else np.nan,
                    'aceptacion_nh':tr['aceptacion_nh'],'vc_max':sal['vc_max']}
            for etiqueta,key in (('', 'tiempos_s'),('libre_', 'libre_s')):
                a,b = estadisticas(base[key][ok]),estadisticas(sal[key][ok])
                for j,m in enumerate(METRICAS):
                    fila[etiqueta+m+'_base'] = a[j]; fila[etiqueta+m+'_escenario'] = b[j]
            filas.append(fila)
            for i in range(len(motor.zonas)):
                for j in range(len(motor.zonas)):
                    mask = ok & (tr['zo']==i) & (tr['zd']==j)
                    matrices.append({'replica':rep,'escenario':esc,'origen':motor.zonas[i],'destino':motor.zonas[j],
                        'base':float(np.median(base['tiempos_s'][mask])) if mask.any() else np.nan,
                        'cerrado':float(np.median(sal['tiempos_s'][mask])) if mask.any() else np.nan})
        if guardar_vehiculos:
            d = {k:tr[k] for k in ('llegadas_h','origen','destino','zo','zd')}
            d['replica'] = np.full(len(tr['par']),rep)
            for esc in escenarios:
                d[esc] = salidas[esc]['tiempos_s']; d[esc+'_libre'] = salidas[esc]['libre_s']
            detalle.append(pd.DataFrame(d))
    return pd.DataFrame(filas),pd.DataFrame(matrices),pd.concat(detalle,ignore_index=True) if detalle else None


def resumir(filas):
    resumen = []
    for (fuente,metodo,demanda,esc),g in filas.groupby(['fuente','metodo','demanda','escenario']):
        if esc == 'base': continue
        for m in METRICAS:
            ic = intervalo(g[m+'_base'],g[m+'_escenario'])
            resumen.append({'fuente':fuente,'metodo':metodo,'demanda':demanda,'escenario':esc,'metrica':m,
                **ic, 'delta_libre_pct':float(cociente(g['libre_'+m+'_base'].mean(),g['libre_'+m+'_escenario'].mean())),
                'p_sin_ruta':float(g.p_sin_ruta.mean()),'replicas':len(g)})
    return resumen
