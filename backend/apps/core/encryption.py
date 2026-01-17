"""
Utilidades de cifrado para credenciales sensibles.
Usa Fernet (AES-128-CBC) para cifrado simétrico.
"""
import os
import base64
from cryptography.fernet import Fernet, InvalidToken


def get_encryption_key() -> bytes:
    """
    Obtiene la key de cifrado desde variable de entorno.
    Si no existe, genera una nueva (solo para desarrollo).
    """
    key = os.environ.get('CREDENTIAL_ENCRYPTION_KEY')

    if not key:
        # En desarrollo, usar key fija (NO USAR EN PRODUCCION)
        # La key debe ser 32 bytes URL-safe base64
        key = 'dev-only-key-do-not-use-in-prod!'
        # Convertir a formato Fernet válido
        key = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b'\0')).decode()

    return key.encode()


def encrypt_value(value: str) -> str:
    """
    Cifra un valor string y retorna el resultado en base64.
    """
    if not value:
        return ''

    f = Fernet(get_encryption_key())
    encrypted = f.encrypt(value.encode())
    return encrypted.decode()


def decrypt_value(encrypted_value: str) -> str:
    """
    Descifra un valor previamente cifrado.
    Retorna string vacío si falla (key incorrecta, valor corrupto, etc.)
    """
    if not encrypted_value:
        return ''

    try:
        f = Fernet(get_encryption_key())
        decrypted = f.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except (InvalidToken, Exception):
        return ''


def generate_key() -> str:
    """
    Genera una nueva key de cifrado Fernet.
    Usar esto para generar CREDENTIAL_ENCRYPTION_KEY en producción.
    """
    return Fernet.generate_key().decode()
