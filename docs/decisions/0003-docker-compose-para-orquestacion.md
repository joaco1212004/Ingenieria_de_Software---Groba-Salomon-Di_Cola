# Docker Compose para orquestación local de contenedores en EC2

## Contexto y Declaración del Problema

A partir del [ADR-0002](0002-dockerizacion-de-fastapi.md) la API se ejecuta
como un contenedor Docker sobre una instancia EC2. Con la incorporación de
Prometheus, Node Exporter y Grafana (ver ADRs
[0006](0006-prometheus-para-metricas-de-la-api.md),
[0007](0007-node-exporter-para-metricas-de-computo.md) y
[0008](0008-grafana-para-dashboards-y-alertas.md)), el producto pasa a ser un
**conjunto de contenedores que comparten red, dependen entre sí y necesitan
volúmenes persistentes** (p. ej. la base de datos de Grafana). Hace falta
elegir cómo orquestar este conjunto.

El pipeline original de CD ejecutaba `docker run` directamente vía SSH, lo
cual deja de ser viable: cada `docker run` aislado obliga a definir
`--network`, `--volume` y dependencias manualmente, con alta probabilidad de
que la instancia quede en un estado inconsistente si cualquier comando falla.

## Factores de Decisión

- Costo operativo y curva de aprendizaje (somos tres personas en un
  cuatrimestre).
- Cantidad de hosts a orquestar (hoy, **uno**: una EC2 t2.micro).
- Reproducibilidad local del entorno de producción.
- Costo monetario sobre los créditos de AWS Academy.

## Opciones Consideradas

- **Opción A — Docker Compose self-hosted en la EC2.** Versionamos un
  `docker-compose.yml` en la raíz del repo. El despliegue se reduce a `git
  pull && docker compose up -d --build`. Compose resuelve red, orden de
  arranque y volúmenes.
- **Opción B — Amazon ECS con Fargate.** Definimos task definitions y un
  service por contenedor. AWS gestiona el ciclo de vida; no necesitamos EC2.
- **Opción C — Amazon EKS (Kubernetes gestionado).** Cluster Kubernetes
  administrado por AWS, con manifiestos versionados.
- **Opción D — `docker run` por servicio sobre la misma EC2.** Mantener el
  modelo del pipeline original sumando líneas para cada nuevo contenedor.

## Resultado de la Decisión

**Opción elegida: A (Docker Compose self-hosted).**

**Por qué:**

- Docker Compose es la herramienta natural de agrupación para un único host,
  que es exactamente nuestro caso. No introduce conceptos nuevos: el equipo
  ya entiende `docker run` y `Dockerfile`, y el salto cognitivo a
  `docker-compose.yml` es trivial.
- ECS/Fargate y EKS son orquestadores diseñados para flotas multi-host con
  necesidades de auto-scaling, alta disponibilidad y service discovery
  distribuido. **Ninguno de esos requisitos aplica en Fase 1**: la agenda
  exige un mock sobre una única instancia. Adoptarlos sería sobre-ingeniería
  con costo de aprendizaje y de créditos AWS (Fargate cobra por vCPU/hora
  asignada incluso al ralentí; EKS cobra USD 0,10/hora por cluster).
- La opción D queda descartada por el problema de consistencia descrito en el
  contexto: con cuatro contenedores que comparten red y volúmenes, mantener
  el orquestado a mano vía `docker run` es propenso a estados parciales.
- El `docker-compose.yml` se versiona en el repo y describe la totalidad del
  estado del host. Reproducir producción en local requiere literalmente el
  mismo comando que en EC2.

### Consecuencias

- **Bueno, porque:** el estado del host se deriva íntegramente de un
  artefacto versionado; el script SSH del CD queda corto y robusto (`docker
  compose down && docker compose up -d --build`); el mismo comando
  funciona en la laptop de cualquier miembro del equipo.
- **Malo, porque:** seguimos atados a una única instancia EC2 — si la VM
  cae, caen todos los servicios (incluido el monitoreo). No hay
  auto-recuperación a nivel de host. Es un trade-off explícito a cambio de
  simplicidad.
- **No cambia:** los jobs `test` y `build-docker` del pipeline, el
  `Dockerfile` de la API ni la estructura de secrets (`EC2_SSH_KEY`).
- **Reversibilidad:** las imágenes producidas son las mismas que correrían
  sobre ECS o EKS, así que migrar en una fase futura no implica reescribir
  los servicios, sólo describirlos en el formato del nuevo orquestador.

### Confirmación

Se verifica con la presencia del archivo `docker-compose.yml` en la raíz del
repositorio y con la ejecución exitosa del job `deploy` del
[pipeline de CI](../../.github/workflows/ci.yml), cuyo último paso ejecuta
`docker compose up -d --build` sobre la EC2.