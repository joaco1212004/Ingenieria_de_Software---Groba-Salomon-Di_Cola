# Runbook: Analytics engineer - cambiar una métrica del modelo Gold

## Propósito y disparador

Este runbook explica cómo agregar o modificar una métrica analítica del modelo Gold, por ejemplo producción mensual de petróleo o gas por operador, provincia o formación. Se ejecuta cuando un stakeholder pide una métrica nueva, cuando cambia la definición de negocio de una métrica existente o cuando un cambio en Bronze/Silver obliga a ajustar el modelo dimensional.

El procedimiento aplica a la capa Silver/Gold definida por la arquitectura medallion del proyecto y busca que modelos, tests de calidad, documentación y dashboards queden alineados.

## Rol, dueño y prerrequisitos

El dueño del procedimiento es el analytics engineer. Necesita acceso al repositorio, permiso para abrir PRs, capacidad de ejecutar tests locales/CI y acceso de lectura a Dagster para verificar que la partición Bronze base existe.

Prerrequisitos:

- La partición Bronze de la fecha de trabajo debe estar materializada para los dos datasets.
- La definición de la métrica debe estar acordada con el data analyst.
- El cambio debe incluir documentación del grano, dimensiones afectadas y reglas de calidad.
- Si el proyecto dbt todavía no está desplegado, este runbook se usa como criterio de aceptación para implementarlo antes de publicar Gold.

## Pasos

1. Confirmar la necesidad de negocio de la métrica:

   ```text
   Nombre: producción mensual no convencional
   Grano: mes, pozo, operador, provincia, tipo de producto
   Consumidor: dashboard BI de producción
   ```

2. Verificar que Bronze tenga datos para la fecha base:

   ```bash
   bash scripts/materialize-bronze.sh YYYY-MM-DD
   ```

3. Revisar columnas disponibles en los CSV crudos de Bronze y decidir el mapeo hacia Silver:

   ```text
   fuente produccion_no_convencional -> staging de producción
   fuente listado_pozos -> staging de pozos/operadores
   ```

4. Agregar o modificar modelos Silver para tipar columnas, normalizar nombres y resolver claves naturales.

5. Agregar o modificar modelos Gold con modelo estrella:

   ```text
   fact_produccion_mensual
   dim_pozo
   dim_operador
   dim_fecha
   dim_geografia
   ```

6. Agregar tests de calidad asociados a la métrica:

   ```text
   schema: columnas obligatorias y tipos esperados
   completeness: campos clave no nulos
   uniqueness: claves de dimensiones sin duplicados
   accepted ranges: volúmenes no negativos
   relationships: fact table referencia dimensiones existentes
   ```

7. Actualizar la documentación del modelo de datos con grano, dimensiones, surrogate keys y decisión SCD.

8. Correr tests locales o esperar el CI del PR:

   ```bash
   poetry run pytest
   poetry run black --check .
   ```

9. Pedir revisión del data analyst para validar nombres de métricas, filtros y semántica de negocio.

10. Mergear solo si CI y revisión funcional pasan.

## Validación

El cambio está listo si:

- La fact table mantiene un grano único y documentado.
- Las dimensiones tienen claves estables y no duplicadas.
- Los tests de calidad pasan y sus resultados quedan persistidos o publicados como artefacto del pipeline.
- La métrica calculada coincide con una muestra manual tomada desde el CSV fuente.
- El dashboard o consulta BI que consume la métrica no cambia de significado sin aprobación del data analyst.

## Si algo falla

Si falla un test de calidad, no se promueve el cambio a Gold. El analytics engineer corrige el modelo o ajusta la regla si el data analyst confirma que la regla estaba mal definida.

Si la métrica no coincide con el cálculo manual, se congela el PR y se revisa el grano. La causa más común es duplicar filas al unir producción con dimensiones no deduplicadas.

Si falta una columna en Bronze, se escala al data engineer para confirmar si cambió la fuente o si se materializó una partición incompleta.

Si un dashboard se rompe, se vuelve a la definición anterior de la métrica en Gold o se marca el dashboard como no confiable hasta que el data analyst valide el cambio.

## Consideraciones no funcionales

Calidad: Gold no debe exponer métricas si los tests de schema, relaciones y rangos fallan. El equipo prioriza evitar métricas incorrectas antes que publicar rápido.

Frescura: el modelo Gold puede actualizarse después de Bronze, pero debe dejar visible la fecha de última actualización para que el data analyst no consuma datos viejos sin saberlo.

Costo: las transformaciones deben correr sobre la EC2 actual mientras el volumen lo permita. No se agrega infraestructura paga salvo que el tiempo de proceso bloquee la entrega.

Gobernanza: cada métrica nueva debe estar documentada con definición, grano y owner. Si no está documentada, no se publica como métrica oficial.

## Decisión funcional justificada

Decisión: la métrica principal de Gold se modela como producción mensual a grano pozo-mes-producto, con dimensiones separadas para pozo, operador, fecha y geografía.

Desde la perspectiva del analytics engineer, esta decisión evita mezclar reglas de negocio dentro de dashboards. Si el grano está en la fact table y las dimensiones están normalizadas, una misma definición puede alimentar varias preguntas: producción por operador, por provincia, por cuenca o por período. Esto reduce inconsistencias entre reportes y hace que los tests de calidad detecten duplicaciones antes de que lleguen al usuario de negocio.

## Decisión no funcional justificada

Decisión: ningún cambio en Gold se mergea si rompe tests de calidad o si no actualiza la documentación del modelo.

Desde la perspectiva del analytics engineer, el costo de frenar un PR es menor que el costo de publicar una métrica incorrecta. El rol es responsable de que el warehouse sea confiable y reutilizable; por eso necesita que cada cambio deje evidencia verificable en CI, no solo una validación manual. Esta restricción también protege al data analyst, que consume Gold como fuente oficial y no debería redescubrir errores de modelado en el dashboard.
