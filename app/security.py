import base64
import hashlib
import hmac
import secrets


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    encoded_salt = base64.b64encode(salt).decode("utf-8")
    encoded_key = base64.b64encode(derived_key).decode("utf-8")
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encoded_salt}${encoded_key}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n_value, r_value, p_value, encoded_salt, encoded_key = stored_hash.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.b64decode(encoded_salt.encode("utf-8"))
        expected_key = base64.b64decode(encoded_key.encode("utf-8"))
        candidate_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_value),
            r=int(r_value),
            p=int(p_value)
        )
        return hmac.compare_digest(candidate_key, expected_key)
    except (ValueError, TypeError):
        return False
