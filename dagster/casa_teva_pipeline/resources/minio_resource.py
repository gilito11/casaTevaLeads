"""
Resource de Dagster para interactuar con MinIO (Data Lake).

Proporciona métodos para guardar, leer y listar archivos JSON en MinIO.
"""

import json
import logging
from io import BytesIO
from typing import List, Dict, Any, Optional

from dagster import ConfigurableResource
from minio import Minio
from pydantic import Field


logger = logging.getLogger(__name__)


class MinIOResource(ConfigurableResource):
    """
    Resource de Dagster para MinIO.

    Attributes:
        endpoint: Endpoint de MinIO (ej: localhost:9000)
        access_key: Access key de MinIO
        secret_key: Secret key de MinIO
        bucket_name: Nombre del bucket a usar
        secure: Si usar HTTPS (default: False para desarrollo)
    """

    endpoint: str = Field(
        default="localhost:9000",
        description="MinIO endpoint"
    )
    access_key: str = Field(
        default="minioadmin",
        description="MinIO access key"
    )
    secret_key: str = Field(
        default="minioadmin",
        description="MinIO secret key"
    )
    bucket_name: str = Field(
        default="casa-teva-data-lake",
        description="Bucket name"
    )
    secure: bool = Field(
        default=False,
        description="Use HTTPS"
    )

    def _get_client(self) -> Minio:
        """Crea y retorna un cliente de MinIO"""
        return Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )

    def _ensure_bucket_exists(self, client: Minio):
        """Asegura que el bucket existe, si no, lo crea"""
        if not client.bucket_exists(self.bucket_name):
            client.make_bucket(self.bucket_name)
            logger.info(f"Bucket creado: {self.bucket_name}")

    def save_json(self, object_name: str, data: Dict[str, Any]) -> bool:
        """
        Guarda un diccionario como JSON en MinIO.

        Args:
            object_name: Path del objeto en MinIO (ej: bronze/tenant_1/...)
            data: Diccionario a guardar

        Returns:
            bool: True si se guardó exitosamente, False en caso contrario
        """
        try:
            client = self._get_client()
            self._ensure_bucket_exists(client)

            # Convertir a JSON
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            json_bytes = json_data.encode('utf-8')

            # Subir a MinIO
            client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=BytesIO(json_bytes),
                length=len(json_bytes),
                content_type='application/json'
            )

            logger.info(f"Archivo guardado en MinIO: {object_name}")
            return True

        except Exception as e:
            logger.error(f"Error guardando en MinIO: {e}")
            return False

    def read_json(self, object_name: str) -> Optional[Dict[str, Any]]:
        """
        Lee un archivo JSON de MinIO.

        Args:
            object_name: Path del objeto en MinIO

        Returns:
            Dict con datos o None si hay error
        """
        try:
            client = self._get_client()

            # Descargar objeto
            response = client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )

            # Leer y parsear JSON
            data = json.loads(response.read().decode('utf-8'))
            response.close()
            response.release_conn()

            logger.debug(f"Archivo leído de MinIO: {object_name}")
            return data

        except Exception as e:
            logger.error(f"Error leyendo de MinIO: {e}")
            return None

    def list_files(self, prefix: str = "") -> List[str]:
        """
        Lista archivos en MinIO con un prefijo dado.

        Args:
            prefix: Prefijo para filtrar (ej: bronze/tenant_1/fotocasa/)

        Returns:
            Lista de paths de objetos
        """
        try:
            client = self._get_client()

            # Listar objetos
            objects = client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
                recursive=True
            )

            # Extraer nombres
            file_list = [obj.object_name for obj in objects]

            logger.info(f"Encontrados {len(file_list)} archivos con prefijo '{prefix}'")
            return file_list

        except Exception as e:
            logger.error(f"Error listando archivos en MinIO: {e}")
            return []

    def delete_file(self, object_name: str) -> bool:
        """
        Elimina un archivo de MinIO.

        Args:
            object_name: Path del objeto a eliminar

        Returns:
            bool: True si se eliminó, False en caso contrario
        """
        try:
            client = self._get_client()

            client.remove_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )

            logger.info(f"Archivo eliminado de MinIO: {object_name}")
            return True

        except Exception as e:
            logger.error(f"Error eliminando archivo de MinIO: {e}")
            return False
