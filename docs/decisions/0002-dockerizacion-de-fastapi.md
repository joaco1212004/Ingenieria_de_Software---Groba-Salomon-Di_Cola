# Dockerización de FastAPI

## Contexto y Declaración del Problema

La agenda técnica de la Fase 1 establece que **todos los componentes de la
Plataforma Predictiva DEBEN ser contenerizados utilizando Docker** para
asegurar portabilidad, consistencia y reproducibilidad entre ambientes. La API
mock está implementada en FastAPI (ver
[ADR-0001](0001-fast-api.md)) y necesitamos definir
cómo empaquetarla y desplegarla sobre la infraestructura de AWS Academy
disponible.

Existen tres caminos razonables: (1) empaquetar la aplicación en una imagen
Docker y correrla sobre una instancia EC2, (2) instalar Python/Poetry y correr
`uvicorn` directamente sobre la EC2 sin contenedor, o (3) desplegar la API
como una función serverless sobre AWS Lambda con un adaptador ASGI
(p. ej. Mangum).

## Factores de Decisión

- Cumplimiento estricto del requisito **DEBE** de la agenda (contenerización
  obligatoria).
- Paridad entre el entorno de desarrollo, el de CI y el de producción.
- Simplicidad operativa para un equipo de tres personas en una asignatura
  cuatrimestral.
- Reversibilidad de la elección si en fases futuras necesitamos migrar a un
  orquestador real.

## Opciones Consideradas

- **Opción A — Imagen Docker corriendo en EC2.** Un `Dockerfile` basado en
  `python:3.12-slim` con Poetry, ejecutado en una instancia EC2 t2.micro.
- **Opción B — Despliegue directo en EC2.** Instalar Python y dependencias en
  el host y correr `uvicorn` como servicio systemd.
- **Opción C — AWS Lambda + API Gateway.** Empaquetar la app con Mangum y
  desplegarla como función serverless detrás de API Gateway.

## Resultado de la Decisión

**Opción elegida: A (Imagen Docker corriendo en EC2).**

**Por qué:**

- Es la única que satisface el requisito **DEBE** de contenerización de la
  agenda. Las opciones B y C lo incumplen o requieren acrobacias (B no usa
  contenedor; C usa un paquete .zip o una imagen Lambda con un runtime
  distinto al runtime de la app local).
- Garantiza paridad entre entornos: la misma imagen que pasa el job
  `build-docker` del CI es la que se reconstruye y corre en la EC2 durante el
  `deploy`. Eliminamos la clase de bug "funciona en mi máquina pero no en el
  servidor" causada por versiones distintas de Python o de librerías
  transitivas.
- El `Dockerfile` actual es minimalista (14 líneas) y aprovecha `poetry.lock`
  para builds reproducibles. La curva operativa es prácticamente nula: cada
  miembro del equipo puede levantar la API en local con un `docker build` +
  `docker run`.
- Mantiene la decisión **reversible**: si en una fase posterior la imagen
  necesita correr sobre ECS, EKS o Fargate (ver ADR-0003), no requiere
  reescribir nada — la imagen es la misma; cambia sólo el orquestador.

### Consecuencias

- **Bueno, porque:** cumple el requisito explícito de la agenda;
  el desarrollo y la CI usan exactamente el mismo artefacto que producción;
  abre la puerta a sumar más servicios contenerizados (Prometheus, Grafana)
  sin reescribir la base.
- **Malo, porque:** corre sobre una única EC2 t2.micro, lo cual no provee
  alta disponibilidad ni auto-scaling. Para Fase 1 (mock con datos
  estáticos) es aceptable; en fases futuras puede volverse un
  cuello de botella.
- **Trade-off conocido:** descartamos Lambda pese a su modelo
  pay-per-invocation porque el cold-start de un runtime Python con
  dependencias pesadas (FastAPI + Pydantic + posibles librerías de ML
  futuras) puede empujarnos por encima del KPI de latencia < 5s definido en
  la agenda.

### Confirmación

La implementación se confirma con la existencia del
[`Dockerfile`](../../Dockerfile) en la raíz del repositorio, con el job
`build-docker` del [pipeline de CI](../../.github/workflows/ci.yml) que
construye la imagen en cada push, y con el contenedor corriendo sobre el
dominio público `api-hidraulicos-tipazos.duckdns.org`.