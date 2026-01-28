import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def derive_key(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Derive a Fernet-compatible encryption key from a password.

    Args:
        password: The password to derive the key from
        salt: Optional salt (if not provided, a new one is generated)

    Returns:
        Tuple of (key, salt)
    """
    import os
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


def encrypt_data(data: str, key: bytes) -> str:
    """Encrypt data using Fernet.

    Args:
        data: The data to encrypt
        key: The encryption key

    Returns:
        Encrypted data as a string
    """
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data.encode())
    return encrypted.decode()


def decrypt_data(encrypted: str, key: bytes) -> str:
    """Decrypt data using Fernet.

    Args:
        encrypted: The encrypted data
        key: The encryption key

    Returns:
        Decrypted data as a string
    """
    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted.encode())
    return decrypted.decode()
