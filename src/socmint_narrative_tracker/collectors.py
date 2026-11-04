import hashlib

def _md5(text: str) -> str:
    # Produces a 12-char hash to fingerprint profile avatars
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]