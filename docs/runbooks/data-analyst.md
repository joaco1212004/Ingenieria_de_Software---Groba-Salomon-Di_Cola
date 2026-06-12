# Runbook: Data analyst - validar datos para publicar un dashboard

## Proposito y disparador

Este runbook describe como validar que los datos estan listos para publicar o actualizar un dashboard de produccion de pozos no convencionales. Se ejecuta antes de mostrar un tablero a usuarios no tecnicos, despues de un cambio en Gold o cuando un usuario reporta que una metrica parece desactualizada o inconsistente.

El objetivo del data analyst no es operar la infraestructura, sino decidir si la informacion disponible es suficientemente fresca, completa y explicable para consumo de negocio.

## Rol, dueno y prerrequisitos

El dueno es el data analyst. Necesita acceso a Dagster UI, al dashboard BI, a la documentacion del modelo de datos y al glosario de metricas. Para acciones tecnicas, coordina con data engineer o analytics engineer.

Prerrequisitos:

- Dagster UI debe estar accesible en `http://api-hidraulicos-tipazos.duckdns.org:3001`.
- Debe existir una corrida exitosa reciente de `bronze_daily_job`.
- La metrica o dashboard debe tener owner y definicion documentada.
- El data analyst debe conocer la fecha de datos esperada para la entrega o demo.

## Pasos

1. Entrar a Dagster UI:

   ```text
   http://api-hidraulicos-tipazos.duckdns.org:3001
   ```

2. Verificar que el job `bronze_daily_job` tenga una corrida `SUCCESS` para la fecha esperada.

3. Confirmar que los dos assets Bronze estan materializados para la misma `fecha_extraccion`:

   ```text
   listado_pozos_bronze
   produccion_no_convencional_bronze
   ```

4. Revisar la documentacion de la metrica antes de publicar:

   ```text
   nombre de metrica
   grano
   filtros permitidos
   fecha de ultima actualizacion
   owner tecnico
   ```

5. Abrir el dashboard BI y validar los filtros principales:

   ```text
   periodo
   operador
   provincia
   tipo de producto
   ```

6. Comparar una muestra de la metrica contra una consulta o calculo de control acordado con el analytics engineer.

7. Verificar que el dashboard muestre o comunique la fecha de ultima actualizacion.

8. Publicar el dashboard solo si la corrida es exitosa, la frescura esta dentro del umbral y la metrica coincide con la definicion documentada.

9. Si se detecta un problema, registrar el hallazgo con:

   ```text
   dashboard afectado
   metrica afectada
   fecha observada
   fecha esperada
   captura o query de evidencia
   owner al que se escala
   ```

## Validacion

El dashboard esta listo si:

- Los datos tienen frescura menor o igual a 24 horas respecto de la ultima corrida esperada.
- Las dos fuentes Bronze de la fecha estan materializadas.
- Las metricas visibles coinciden con la definicion del modelo Gold.
- Los filtros no generan totales imposibles, negativos o vacios inesperados.
- El usuario de negocio puede ver la fecha de ultima actualizacion o esta documentada junto al tablero.

## Si algo falla

Si Dagster no tiene corrida exitosa, no publicar el dashboard como actualizado. Escalar al data engineer con la fecha esperada y el run fallido.

Si Bronze esta bien pero la metrica no coincide, escalar al analytics engineer con la definicion esperada y una muestra del error.

Si el dashboard esta caido pero los datos estan correctos, registrar incidente de BI y usar una consulta o export controlado como plan B para la demo.

Si hay dudas de definicion de negocio, no cambiar filtros o formulas en silencio. Registrar la decision pendiente y pedir aprobacion del owner de la metrica.

## Consideraciones no funcionales

Frescura: para este proyecto, el data analyst acepta datos diarios. Si la ultima corrida exitosa tiene mas de 24 horas, el dashboard debe marcarse como no actualizado.

Costo: el data analyst no debe pedir backfills masivos para explorar hipotesis. Primero valida con una fecha puntual y solo solicita reprocesos adicionales si hay impacto real en una entrega o metrica publicada.

Privacidad: las fuentes usadas son publicas y no contienen PII sensible, pero las capturas de dashboards y exports deben compartirse solo dentro del equipo o la catedra.

Gobernanza: una metrica sin definicion documentada no se considera oficial. Puede usarse para exploracion, pero no para una demo o decision de negocio.

## Decision funcional justificada

Decision: el dashboard publica metricas de produccion solo cuando `listado_pozos_bronze` y `produccion_no_convencional_bronze` estan disponibles para la misma `fecha_extraccion`.

Desde la perspectiva del data analyst, esta decision evita contar una historia mezclando catastro de pozos de una fecha con produccion de otra. Aunque ambas fuentes sean publicas y parezcan independientes, el usuario de negocio espera que los filtros por operador, provincia o pozo expliquen la produccion del mismo corte temporal. Si las fechas no coinciden, el analista puede terminar justificando diferencias que en realidad son un problema de sincronizacion del pipeline.

## Decision no funcional justificada

Decision: el dashboard debe mostrar datos con una frescura maxima de 24 horas o quedar marcado como no actualizado.

Desde la perspectiva del data analyst, la frescura es parte de la confianza del tablero. Un dato viejo puede ser tecnicamente correcto, pero si el usuario cree que esta viendo el ultimo snapshot disponible, la interpretacion de negocio queda sesgada. El umbral de 24 horas acompana la frecuencia diaria del pipeline y evita gastar recursos en actualizaciones innecesarias, manteniendo una garantia clara para usuarios no tecnicos.
