"""
Resource de Dagster para interactuar con PostgreSQL.

Proporciona métodos para ejecutar queries e insertar datos.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

import psycopg2
from psycopg2.extras import Json, execute_values
from dagster import ConfigurableResource
from pydantic import Field


logger = logging.getLogger(__name__)


class PostgresResource(ConfigurableResource):
    """
    Resource de Dagster para PostgreSQL.

    Attributes:
        host: Host de PostgreSQL
        port: Puerto de PostgreSQL
        database: Nombre de la base de datos
        user: Usuario de PostgreSQL
        password: Contraseña de PostgreSQL
        sslmode: Modo SSL (require para Azure)
    """

    host: str = Field(
        default="localhost",
        description="PostgreSQL host"
    )
    port: int = Field(
        default=5432,
        description="PostgreSQL port"
    )
    database: str = Field(
        default="casa_teva_db",
        description="Database name"
    )
    user: str = Field(
        default="casa_teva",
        description="PostgreSQL user"
    )
    password: str = Field(
        default="casateva2024",
        description="PostgreSQL password"
    )
    sslmode: str = Field(
        default="prefer",
        description="SSL mode (require for Azure)"
    )

    def _get_connection(self) -> psycopg2.extensions.connection:
        """Crea y retorna una conexión a PostgreSQL (internal)"""
        conn_params = {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password': self.password,
        }
        # Añadir sslmode si no es el valor por defecto
        if self.sslmode and self.sslmode != "prefer":
            conn_params['sslmode'] = self.sslmode

        return psycopg2.connect(**conn_params)

    def get_connection(self) -> psycopg2.extensions.connection:
        """Crea y retorna una conexión a PostgreSQL (public, for use with context manager)"""
        return self._get_connection()

    def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        fetch: bool = True
    ) -> Optional[List[Tuple]]:
        """
        Ejecuta una query SQL.

        Args:
            query: Query SQL a ejecutar
            params: Parámetros de la query (opcional)
            fetch: Si hacer fetchall() de los resultados

        Returns:
            Lista de tuplas con resultados, o None si hay error
        """
        conn = None
        cursor = None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(query, params)

            if fetch:
                results = cursor.fetchall()
            else:
                results = None

            conn.commit()

            logger.debug(f"Query ejecutada exitosamente")
            return results

        except Exception as e:
            logger.error(f"Error ejecutando query: {e}")
            if conn:
                conn.rollback()
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def insert_data(
        self,
        table: str,
        data: Dict[str, Any],
        schema: str = "public"
    ) -> bool:
        """
        Inserta un registro en una tabla.

        Args:
            table: Nombre de la tabla
            data: Diccionario con datos a insertar
            schema: Schema de la tabla (default: public)

        Returns:
            bool: True si se insertó exitosamente, False en caso contrario
        """
        conn = None
        cursor = None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Construir query INSERT
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            table_name = f"{schema}.{table}"

            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

            cursor.execute(query, tuple(data.values()))
            conn.commit()

            logger.info(f"Registro insertado en {table_name}")
            return True

        except Exception as e:
            logger.error(f"Error insertando datos: {e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def insert_raw_listing(
        self,
        tenant_id: int,
        portal: str,
        data_lake_path: str,
        raw_data: Dict[str, Any]
    ) -> bool:
        """
        Inserta un listing en la tabla raw.raw_listings.

        Args:
            tenant_id: ID del tenant
            portal: Nombre del portal (fotocasa, milanuncios, wallapop)
            data_lake_path: Path del archivo en MinIO
            raw_data: Datos raw del listing

        Returns:
            bool: True si se insertó exitosamente
        """
        conn = None
        cursor = None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                INSERT INTO raw.raw_listings (
                    tenant_id,
                    portal,
                    data_lake_path,
                    raw_data,
                    scraping_timestamp
                ) VALUES (%s, %s, %s, %s, NOW())
            """

            cursor.execute(
                query,
                (tenant_id, portal, data_lake_path, Json(raw_data))
            )

            conn.commit()

            logger.debug(f"Listing insertado en raw.raw_listings: {data_lake_path}")
            return True

        except Exception as e:
            logger.error(f"Error insertando listing: {e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def bulk_insert_raw_listings(
        self,
        listings: List[Dict[str, Any]]
    ) -> int:
        """
        Inserta múltiples listings en raw.raw_listings usando bulk insert.

        Args:
            listings: Lista de diccionarios con datos de listings
                     Cada dict debe tener: tenant_id, portal, data_lake_path, raw_data

        Returns:
            int: Número de registros insertados
        """
        if not listings:
            return 0

        conn = None
        cursor = None

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Preparar datos para execute_values
            values = [
                (
                    item['tenant_id'],
                    item['portal'],
                    item['data_lake_path'],
                    Json(item['raw_data'])
                )
                for item in listings
            ]

            query = """
                INSERT INTO raw.raw_listings (
                    tenant_id,
                    portal,
                    data_lake_path,
                    raw_data,
                    scraping_timestamp
                ) VALUES %s
            """

            # Usar execute_values para bulk insert
            execute_values(
                cursor,
                query,
                values,
                template="(%s, %s, %s, %s, NOW())"
            )

            conn.commit()

            logger.info(f"{len(listings)} listings insertados en raw.raw_listings")
            return len(listings)

        except Exception as e:
            logger.error(f"Error en bulk insert: {e}")
            if conn:
                conn.rollback()
            return 0

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_latest_scraping_timestamp(
        self,
        tenant_id: int,
        portal: str
    ) -> Optional[str]:
        """
        Obtiene el timestamp del último scraping para un tenant y portal.

        Args:
            tenant_id: ID del tenant
            portal: Nombre del portal

        Returns:
            str: Timestamp en formato ISO, o None
        """
        query = """
            SELECT MAX(scraping_timestamp)
            FROM raw.raw_listings
            WHERE tenant_id = %s AND portal = %s
        """

        result = self.execute_query(query, (tenant_id, portal))

        if result and result[0][0]:
            return result[0][0].isoformat()
        return None

    def get_active_zones(self, tenant_id: int = None) -> List[Dict[str, Any]]:
        """
        Obtiene las zonas activas de la base de datos.

        Args:
            tenant_id: ID del tenant (opcional, si None obtiene todas)

        Returns:
            Lista de zonas con slug, nombre, tenant_id y portales habilitados
        """
        # Build portales array from individual boolean fields
        portales_sql = """
            ARRAY_REMOVE(ARRAY[
                CASE WHEN z.scrapear_milanuncios THEN 'milanuncios' END,
                CASE WHEN z.scrapear_fotocasa THEN 'fotocasa' END,
                CASE WHEN z.scrapear_habitaclia THEN 'habitaclia' END,
                CASE WHEN z.scrapear_idealista THEN 'idealista' END
            ], NULL) as portales
        """

        if tenant_id:
            query = f"""
                SELECT z.slug, z.nombre, z.tenant_id, t.nombre as tenant_nombre,
                       {portales_sql}
                FROM zonas_geograficas z
                JOIN tenants t ON z.tenant_id = t.tenant_id
                WHERE z.activa = true AND z.tenant_id = %s
                ORDER BY z.tenant_id, z.nombre
            """
            params = (tenant_id,)
        else:
            query = f"""
                SELECT z.slug, z.nombre, z.tenant_id, t.nombre as tenant_nombre,
                       {portales_sql}
                FROM zonas_geograficas z
                JOIN tenants t ON z.tenant_id = t.tenant_id
                WHERE z.activa = true
                ORDER BY z.tenant_id, z.nombre
            """
            params = None

        result = self.execute_query(query, params)

        zones = []
        if result:
            for row in result:
                zones.append({
                    'slug': row[0],
                    'nombre': row[1],
                    'tenant_id': row[2],
                    'tenant_nombre': row[3],
                    'portales': row[4] if row[4] else [],
                })

        return zones

    def get_scraping_stats(self, tenant_id: int = None) -> Dict[str, Any]:
        """
        Obtiene estadísticas de scraping.

        Args:
            tenant_id: ID del tenant (opcional)

        Returns:
            Dict con estadísticas
        """
        where_clause = "WHERE tenant_id = %s" if tenant_id else ""
        params = (tenant_id,) if tenant_id else None

        # Total de leads from marts.dim_leads
        query = f"""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT portal) as portales,
                MAX(fecha_scraping) as ultimo_scraping
            FROM marts.dim_leads
            {where_clause}
        """
        result = self.execute_query(query, params)

        stats = {
            'total_leads': 0,
            'portales_activos': 0,
            'ultimo_scraping': None,
        }

        if result and result[0]:
            stats['total_leads'] = result[0][0] or 0
            stats['portales_activos'] = result[0][1] or 0
            stats['ultimo_scraping'] = result[0][2].isoformat() if result[0][2] else None

        return stats
