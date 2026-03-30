# Usar Registros de Decisiones Arquitectónicas en Markdown

## Contexto y Declaración del Problema

Queremos registrar las decisiones arquitectónicas tomadas en este proyecto, independientemente de si las decisiones conciernen a la arquitectura ("registro de decisión arquitectónica"), al código u otros ámbitos.
¿Qué formato y estructura deben seguir estos registros?

## Opciones Consideradas

* [MADR](https://adr.github.io/madr/) 4.0.0 – Los Registros de Decisiones Arquitectónicas en Markdown
* [Plantilla de Michael Nygard](http://thinkrelevance.com/blog/2011/11/15/documenting-architecture-decisions) – La primera encarnación del término "ADR"
* [Decisiones Arquitectónicas Sostenibles](https://www.infoq.com/articles/sustainable-architectural-design-decisions) – Las sentencias en forma Y
* Otras plantillas listadas en <https://github.com/joelparkerhenderson/architecture_decision_record>
* Sin formato – Sin convenciones para el formato y estructura de archivos

## Resultado de la Decisión

Opción elegida: "MADR 4.0.0", porque

* Los supuestos implícitos deben hacerse explícitos.
  La documentación de diseño es importante para que las personas puedan comprender las decisiones en el futuro.
  Ver también ["A rational design process: How and why to fake it"](https://doi.org/10.1109/TSE.1986.6312940).
* MADR permite capturar de forma estructurada cualquier decisión.
* El formato MADR es ligero y se adapta a nuestro estilo de desarrollo.
* La estructura MADR es comprensible y facilita su uso y mantenimiento.
* El proyecto MADR está activo.
