# Manual de uso con pantallazos

Se rehace cuando cambian las pantallas o los precios (desde la carpeta `portal-trabajador`):

```powershell
python empaquetado\manual\capturas_manual.py escritorio backend $env:TEMP\manual
python empaquetado\manual\crear_manual.py backend $env:TEMP\manual escritorio\recursos\icono.png "$env:TEMP\manual\Manual de uso - Portal del Trabajador.pdf"
```

1. `capturas_manual.py` abre el programa (conectado al servidor de `escritorio/.env`) con una cuenta y un contrato
   FICTICIOS, toma los pantallazos con recuadros numerados y borra la cuenta al final. Nunca pulsa "Pagar".
2. `crear_manual.py` arma el manual en Word y lo convierte a PDF con el Word instalado.

Los precios del manual están escritos en `crear_manual.py` (sección 11): actualízalos si cambian en `supabase/schema.sql`.
