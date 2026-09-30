"""Provider-facing contracts for CBT AI structured question output"""
from __future__ import annotations

import json
from functools import lru_cache
from pydantic import BaseModel



from app.modules.cbt.ai.schemas import(
    AIQuestionBatchDraft,
    AIRegeneratedQuestionDraft
)


QUESTION_GENERATION_RULES = """
You are a CBT educational question-authoring engine.

Generate questions strictly from the supplied academic context and
author instructions.

Rules:

- Only generate supported question types:
  - single_choice
  - multiple_choice

- A single_choice question must have exactly one option where
  is_correct is true.

- A multiple_choice question must have at least two options where
  is_correct is true and at least one option where is_correct is false.

- Every question must have at least two answer options.

- Every answer option must contain text, an image directive, or both.

- Answer options within a question must be unique.

- Questions within a generated batch must not be duplicates.

- Only include an image directive when a visual is genuinely required.

- Never invent media IDs, asset IDs, database IDs, or file paths.

- Do not add fields that are not defined by the response schema.

- Follow the requested subject, academic level, topics, question count,
  question-type distribution, and author instructions.

Return only JSON matching the supplied response schema.
Do not return markdown, code fences, commentary, or additional text.
""".strip()


QUESTION_REGENERATION_RULES = """
You are a CBT educational question-editing engine.

Regenerate exactly one existing CBT question according to the supplied
academic context and transformation instruction.

Rules:

- Only use supported question types:
  - single_choice
  - multiple_choice

- Preserve the current question type unless the request explicitly
  allows it to change.

- A single_choice question must have exactly one option where
  is_correct is true.

- A multiple_choice question must have at least two options where
  is_correct is true and at least one option where is_correct is false.

- Every question must have at least two answer options.

- Every answer option must contain text, an image directive, or both.

- Answer options must be unique.

- Only include an image directive when a visual is genuinely required.

- Never invent media IDs, asset IDs, database IDs, or file paths.

- Do not add fields that are not defined by the response schema.

Return only JSON matching the supplied response schema.
Do not return markdown, code fences, commentary, or additional text.
""".strip()


QUESTION_REPAIR_RULES = """
You previously generated an invalid CBT question batch.

Repair the supplied batch using the validation feedback.

Do not create unrelated questions.
Preserve the original academic intent.
Return the complete repaired batch.
Follow the same response schema.
"""





def _schema_to_json(model : BaseModel) -> str:
    """
    Convert a Pydantic model into compact JSON Schema
    text suitable for inclusion in an LLM system prompt
    """

    return json.dumps(
        model.model_json_schema(),
        ensure_ascii = False,
        separators = (",", ":")
    )






@lru_cache(maxsize=1)
def question_generation_schema_text() -> str:
    """
    Return the canonical schema for a generated question batch.
    """
    return _schema_to_json(AIQuestionBatchDraft)



@lru_cache(maxsize=1)
def question_regeneration_schema_text() -> str:
    """
    Return the canonical schema for one regenerated question.
    """
    return _schema_to_json(AIRegeneratedQuestionDraft)




def build_question_generation_prompt() -> str:
    """
    Build the provider-neutral generation contract.
    """
    return (
        f"{QUESTION_GENERATION_RULES}\n\n"
        "RESPONSE JSON SCHEMA:\n"
        f"{question_generation_schema_text()}"
    )


def build_question_regeneration_prompt() -> str:
    """
    Build the provider-neutral regeneration contract.
    """
    return (
        f"{QUESTION_REGENERATION_RULES}\n\n"
        "RESPONSE JSON SCHEMA:\n"
        f"{question_regeneration_schema_text()}"
    )




def build_question_repair_prompt() -> str:
    return (
        f"{QUESTION_REPAIR_RULES}\n\n"
        "RESPONSE JSON SCHEMA:\n"
        f"{question_generation_schema_text()}"
    )
