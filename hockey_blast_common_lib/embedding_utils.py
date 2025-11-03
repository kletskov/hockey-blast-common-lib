"""
Embedding utilities for vector search using AWS Bedrock Titan.

This module provides functions to generate embeddings for text using AWS Bedrock's
Titan embedding model and store them in the database for semantic search.
"""

import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# AWS Bedrock configuration
BEDROCK_REGION = "us-west-2"
BEDROCK_EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSION = 1024  # Titan v2 produces 1024-dimensional embeddings


def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate embedding vector for text using AWS Bedrock Titan.

    Args:
        text: Text to embed (e.g., "Pavel Kletskov" or "Good Guys")

    Returns:
        List of floats representing the embedding vector (1024 dimensions)
        None if embedding generation fails
    """
    if not text or not text.strip():
        logger.warning("Empty text provided to generate_embedding")
        return None

    try:
        import boto3

        bedrock = boto3.client(
            service_name="bedrock-runtime",
            region_name=BEDROCK_REGION
        )

        # Titan embedding API request format
        request_body = {
            "inputText": text.strip()
        }

        response = bedrock.invoke_model(
            modelId=BEDROCK_EMBEDDING_MODEL,
            body=json.dumps(request_body)
        )

        response_body = json.loads(response["body"].read())
        embedding = response_body.get("embedding")

        if not embedding:
            logger.error(f"No embedding returned for text: {text[:50]}")
            return None

        if len(embedding) != EMBEDDING_DIMENSION:
            logger.error(
                f"Unexpected embedding dimension: {len(embedding)} (expected {EMBEDDING_DIMENSION})"
            )
            return None

        return embedding

    except Exception as e:
        logger.error(f"Failed to generate embedding for '{text[:50]}': {e}")
        return None


def update_human_embedding(session, human_id: int, full_name: str) -> bool:
    """
    Generate and store embedding for a human (player/referee/scorekeeper).

    Args:
        session: SQLAlchemy session
        human_id: Human ID in database
        full_name: Full name like "Pavel Kletskov"

    Returns:
        True if embedding was successfully stored, False otherwise
    """
    from datetime import datetime
    from hockey_blast_common_lib.models import HumanEmbedding

    if not full_name or not full_name.strip():
        logger.warning(f"Empty full_name for human_id {human_id}")
        return False

    # Generate embedding
    embedding = generate_embedding(full_name.strip())
    if not embedding:
        return False

    try:
        # Convert Python list to PostgreSQL array format for vector type
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Check if embedding already exists using ORM
        existing = session.query(HumanEmbedding).filter_by(human_id=human_id).first()

        if existing:
            # Update existing record
            # Note: Need raw SQL for vector type casting with ::vector
            # Using format() for embedding since it needs ::vector cast
            from sqlalchemy import text
            sql = text(f"""
                UPDATE human_embeddings
                SET full_name = :full_name,
                    embedding = '{embedding_str}'::vector,
                    updated_at = :updated_at
                WHERE human_id = :human_id
            """)
            session.execute(
                sql,
                {
                    "human_id": human_id,
                    "full_name": full_name.strip(),
                    "updated_at": datetime.utcnow()
                }
            )
        else:
            # Insert new record
            # Note: Need raw SQL for vector type casting with ::vector
            # Using format() for embedding since it needs ::vector cast
            from sqlalchemy import text
            sql = text(f"""
                INSERT INTO human_embeddings (human_id, full_name, embedding, updated_at)
                VALUES (:human_id, :full_name, '{embedding_str}'::vector, :updated_at)
            """)
            session.execute(
                sql,
                {
                    "human_id": human_id,
                    "full_name": full_name.strip(),
                    "updated_at": datetime.utcnow()
                }
            )

        logger.info(f"Updated embedding for human_id={human_id}, name='{full_name}'")
        return True

    except Exception as e:
        logger.error(f"Failed to store embedding for human_id={human_id}: {e}")
        return False


def update_team_embedding(session, team_id: int, team_name: str) -> bool:
    """
    Generate and store embedding for a team.

    Args:
        session: SQLAlchemy session
        team_id: Team ID in database
        team_name: Team name like "Good Guys"

    Returns:
        True if embedding was successfully stored, False otherwise
    """
    from datetime import datetime
    from hockey_blast_common_lib.models import TeamEmbedding

    if not team_name or not team_name.strip():
        logger.warning(f"Empty team_name for team_id {team_id}")
        return False

    # Generate embedding
    embedding = generate_embedding(team_name.strip())
    if not embedding:
        return False

    try:
        # Convert Python list to PostgreSQL array format for vector type
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Check if embedding already exists using ORM
        existing = session.query(TeamEmbedding).filter_by(team_id=team_id).first()

        if existing:
            # Update existing record
            # Note: Need raw SQL for vector type casting with ::vector
            # Using format() for embedding since it needs ::vector cast
            from sqlalchemy import text
            sql = text(f"""
                UPDATE team_embeddings
                SET team_name = :team_name,
                    embedding = '{embedding_str}'::vector,
                    updated_at = :updated_at
                WHERE team_id = :team_id
            """)
            session.execute(
                sql,
                {
                    "team_id": team_id,
                    "team_name": team_name.strip(),
                    "updated_at": datetime.utcnow()
                }
            )
        else:
            # Insert new record
            # Note: Need raw SQL for vector type casting with ::vector
            # Using format() for embedding since it needs ::vector cast
            from sqlalchemy import text
            sql = text(f"""
                INSERT INTO team_embeddings (team_id, team_name, embedding, updated_at)
                VALUES (:team_id, :team_name, '{embedding_str}'::vector, :updated_at)
            """)
            session.execute(
                sql,
                {
                    "team_id": team_id,
                    "team_name": team_name.strip(),
                    "updated_at": datetime.utcnow()
                }
            )

        logger.info(f"Updated embedding for team_id={team_id}, name='{team_name}'")
        return True

    except Exception as e:
        logger.error(f"Failed to store embedding for team_id={team_id}: {e}")
        return False


def search_embeddings_semantic(
    session,
    query: str,
    entity_type: str = "all",
    limit: int = 10
) -> List[dict]:
    """
    Semantic search across human and team embeddings.

    Args:
        session: SQLAlchemy session
        query: Search query (e.g., "good guy", "pavel")
        entity_type: "human", "team", or "all"
        limit: Maximum number of results

    Returns:
        List of dicts with keys: type, id, name, similarity
    """
    from sqlalchemy import text

    # Generate query embedding
    query_embedding = generate_embedding(query)
    if not query_embedding:
        logger.error(f"Failed to generate embedding for query: {query}")
        return []

    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    results = []

    try:
        # Search humans
        # Note: Using raw SQL for pgvector distance operator (<=>)
        # Using format() for embedding since it needs ::vector cast
        if entity_type in ("human", "all"):
            sql = text(f"""
                SELECT
                    human_id,
                    full_name,
                    1 - (embedding <=> '{embedding_str}'::vector) as similarity
                FROM human_embeddings
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT :limit
            """)
            human_results = session.execute(sql, {"limit": limit}).fetchall()

            for row in human_results:
                results.append({
                    "type": "human",
                    "id": row[0],
                    "name": row[1],
                    "similarity": float(row[2])
                })

        # Search teams
        # Note: Using raw SQL for pgvector distance operator (<=>)
        # Using format() for embedding since it needs ::vector cast
        if entity_type in ("team", "all"):
            sql = text(f"""
                SELECT
                    team_id,
                    team_name,
                    1 - (embedding <=> '{embedding_str}'::vector) as similarity
                FROM team_embeddings
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT :limit
            """)
            team_results = session.execute(sql, {"limit": limit}).fetchall()

            for row in team_results:
                results.append({
                    "type": "team",
                    "id": row[0],
                    "name": row[1],
                    "similarity": float(row[2])
                })

        # Sort by similarity descending and limit
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    except Exception as e:
        logger.error(f"Semantic search failed for query '{query}': {e}")
        return []
