from typing import List, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
import uuid


VECTOR_SIZE = 768   # gemini-embedding-001 output dimension
_client: Optional[QdrantClient] = None


def get_client(host: str, port: int) -> QdrantClient:
    """
    Return a singleton Qdrant client.
    """
    global _client
    if _client is None:
        _client = QdrantClient(host=host, port=port)
    return _client


def ensure_collection(client: QdrantClient, collection: str) -> None:
    """
    Create collection if it does not exist yet.
    """
    existing = [c.name for c in client.get_collections().collections]
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )


def upsert_vectors(
    client: QdrantClient,
    collection: str,
    person_id: str,
    event_id: str,
    chunk_index: int,
    doc_type: str,
    text: str,
    vector: List[float],
) -> None:
    """
    Insert one chunk vector into Qdrant with full metadata payload.
    """
    point = PointStruct(
        id      = str(uuid.uuid4()),
        vector  = vector,
        payload = {
            "person_id"   : person_id,
            "event_id"    : event_id,
            "chunk_index" : chunk_index,
            "doc_type"    : doc_type,
            "text"        : text,
        },
    )
    client.upsert(collection_name=collection, points=[point])


def delete_patient_vectors(
    client: QdrantClient,
    collection: str,
    person_id: str,
) -> None:
    """
    Delete ALL vectors for a given person_id from Qdrant.
    Called before re-embedding to avoid stale vectors.
    """
    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="person_id",
                    match=MatchValue(value=person_id),
                )
            ]
        ),
    )


def search_patient_vectors(
    client: QdrantClient,
    collection: str,
    person_id: str,
    query_vector: List[float],
    top_k: int = 5,
) -> List[Dict]:
    """
    Search Qdrant for top_k most relevant chunks for a patient.
    Strictly filtered to this person_id only.
    Returns list of { text, event_id, doc_type, score }.
    """
    results = client.search(
        collection_name=collection,
        query_vector=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="person_id",
                    match=MatchValue(value=person_id),
                )
            ]
        ),
        limit=top_k,
    )

    return [
        {
            "text"     : r.payload.get("text", ""),
            "event_id" : r.payload.get("event_id", ""),
            "doc_type" : r.payload.get("doc_type", ""),
            "score"    : round(r.score, 4),
        }
        for r in results
    ]


def patient_has_vectors(
    client: QdrantClient,
    collection: str,
    person_id: str,
) -> bool:
    """
    Check if a patient already has vectors embedded in Qdrant.
    """
    results = client.scroll(
        collection_name=collection,
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="person_id",
                    match=MatchValue(value=person_id),
                )
            ]
        ),
        limit=1,
    )
    return len(results[0]) > 0
