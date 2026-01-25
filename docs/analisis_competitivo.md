# Analisis Competitivo: Casa Teva Lead System vs Fotocasa Pro vs Idealista Tools

> **Fecha**: Enero 2026
> **Version**: 1.0

---

## 1. Resumen Ejecutivo

El mercado de herramientas CRM para el sector inmobiliario en Espana esta dominado por dos grandes players: **Fotocasa Pro** (grupo Adevinta) e **Idealista Tools** (grupo Idealista). Ambos ofrecen soluciones integradas con sus respectivos portales, pero con un modelo de negocio que genera **dependencia del portal** y **costes elevados** para las agencias.

**Casa Teva Lead System** se posiciona como una alternativa independiente que:
- Agrega leads de **4 portales simultaneamente** (habitaclia, fotocasa, milanuncios, idealista)
- Ofrece **alertas de bajadas de precio** que los portales no proporcionan
- Detecta **duplicados cross-portal** para evitar pagar multiples veces por el mismo lead
- Automatiza el **contacto inicial** sin depender de APIs oficiales
- Proporciona **propiedad total de los datos** sin lock-in

**Coste mensual estimado**:
| Solucion | Coste/mes |
|----------|-----------|
| Casa Teva Lead System | ~50 EUR (ScrapingBee) |
| Fotocasa Pro Basic | 150-500 EUR |
| Idealista Tools | 300-1000+ EUR |

---

## 2. Tabla Comparativa de Funcionalidades

| Funcionalidad | Casa Teva Lead System | Fotocasa Pro | Idealista Tools |
|---------------|:---------------------:|:------------:|:---------------:|
| **Captura de Leads** | 4 portales | 3 portales (fotocasa, habitaclia, milanuncios) | 1 portal (idealista) |
| **Agregacion Multi-Portal** | SI | Parcial (grupo Adevinta) | NO |
| **Seguimiento de Precios** | SI (historico + alertas) | Limitado | Limitado |
| **Alertas Bajadas de Precio** | SI (>5%, Telegram) | NO | NO |
| **Deteccion Duplicados Cross-Portal** | SI | NO | NO |
| **Automatizacion de Contacto** | SI (4 portales) | NO | NO |
| **Lead Scoring Personalizable** | SI (0-90 pts, configurable) | Basico | Basico |
| **CRM Integrado** | SI | SI | SI |
| **App Movil / PWA** | SI (PWA) | SI | SI |
| **Valoracion de Inmuebles** | SI (widget + PDF) | SI (DataVenues) | SI |
| **ACM (Analisis Comparativo)** | SI | SI | SI |
| **Tours Virtuales** | NO | SI (Visita Express) | SI |
| **Publicacion en Portales** | NO | SI | SI (180+ portales) |
| **Sync Google Calendar** | SI | SI | SI |
| **API Propia** | SI (REST + API Key) | NO | NO |
| **Propiedad de Datos** | 100% | Dependiente | Dependiente |
| **Soporte 24/7** | NO | SI | SI |

### Detalle de Funcionalidades por Plataforma

#### Fotocasa Pro
- **Packs**: Start, Basic, Premium
- **Portales incluidos**: Fotocasa, Habitaclia, Milanuncios (grupo Adevinta)
- **CRM**: Agenda, calendario, gestion fotografias, tours 3D
- **DataVenues**: Big Data inmobiliario con datos de demanda
- **Posicionamiento**: Prioritario, Top, Premium, Oportunidad
- **Extras**: Visita Express, captacion particulares, MyDominance

#### Idealista Tools
- **Software**: CRM todo-en-uno accesible desde cualquier dispositivo
- **Integracion**: Solo con portal Idealista
- **Valoracion**: Estimacion de precios con informe personalizado
- **Publicacion**: Conexion con 180+ portales (via Inmovilla)
- **Formacion**: Cursos inmobiliarios gratuitos

---

## 3. Ventajas Competitivas (PROS)

### 3.1 Agregacion Multi-Portal Real
Mientras Fotocasa Pro solo agrega portales de su propio grupo (Adevinta) e Idealista se limita a su portal, **Casa Teva captura leads de los 4 principales portales** incluyendo competidores directos. Esto significa:
- Mayor cobertura del mercado
- Deteccion de oportunidades antes que la competencia
- Vision completa del inventario disponible

### 3.2 Alertas de Bajadas de Precio
Funcionalidad **unica en el mercado**. Cuando un inmueble baja mas del 5%, se genera una alerta automatica via Telegram. Esto permite:
- Identificar propietarios motivados a vender
- Detectar oportunidades de captacion
- Actuar antes que la competencia

### 3.3 Deteccion de Duplicados Cross-Portal
El sistema identifica automaticamente el mismo inmueble publicado en multiples portales mediante:
- Matching por telefono del propietario
- Matching por ubicacion + precio + metros
- Evita pagar multiples veces por el mismo lead

### 3.4 Automatizacion de Contacto
Contacto automatico con propietarios en los 4 portales:
- **Fotocasa**: Auto-login + formulario
- **Habitaclia**: 2Captcha para reCAPTCHA
- **Milanuncios**: Camoufox + chat interno
- **Idealista**: Parcial (DataDome bloquea login)

Limite configurable: 5 contactos/dia con delays de 2-5 min.

### 3.5 Sin Lock-in de Portal
Los datos son **100% propiedad del usuario**:
- Base de datos PostgreSQL accesible
- API REST propia para integraciones
- Exportacion sin restricciones
- Sin dependencia de ningun portal especifico

### 3.6 Lead Scoring Avanzado
Sistema de puntuacion personalizable (0-90 pts) basado en:
- Dias en mercado
- Disponibilidad de telefono
- Cantidad de fotos
- Precio relativo a la zona
- Historial de bajadas de precio

### 3.7 Coste Significativamente Menor
| Concepto | Casa Teva | Competencia |
|----------|-----------|-------------|
| Infraestructura | GRATIS (Fly.io, Neon, GitHub Actions) | Incluido |
| Scraping | ~50 EUR/mes (ScrapingBee) | N/A |
| **Total** | **~50 EUR/mes** | **150-1000+ EUR/mes** |

Ahorro potencial: **100-950 EUR/mes** respecto a soluciones comerciales.

---

## 4. Limitaciones (CONTRAS)

### 4.1 Menor Reconocimiento de Marca
- Fotocasa Pro e Idealista son marcas establecidas con anos de trayectoria
- Casa Teva es una solucion nueva sin presencia en el mercado
- Las agencias prefieren soluciones "oficiales" por percepcion de seguridad

### 4.2 Sin Integraciones API Oficiales
- Dependencia de web scraping para obtener datos
- Riesgo de cambios en la estructura de los portales
- Los portales pueden implementar medidas anti-scraping mas agresivas
- Idealista ya usa DataDome, lo que limita la automatizacion

### 4.3 Equipo de Soporte Reducido
- Sin soporte 24/7 ni linea telefonica
- Documentacion limitada
- Dependencia de un equipo pequeno vs corporaciones grandes

### 4.4 Dependencia del Web Scraping
- Fragilidad ante cambios en los portales
- Posibles problemas legales (terminos de servicio)
- Necesidad de mantenimiento constante de scrapers
- Algunos portales (idealista) son mas dificiles de scrapear

### 4.5 Sin Publicacion en Portales
- No permite publicar anuncios desde la plataforma
- Es una herramienta de captacion, no de publicacion
- Las agencias aun necesitan contratar portales para publicar

### 4.6 Sin Tours Virtuales Integrados
- No incluye herramientas tipo Visita Express
- Requiere integracion con servicios externos

---

## 5. Estrategia Comercial Recomendada

### 5.1 Publico Objetivo

**Target Primario: Agentes Inmobiliarios Independientes**
- 1-3 agentes
- Presupuesto limitado
- Frustrados con costes de portales
- Buscan ventaja competitiva

**Target Secundario: Agencias Pequenas-Medianas**
- 3-10 agentes
- Ya pagan Fotocasa Pro o Idealista
- Buscan complementar con agregacion multi-portal
- Interesados en alertas de bajadas de precio

**NO Target (evitar)**
- Grandes franquicias con contratos corporativos
- Agencias que solo trabajan con un portal
- Negocios sin capacidad tecnica minima

### 5.2 Propuesta de Valor

**Mensaje Principal**:
> "Captura leads de 4 portales al precio de ninguno. Detecta oportunidades antes que tu competencia con alertas de bajadas de precio."

**Mensajes Secundarios**:
- "Ahorra 100-500 EUR/mes respecto a Fotocasa Pro"
- "Detecta duplicados: no pagues 3 veces por el mismo lead"
- "Tus datos son tuyos: sin lock-in, API abierta"
- "Contacto automatico mientras duermes"

### 5.3 Estrategia de Pricing

**Modelo Recomendado: SaaS con tiers**

| Plan | Precio/mes | Incluye |
|------|------------|---------|
| **Starter** | 49 EUR | 2 zonas, 100 leads/mes, alertas Telegram |
| **Profesional** | 99 EUR | 5 zonas, 500 leads/mes, contacto automatico (2/dia) |
| **Agencia** | 199 EUR | Zonas ilimitadas, leads ilimitados, 5 contactos/dia, API |

**Justificacion**:
- Starter: Competir con "no hacer nada" o Excel
- Profesional: Competir con Fotocasa Pro Start (~150 EUR)
- Agencia: Alternativa a Fotocasa Pro Basic/Premium

### 5.4 Estrategia de Demo/Trial

**Trial de 14 dias**:
1. Configuracion guiada de 1 zona geografica
2. Primer scraping en vivo durante la demo
3. Envio de primera alerta Telegram
4. Muestra de 20-30 leads con scoring

**Demo en vivo (30 min)**:
1. Mostrar dashboard con leads reales de su zona (5 min)
2. Explicar lead scoring y por que ese orden (5 min)
3. Mostrar historico de precios y alertas de bajada (5 min)
4. Demostrar deteccion de duplicados cross-portal (5 min)
5. Simular contacto automatico (5 min)
6. Q&A y cierre (5 min)

### 5.5 Manejo de Objeciones

| Objecion | Respuesta |
|----------|-----------|
| "Ya tengo Fotocasa Pro" | "Perfecto, nosotros complementamos. Capturamos leads de Idealista y detectamos duplicados que estas pagando doble." |
| "El scraping es ilegal" | "Extraemos datos publicos igual que Google. Miles de empresas lo hacen. Tu competencia ya lo usa." |
| "Que pasa si deja de funcionar?" | "Mantenemos los scrapers actualizados. Si un portal cambia, lo arreglamos en 24-48h. Ademas tienes garantia de devolucion." |
| "Idealista me da mas leads" | "Seguramente, pero te cobra 300 EUR/mes. Con nosotros pagas 50 EUR y capturas de 4 portales." |
| "Es muy tecnico para mi" | "La instalacion la hacemos nosotros. Tu solo configuras las zonas y recibes alertas en Telegram." |
| "Prefiero una marca conocida" | "Entiendo. Prueba 14 dias gratis y compara resultados. Si no supera a tu herramienta actual, no pagas nada." |
| "No tengo tiempo para otra herramienta" | "Es automatico. Configuras una vez, recibes alertas en Telegram. 5 minutos/dia maximo." |

### 5.6 Canales de Adquisicion

**Corto Plazo (0-6 meses)**:
1. **LinkedIn**: Contenido sobre captacion inmobiliaria, tips de scraping
2. **Grupos Facebook/WhatsApp** de agentes inmobiliarios
3. **Referencias**: 20% descuento por referido convertido
4. **Demos personalizadas** via calendly

**Medio Plazo (6-12 meses)**:
1. **SEO**: "alternativa fotocasa pro", "captacion leads inmobiliarios"
2. **Webinars**: "Como captar 10x mas leads con automatizacion"
3. **Partnerships**: Asociaciones de agentes inmobiliarios
4. **Caso de estudio**: Publicar resultados de clientes early adopters

---

## 6. Conclusiones

Casa Teva Lead System tiene una **propuesta de valor diferenciada** en un mercado dominado por soluciones vinculadas a portales. Las principales ventajas son:

1. **Agregacion real multi-portal** (4 vs 1-3)
2. **Alertas de bajadas de precio** (unico en el mercado)
3. **Coste 3-20x menor** que la competencia
4. **Propiedad total de datos** sin dependencia

Las principales barreras a superar son:
1. **Reconocimiento de marca** - requiere casos de exito publicables
2. **Fragilidad del scraping** - requiere mantenimiento continuo
3. **Percepcion de riesgo** - trial gratuito y garantia mitigan

**Recomendacion**: Lanzar con pricing agresivo (49-199 EUR/mes) enfocado en agentes independientes y agencias pequenas, usando trial de 14 dias y demos personalizadas como principal canal de conversion.

---

## Fuentes

- [Fotocasa Pro - Soluciones](https://pro.fotocasa.es/soluciones/)
- [Fotocasa Pro - CRM Inmobiliario](https://pro.fotocasa.es/crm-inmobiliario/)
- [Fotocasa Pro - Packs](https://pro.fotocasa.es/soluciones-packs/)
- [Blog Fotocasa Pro - Claves para optimizar](https://blogprofesional.fotocasa.es/claves-optimizar-negocio-fotocasa-pro/)
- [Idealista Tools](https://www.idealista.com/tools/)
- [Idealista - Software recomendado](https://www.idealista.com/en/tools/software-recomendado-para-inmobiliarias)
- [Inmovilla CRM](https://inmovilla.com/)
- [ImmoEdge - Fotocasa Review](https://immoedge.com/fotocasa-property-portal-review/)
- [ImmoEdge - Idealista Review](https://immoedge.com/idealista-property-portal-review/)
- [Comparativa CRM Inmobiliarios](https://www.avaibook.com/blog/comparativa-crm-inmobiliarios/)
