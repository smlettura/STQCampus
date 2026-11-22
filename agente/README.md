# Agente del copiloto (PC del equipo de IA)

El modelo corre en Ollama en un PC del equipo. Este agente lo conecta con la plataforma **sin abrir puertos**:
pregunta cada 10 s si hay solicitudes (HTTPS saliente), toma una, la pasa a Ollama en `127.0.0.1:11434` y devuelve
el borrador. Si el PC está apagado, las solicitudes esperan en la cola hasta 24 horas y la pantalla «Generar informe»
muestra «Equipo de IA apagado».

Al PC solo llega texto **seudonimizado** (`[ESTUDIANTE]`, `[CURSO]`, `[PROFESIONAL_1]`…). La plataforma reemplaza
los marcadores por los datos reales cuando el borrador vuelve. El agente no guarda nada en disco.

## Requisitos
- Python 3.9 o superior (solo biblioteca estándar).
- Ollama con `gemma2:9b` (`ollama pull gemma2:9b`) y el modelo del copiloto creado con
  `ollama create stq-copiloto -f docs/ia/Modelfile` (no modifica pesos: solo fija el prompt v4 y los parámetros).
  Alternativa: usar `gemma2:9b` directamente (`IA_MODELO=gemma2:9b` en el servidor y `MODELO=gemma2:9b` aquí): la
  plataforma envía el prompt de sistema v4 en cada solicitud.

## Instalación
1. En el servidor (una vez): `docker compose -f docker-compose.prod.yml exec web python manage.py crear_token_agente pc-equipo-ia`.
   Copie el token que aparece: **se muestra una sola vez**.
2. En el PC: copie esta carpeta, cree `agente.env` a partir de `agente.env.ejemplo` y pegue la URL y el token.
3. Pruebe: `python agente_stq.py --probar` → debe decir `Ollama: OK · Plataforma: 200`.
4. Déjelo como servicio:
   - **Windows:** `powershell -ExecutionPolicy Bypass -File servicio\instalar_windows.ps1` (agregue `LOG_ARCHIVO=agente.log` en `agente.env`).
   - **Linux:** `servicio/agente-stq.service` (systemd); instrucciones dentro del archivo.

## Operación
- Revocar el token (PC perdido o cambio de equipo): `manage.py crear_token_agente pc-equipo-ia --revocar` y emita otro.
- Ver estado: `manage.py crear_token_agente --listar` (último latido y modelo).
- Si Ollama falla, el agente informa el error y la plataforma reintenta hasta 3 veces; después la solicitud queda en «error».
- El prompt (v4), la plantilla y los parámetros viven en el servidor (`apps/ia/motor.py` y `apps/ia/instrucciones.py`);
  el agente solo los transporta. Los guardianes de entrada y salida (`apps/ia/guardas.py`) corren en el servidor: si la
  salida se sale de los límites, la plataforma pide al agente una versión corregida (una vez) y, si persiste, el
  borrador queda «bloqueado».
- Para que el modelo no se descargue de la memoria entre borradores: `IA_KEEP_ALIVE` en el servidor (por defecto 60m).
  Antes de una demostración, haga un borrador de prueba para «calentarlo» (la primera generación tarda más).

## Probar sin el modelo real
`python agente/ollama_simulado.py` levanta en `127.0.0.1:11434` un Ollama falso que responde un borrador fijo
(útil para probar el flujo completo antes de recibir el modelo).
