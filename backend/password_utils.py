"""
Password hashing and verification utilities using bcrypt.
"""
import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password as a string
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hashed password.

    Args:
        password: Plain text password to verify
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )
