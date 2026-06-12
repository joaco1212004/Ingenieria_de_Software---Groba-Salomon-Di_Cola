# Runbook: Analytics engineer - cambiar una metrica del modelo Gold

## Proposito y disparador

Este runbook describe como agregar o modificar una metrica analitica del modelo Gold, por ejemplo produccion mensual de petroleo/gas por operador, provincia o formacion. Se ejecuta cuando un stakeholder pide una nueva metrica, cuando cambia la definicion de negocio de una metrica existente o cuando un cambio en Bronze/Silver requiere ajustar el modelo dimensional.

El procedimiento aplica a la capa Silver/Gold definida por la arquitectura medallion del proyecto y debe mantener alineados modelos, tests de calidad, documentacion y dashboards.

## Rol, dueno y prerrequisitos

El dueno es el analytics engineer. Necesita acceso al repositorio, permiso para abrir PRs, capacidad de ejecutar tests locales/CI y acceso de lectura a Dagster para verificar que la particion Bronze base existe.

Prerrequisitos:

- La particion Bronze de la fecha de trabajo debe estar materializada para los dos datasets.
- La definicion de la metrica debe estar acordada con el data analyst.
- El cambio debe incluir documentacion del grano, dimensiones afectadas y reglas de calidad.
- Si el proyecto dbt todavia no esta desplegado, este runbook se usa como criterio de aceptacion para implementarlo antes de publicar Gold.

## Pasos

1. Confirmar la necesidad de negocio de la metrica:

   ```text
   Nombre: produccion mensual no convencional
   Grano: mes, pozo, operador, provincia, tipo de producto
   Consumidor: dashboard BI de produccion
   ```

2. Verificar que Bronze tiene datos para la fecha base:

   ```bash
   bash scripts/materialize-bronze.sh YYYY-MM-DD
   ```

3. Revisar columnas disponibles en los CSV crudos de Bronze y decidir el mapeo hacia Silver:

   ```text
   fuente produccion_no_convencional -> staging de produccion
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

6. Agregar tests de calidad asociados a la metrica:

   ```text
   schema: columnas obligatorias y tipos esperados
   completeness: campos clave no nulos
   uniqueness: claves de dimensiones sin duplicados
   accepted ranges: volumenes no negativos
   relationships: fact table referencia dimensiones existentes
   ```

7. Actualizar la documentacion del modelo de datos con grano, dimensiones, surrogate keys y decision SCD.

8. Correr tests locales o esperar el CI del PR:

   ```bash
   poetry run pytest
   poetry run black --check .
   ```

9. Pedir revision del data analyst para validar nombres de metricas, filtros y semantica de negocio.

10. Mergear solo si CI y revision funcional pasan.

## Validacion

El cambio esta listo si:

- La fact table mantiene un grano unico y documentado.
- Las dimensiones tienen claves estables y no duplicadas.
- Los tests de calidad pasan y sus resultados quedan persistidos o publicados como artefacto del pipeline.
- La metrica calculada coincide con una muestra manual tomada desde el CSV fuente.
- El dashboard o consulta BI que consume la metrica no cambia de significado sin aprobacion del data analyst.

## Si algo falla

Si falla un test de calidad, no se promueve el cambio a Gold. El analytics engineer corrige el modelo o ajusta la regla si el data analyst confirma que la regla estaba mal definida.

Si la metrica no coincide con el calculo manual, congelar el PR y revisar el grano. La causa mas comun es duplicar filas al unir produccion con dimensiones no deduplicadas.

Si falta una columna en Bronze, escalar al data engineer para confirmar si cambio la fuente o si se materializo una particion incompleta.

Si un dashboard se rompe, volver a la definicion anterior de la metrica en Gold o marcar el dashboard como no confiable hasta que el data analyst valide el cambio.

## Consideraciones no funcionales

Calidad: Gold no debe exponer metricas si los tests de schema, relaciones y rangos fallan. El equipo prioriza evitar metricas incorrectas sobre publicar rapido.

Frescura: el modelo Gold puede actualizarse despues de Bronze, pero debe dejar visible la fecha de ultima actualizacion para que el data analyst no consuma datos viejos sin saberlo.

Costo: las transformaciones deben correr sobre la EC2 actual mientras el volumen lo permita. No se agrega infraestructura paga salvo que el tiempo de proceso bloquee la entrega.

Gobernanza: cada metrica nueva debe estar documentada con definicion, grano y owner. Si no esta documentada, no se publica como metrica oficial.

## Decision funcional justificada

Decision: la metrica principal de Gold se modela como produccion mensual a grano pozo-mes-producto, con dimensiones separadas para pozo, operador, fecha y geografia.

Desde la perspectiva del analytics engineer, esta decision evita mezclar reglas de negocio dentro de dashboards. Si el grano esta en la fact table y las dimensiones estan normalizadas, una misma definicion puede alimentar varias preguntas: produccion por operador, por provincia, por cuenca o por periodo. Esto reduce inconsistencias entre reportes y hace que los tests de calidad detecten duplicaciones antes de que lleguen al usuario de negocio.

## Decision no funcional justificada

Decision: ningun cambio en Gold se mergea si rompe tests de calidad o si no actualiza la documentacion del modelo.

Desde la perspectiva del analytics engineer, el costo de frenar un PR es menor que el costo de publicar una metrica incorrecta. El rol es responsable de que el warehouse sea confiable y reutilizable; por eso necesita que cada cambio deje evidencia verificable en CI, no solo una validacion manual. Esta restriccion tambien protege al data analyst, que consume Gold como fuente oficial y no deberia redescubrir errores de modelado en el dashboard.
