import os
import sys


def _connect_v3(api_key: str):
    """Try Pinecone v3 style client."""
    try:
        from pinecone import Pinecone  # v3 SDK
    except Exception:
        return None

    pc = Pinecone(api_key=api_key)
    try:
        names = pc.list_indexes().names()  # preferred in v3
    except Exception:
        # Fallback: print raw object if .names() isn't available
        names = pc.list_indexes()
    print("Connected (v3), indexes:", names)
    return True


def _connect_v2(api_key: str, environment: str):
    """Fallback to Pinecone v2 style init/list."""
    try:
        import pinecone as pc  # v2 SDK
    except Exception as e:
        raise SystemExit(
            "pinecone package is not installed. Please run 'pip install pinecone-client==2.2.2' and try again."
        ) from e

    if not environment:
        raise SystemExit("PINECONE_ENVIRONMENT is required for pinecone-client v2.x")
    pc.init(api_key=api_key, environment=environment)
    print("Connected (v2), indexes:", pc.list_indexes())
    return True


def main() -> None:
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise SystemExit("Missing env: PINECONE_API_KEY")
    env = os.getenv("PINECONE_ENVIRONMENT")  # optional for v3, required for v2

    # Prefer v3 client if available; otherwise try v2.
    used = _connect_v3(api_key)
    if not used:
        _connect_v2(api_key, env)


if __name__ == "__main__":
    main()
