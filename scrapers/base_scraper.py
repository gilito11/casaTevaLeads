"""
Clase base para todos los scrapers de portales inmobiliarios.

Esta clase proporciona funcionalidad común para:
- Guardar datos en MinIO (data lake)
- Guardar datos en PostgreSQL (raw layer)
- Normalización de datos (teléfonos, zonas)
- Filtrado de particulares vs profesionales
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Dict, Optional, Any

import psycopg2
from minio import Minio
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

    Proporciona funcionalidad común para persistencia en data lake (MinIO),
    base de datos (PostgreSQL) y normalización de datos.

    Attributes:
        tenant_id (int): ID del tenant al que pertenece este scraper
        zones (dict): Diccionario con zonas geográficas a scrapear
        filters (dict): Filtros a aplicar (precio, habitaciones, etc.)
        minio_client (Minio): Cliente de MinIO para data lake
        postgres_conn: Conexión a PostgreSQL
    """

    def __init__(
        self,
        tenant_id: int,
        zones: Dict[str, Any],
        filters: Dict[str, Any],
        minio_config: Optional[Dict[str, str]] = None,
        postgres_config: Optional[Dict[str, str]] = None
    ):
        """
        Inicializa el scraper base.

        Args:
            tenant_id: ID del tenant
            zones: Zonas geográficas a scrapear
                   Ejemplo: {"lleida_ciudad": {"enabled": True, "codigos_postales": ["25001"]}}
            filters: Filtros de scraping
                    Ejemplo: {"filtros_precio": {"min": 50000, "max": 1000000}}
            minio_config: Configuración de MinIO (endpoint, access_key, secret_key, bucket)
            postgres_config: Configuración de PostgreSQL (host, port, database, user, password)
        """
        self.tenant_id = tenant_id
        self.zones = zones
        self.filters = filters

        # Inicializar cliente MinIO
        if minio_config:
            self.minio_client = self._init_minio(minio_config)
        else:
            self.minio_client = None
            logger.warning("MinIO no configurado - save_to_data_lake no funcionará")

        # Inicializar conexión PostgreSQL
        if postgres_config:
            self.postgres_conn = self._init_postgres(postgres_config)
        else:
            self.postgres_conn = None
            logger.warning("PostgreSQL no configurado - save_to_postgres_raw no funcionará")

        logger.info(f"Scraper inicializado para tenant_id={tenant_id}")

    def _init_minio(self, config: Dict[str, str]) -> Minio:
        """
        Inicializa cliente de MinIO.

        Args:
            config: Configuración con endpoint, access_key, secret_key, secure

        Returns:
            Cliente de MinIO configurado
        """
        try:
            client = Minio(
                endpoint=config.get('endpoint', 'localhost:9000'),
                access_key=config.get('access_key', 'minioadmin'),
                secret_key=config.get('secret_key', 'minioadmin'),
                secure=config.get('secure', False)
            )
            logger.info(f"Cliente MinIO inicializado: {config.get('endpoint')}")
            return client
        except Exception as e:
            logger.error(f"Error al inicializar MinIO: {e}")
            raise

    def _init_postgres(self, config: Dict[str, str]) -> psycopg2.extensions.connection:
        """
        Inicializa conexión a PostgreSQL.

        Args:
            config: Configuración con host, port, database, user, password

        Returns:
            Conexión a PostgreSQL
        """
        try:
            conn = psycopg2.connect(
                host=config.get('host', 'localhost'),
                port=config.get('port', 5432),
                database=config.get('database', 'casa_teva_db'),
                user=config.get('user', 'casa_teva'),
                password=config.get('password', '')
            )
            logger.info(f"Conexión PostgreSQL establecida: {config.get('database')}")
            return conn
        except Exception as e:
            logger.error(f"Error al conectar a PostgreSQL: {e}")
            raise

    def save_to_data_lake(self, listing_data: Dict[str, Any], portal: str) -> Optional[str]:
        """
        Guarda los datos del anuncio en el data lake (MinIO).

        El path sigue la estructura: bronze/tenant_{id}/{portal}/{YYYY-MM-DD}/listing_{uuid}.json

        Args:
            listing_data: Datos del anuncio a guardar
            portal: Nombre del portal (fotocasa, milanuncios, wallapop)

        Returns:
            str: Path completo del archivo en MinIO, o None si hubo error

        Example:
            >>> path = scraper.save_to_data_lake({"precio": 150000}, "fotocasa")
            >>> print(path)
            'bronze/tenant_1/fotocasa/2025-12-07/listing_abc123.json'
        """
        if not self.minio_client:
            logger.error("MinIO no está configurado")
            return None

        try:
            # Generar path único
            fecha = datetime.now().strftime('%Y-%m-%d')
            listing_uuid = str(uuid.uuid4())
            object_name = f"bronze/tenant_{self.tenant_id}/{portal}/{fecha}/listing_{listing_uuid}.json"

            # Convertir datos a JSON
            json_data = json.dumps(listing_data, ensure_ascii=False, indent=2)
            json_bytes = json_data.encode('utf-8')

            # Subir a MinIO
            bucket_name = 'casa-teva-data-lake'

            # Crear bucket si no existe
            if not self.minio_client.bucket_exists(bucket_name):
                self.minio_client.make_bucket(bucket_name)
                logger.info(f"Bucket creado: {bucket_name}")

            # Subir archivo
            from io import BytesIO
            self.minio_client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=BytesIO(json_bytes),
                length=len(json_bytes),
                content_type='application/json'
            )

            logger.info(f"Datos guardados en data lake: {object_name}")
            return object_name

        except Exception as e:
            logger.error(f"Error al guardar en data lake: {e}")
            return None

    def save_to_postgres_raw(
        self,
        listing_data: Dict[str, Any],
        data_lake_path: str,
        portal: str
    ) -> bool:
        """
        Guarda los datos del anuncio en la tabla raw.raw_listings de PostgreSQL.

        Args:
            listing_data: Datos del anuncio
            data_lake_path: Path del archivo en MinIO
            portal: Nombre del portal

        Returns:
            bool: True si se guardó correctamente, False si hubo error

        Example:
            >>> success = scraper.save_to_postgres_raw(
            ...     listing_data={"precio": 150000},
            ...     data_lake_path="bronze/tenant_1/fotocasa/2025-12-07/listing_abc.json",
            ...     portal="fotocasa"
            ... )
        """
        if not self.postgres_conn:
            logger.error("PostgreSQL no está configurado")
            return False

        try:
            cursor = self.postgres_conn.cursor()

            # SQL para insertar en raw.raw_listings
            sql = """
                INSERT INTO raw.raw_listings (
                    tenant_id,
                    portal,
                    data_lake_path,
                    raw_data,
                    scraping_timestamp
                ) VALUES (%s, %s, %s, %s, %s)
            """

            # Ejecutar insert
            cursor.execute(
                sql,
                (
                    self.tenant_id,
                    portal,
                    data_lake_path,
                    Json(listing_data),  # Convertir dict a JSONB
                    datetime.now()
                )
            )

            self.postgres_conn.commit()
            cursor.close()

            logger.info(f"Datos guardados en PostgreSQL: {portal} - {data_lake_path}")
            return True

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
