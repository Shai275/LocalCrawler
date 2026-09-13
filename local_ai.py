"""Compatibility entry point shared by summary and comparison."""
from ai_providers import AIProviderConfig, create_provider


async def structured_reply(model, instruction, content, schema, validate, *, provider=None):
    backend = provider or create_provider(AIProviderConfig(model=model))
    return await backend.structured_reply(model, instruction, content, schema, validate)
