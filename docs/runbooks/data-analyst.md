# Runbook: Data analyst - validar datos para publicar un dashboard

## Propósito y disparador

Este runbook explica cómo validar que los datos estén listos para publicar o actualizar un dashboard de producción de pozos no convencionales. Se ejecuta antes de mostrar un tablero a usuarios no técnicos, después de un cambio en Gold o cuando un usuario reporta que una métrica parece desactualizada o inconsistente.

El objetivo del data analyst no es operar la infraestructura, sino decidir si la información disponible es suficientemente fresca, completa y explicable para consumo de negocio.

## Rol, dueño y prerrequisitos

El dueño del procedimiento es el data analyst. Necesita acceso a Dagster UI, al dashboard BI, a la documentación del modelo de datos y al glosario de métricas. Para acciones técnicas, coordina con el data engineer o el analytics engineer.

Prerrequisitos:

- Dagster UI debe estar accesible en `http://api-hidraulicos-tipazos.duckdns.org:3001`.
- Debe existir una corrida exitosa reciente de `bronze_daily_job`.
- La métrica o dashboard debe tener owner y definición documentada.
- El data analyst debe conocer la fecha de datos esperada para la entrega o demo.

## Pasos

1. Entrar a Dagster UI:

   ```text
   http://api-hidraulicos-tipazos.duckdns.org:3001
   ```

2. Verificar que el job `bronze_daily_job` tenga una corrida `SUCCESS` para la fecha esperada.

3. Confirmar que los dos assets Bronze estén materializados para la misma `fecha_extraccion`:

   ```text
   listado_pozos_bronze
   produccion_no_convencional_bronze
   ```

4. Revisar la documentación de la métrica antes de publicar:

   ```text
   nombre de métrica
   grano
   filtros permitidos
   fecha de última actualización
   owner técnico
   ```

5. Abrir el dashboard BI y validar los filtros principales:

   ```text
   período
   operador
   provincia
   tipo de producto
   ```

6. Comparar una muestra de la métrica contra una consulta o cálculo de control acordado con el analytics engineer.

7. Verificar que el dashboard muestre o comunique la fecha de última actualización.

8. Publicar el dashboard solo si la corrida es exitosa, la frescura está dentro del umbral y la métrica coincide con la definición documentada.

9. Si se detecta un problema, registrar el hallazgo con:

   ```text
   dashboard afectado
   métrica afectada
   fecha observada
   fecha esperada
   captura o query de evidencia
   owner al que se escala
   ```

## Validación

El dashboard está listo si:

- Los datos tienen frescura menor o igual a 24 horas respecto de la última corrida esperada.
- Las dos fuentes Bronze de la fecha están materializadas.
- Las métricas visibles coinciden con la definición del modelo Gold.
- Los filtros no generan totales imposibles, negativos o vacíos inesperados.
- El usuario de negocio puede ver la fecha de última actualización o esta queda documentada junto al tablero.

## Si algo falla

Si Dagster no tiene corrida exitosa, no se publica el dashboard como actualizado. Se escala al data engineer con la fecha esperada y el run fallido.

Si Bronze está bien pero la métrica no coincide, se escala al analytics engineer con la definición esperada y una muestra del error.

Si el dashboard está caído pero los datos están correctos, se registra un incidente de BI y se usa una consulta o export controlado como plan B para la demo.

Si hay dudas de definición de negocio, no se cambian filtros o fórmulas en silencio. Se registra la decisión pendiente y se pide aprobación del owner de la métrica.

## Consideraciones no funcionales

Frescura: para este proyecto, el data analyst acepta datos diarios. Si la última corrida exitosa tiene más de 24 horas, el dashboard debe marcarse como no actualizado.

Costo: el data analyst no debe pedir backfills masivos para explorar hipótesis. Primero valida con una fecha puntual y solo solicita reprocesos adicionales si hay impacto real en una entrega o métrica publicada.

Privacidad: las fuentes usadas son públicas y no contienen PII sensible, pero las capturas de dashboards y exports deben compartirse solo dentro del equipo o la cátedra.

Gobernanza: una métrica sin definición documentada no se considera oficial. Puede usarse para exploración, pero no para una demo o decisión de negocio.

## Decisión funcional justificada

Decisión: el dashboard publica métricas de producción solo cuando `listado_pozos_bronze` y `produccion_no_convencional_bronze` están disponibles para la misma `fecha_extraccion`.

Desde la perspectiva del data analyst, esta decisión evita contar una historia mezclando catastro de pozos de una fecha con producción de otra. Aunque ambas fuentes sean públicas y parezcan independientes, el usuario de negocio espera que los filtros por operador, provincia o pozo expliquen la producción del mismo corte temporal. Si las fechas no coinciden, el analista puede terminar justificando diferencias que en realidad son un problema de sincronización del pipeline.

## Decisión no funcional justificada

Decisión: el dashboard debe mostrar datos con una frescura máxima de 24 horas o quedar marcado como no actualizado.

Desde la perspectiva del data analyst, la frescura es parte de la confianza del tablero. Un dato viejo puede ser técnicamente correcto, pero si el usuario cree que está viendo el último snapshot disponible, la interpretación de negocio queda sesgada. El umbral de 24 horas acompaña la frecuencia diaria del pipeline y evita gastar recursos en actualizaciones innecesarias, manteniendo una garantía clara para usuarios no técnicos.
