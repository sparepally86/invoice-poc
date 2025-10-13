import os

try:
    import pinecone
except ImportError as e:
    raise SystemExit(
        "pinecone package is not installed. Please run 'pip install pinecone-client==2.2.2' and try again."
    ) from e


def main() -> None:
    try:
        api_key = os.environ["PINECONE_API_KEY"]
        env = os.environ["PINECONE_ENVIRONMENT"]
    except KeyError as e:
        print("Missing env:", e)
        raise

    pinecone.init(api_key=api_key, environment=env)
    print("Connected, indexes:", pinecone.list_indexes())


if __name__ == "__main__":
    main()
