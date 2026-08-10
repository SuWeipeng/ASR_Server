"""
Dictionary API routes (for word lookups)
"""
from fastapi import APIRouter, HTTPException
from app.services.dictionary_service import dictionary_service
from app.models.schemas import (
    DictionaryLookupRequest,
    DictionaryResponse,
    DictionaryEntry,
)
from app.utils import logger

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])


@router.get("/lookup/{word}", response_model=DictionaryResponse)
async def lookup_word(word: str):
    """
    Look up word definition

    Returns phonetic, part of speech, definition, example, etc.

    Note: This is a placeholder endpoint.
    In production, integrate with real dictionary API or database.
    """
    try:
        logger.debug(f"Dictionary lookup: {word}")

        # Check if service is available
        if not dictionary_service.is_available():
            return DictionaryResponse(
                success=False,
                entry=None,
                message="Dictionary service not available (not implemented yet)"
            )

        # Look up word
        entry = dictionary_service.lookup_word(word)

        if not entry:
            return DictionaryResponse(
                success=False,
                entry=None,
                message=f"Word not found: {word}"
            )

        # Convert domain model to schema
        entry_schema = DictionaryEntry(
            word=entry.word,
            phonetic=entry.phonetic,
            part_of_speech=entry.part_of_speech,
            definition=entry.definition,
            example=entry.example,
            synonyms=entry.synonyms
        )

        return DictionaryResponse(
            success=True,
            entry=entry_schema,
            message="Word found"
        )

    except Exception as e:
        logger.error(f"Dictionary lookup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available")
async def check_dictionary_available():
    """
    Check if dictionary service is available
    """
    return {
        "available": dictionary_service.is_available(),
        "message": "Dictionary service is placeholder (not implemented yet)"
    }
