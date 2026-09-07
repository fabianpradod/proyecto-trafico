"""Figuras reproducibles y mapa autónomo para la defensa, sin red ni Docker."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import polyline
import config as c
from simulacion import cociente


def estilo():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
                        'axes.spines.right':False,'figure.dpi':130,'savefig.bbox':'tight'})


def guardar(fig,nombre):
    for ext in ('svg','png'):
        destino = c.FIGURAS/f'{nombre}.{ext}'
        fig.savefig(destino)
        if ext == 'svg':
            destino.write_text('\n'.join(linea.rstrip() for linea in destino.read_text().splitlines()) + '\n')
    plt.close(fig)


def principales(resultado):
    return pd.DataFrame([r for r in resultado['resumen'] if r['fuente']=='pcg64' and
                         r['metodo']=='polar' and r['demanda']==1])


def figuras(cache, resultado, vehiculos, matrices):
    estilo(); resumen=principales(resultado)
    # 2: selección reproducible de una ruta afectada, mayor desvío relativo.
    fig,axs=plt.subplots(1,2,figsize=(12,6))
    for ax,esc in zip(axs,('vista_hermosa','reforma')):
        rutas=cache['rutas']; candidatos=[k for k,r in rutas[esc].items() if r and rutas['base'][k] and rutas['base'][k]['duracion_s']>0]
        par=max(candidatos,key=lambda k:rutas[esc][k]['duracion_s']/rutas['base'][k]['duracion_s'])
        for e,color in (('base',c.NAVY),(esc,c.ORANGE)):
            coords=np.array(polyline.decode(rutas[e][par]['geometria']))
            ax.plot(coords[:,1],coords[:,0],color=color,lw=2.2,alpha=.8,label=c.ESCENARIOS[e]['etiqueta'])
        i,j=map(int,par.split(',')); puntos=cache['manifiesto']['puntos']
        for idx,label in ((i,'O'),(j,'D')):
            p=puntos[idx];ax.scatter(p['lon'],p['lat'],color=c.YELLOW,zorder=4);ax.annotate(label,(p['lon'],p['lat']))
        ax.set_title(f"{esc.replace('_',' ').title()} · {puntos[i]['id']} → {puntos[j]['id']}")
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
        ax.set_xlabel('Longitud');ax.set_ylabel('Latitud');ax.set_aspect(1/np.cos(np.radians(c.BBOX[0])));ax.legend(fontsize=8)
    fig.suptitle('02 · Desvíos sobre la red OSM — geometría real de rutas OSRM')
    fig.tight_layout();guardar(fig,'02_rutas_antes_despues')
    # 3: distribuciones de todas las réplicas principales.
    fig,axs=plt.subplots(1,2,figsize=(12,4.5))
    for ax,esc in zip(axs,('vista_hermosa','reforma')):
        a,b=vehiculos['base']/60,vehiculos[esc]/60
        ok=np.isfinite(a)&np.isfinite(b);lim=np.percentile(np.r_[a[ok],b[ok]],99.5)
        bins=np.linspace(0,lim,60)
        ax.hist(a[ok],bins=bins,weights=np.full(ok.sum(),1/ok.sum()),alpha=.5,color=c.NAVY,label='Base')
        ax.hist(b[ok],bins=bins,weights=np.full(ok.sum(),1/ok.sum()),alpha=.5,color=c.ORANGE,label='Cierre')
        ax.set_title(esc.replace('_',' ').title());ax.set_xlabel('Tiempo simulado (minutos)');ax.set_ylabel('Fracción de viajes por intervalo');ax.legend()
    fig.suptitle('03 · Distribución de tiempos — eje hasta p99.5 combinado; cola omitida <1%')
    fig.tight_layout();guardar(fig,'03_histogramas')
    # 4: cocientes de medias de medianas por réplica, misma definición que KPI.
    fig,axs=plt.subplots(1,2,figsize=(10,4.5)); tablas={}
    for esc in ('vista_hermosa','reforma'):
        g=matrices[matrices.escenario==esc].groupby(['origen','destino'])[['base','cerrado']].mean()
        g['delta']=cociente(g.base,g.cerrado)
        tablas[esc]=g.delta.unstack().reindex(index=c.ZONAS,columns=c.ZONAS).to_numpy()
    vmax=max(1.,max(np.nanmax(np.abs(v)) for v in tablas.values()))
    for ax,(esc,v) in zip(axs,tablas.items()):
        im=ax.imshow(v,cmap=LinearSegmentedColormap.from_list('trafico',[c.NAVY,'white',c.ORANGE]),vmin=-vmax,vmax=vmax)
        ax.set_xticks(range(3),c.ZONAS);ax.set_yticks(range(3),c.ZONAS)
        ax.set_xlabel('Destino');ax.set_ylabel('Origen');ax.set_title(esc.replace('_',' ').title())
        for i in range(3):
            for j in range(3):ax.text(j,i,f'{v[i,j]:+.1f}%',ha='center',va='center',color='white' if abs(v[i,j])>.6*vmax else c.NAVY)
    fig.colorbar(im,ax=axs,shrink=.75,label='Cambio de mediana (%)');fig.suptitle('04 · Impacto por par de zonas')
    guardar(fig,'04_matriz_zonas')
    # 8: demanda, incertidumbre por réplica.
    fig,axs=plt.subplots(1,2,figsize=(11,4.5))
    for ax,metrica in zip(axs,('mediana','p95')):
        for esc,color in (('vista_hermosa',c.ORANGE),('reforma',c.NAVY)):
            rows=sorted([r for r in resultado['resumen'] if r['fuente']=='pcg64' and r['metodo']=='polar' and r['escenario']==esc and r['metrica']==metrica],key=lambda r:r['demanda'])
            x=[r['demanda'] for r in rows];y=[r['delta_pct'] for r in rows]
            ax.plot(x,y,'o-',color=color,label=esc.replace('_',' ').title())
            ax.fill_between(x,[r['ic_pareado'][0] for r in rows],[r['ic_pareado'][1] for r in rows],color=color,alpha=.15)
        ax.axhline(0,color=c.GREY,lw=.8);ax.set_xlabel('Multiplicador de demanda');ax.set_ylabel(f'Δ% {metrica}');ax.legend(fontsize=9)
    fig.suptitle('08 · Sensibilidad a demanda — IC bootstrap pareado de 95%');fig.tight_layout();guardar(fig,'08_sensibilidad_demanda')
    # 9: no se promete reducción; se mide la ganancia observada.
    fig,ax=plt.subplots(figsize=(10,5));x=np.arange(len(resumen));w=.36
    wp=np.array([np.diff(v)[0] for v in resumen.ic_pareado]);wi=np.array([np.diff(v)[0] for v in resumen.ic_no_pareado])
    ax.bar(x-w/2,wp,w,label='Pareado (CRN)',color=c.NAVY);ax.bar(x+w/2,wi,w,label='No pareado (remuestreo independiente)',color=c.ORANGE)
    ax.set_xticks(x,[f"{r.escenario.replace('_',' ')}\n{r.metrica}" for r in resumen.itertuples()],rotation=15)
    ax.set_ylabel('Ancho del IC (puntos porcentuales)');ax.legend();ax.set_title('09 · Ganancia medida de números aleatorios comunes')
    fig.tight_layout();guardar(fig,'09_intervalos_pareados')
    mapa_interactivo(cache,resultado)
    return tablas


def mapa_interactivo(cache,resultado):
    # El HTML incluye geometrías y JavaScript; funciona desconectado, sin CDNs.
    datos={'puntos':cache['manifiesto']['puntos'], 'rutas':{esc:{k:None if r is None else
         {'g':r['geometria'],'s':r['duracion_s']} for k,r in rs.items()} for esc,rs in cache['rutas'].items()},
         'resumen':principales(resultado).to_dict('records')}
    plantilla='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tráfico · Zonas 10, 15 y 16</title><style>
:root{font-family:system-ui;color:#003865;background:#f3f5f7}body{max-width:1200px;margin:auto;padding:24px}h1{font-size:30px;margin:0}p{line-height:1.5}.panel{background:white;padding:20px;border-radius:12px;margin:16px 0}select{font:inherit;padding:10px;border:1px solid #bbb;border-radius:6px;margin:5px}svg{width:100%;height:560px;background:#f8fafc}.metrics{display:flex;gap:25px;flex-wrap:wrap}.metrics b{font-size:26px;display:block}#status{min-height:28px}.base{color:#003865}.closed{color:#FC4C02}footer{font-size:13px;color:#696969}label{display:inline-block}
</style><h1>¿Qué pasa al cerrar una vía principal?</h1><p>Zonas 10, 15 y 16 · Ciudad de Guatemala · Modelación y Simulación, UVG</p>
<div class="panel"><label>Escenario <select id="esc"><option value="base">Sin cierre</option><option value="vista_hermosa" selected>Cierre Vista Hermosa</option><option value="reforma">Cierre Reforma</option></select></label>
<label>Par origen → destino <select id="par"></select></label><div id="metrics" class="metrics"></div></div>
<div class="panel"><div id="status"></div><p><span class="base">━ Ruta base</span> · <span class="closed">━ Ruta del escenario</span> · O = origen, D = destino</p>
<svg id="map" viewBox="0 0 1000 560" role="img" aria-label="Rutas georreferenciadas antes y después del cierre"><g id="roads"></g><path id="basepath" fill="none" stroke="#003865" stroke-width="5" opacity=".65"/><path id="closedpath" fill="none" stroke="#FC4C02" stroke-width="3"/><g id="points"></g></svg></div>
<footer>Red georreferenciada sin mapa base; geometrías reales OSM/OSRM. Las líneas grises son rutas base del pool. Los KPI son resultados del modelo BPR y __REPLICAS__ réplicas; los minutos del par seleccionado son sólo de flujo libre. Pool fijo de 24 puntos, parámetros no calibrados, sin equilibrio ni datos de tráfico observado. Un pequeño Δ negativo puede deberse a semáforos distintos en las rutas alternativas; no demuestra una mejora real. HTML autónomo: funciona sin conexión. © OpenStreetMap contributors, ODbL.</footer>
<script>const D=__DATOS__;
function decode(s){let out=[],i=0,lat=0,lon=0;while(i<s.length){let v=[];for(let k=0;k<2;k++){let b,sh=0,r=0;do{b=s.charCodeAt(i++)-63;r|=(b&31)<<sh;sh+=5}while(b>=32);v.push((r&1)?~(r>>1):(r>>1))}lat+=v[0];lon+=v[1];out.push([lat/1e5,lon/1e5])}return out}
const coords={};for(const [e,rs] of Object.entries(D.rutas)){coords[e]={};for(const[k,r]of Object.entries(rs))coords[e][k]=r?decode(r.g):[]}
const par=document.getElementById('par'),esc=document.getElementById('esc');
for(const k of Object.keys(D.rutas.base)){const[i,j]=k.split(',').map(Number);const opt=document.createElement('option');opt.value=k;opt.textContent=D.puntos[i].id+' → '+D.puntos[j].id;par.appendChild(opt)}
par.value=Object.keys(D.rutas.base).filter(k=>D.rutas.base[k]&&D.rutas.vista_hermosa[k]).sort((a,b)=>D.rutas.vista_hermosa[b].s/D.rutas.base[b].s-D.rutas.vista_hermosa[a].s/D.rutas.base[a].s)[0];
const fmt=v=>v.toFixed(Math.abs(v)<.1?3:1);
function update(){const e=esc.value,k=par.value,ps=[...coords.base[k],...coords[e][k]];if(!ps.length){document.getElementById('status').textContent='Sin ruta en ambos escenarios';return}
let minLat=Math.min(...ps.map(p=>p[0])),maxLat=Math.max(...ps.map(p=>p[0])),minLon=Math.min(...ps.map(p=>p[1])),maxLon=Math.max(...ps.map(p=>p[1]));
const cos=Math.cos(minLat*Math.PI/180),scale=Math.min(900/Math.max((maxLon-minLon)*cos,1e-5),460/Math.max(maxLat-minLat,1e-5));
const project=p=>[500+(p[1]-(minLon+maxLon)/2)*cos*scale,280-(p[0]-(minLat+maxLat)/2)*scale];
const path=ps=>ps.map((p,i)=>(i?'L':'M')+project(p).map(v=>v.toFixed(1)).join(',')).join(' ');
document.getElementById('roads').innerHTML=Object.values(coords.base).map(ps=>'<path d="'+path(ps)+'" fill="none" stroke="#cbd5df" stroke-width=".5"/>').join('');
document.getElementById('basepath').setAttribute('d',path(coords.base[k]));document.getElementById('closedpath').setAttribute('d',e==='base'?'':path(coords[e][k]));
const[i,j]=k.split(',').map(Number);document.getElementById('points').innerHTML=[[i,'O'],[j,'D']].map(([n,t])=>{const p=project([D.puntos[n].lat,D.puntos[n].lon]);return '<circle cx="'+p[0]+'" cy="'+p[1]+'" r="7" fill="#FDB92E"/><text x="'+(p[0]+10)+'" y="'+(p[1]-10)+'" font-size="18">'+t+'</text>'}).join('');
const a=D.rutas.base[k],b=D.rutas[e][k];document.getElementById('status').textContent='Flujo libre del par: base '+(a?(a.s/60).toFixed(1)+' min':'sin ruta')+' → escenario '+(b?(b.s/60).toFixed(1)+' min':'sin ruta')+(a&&b?' · cambio '+(100*(b.s/a.s-1)).toFixed(1)+'%':'');
const r=D.resumen.filter(x=>x.escenario===e);document.getElementById('metrics').innerHTML=e==='base'?'<p>Referencia sin cierre · demanda ×1</p>':r.map(x=>'<div><b>'+fmt(x.delta_pct)+'%</b>Δ '+({'mediana':'mediana','p95':'p95','red_total':'tiempo total'}[x.metrica])+'<br><small>IC 95%: '+x.ic_pareado.map(fmt).join(' a ')+'%</small></div>').join('');}
esc.onchange=update;par.onchange=update;update();</script></html>'''
    html=plantilla.replace('__REPLICAS__',str(resultado['replicas'])).replace('__DATOS__',json.dumps(datos,ensure_ascii=False).replace('</','<\\/'))
    (c.FIGURAS/'10_mapa_interactivo.html').write_text(html)
