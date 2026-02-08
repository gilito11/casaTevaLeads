"""
Clase base para todos los scrapers de portales inmobiliarios.

Esta clase proporciona funcionalidad común para:
- Guardar datos en PostgreSQL (marts.dim_leads)
- Normalización de datos (teléfonos, zonas)
- Filtrado de particulares vs profesionales
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Dict, Optional, Any

import psycopg2
from psycopg2.extras import Json

from scrapers.utils.particular_filter import debe_scrapear


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BaseScraper:
    """
    Clase base abstracta para scrapers de portales inmobiliarios.

    Proporciona funcionalidad común para persistencia en PostgreSQL
    y normalización de datos.

    Attributes:
        tenant_id (int): ID del tenant al que pertenece este scraper
        zones (dict): Diccionario con zonas geográficas a scrapear
        filters (dict): Filtros a aplicar (precio, habitaciones, etc.)
        postgres_conn: Conexión a PostgreSQL
    """

    def __init__(
        self,
        tenant_id: int,
        zones: Dict[str, Any] = None,
        filters: Dict[str, Any] = None,
        minio_config: Optional[Dict[str, str]] = None,  # Deprecated, se ignora
        postgres_config: Optional[Dict[str, str]] = None,
        portal: str = None
    ):
        """
        Inicializa el scraper base.

        Args:
            tenant_id: ID del tenant
            zones: Zonas geográficas a scrapear (opcional)
                   Ejemplo: {"lleida_ciudad": {"enabled": True, "codigos_postales": ["25001"]}}
            filters: Filtros de scraping (opcional)
                    Ejemplo: {"filtros_precio": {"min": 50000, "max": 1000000}}
            minio_config: DEPRECATED - se ignora, mantenido por compatibilidad
            postgres_config: Configuración de PostgreSQL (host, port, database, user, password)
            portal: Nombre del portal (opcional, para uso con save_listing)
        """
        self.tenant_id = tenant_id
        self.zones = zones or {}
        self.filters = filters or {}
        self.portal = portal

        # Inicializar conexión PostgreSQL
        if postgres_config:
            self.postgres_conn = self._init_postgres(postgres_config)
        else:
            self.postgres_conn = None
            logger.warning("PostgreSQL no configurado - save_to_postgres_raw no funcionará")

        logger.info(f"Scraper inicializado para tenant_id={tenant_id}")

    def _init_postgres(self, config: Dict[str, str]) -> psycopg2.extensions.connection:
        """
        Inicializa conexión a PostgreSQL.

        Args:
            config: Configuración con host, port, database, user, password, sslmode

        Returns:
            Conexión a PostgreSQL
        """
        try:
            # Construir parámetros de conexión
            conn_params = {
                'host': config.get('host', 'localhost'),
                'port': config.get('port', 5432),
                'database': config.get('database', 'casa_teva_db'),
                'user': config.get('user', 'casa_teva'),
                'password': config.get('password', ''),
            }
            # Añadir sslmode si está presente (requerido para Neon/remote)
            if config.get('sslmode'):
                conn_params['sslmode'] = config.get('sslmode')

            conn = psycopg2.connect(**conn_params)
            logger.info(f"Conexión PostgreSQL establecida: {config.get('database')} (host: {config.get('host')})")
            return conn
        except Exception as e:
            logger.error(f"Error al conectar a PostgreSQL: {e}")
            raise

    def save_to_data_lake(self, listing_data: Dict[str, Any], portal: str) -> Optional[str]:
        """
        DEPRECATED: MinIO ha sido eliminado del proyecto.

        Los datos se guardan directamente en PostgreSQL como JSONB.
        Este método se mantiene por compatibilidad pero no hace nada.

        Returns:
            None siempre
        """
        return None

    def _generate_lead_id(self, portal: str, anuncio_id: str) -> int:
        """
        Genera un lead_id único como entero (hash truncado).

        Args:
            portal: Nombre del portal
            anuncio_id: ID del anuncio en el portal

        Returns:
            int: ID numérico único (fits in PostgreSQL integer: max 2.1 billion)
        """
        # Crear un string único combinando tenant, portal y anuncio_id
        unique_string = f"{self.tenant_id}:{portal}:{anuncio_id}"
        # Convertir MD5 a entero - usar módulo para mantener en rango de int
        hash_hex = hashlib.md5(unique_string.encode()).hexdigest()
        # Use modulo to keep within PostgreSQL integer range (0 to 2,147,483,647)
        return int(hash_hex, 16) % 2147483647

    def _is_in_blacklist(self, portal: str, anuncio_id: str) -> bool:
        """
        Verifica si un anuncio está en la blacklist.

        Args:
            portal: Nombre del portal
            anuncio_id: ID del anuncio en el portal

        Returns:
            bool: True si está en blacklist, False si no
        """
        if not self.postgres_conn:
            return False

        try:
            cursor = self.postgres_conn.cursor()
            cursor.execute("""
                SELECT 1 FROM leads_anuncio_blacklist
                WHERE tenant_id = %s AND portal = %s AND anuncio_id = %s
                LIMIT 1
            """, (self.tenant_id, portal, anuncio_id))
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Exception as e:
            logger.debug(f"Error checking blacklist: {e}")
            return False

    def save_to_postgres_raw(
        self,
        listing_data: Dict[str, Any],
        data_lake_path: str,
        portal: str
    ) -> bool:
        """
        Guarda los datos del anuncio en la tabla marts.dim_leads de PostgreSQL.

        Args:
            listing_data: Datos del anuncio (normalizados)
            data_lake_path: Referencia al origen de datos
            portal: Nombre del portal

        Returns:
            bool: True si se guardó correctamente, False si hubo error
        """
        if not self.postgres_conn:
            logger.error("PostgreSQL no está configurado")
            return False

        try:
            cursor = self.postgres_conn.cursor()

            # Generar lead_id como MD5 hash
            anuncio_id = str(listing_data.get('anuncio_id', ''))
            if not anuncio_id:
                logger.warning(f"Anuncio sin ID, no se puede guardar")
                return False

            # Check if anuncio is in blacklist
            if self._is_in_blacklist(portal, anuncio_id):
                logger.debug(f"Anuncio en blacklist, ignorando: {portal} - {anuncio_id}")
                return False

            lead_id = self._generate_lead_id(portal, anuncio_id)

            # Preparar fotos como JSON string para el campo JSONB
            fotos = listing_data.get('fotos', [])
            if isinstance(fotos, list):
                fotos_json = json.dumps(fotos)
            else:
                fotos_json = '[]'

            # SQL para insertar en marts.dim_leads
            # Usa ON CONFLICT para actualizar si ya existe
            sql = """
                INSERT INTO marts.dim_leads (
                    lead_id,
                    tenant_id,
                    telefono_norm,
                    email,
                    nombre,
                    direccion,
                    zona_geografica,
                    codigo_postal,
                    tipo_inmueble,
                    precio,
                    habitaciones,
                    metros,
                    descripcion,
                    fotos,
                    portal,
                    url_anuncio,
                    data_lake_reference,
                    estado,
                    numero_intentos,
                    fecha_scraping,
                    created_at,
                    updated_at,
                    anuncio_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (lead_id) DO NOTHING
            """

            now = datetime.now()

            # Prepare values ensuring NOT NULL constraints are satisfied
            # NOT NULL columns: lead_id, telefono_norm, direccion, zona_geografica,
            #                   precio, portal, url_anuncio, fecha_scraping
            telefono = listing_data.get('telefono') or ''
            direccion = listing_data.get('direccion') or listing_data.get('ubicacion') or 'Sin dirección'
            zona = listing_data.get('zona_geografica') or listing_data.get('zona_busqueda') or 'Sin zona'
            precio = listing_data.get('precio')
            if precio is None:
                precio = 0  # Default price for NOT NULL constraint
            url = listing_data.get('url_anuncio') or listing_data.get('detail_url') or ''

            # Ejecutar insert
            cursor.execute(
                sql,
                (
                    lead_id,
                    self.tenant_id,
                    telefono,
                    listing_data.get('email') or None,
                    listing_data.get('vendedor') or listing_data.get('nombre') or None,
                    direccion,
                    zona,
                    listing_data.get('codigo_postal') or None,
                    listing_data.get('tipo_inmueble') or 'piso',
                    precio,
                    listing_data.get('habitaciones') or None,
                    listing_data.get('metros') or None,
                    listing_data.get('descripcion') or None,
                    fotos_json,
                    portal,
                    url,
                    data_lake_path,
                    'NUEVO',
                    0,
                    now,
                    now,
                    now,
                    anuncio_id,
                )
            )

            rows_affected = cursor.rowcount
            self.postgres_conn.commit()
            cursor.close()

            if rows_affected > 0:
                logger.info(f"Lead guardado en PostgreSQL: {portal} - {anuncio_id}")
            else:
                logger.debug(f"Duplicado ignorado: {portal} - {anuncio_id}")
            return rows_affected > 0

        except Exception as e:
            logger.error(f"Error al guardar en PostgreSQL: {e}")
            if self.postgres_conn:
                self.postgres_conn.rollback()
            return False

    def normalize_phone(self, phone_str: str) -> Optional[str]:
        """
        Normaliza un número de teléfono español.

        Elimina espacios, guiones, paréntesis y el prefijo +34.
        Devuelve solo los dígitos.

        Args:
            phone_str: Número de teléfono a normalizar

        Returns:
            str: Número normalizado (solo dígitos), o None si no es válido

        Examples:
            >>> scraper.normalize_phone("+34 973 12 34 56")
            '973123456'
            >>> scraper.normalize_phone("(973) 123-456")
            '973123456'
            >>> scraper.normalize_phone("+34 612 345 678")
            '612345678'
        """
        if not phone_str or not isinstance(phone_str, str):
            return None

        # Quitar espacios, guiones, paréntesis
        cleaned = re.sub(r'[\s\-\(\)]', '', phone_str)

        # Quitar +34 al inicio
        if cleaned.startswith('+34'):
            cleaned = cleaned[3:]
        elif cleaned.startswith('0034'):
            cleaned = cleaned[4:]
        elif cleaned.startswith('34'):
            cleaned = cleaned[2:]

        # Quedarse solo con dígitos
        digits = re.sub(r'\D', '', cleaned)

        # Validar que tenga 9 dígitos (teléfonos españoles)
        if len(digits) == 9:
            return digits
        else:
            logger.warning(f"Teléfono no válido (no tiene 9 dígitos): {phone_str} -> {digits}")
            return digits if digits else None

    def classify_zone(self, codigo_postal: str) -> str:
        """
        Clasifica la zona geográfica basándose en el código postal.

        Args:
            codigo_postal: Código postal (5 dígitos)

        Returns:
            str: Zona clasificada

        Examples:
            >>> scraper.classify_zone("25001")
            'Lleida Ciudad'
            >>> scraper.classify_zone("25100")
            'Lleida Provincia'
            >>> scraper.classify_zone("43001")
            'Tarragona Costa'
        """
        if not codigo_postal or not isinstance(codigo_postal, str):
            return "Desconocida"

        # Obtener los primeros 2 dígitos
        prefix = codigo_postal[:2]

        if prefix == '25':
            # Lleida
            # 25001-25008 son Lleida ciudad
            try:
                cp_num = int(codigo_postal)
                if 25001 <= cp_num <= 25008:
                    return "Lleida Ciudad"
                else:
                    return "Lleida Provincia"
            except ValueError:
                return "Lleida Provincia"
        elif prefix == '43':
            return "Tarragona Costa"
        else:
            return "Lleida Provincia"

    def should_scrape(self, listing_data: Dict[str, Any]) -> bool:
        """
        Determina si un anuncio debe ser scrapeado según los filtros.

        Usa el sistema de filtrado de particulares para rechazar:
        - Inmobiliarias/agencias
        - Particulares que rechacen inmobiliarias

        Args:
            listing_data: Datos del anuncio

        Returns:
            bool: True si debe scrapearse, False si debe ignorarse
        """
        return debe_scrapear(listing_data)

    def scrape(self):
        """
        Método abstracto que debe ser implementado por cada scraper específico.

        Cada scraper de portal (Fotocasa, Milanuncios, Wallapop) debe
        implementar su propia lógica de scraping.

        Raises:
            NotImplementedError: Si no se implementa en la clase hija
        """
        raise NotImplementedError("El método scrape() debe ser implementado por la clase hija")

    def normalize_listing(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza los datos de un anuncio para que sean consistentes entre portales.

        Campos estandarizados:
        - tenant_id: int
        - portal: str
        - anuncio_id: str (único por portal)
        - titulo: str
        - descripcion: str
        - precio: float (sin símbolos, solo número)
        - direccion: str
        - zona_busqueda: str (zona usada para búsqueda)
        - zona_geografica: str (zona geográfica real)
        - habitaciones: int
        - banos: int
        - metros: float
        - fotos: list[str] (URLs de imágenes)
        - vendedor: str
        - es_particular: bool
        - url_anuncio: str (URL completa del anuncio)
        - telefono: str (normalizado, solo 9 dígitos)
        - email: str

        Args:
            listing_data: Datos crudos del anuncio

        Returns:
            Dict con datos normalizados
        """
        normalized = {
            'tenant_id': listing_data.get('tenant_id', self.tenant_id),
            'portal': listing_data.get('portal', ''),
            'anuncio_id': str(listing_data.get('anuncio_id', '')),
            'titulo': str(listing_data.get('titulo', '') or '').strip(),
            'descripcion': str(listing_data.get('descripcion', '') or '').strip(),
            'direccion': str(listing_data.get('direccion', '') or listing_data.get('ubicacion', '') or '').strip(),
            'zona_busqueda': str(listing_data.get('zona_busqueda', '') or '').strip(),
            'zona_geografica': str(listing_data.get('zona_geografica', '') or listing_data.get('zona', '') or '').strip(),
            'vendedor': str(listing_data.get('vendedor', 'Particular') or 'Particular').strip(),
            'es_particular': bool(listing_data.get('es_particular', True)),
            'url_anuncio': str(listing_data.get('url_anuncio', '') or listing_data.get('detail_url', '') or '').strip(),
            'email': str(listing_data.get('email', '') or '').strip(),
        }

        # Normalizar precio
        precio = listing_data.get('precio')
        if precio is not None:
            try:
                if isinstance(precio, str):
                    # Eliminar símbolos de moneda y espacios
                    precio = re.sub(r'[€$\s.]', '', precio)
                    precio = precio.replace(',', '.')
                normalized['precio'] = float(precio)
            except (ValueError, TypeError):
                normalized['precio'] = None
        else:
            normalized['precio'] = None

        # Normalizar habitaciones
        habitaciones = listing_data.get('habitaciones')
        if habitaciones is not None:
            try:
                normalized['habitaciones'] = int(habitaciones)
            except (ValueError, TypeError):
                normalized['habitaciones'] = None
        else:
            normalized['habitaciones'] = None

        # Normalizar baños
        banos = listing_data.get('banos')
        if banos is not None:
            try:
                normalized['banos'] = int(banos)
            except (ValueError, TypeError):
                normalized['banos'] = None
        else:
            normalized['banos'] = None

        # Normalizar metros
        metros = listing_data.get('metros')
        if metros is not None:
            try:
                if isinstance(metros, str):
                    metros = metros.replace(',', '.')
                    metros = re.sub(r'[^\d.]', '', metros)
                normalized['metros'] = float(metros)
            except (ValueError, TypeError):
                normalized['metros'] = None
        else:
            normalized['metros'] = None

        # Normalizar fotos
        fotos = listing_data.get('fotos', [])
        if isinstance(fotos, list):
            normalized['fotos'] = [str(f) for f in fotos if f and str(f).startswith('http')]
        elif isinstance(fotos, str) and fotos.startswith('http'):
            normalized['fotos'] = [fotos]
        else:
            normalized['fotos'] = []

        # Normalizar teléfono
        telefono = listing_data.get('telefono')
        if telefono:
            normalized['telefono'] = self.normalize_phone(telefono)
        else:
            normalized['telefono'] = None

        return normalized

    def save_listing(self, listing_data: Dict[str, Any]) -> bool:
        """
        Normaliza y guarda un anuncio en PostgreSQL.

        Args:
            listing_data: Datos crudos del anuncio

        Returns:
            bool: True si se guardó correctamente
        """
        # Normalizar datos
        normalized = self.normalize_listing(listing_data)

        # Guardar en PostgreSQL
        portal = normalized.get('portal', 'unknown')
        data_lake_path = f"raw/{self.tenant_id}/{portal}/{normalized.get('anuncio_id', 'unknown')}"

        return self.save_to_postgres_raw(normalized, data_lake_path, portal)

    def close(self):
        """
        Cierra las conexiones abiertas (PostgreSQL).

        El cliente de MinIO no requiere cierre explícito.
        """
        if self.postgres_conn:
            self.postgres_conn.close()
            logger.info("Conexión PostgreSQL cerrada")

    def __enter__(self):
        """Soporte para context manager (with statement)"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra conexiones al salir del context manager"""
        self.close()
