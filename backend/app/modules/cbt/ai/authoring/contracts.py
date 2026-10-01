"""Provider-facing contracts for CBT AI structured question output."""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import BaseModel

from app.modules.cbt.ai.authoring.schemas import (
    AIQuestionBatchDraft,
    AIRegeneratedQuestionDraft,
)


DIFFICULTY_RULES = """
The authoring request contains a `difficulty` field with one of these values:
`easy`, `medium`, or `difficult`. During repair, read the target difficulty from
`original_request.difficulty`.

Interpret difficulty relative to the supplied academic_level. Never make a
question harder by introducing subject matter that belongs above the requested
academic level or outside the supplied topics/context.

When difficulty is "easy":

- Prefer direct recall, recognition, definitions, identification, and simple
  one-step reasoning or calculations.
- Keep wording straightforward and distractors clearly distinguishable for a
  learner who understands the taught concept.

When difficulty is "medium":

- Prefer understanding and application of the taught concept.
- Questions may require a short scenario, a brief calculation, connecting two
  related facts, interpreting supplied information, or distinguishing between
  plausible distractors.

When difficulty is "difficult":

- Prefer deeper application, comparison, inference, analysis, or multi-step
  reasoning that remains appropriate for the supplied academic_level.
- Use plausible distractors that reflect common misconceptions where useful.
- Difficulty must come from cognitive demand and application, not obscure
  wording, trick questions, ambiguity, or material beyond the requested level.

For every difficulty level, keep questions fair, unambiguous, and answerable
from the requested curriculum scope.
""".strip()


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

- The generated batch must contain at least one question that genuinely
  uses a visual.
- Text-only questions must remain dominant. When generating three or more
  questions, the number of visual-bearing questions must be lower than the
  number of text-only questions.
- For a two-question batch, one visual-bearing question and one text-only
  question is acceptable.
- For a one-question batch, the single question must contain a meaningful
  visual directive.
- Do not attach decorative or irrelevant images just to satisfy the rule.
  Instead, formulate visual questions where the image has real assessment
  value for the supplied subject, topic, level, and author instructions.
- A question counts as visual-bearing when the question itself or at least
  one answer option contains an image directive.
- Every question or answer option that depends on a visual must contain the
  corresponding complete image directive.
- Never refer to a missing visual.

An image directive describes a visual that will be resolved later by the
application. Never invent image URLs, media IDs, asset IDs, database IDs,
or file paths.

For every image directive:

- `requirement` is the detailed semantic description of the visual the
  question actually needs. Be precise here.
- `search_query` is NOT an image-generation prompt. It is a strict keyword
  retrieval query for web-image search. Use only 2 to 4 concrete, noun-heavy
  content keywords that are likely to exist in image titles, descriptions,
  or tags. Keep it broad enough to retrieve candidates for later visual
  evaluation.
- Do not pad `search_query` with generic words such as "clear", "educational",
  "study", "biology", "science", "image", "picture", "illustration", or
  "diagram" unless that word is essential to the subject itself.
- Prefer `search_query` values like "tree rings", "animal cell", or
  "human skeleton" over descriptive phrases like "clear educational biology
  diagram showing a tree trunk cross section with annual rings".
- `generation_prompt` may be detailed and descriptive because it is used only
  when web retrieval cannot supply a suitable image.
""".strip()


REFERENCE_IMAGE_RULES = """
The application may attach existing reference images to regeneration or repair
requests. These are real image inputs supplied separately from the JSON text.
When the request contains an object with `reference_image_label`, use the
attached image with the same label as the visual content for that location.
Do not treat `reference_image_label` as a URL, file path, or text description,
and do not copy it into the response schema.
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
  question-type distribution, difficulty, visual policy, and author instructions.

{DIFFICULTY_RULES}

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

- Rewrite the question to the requested difficulty while remaining within the
  supplied academic_level and topic scope.
- Follow the visual policy in the request even when the original question
  used a different visual style.
- If visual_mode is text_only, rewrite the regenerated question so it is
  fully answerable without a visual.
- If visual_mode is auto, the regenerated question must contain at least
  one meaningful question-level or option-level image directive.

{DIFFICULTY_RULES}

{REFERENCE_IMAGE_RULES}

{VISUAL_POLICY_RULES}

Return only JSON matching the supplied response schema.
Do not return markdown, code fences, commentary, or additional text.
""".strip()


QUESTION_REPAIR_RULES = f"""
You previously generated an invalid CBT question batch.

Repair the supplied output using the validation feedback.

Rules:

- Correct every reported validation issue.
- Do not create unrelated questions.
- Preserve valid question content where possible.
- Preserve the original academic intent.
- Follow the original request, including its difficulty and visual_mode policy.
- Return the complete repaired batch, not a patch or diff.
- Follow the same response schema.
- If `invalid_questions` is empty because the previous provider response could
  not be parsed as structured JSON, regenerate the complete batch once from
  `original_request` and the supplied validation feedback.
- A malformed or structurally unusable prior response is not permission to
  change the requested question count, question-type distribution, topics,
  academic level, difficulty, visual policy, or author instructions.

{DIFFICULTY_RULES}

{REFERENCE_IMAGE_RULES}

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
        f"{QUESTION_GENERATION_RULES}\n\nRESPONSE JSON SCHEMA:\n{question_generation_schema_text()}"
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
    return f"{QUESTION_REPAIR_RULES}\n\nRESPONSE JSON SCHEMA:\n{question_generation_schema_text()}"
