# Utilización de FastAPI

## Contexto y Declaración del Problema

El equipo necesita elegir un framework web para el desarrollo del backend del producto. Dado que los integrantes del equipo tienen mayor experiencia con el ecosistema Python, se busca un framework que permita desarrollar APIs RESTful de manera eficiente, con buenas prácticas incorporadas y una curva de aprendizaje baja dentro del stack conocido.

## Opciones Consideradas

* FastAPI
* Flask
* Django REST Framework

## Resultado de la Decisión

Opción elegida: **FastAPI**, porque es la opción que mejor equilibra rendimiento, productividad del equipo y calidad del código dentro del stack Python. Ofrece validación automática de datos, documentación interactiva generada automáticamente y soporte nativo para programación asíncrona, lo que lo hace adecuado para el desarrollo de APIs modernas sin requerir configuración adicional significativa.

### Consecuencias

* Bueno, porque el equipo ya está familiarizado con Python, reduciendo la curva de aprendizaje.
* Bueno, porque la validación de datos con Pydantic y la generación automática de documentación (Swagger/OpenAPI) aceleran el desarrollo y reducen errores.
* Malo, porque al ser un framework más liviano que Django, la gestión de funcionalidades como autenticación, ORM o administración requiere integrar librerías adicionales de forma manual.

## Comparación de Opciones

| Criterio                        | FastAPI | Flask | Django REST Framework |
|---------------------------------|---------|-------|-----------------------|
| Familiaridad del equipo (Python)| Alta    | Alta  | Media                 |
| Rendimiento                     | Alto    | Medio | Medio                 |
| Validación automática           | Sí      | No    | Parcial               |
| Documentación auto-generada     | Sí      | No    | No                    |
| Soporte async nativo            | Sí      | Limitado | No               |
| Tiempo de configuración inicial | Bajo    | Bajo  | Alto                  |
| Tamaño del ecosistema           | Creciente | Maduro | Muy maduro         |

