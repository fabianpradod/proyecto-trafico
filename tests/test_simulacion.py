import copy
from dataclasses import replace
import numpy as np
import pytest
import requests
from unittest.mock import Mock, patch
import osrm
import red
from generadores import Generador
from simulacion import Motor, Parametros, probabilidades_od, intervalo, estadisticas, cociente


def cache_minimo():
    puntos = [{'zona':z} for z in ('z10','z15','z16') for _ in range(2)]
    r = {'nodos':[1,2], 'duraciones_s':[100.], 'distancias_m':[500.], 'duracion_s':110.}
    return {'manifiesto':{'puntos':puntos},'metadatos':{'segmentos':{'1,2':{'highway':'residential','carriles':1}},'semaforos':[2]},
            'rutas':{'base':{'0,2':r},'cierre':{'0,2':copy.deepcopy(r)}}}


def test_bpr_unidades_residuo_demoras_y_no_ruta():
    motor = Motor(cache_minimo())
    tr = {'par':np.array([2,2,3]),'llegadas_h':np.array([.1,.2,.2]),'velocidad':np.array([1.,2.,1.]),
          'capacidad':np.array([8.]),'demora':np.array([[20.],[30.],[10.]])}
    out = motor.simular(tr,'base',Parametros(horizonte_h=.5,ventana_h=.25))
    # Dos vehículos / .25 h = 8 veh/h: v/c=1; residuo 10 s sin BPR.
    np.testing.assert_allclose(out['tiempos_s'][:2],[100*1.15+10+20,(100*1.15+10)/2+30])
    assert np.isnan(out['tiempos_s'][2])
    assert out['vc_max']==1.


def test_ultima_ventana_parcial():
    motor = Motor(cache_minimo())
    tr = {'par':np.array([2]),'llegadas_h':np.array([.29]),'velocidad':np.ones(1),
          'capacidad':np.array([20.]),'demora':np.zeros((1,1))}
    out = motor.simular(tr,'base',Parametros(horizonte_h=.3,ventana_h=.25))
    assert out['vc_max']==pytest.approx(1.)


def test_crn_y_escenarios_identicos():
    motor = Motor(cache_minimo()); p=Parametros(lambda_min=5,lambda_max=10)
    tr=motor.trafico(777,parametros=p); tr2=motor.trafico(777,parametros=p)
    for key in tr: np.testing.assert_array_equal(tr[key],tr2[key])
    np.testing.assert_array_equal(motor.simular(tr,'base')['tiempos_s'],motor.simular(tr,'cierre')['tiempos_s'])
    assert np.all(tr['origen']!=tr['destino'])


def test_bpr_cero_recupera_osrm():
    motor = Motor(cache_minimo())
    tr={'par':np.array([2]),'llegadas_h':np.array([.1]),'velocidad':np.ones(1),
        'capacidad':np.ones(1),'demora':np.zeros((1,1))}
    np.testing.assert_allclose(motor.simular(tr,'base',Parametros(alpha=0))['tiempos_s'],[110.])


def test_od_fraccion_exacta():
    p = probabilidades_od(Parametros(intrazonal=.2))
    assert p.sum()==pytest.approx(1)
    assert np.trace(p)==pytest.approx(.2)
    assert np.trace(probabilidades_od(Parametros(intrazonal=0)))==0
    assert np.trace(probabilidades_od(Parametros(intrazonal=1)))==pytest.approx(1)


def test_bootstrap_cociente_y_pareamiento():
    a=np.arange(1.,31.); b=a*1.2
    ic=intervalo(a,b)
    assert ic['delta_pct']==pytest.approx(20)
    np.testing.assert_allclose(ic['ic_pareado'],[20,20])
    assert np.diff(ic['ic_no_pareado'])[0]>0
    assert ic['reduccion_ancho_pct']==pytest.approx(100)
    assert intervalo(np.zeros(3),np.ones(3))['ic_pareado'] is None
    assert np.isnan(cociente(0,1))
    assert np.isnan(estadisticas([])).all()


@pytest.mark.parametrize('fuente',['pcg64','lcg','randu'])
@pytest.mark.parametrize('metodo',['polar','rechazo'])
def test_generadores_momentos_y_reproducibilidad(fuente,metodo):
    g=Generador(777,fuente,metodo)
    x=g.normales(20000)
    np.testing.assert_array_equal(x,Generador(777,fuente,metodo).normales(20000))
    assert abs(x.mean())<.05
    assert abs(x.std()-1)<.05
    assert ((g.uniformes(2000)>0)&(g.uniformes(2000)<1)).all()
    assert (g.normales_truncadas(2000,1.,.1,.5,1.5)>=.5).all()
    assert g.erlang(20000,2,.1).mean()==pytest.approx(20,rel=.03)


def test_nhpp_y_envolvente():
    g=Generador(777)
    x=g.poisson_nh(3,lambda t:200,200)
    assert len(x)==pytest.approx(600,rel=.15)
    assert np.all(np.diff(x)>0) and x.max()<3
    with pytest.raises(ValueError): g.poisson_nh(3,lambda t:201,200)


def test_osrm_noroute_http400_y_anotaciones():
    respuesta=Mock(); respuesta.json.return_value={'code':'NoRoute'}
    respuesta.raise_for_status.side_effect=requests.HTTPError()
    with patch('osrm.requests.get',return_value=respuesta): assert osrm.ruta((0,0),(1,1)) is None
    with patch('osrm._pedir',return_value={'routes':[{'distance':500,'duration':110,
        'legs':[{'annotation':{'nodes':[1,2],'duration':[100],'distance':[500]}}]}]}):
        r=osrm.ruta((0,0),(1,1)); assert r['residuo_s']==10 and r['duraciones_s']==[100]


def test_metadatos_carriles_y_cierre_por_segmento():
    ways=[{'id':9,'nodes':[1,2], 'tags':{'highway':'primary','lanes':'4','lanes:forward':'3'}}]
    r=red.atributos_segmentos(ways,{(1,2),(2,1)})
    assert r['1,2']['carriles']==3 and r['2,1']['carriles']==1
    assert not red.recorre_cerrados([1,3,2],{(1,2)})
    assert red.recorre_cerrados([1,2],{(1,2)})==[(1,2)]
