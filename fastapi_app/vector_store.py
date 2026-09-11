import os
import uuid

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb  # noqa: E402
from chromadb.config import Settings

from config import CHROMA_PATH, IDEAS_COLLECTION
from hf_client import embed

_client = chromadb.PersistentClient(
    path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False, allow_reset=True)
)
_collection = _client.get_or_create_collection(
    name=IDEAS_COLLECTION, metadata={"hnsw:space": "cosine"}
)


async def add_idea(text: str, metadata: dict) -> str:
    idea_id = str(uuid.uuid4())
    vector = (await embed([text]))[0]
    _collection.add(ids=[idea_id], embeddings=[vector], documents=[text], metadatas=[metadata])
    return idea_id


async def query(text: str, n_results: int = 5) -> list[dict]:
    if _collection.count() == 0:
        return []
    vector = (await embed([text]))[0]
    raw = _collection.query(
        query_embeddings=[vector],
        n_results=min(n_results, _collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    return [
        {
            "id": raw["ids"][0][index],
            "document": raw["documents"][0][index],
            "metadata": raw["metadatas"][0][index] or {},
            "distance": raw["distances"][0][index],
        }
        for index in range(len(raw["ids"][0]))
    ]


def count() -> int:
    return _collection.count()
