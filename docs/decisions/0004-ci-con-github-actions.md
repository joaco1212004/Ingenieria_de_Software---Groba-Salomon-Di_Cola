# CI con GitHub Actions

## Contexto y Declaración del Problema

La agenda técnica de la Fase 1 establece que el sistema **DEBE** implementar
un pipeline de Integración Continua que (a) ejecute pruebas unitarias y de
integración tras cada commit o pull request, (b) realice análisis estático
de código, y (c) genere artefactos inmutables (imágenes Docker) listos para
despliegue. Necesitamos elegir el motor de CI sobre el cual construir este
pipeline.

El repositorio del proyecto está alojado en GitHub. La cátedra otorga
créditos de AWS Academy, lo cual habilita el uso de servicios nativos de AWS
como CodeBuild + CodePipeline. Convive entonces la opción del CI integrado
al gestor de repositorio (GitHub Actions) con la opción del CI nativo del
cloud provider.

## Factores de Decisión

- Acoplamiento al gestor de repositorios (los PRs viven en GitHub).
- Costo monetario y consumo de créditos de AWS Academy, que son finitos y
  compartidos con el cómputo de producción.
- Curva de configuración inicial: el pipeline tiene que estar funcionando en
  la primera semana de Fase 1.
- Disponibilidad de runners gratuitos para repositorios públicos.

## Opciones Consideradas

- **Opción A — GitHub Actions.** Pipeline definido en
  `.github/workflows/ci.yml`, ejecutado por runners hospedados por GitHub.
- **Opción B — AWS CodeBuild + CodePipeline.** CodeBuild ejecuta los jobs
  (tests, lint, build docker) y CodePipeline orquesta el flujo,
  integrado con GitHub vía webhook.
- **Opción C — Jenkins self-hosted en EC2.** Un servidor Jenkins corriendo
  sobre los créditos de AWS Academy, configurado por GUI.

## Resultado de la Decisión

**Opción elegida: A (GitHub Actions).**

**Por qué:**

- **Cero fricción de integración:** los eventos de PR y push ya viven en
  GitHub. Actions corre nativamente sobre estos eventos sin necesidad de
  configurar webhooks, IAM roles cross-account ni tokens de acceso. La
  experiencia para el revisor de un PR (ver el check ✓/✗ junto al commit)
  es instantánea.
- **Costo nulo en repositorios públicos:** GitHub provee runners
  hospedados ilimitados para repos públicos. No consumimos créditos de AWS
  Academy en CI, que son finitos y los queremos preservar para correr la
  EC2 de producción durante todo el cuatrimestre.
- **Configuración como código en el mismo repo:** el archivo
  [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) se versiona
  junto al código que prueba. Un PR que cambia tests y la configuración de
  CI se evalúa atómicamente. CodePipeline, en cambio, mezcla configuración
  en consola AWS y `buildspec.yml`, partiendo el pipeline en dos fuentes
  de verdad.
- **Curva de aprendizaje mínima:** el equipo ya conoce la sintaxis
  declarativa YAML de Actions y el ecosistema de actions reutilizables
  (`actions/checkout`, `actions/setup-python`, `appleboy/ssh-action`).
  Jenkins implicaría aprender Groovy + administrar un servidor; CodeBuild
  implicaría aprender el modelo de IAM + buildspec.

### Consecuencias

- **Bueno, porque:** el pipeline es código versionado en el mismo repo; no
  consume créditos de AWS Academy; la integración con PRs es nativa; la
  contratación de capacidades (matriz de versiones, paralelismo, caching)
  se reduce a editar YAML.
- **Malo, porque:** quedamos atados al ecosistema de GitHub y a la
  disponibilidad de sus runners hospedados. Si en algún momento el
  proyecto se moviera a GitLab/Bitbucket o se volviera privado con muchos
  minutos de uso, habría que reevaluar. Para el horizonte temporal de este
  cuatrimestre el riesgo es despreciable.
- **No exploramos** una integración CodePipeline → GitHub Actions: no
  agrega valor en un escenario donde toda la operación está en GitHub y la
  infra cabe en una sola EC2.

### Confirmación

Se verifica con la existencia del archivo
[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml), que define los
jobs `test` (pytest + black) y `build-docker`, y con el badge de estado
verde en los pull requests del repositorio.