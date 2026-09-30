"""Provider-facing contracts for CBT AI structured question output."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import BaseModel

from app.modules.cbt.ai.schemas import (
    AIQuestionBatchDraft,
    AIRegeneratedQuestionDraft,
)


VISUAL_POLICY_RULES = """
The authoring request contains a `visual_mode` field that controls whether
visual-dependent questions may be authored. During repair, read this policy
from `original_request.visual_mode`.

When visual_mode is "text_only":

- Generate only questions that are completely answerable from text alone.
- Do not create questions that require diagrams, photographs, charts,
  graphs, maps, illustrations, labelled figures, or other visual material.
- Do not refer to an image, diagram, figure, chart, graph, picture,
  object, or labelled visual that is not present.
- The question-level `image` field must be null.
- Every answer option `image` field must be null.

When visual_mode is "auto":

- Prefer text-only questions when a visual is unnecessary.
- A visual-dependent question may be authored only when the visual
  genuinely improves or is required by the assessment.
- Every question that depends on a visual must contain a complete
  question-level image directive.
- Every answer option that depends on a visual must contain a complete
  option-level image directive.
- Never refer to a missing visual.

When visual_mode is "prefer_visuals":

- Prefer meaningful visual questions where appropriate for the supplied
  subject, topic, academic level, and author instructions.
- Do not add decorative or irrelevant visuals simply to satisfy the
  preference.
- Every question or answer option that depends on a visual must contain
  the corresponding complete image directive.
- Never refer to a missing visual.

An image directive describes a visual that will be resolved later by the
application. Never invent image URLs, media IDs, asset IDs, database IDs,
or file paths.
""".strip()


QUESTION_GENERATION_RULES = f"""
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

- Do not add fields that are not defined by the response schema.

- Follow the requested subject, academic level, topics, question count,
  question-type distribution, visual policy, and author instructions.

{VISUAL_POLICY_RULES}

Return only JSON matching the supplied response schema.
Do not return markdown, code fences, commentary, or additional text.
""".strip()


QUESTION_REGENERATION_RULES = f"""
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

- Do not add fields that are not defined by the response schema.

- Follow the visual policy in the request even when the original question
  used a different visual style. If visual_mode is text_only, rewrite the
  regenerated question so it is fully answerable without a visual.

{VISUAL_POLICY_RULES}

Return only JSON matching the supplied response schema.
Do not return markdown, code fences, commentary, or additional text.
""".strip()


QUESTION_REPAIR_RULES = f"""
You previously generated an invalid CBT question batch.

Repair the supplied batch using the validation feedback.

Rules:

- Correct every reported validation issue.
- Do not create unrelated questions.
- Preserve valid question content where possible.
- Preserve the original academic intent.
- Follow the original request, including its visual_mode policy.
- Return the complete repaired batch, not a patch or diff.
- Follow the same response schema.

{VISUAL_POLICY_RULES}

Return only JSON matching the supplied response schema.
Do not return markdown, code fences, commentary, or additional text.
""".strip()


def _schema_to_json(model: type[BaseModel]) -> str:
    """Convert a Pydantic model into compact JSON Schema text."""

    return json.dumps(
        model.model_json_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
    )


@lru_cache(maxsize=1)
def question_generation_schema_text() -> str:
    """Return the canonical schema for a generated question batch."""

    return _schema_to_json(AIQuestionBatchDraft)


@lru_cache(maxsize=1)
def question_regeneration_schema_text() -> str:
    """Return the canonical schema for one regenerated question."""

    return _schema_to_json(AIRegeneratedQuestionDraft)


def build_question_generation_prompt() -> str:
    """Build the provider-neutral generation contract."""

    return (
        f"{QUESTION_GENERATION_RULES}\n\n"
        "RESPONSE JSON SCHEMA:\n"
        f"{question_generation_schema_text()}"
    )


def build_question_regeneration_prompt() -> str:
    """Build the provider-neutral regeneration contract."""

    return (
        f"{QUESTION_REGENERATION_RULES}\n\n"
        "RESPONSE JSON SCHEMA:\n"
        f"{question_regeneration_schema_text()}"
    )


def build_question_repair_prompt() -> str:
    """Build the provider-neutral repair contract."""

    return (
        f"{QUESTION_REPAIR_RULES}\n\n"
        "RESPONSE JSON SCHEMA:\n"
        f"{question_generation_schema_text()}"
    )
