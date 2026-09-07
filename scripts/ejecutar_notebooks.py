"""Ejecuta los notebooks nuevos y guarda salidas; falla ante la primera excepción."""
from pathlib import Path
import sys
import nbformat
from nbclient import NotebookClient
raiz=Path(__file__).resolve().parents[1]
seleccion=sys.argv[1:] or ['03_generadores.ipynb','04_simulacion.ipynb','05_analisis_y_figuras.ipynb']
for nombre in seleccion:
    p=raiz/'notebooks'/nombre
    n=nbformat.read(p,as_version=4)
    print('Ejecutando',nombre,flush=True)
    NotebookClient(n,timeout=900,kernel_name='trafico',resources={'metadata':{'path':str(p.parent)}}).execute()
    nbformat.write(n,p)
    print('OK',nombre,flush=True)
