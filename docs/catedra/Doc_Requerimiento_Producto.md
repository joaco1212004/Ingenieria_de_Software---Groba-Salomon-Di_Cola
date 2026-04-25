# Documento de Requerimientos: Plataforma Predictiva

**Versión:** Draft v0.1  
**Fecha:** Marzo 2026  
**Owner:** Equipo Ingeniería de Software  

---

## Índice

* [Resumen Ejecutivo](#resumen-ejecutivo)
* [Contexto / Problema](#contexto--problema)
* [Usuarios](#usuarios)
* [Casos de Uso](#casos-de-uso)
* [Objetivos Primarios](#objetivos-primarios)
* [Objetivos Secundarios](#objetivos-secundarios)
* [Alcance](#alcance)
* [Stakeholders](#stakeholders)
* [Requerimientos Funcionales](#requerimientos-funcionales)
* [Requerimientos No Funcionales](#requerimientos-no-funcionales)
* [Métricas de éxito (KPIs)](#métricas-de-éxito-kpis)
* [Dependencias y riesgos](#dependencias-y-riesgos)
* [Roadmap](#roadmap)
* [Preguntas abiertas](#preguntas-abiertas)

---

## Resumen Ejecutivo

Este documento describe los requerimientos para el desarrollo de una plataforma que permita pronosticar la producción futura de hidrocarburos.

El producto busca mejorar la previsibilidad del volumen producido y reducir la incertidumbre en la planificación operativa mediante una plataforma que permita a los equipos técnicos y de planificación optimizar la toma de decisiones y anticipar escenarios de producción.

**El sistema incluirá:**
* Módulo de carga e integración de datos históricos de producción, pozos y variables operativas.
* Motor de modelado y pronóstico basado en algoritmos estadísticos y/o de machine learning.
* Panel de visualización con dashboards interactivos y gráficos de tendencias.
* API REST para consulta, integración y consumo de resultados desde sistemas externos.
* Registro y trazabilidad de cambios en modelos y supuestos.

**Notas:**
* En este documento se utilizará la convención del [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
* En adición a lo presentado en este documento se emitirán agendas técnicas que especificarán en mayor detalle los requerimientos que **DEBE** cumplir cada fase de entrega.

---

## Contexto / Problema

Los equipos de planificación, ingeniería de reservorios y operaciones enfrentan dificultades para estimar con precisión la producción futura de hidrocarburos, lo que genera:

* Alta incertidumbre en la planificación operativa y presupuestaria.
* Decisiones reactivas basadas en información incompleta o desactualizada.
* Pérdida de oportunidades de optimización en pozos y activos.
* Dificultades para planificar inversiones, mantenimiento y compromisos comerciales.

Actualmente los pronósticos se realizan mediante planillas dispersas, modelos manuales o herramientas no integradas, con fuerte dependencia del conocimiento individual y limitada trazabilidad sobre los supuestos utilizados.

---

## Usuarios

A continuación se detallan los usuarios principales de la Plataforma de Predictiva, identificando sus roles y los casos de uso fundamentales que el sistema debe soportar:

| Rol del Usuario | Perfil/Equipo | Necesidad Clave |
| :--- | :--- | :--- |
| **Analista de Planificación** | Equipo de Planificación y Presupuesto | Evaluar información histórica de producción y pronósticos para la planificación financiera, operativa y la elaboración de presupuestos (anuales y plurianuales). |
| **Ingeniero de Reservorios** | Equipo de Ingeniería de Reservorios | Evaluar el impacto de diferentes estrategias de desarrollo y operación, simular escenarios de producción y validar la precisión de los modelos predictivos. |
| **Arquitecto/Especialista de Datos** | Equipo de Gobernanza de Datos/IT | Asegurar la calidad, la seguridad y la trazabilidad de los datos de entrada y los resultados del pronóstico, cumpliendo con las políticas de gobernanza. |

---

## Casos de Uso

| Caso de Uso | Descripción |
| :--- | :--- |
| **1. Generación y Visualización de Pronóstico Base** | El sistema debe permitir a los **Analistas de Planificación** visualizar el pronóstico de producción para diferentes horizontes (corto, medio y largo plazo), con la capacidad de desagregar los resultados por pozo, yacimiento o activo. |
| **2. Simulación y Comparación de Escenarios** | Los **Ingenieros de Reservorios** deben poder crear y comparar múltiples escenarios *what-if* modificando variables clave (p. ej., fecha de *turn-on* de pozos, *downtime* por mantenimiento) para cuantificar su impacto en el pronóstico final, utilizando las capacidades de modelado. |
| **3. Integración de Pronóstico en Sistemas Externos** | El pronóstico generado por la plataforma debe ser consultado y consumido automáticamente por otros sistemas corporativos. |
| **4. Aseguramiento y Auditoría de Datos y Modelos** | Los **Arquitectos/Especialistas de Datos** deben poder rastrear el linaje de los datos utilizados en el entrenamiento y la predicción, y auditar los cambios en los modelos, garantizando el cumplimiento de las políticas de datos y la transparencia. |
| **5. Reporte y Análisis Avanzado de Resultados** | Los usuarios de **Planificación** y **Reservorios** deben poder crear reportes personalizados y *dashboards* a medida. |

---

## Objetivos Primarios

* **Precisión del Pronóstico:** Incrementar la exactitud en la estimación de la producción de hidrocarburos a corto, medio y largo plazo.
* **Reducción de Incertidumbre:** Minimizar la incertidumbre en la planificación operativa y presupuestaria.
* **Optimización de Decisiones:** Facilitar la toma de decisiones proactiva mediante la simulación de escenarios (*what-if*).

## Objetivos Secundarios

* **Gobernanza de Datos:** Asegurar la calidad, seguridad y centralización de los datos de entrada y resultados.
* **Integración Sistémica:** Habilitar la consulta y el consumo automático de pronósticos vía API REST por otros sistemas corporativos.
* **Trazabilidad de Modelos:** Garantizar la auditabilidad y el linaje de los modelos predictivos y sus supuestos.
* **Análisis Visual:** Ofrecer *dashboards* interactivos y herramientas para el reporte y análisis avanzado de resultados.

---

## Alcance

### Incluye
* Plataforma de pronóstico de producción de hidrocarburos.
* Integración de datos históricos (producción, pozos, variables operativas).
* Motor de modelado predictivo (estadístico/ML).
* Dashboards interactivos y herramientas de visualización de tendencias.
* API REST para consumo e integración de pronósticos.
* Funcionalidad de simulación de escenarios (*what-if*).
* Registro y trazabilidad de modelos y datos (linaje, auditoría).

### No Incluye
* Adquisición de datos en campo o sistemas SCADA.
* Ejecución de simulaciones complejas de reservorios 3D (fuera del motor predictivo).
* Funcionalidad completa de planificación financiera o presupuestaria (solo provee el pronóstico).
* Herramientas de control operativo o automatización de activos en tiempo real.
* Descubrimiento causal, métodos numéricos de optimización sobre los parámetros de *what-ifs*.

---

## Stakeholders

* **Dirección / Gerencia Ejecutiva:** Responsables de la aprobación del proyecto, inversión, y la planificación estratégica y presupuestaria de alto nivel.
* **Equipo de Planificación y Presupuesto:** Usuarios clave del pronóstico para la elaboración de planes financieros y operativos.
* **Equipo de Ingeniería de Reservorios:** Usuarios clave para la simulación de escenarios y la validación de modelos predictivos.
* **Equipo de Gobernanza de Datos / IT:** Responsables de la infraestructura, seguridad, calidad de datos y cumplimiento normativo.
* **Equipo de Operaciones / Comercial:** Interesados en el volumen de producción pronosticado para la logística, el mantenimiento y los compromisos de venta.

---

## Requerimientos Funcionales

* **Carga y Gestión de Datos:** El sistema **DEBE** permitir la ingesta, validación y almacenamiento de datos históricos de producción, pozos y variables operativas.
* **Generación de Pronóstico Base:** El sistema **DEBE** realizar el cálculo y la visualización de pronósticos de producción para diferentes horizontes, con desagregación por activo/yacimiento/pozo.
* **Simulación What-if:** El sistema **DEBE** soportar la creación, modificación y comparación de múltiples escenarios de pronóstico basados en la alteración de variables operativas clave.
* **API de Consulta (REST):** El sistema **DEBE** exponer una API REST para el acceso programático a los resultados del pronóstico, facilitando su consumo por sistemas externos.
* **Visualización y Reporte:** El sistema **DEBE** proveer *dashboards* interactivos para el análisis avanzado de tendencias y la comparación de resultados.
* **Trazabilidad y Auditoría:** El sistema **DEBE** garantizar el registro de linaje de datos, modelos entrenados y todos los cambios en los supuestos utilizados.

---

## Requerimientos No Funcionales

* **Rendimiento:** El tiempo de respuesta para la generación de un nuevo pronóstico base **DEBE** ser menor a 5 segundos. La interactividad de los dashboards **DEBE** cargar la información en menos de 5 segundos.
* **Disponibilidad:** El servicio de la API REST **DEBE** mantener una disponibilidad del 99.5% durante el horario operativo.

---

## Métricas de éxito (KPIs)

* **Precisión del Pronóstico:** Reducción del Error Medio Absoluto Porcentual (MAPE) para el pronóstico a corto plazo comparado con un baseline de mantener el último datapoint.
* **Adopción por Usuario:** Número promedio de escenarios what-if simulados por ingeniero de reservorios al mes.
* **Gobernanza de Datos:** Cobertura de al menos el 85% en cuanto a trazabilidad y auditoría de la versión del modelo y los datos de entrenamiento utilizados.
* **Integración:** Frecuencia de consulta y consumo de los resultados vía API REST por sistemas externos.

---

## Dependencias y riesgos

* **Dependencias**
    * **Datos Históricos:** La disponibilidad, calidad y unificación de los datos históricos de producción y operativos es crítica.
    * **Infraestructura IT:** Requerimiento de provisión oportuna de la infraestructura de alojamiento y procesamiento.
* **Riesgos**
    * **Precisión del Modelo:** Riesgo de que los modelos no alcancen la exactitud de pronóstico esperada.
    * **Adopción:** Posible resistencia al cambio o baja adopción por parte de los usuarios clave.
    * **Alcance:** Solicitudes de funcionalidades que excedan el alcance definido.

---

## Roadmap

* **Fase 1:**
    * Objetivo: Desarrollar sistema que ofrezca una interfaz de demo del servicio a prestar.
    * Fecha estimada: 2026-04-28
    * Entregables: Referir a la agenda técnica de la fase 1 para más detalle.
* **Fase 2:**
    * Objetivo: Implementar funcionalidad para ingesta, manejo y procesamiento de datos.
    * Fecha estimada: 2026-06-09
    * Entregables: Referir a la agenda técnica de la fase 2 para más detalle.
* **Fase 3:**
    * Objetivo: Implementar modelo predictivo integrado dentro del sistema.
    * Fecha estimada: 2026-06-30
    * Entregables: Referir a la agenda técnica de la fase 3 para más detalle.

---

## Preguntas abiertas

* **Fuentes de Datos y Especificaciones:** ¿Cuáles son las fuentes de datos específicas (sistemas, bases de datos) que se utilizarán para la ingesta de datos históricos de producción, pozos y variables operativas? Se requiere la especificación técnica de los esquemas de datos.
* **Definición de Horizonte de Pronóstico:** Se necesita confirmar la definición temporal exacta de los horizontes de pronóstico: ¿Cuál es el período para "corto plazo", "medio plazo" y "largo plazo"? (Esto impacta directamente en el KPI de Precisión del Pronóstico).
* **Requerimientos de Seguridad de la API:** ¿Existen requerimientos no funcionales específicos de seguridad o autenticación (ej. OAuth, claves API, límites de tasa) para la API de Consulta (REST)?
* **Definición de Baseline para KPI:** Confirmar el "baseline" (línea de base) actual para el cálculo del Error Medio Absoluto Porcentual (MAPE) y establecer el valor objetivo de reducción.