# Manual de Usuario - Casa Teva CRM

Sistema de gestion de leads inmobiliarios para la captacion de propiedades en venta.

---

## 1. Introduccion

Casa Teva CRM es una aplicacion web para la gestion de leads inmobiliarios. El sistema captura automaticamente anuncios de propiedades en venta desde portales inmobiliarios (Habitaclia, Fotocasa, Idealista, Milanuncios) y los presenta en una interfaz centralizada para su seguimiento comercial.

### Acceso al sistema

1. Acceder a la URL del CRM
2. Introducir usuario y contrasena
3. Pulsar "Iniciar sesion"

### Navegacion principal

El menu lateral izquierdo contiene las secciones principales:

- **Dashboard**: Vista general con metricas clave
- **Propiedades**: Listado de leads/anuncios capturados
- **Contactos**: Gestion de propietarios contactados
- **Scrapers**: Configuracion de zonas de busqueda
- **Analytics**: Graficos y estadisticas detalladas
- **Mi Perfil**: Configuracion personal

---

## 2. Ver Leads (Propiedades)

### Listado de propiedades

Acceder desde el menu lateral > **Propiedades**.

La tabla muestra:
- Direccion/ubicacion
- Precio de venta
- Superficie (m2)
- Numero de habitaciones
- Portal de origen (Habitaclia, Fotocasa, etc.)
- Estado del lead
- Fecha de captura

### Filtros disponibles

- **Busqueda**: Por telefono, direccion o zona
- **Estado**: NUEVO, EN_PROCESO, CONTACTADO_SIN_RESPUESTA, INTERESADO, NO_INTERESADO, EN_ESPERA, NO_CONTACTAR, CLIENTE, YA_VENDIDO
- **Portal**: Filtrar por portal de origen
- **Zona**: Filtrar por zona geografica

### Ver detalle de un lead

Hacer clic en cualquier fila para acceder al detalle completo:
- Informacion del anuncio (titulo, descripcion, fotos)
- Datos del contacto (telefono)
- URL del anuncio original
- Historial de notas
- Cambio de estado

### Acciones masivas

1. Seleccionar varios leads usando las casillas de verificacion
2. Elegir accion en el menu desplegable:
   - **Cambiar estado**: Aplicar un estado a todos los seleccionados
   - **Eliminar**: Borrar los leads seleccionados
   - **Eliminar + Blacklist**: Borrar y evitar que vuelvan a aparecer

---

## 3. Gestionar Contactos

### Crear contacto desde un lead

1. Abrir el detalle de un lead
2. Pulsar "Crear contacto"
3. El sistema agrupa automaticamente todas las propiedades del mismo telefono

### Vista de contactos

Acceder desde el menu lateral > **Contactos**.

Cada contacto muestra:
- Nombre (si se ha completado)
- Telefono principal y secundario
- Email
- Numero de propiedades asociadas

### Detalle del contacto

Al abrir un contacto se visualiza:
- Datos personales editables
- Lista de propiedades del contacto
- Historial de interacciones

### Registrar interacciones

1. En el detalle del contacto, usar el formulario "Nueva interaccion"
2. Seleccionar tipo: Llamada, Email, WhatsApp, Visita, Nota u Otro
3. Escribir descripcion
4. Indicar fecha/hora
5. Pulsar "Guardar"

---

## 4. Dashboard de Analytics

Acceder desde el menu lateral > **Analytics**.

### KPIs principales

- Total de leads
- Leads nuevos (sin gestionar)
- Leads en proceso
- Leads interesados
- Tasa de conversion
- Valor del pipeline

### Graficos disponibles

- **Embudo de conversion**: Distribucion de leads por estado
- **Leads por dia**: Tendencia de captacion ultimos 30 dias
- **Evolucion de precios**: Media semanal de precios
- **Comparativa portales**: Rendimiento por portal de origen
- **Precios por zona**: Media de precios por zona geografica
- **Tipologia**: Distribucion por tipo de inmueble

### Mapa de zonas

Acceder desde Analytics > **Mapa**.

Visualiza las zonas de scraping con marcadores que indican:
- Numero de leads en cada zona
- Precio medio

---

## 5. Configuracion de Zonas de Scraping

Acceder desde el menu lateral > **Scrapers**.

### Zonas preconfiguradas

El sistema incluye mas de 20 zonas predefinidas organizadas por region:

**Provincia de Lleida**
- Lleida, Balaguer, Mollerussa, Tarrega, Alcoletge, Alpicat, Torrefarrera, etc.

**Costa Daurada**
- Salou, Cambrils, Miami Platja, La Pineda, Vilafortuny, Mont-roig del Camp, etc.

**Tarragona**
- Tarragona, Reus, Valls, Montblanc

**Terres de l'Ebre**
- Tortosa, Amposta, Deltebre, L'Ametlla de Mar, Sant Carles de la Rapita

### Activar/desactivar zonas

1. Localizar la zona deseada en el panel
2. Usar el interruptor para activar/desactivar
3. Configurar que portales scrapear en cada zona

### Parametros de zona

Cada zona tiene:
- Coordenadas geograficas
- Radio de busqueda (km)
- Precio minimo (para filtrar alquileres)
- Portales activos (Habitaclia, Fotocasa, Idealista, Milanuncios)

### Schedule de ejecucion

Los scrapers se ejecutan automaticamente a las 12:00 y 18:00 (hora de Espana), coincidiendo con los picos de publicacion de anuncios.

---

## 6. FAQ

**P: Los leads aparecen duplicados?**
R: El sistema usa el telefono normalizado como identificador unico. Si un propietario publica en varios portales, aparecera como un solo contacto con varias propiedades.

**P: Como evito que un anuncio vuelva a aparecer?**
R: Al eliminar un lead, marcar la opcion "Anadir a blacklist". El sistema ignorara ese anuncio en futuras ejecuciones.

**P: Por que algunos leads no tienen telefono?**
R: Algunos anuncios no publican telefono visible. El sistema extrae telefonos de la descripcion cuando es posible.

**P: Con que frecuencia se actualizan los datos?**
R: Los scrapers se ejecutan 2 veces al dia (12:00 y 18:00). Los nuevos leads aparecen tras cada ejecucion.

**P: Que significa cada estado?**

| Estado | Descripcion |
|--------|-------------|
| NUEVO | Lead recien capturado, sin gestionar |
| EN_PROCESO | Se esta trabajando en este lead |
| CONTACTADO_SIN_RESPUESTA | Se intento contactar pero no hubo respuesta |
| INTERESADO | El propietario mostro interes |
| NO_INTERESADO | El propietario no esta interesado |
| EN_ESPERA | Pendiente de seguimiento futuro |
| NO_CONTACTAR | No volver a contactar |
| CLIENTE | Conversion exitosa |
| YA_VENDIDO | La propiedad ya se vendio |

**P: Puedo exportar los datos?**
R: Si, desde Analytics usar el boton "Exportar CSV" para descargar los datos filtrados.

**P: El sistema detecta inmobiliarias?**
R: Si, el pipeline dbt filtra automaticamente anuncios que contienen frases como "abstenerse agencias" o "sin intermediarios". Ademas, usuarios que publican 5+ anuncios se marcan automaticamente como inmobiliarias.

---

## Soporte

Para dudas o problemas tecnicos, contactar con el administrador del sistema.
