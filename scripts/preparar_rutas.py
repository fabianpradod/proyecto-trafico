"""Cache real de rutas y metadatos: ejecutar una vez con OSRM local.

Restaura la base incluso ante un error. No usa el servidor público para cierres.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import gzip
import hashlib
import json
import subprocess
from datetime import datetime, timezone
import config as c
import osrm
import red


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def aplicar(escenario):
    cmd = ['bash', 'osrm/cerrar.sh']
    if escenario != 'base': cmd += [f'data/derivados/cierre_{escenario}.csv']
    subprocess.run(cmd, cwd=c.RAIZ, check=True)
    osrm.esperar()


def main():
    if not osrm.disponible(): raise RuntimeError('Se requiere OSRM local: ver README')
    puntos = json.loads((c.DERIVADOS/'02_linea_base.json').read_text())['puntos_od']
    rutas = {}
    try:
        for escenario in c.ESCENARIOS:
            aplicar(escenario)
            rutas[escenario] = {}
            for i, o in enumerate(puntos):
                for j, d in enumerate(puntos):
                    if i == j: continue
                    rutas[escenario][f'{i},{j}'] = osrm.ruta(
                        (o['lat'], o['lon']), (d['lat'], d['lon']), geometria=True)
                print(escenario, i+1, '/', len(puntos), flush=True)
    finally:
        aplicar('base')
    with gzip.open(c.OSM/'rutas_sin_validar.json.gz', 'wt') as f:
        json.dump(rutas, f)
    validacion = {}
    for escenario in list(c.ESCENARIOS)[1:]:
        cerrados = {tuple(map(int, l.split(',')[:2])) for l in
                    (c.DERIVADOS/f'cierre_{escenario}.csv').read_text().splitlines()}
        afectados = 0
        for par, r in rutas[escenario].items():
            base = rutas['base'][par]
            if r:
                assert not red.recorre_cerrados(r['nodos'], cerrados), (escenario, par)
            if base and red.recorre_cerrados(base['nodos'], cerrados): afectados += 1
            if base and r:
                # Tolerancia de redondeo del API: décimas de segundo.
                assert r['duracion_s'] >= base['duracion_s'] - .2, (escenario, par, 'monotonía')
                if not red.recorre_cerrados(base['nodos'], cerrados):
                    assert abs(r['duracion_s'] - base['duracion_s']) <= .2, (escenario, par, 'especificidad', base['duracion_s'], r['duracion_s'])
        assert afectados > 0, f'{escenario}: cierre no intercepta ninguna ruta base'
        validacion[escenario] = {'pares_verificados': len(rutas[escenario]), 'rutas_base_afectadas': afectados,
                                 'segmentos_cerrados': len(cerrados), 'tolerancia_s': .2}
    segmentos = set(); nodos = set()
    for rs in rutas.values():
        for r in rs.values():
            if r:
                segmentos.update(red.segmentos_de_ruta(r['nodos'])); nodos.update(r['nodos'])
    pbf = c.OSM/c.PBF_NOMBRE
    metadatos = red.metadatos_pbf(pbf, segmentos, nodos)
    faltantes = segmentos - {tuple(map(int, k.split(','))) for k in metadatos['segmentos']}
    assert not faltantes, f'{len(faltantes)} segmentos sin clase en el PBF'
    manifiesto = {'version': 1, 'creado_utc': datetime.now(timezone.utc).isoformat(),
                  'pbf_sha256': sha(pbf), 'pbf_url': c.PBF_URL,
                  'cierres_sha256': {s: sha(c.DERIVADOS/f'cierre_{s}.csv') for s in list(c.ESCENARIOS)[1:]},
                  'osrm_imagen': subprocess.check_output(['docker', 'image', 'inspect',
                    'ghcr.io/project-osrm/osrm-backend:latest', '--format', '{{.Id}}'], text=True).strip(),
                  'validacion': validacion, 'puntos': puntos}
    destino = c.DERIVADOS/'04_rutas.json.gz'
    with gzip.open(destino.with_suffix('.tmp'), 'wt') as f:
        json.dump({'manifiesto': manifiesto, 'rutas': rutas, 'metadatos': metadatos}, f)
    destino.with_suffix('.tmp').replace(destino)
    (c.DERIVADOS/'04_manifiesto_rutas.json').write_text(json.dumps(manifiesto, indent=2))
    print('Listo:', destino, len(segmentos), 'segmentos;', len(metadatos['semaforos']), 'semáforos')

if __name__ == '__main__': main()
