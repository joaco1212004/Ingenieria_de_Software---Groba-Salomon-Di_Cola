# CD con GitHub Actions vía SSH deploy a EC2

## Contexto y Declaración del Problema

La adenda técnica exige Despliegue Continuo a los ambientes destino con
verificación automática de salud post-despliegue. En el
[ADR-0004](0004-ci-con-github-actions.md) decidimos usar GitHub Actions
como motor de CI; queda definir cómo se ejecuta el paso de **deploy** que
publica los cambios mergeados a `main` sobre la instancia EC2 de
producción.

La EC2 corre sobre AWS Academy. Los créditos están disponibles pero se
quieren preservar para cómputo, no para piezas adicionales de
infraestructura de despliegue. Existen dos caminos típicos: extender el
mismo pipeline de Actions para que abra una sesión SSH contra la EC2 y
ejecute el redeploy, o introducir AWS CodeDeploy con un agent en la
instancia y describir el despliegue como una aplicación AWS administrada.

## Factores de Decisión

- Reutilización del motor de CI ya elegido (GitHub Actions).
- Restricción operativa: una única EC2 t2.micro, sin auto-scaling ni
  rolling updates entre N instancias.
- Costo en créditos de AWS Academy y en tiempo de configuración (IAM,
  agents, S3 bucket de artefactos).
- Simplicidad del modelo mental para el equipo.

## Opciones Consideradas

- **Opción A — GitHub Actions con `appleboy/ssh-action` contra EC2.** El
  job `deploy` se conecta por SSH usando una llave privada guardada como
  secret y ejecuta `git pull && docker compose up -d --build`.
- **Opción B — AWS CodeDeploy.** Instalar el agent de CodeDeploy en la
  EC2, definir un `appspec.yml`, subir artefactos a S3 y disparar
  despliegues desde CodePipeline o desde una action de AWS.
- **Opción C — Self-hosted runner de GitHub Actions sobre la EC2.** El job
  de deploy corre directamente dentro del runner, sobre el host destino,
  sin SSH.

## Resultado de la Decisión

**Opción elegida: A (GitHub Actions con SSH deploy contra EC2).**

**Por qué:**

- Es la **continuación natural** del ADR-0004: el mismo workflow YAML
  define `test`, `build-docker` y `deploy`, los tres con dependencias
  explícitas vía `needs:`. El job `deploy` está además protegido por
  `if: github.ref == 'refs/heads/main'`, garantizando que sólo `main`
  llega a producción.
- **CodeDeploy es overkill para una sola instancia:** sus features
  diferenciales (rolling, blue/green, canary entre N instancias detrás de
  un ELB) no se usan cuando hay un único host. A cambio paga el costo de
  configurar un IAM role, instalar y mantener el agent, mantener un S3
  bucket de artefactos y aprender el formato `appspec.yml`. Para Fase 1
  ese costo es injustificable.
- **El self-hosted runner sobre la EC2 introduce un riesgo de seguridad
  innecesario:** un runner self-hosted con acceso a internet ejecuta código
  arbitrario que viene de pull requests; si alguien forkea y abre un PR
  malicioso, el código se ejecuta en el host de producción. SSH desde un
  runner hospedado por GitHub aísla mejor el blast radius.
- **`docker compose down && up -d --build` es atómico para nuestro caso:**
  baja todos los servicios y los relevanta. El downtime es de ~5 segundos
  en una t2.micro y aceptable para un mock de Fase 1. Si más adelante el
  KPI de uptime exige zero-downtime, la decisión es revisable
  reemplazando este bloque por un esquema con dos contenedores y un
  proxy delante.

### Consecuencias

- **Bueno, porque:** el workflow es un único archivo, leíble de punta a
  punta; no consume créditos AWS adicionales fuera de la EC2; el rollback
  es un `git revert` + push (el deploy se reactiva solo).
- **Malo, porque:** la llave SSH vive como secret en GitHub. Su rotación
  exige actualizar el secret manualmente. Lo aceptamos porque es la única
  credencial sensible del flujo.
- **Malo, porque:** el deploy compila la imagen sobre la propia EC2,
  consumiendo CPU del host de producción durante el build. Para una
  t2.micro y un build chico es marginal; en una fase futura con builds
  pesados conviene migrar a `docker push` desde el CI a un registry y
  `docker pull` desde la EC2.
- **No tiene rolling/canary:** el deploy es un reinicio del compose. Lo
  hacemos consciente y queda registrado para revisar si los KPIs de
  disponibilidad lo exigen.

### Confirmación

Se verifica con la ejecución exitosa del job `deploy` en
[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) tras cada
merge a `main`, y con el contenedor de la API respondiendo en el dominio
`api-hidraulicos-tipazos.duckdns.org` luego del despliegue.