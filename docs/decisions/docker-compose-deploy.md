# Migración del deploy a Docker Compose

**status: Aceptado**
**date: 2026-04-13**
**decision-makers: Groba, Salomon, Di Cola**
**consulted:**
**informed: Equipo Docente (Ingeniería de Software)**

## Contexto y Declaración del Problema

El pipeline actual de Continuous Deployment definido en
[.github/workflows/ci.yml](../../.github/workflows/ci.yml) asume que el
producto es un único contenedor de la API. El job `deploy` se conecta por SSH
a la instancia EC2 y ejecuta literalmente:

```
git pull origin main
docker build -t predictiva-api .
docker stop mi-api || true
docker rm mi-api || true
docker run -d --name mi-api -p 8000:8000 predictiva-api
```

Con la incorporación de Prometheus y Grafana (decidida en los ADRs 0002 y
0003), el producto pasa a ser **un conjunto de tres contenedores** que
comparten red y dependen entre sí. El enfoque actual deja de ser suficiente:
cada `docker run` aislado obliga a definir `--network`, `--volume` y
dependencias manualmente en el script SSH, con alta probabilidad de que la
instancia quede en un estado inconsistente si cualquier comando falla.

Necesitamos decidir cómo evolucionar el deploy sin reescribir el resto del
pipeline y sin introducir herramientas nuevas que el equipo aún no use.

## Opciones Consideradas

- **Opción A — Mantener `docker run`, uno por servicio.** Agregamos más
  líneas al script SSH para Prometheus y Grafana, con sus propios volúmenes
  y una red Docker creada a mano. Mínimo cambio de herramientas.
- **Opción B — `docker compose down && docker compose up -d --build`.**
  Versionamos un `docker-compose.yml` en la raíz del repo. El script SSH se
  reduce a dos comandos: `git pull` y `docker compose up -d --build`. Compose
  resuelve la red, el orden de arranque y los volúmenes.
- **Opción C — Introducir un orquestador real (ECS, Kubernetes, Nomad).**
  Delegar el ciclo de vida de los contenedores a un sistema de cluster.

## Resultado de la Decisión

**Opción elegida: B (Docker Compose).**

**Por qué:**

- Docker Compose es la herramienta natural de agrupación para un único host,
  que es exactamente nuestro caso (una EC2 t2.micro). No introduce conceptos
  nuevos — todos los miembros del equipo ya entienden `docker run` y
  `Dockerfile`, y el salto cognitivo a `docker-compose.yml` es trivial.
- El cambio en el pipeline es **quirúrgico**: reemplazamos el bloque de
  `docker build / stop / rm / run` por `docker compose down && docker
  compose up -d --build`. No tocamos los jobs `test` ni `build-docker`: el
  primero sigue siendo el gate de calidad del PR, y el segundo sigue
  funcionando como smoke test del Dockerfile. Opción C implicaría rediseñar
  el pipeline entero y aprender una herramienta nueva.
- El job `build-docker` actual construye la imagen pero **no la sube a
  ningún registry** (ni GHCR ni ECR): es efectivamente un test de que el
  `docker build` compila limpio, nada más. Esto sigue siendo válido en Fase
  1 porque el build real se hace en la EC2 con `--build` al momento del
  `docker compose up`. Evitamos así el costo operativo de configurar un
  registry privado, cosa que la adenda sólo sugiere como "DEBERÍA", no como
  "DEBE".
- `docker compose up -d --build` hace rebuild únicamente del servicio que
  referencia `build: .` (la API). Prometheus y Grafana usan imágenes
  oficiales de Docker Hub y se pullean la primera vez, no en cada deploy.

### Consecuencias

- **Bueno, porque:** el estado del host se deriva íntegramente de un
  artefacto versionado (`docker-compose.yml`). Para reproducir producción en
  local, basta con ejecutar el mismo comando. El script SSH queda corto y
  robusto: si Compose falla, no deja el host a medio migrar porque baja
  todos los servicios antes de levantarlos.
- **Malo, porque:** seguimos construyendo la imagen en la propia instancia
  EC2 (ocupa CPU y disco de la misma máquina que sirve tráfico, aunque sea
  brevemente). La alternativa — pushear a un registry desde CI y pullear en
  EC2 — la dejamos para una fase futura donde el tiempo de build en la
  instancia sea un problema real.
- **No cambia:** los jobs `test` y `build-docker` del pipeline, el Dockerfile
  de la API, ni la estructura de secrets (`EC2_SSH_KEY`). Sólo se modifica
  el bloque `script:` del job `deploy`.
