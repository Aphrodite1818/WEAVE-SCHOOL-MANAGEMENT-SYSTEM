from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass , field
from typing import Any , Mapping , Sequence



@dataclass(slots = True)
class ProviderUsage:
    """
    Normalized usage/cost metadata returned by a provider call
    """

    input_tokens : int = 0
    output_tokens : int = 0
    cache_read_tokens : int = 0

    #optional provider-side calculated cost , if available
    provider_cost : float | None = None
    currency : str | None  = "USD"


@dataclass(slots = True)
class ProviderQuestionGenerationResult:
    """
    Result returned when a provider generates a batch of 
    draft questions

    'question' is intentionally kept as a list of dict for now
    because the final CBT AI domain schemas are not locked yet.
    The orchestration/validation layer will later validate and
    normalize these strictly before they are returned to CBT
    """

    questions : list[dict[str , Any]]
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    raw_response : dict[str, Any] | None = None



@dataclass(slots = True)
class ProviderQuestionRegenerationResult:
    """
    Result returned when a provider regenerates/ transforms a 
    single draft question
    """

    question : dict[str , Any]
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    raw_response : dict[str , Any] | None = None

@dataclass(slots=True)
class ProviderGeneratedImage:
    """
    Normalized generated-image payload.

    The provider may either return:
    - a direct URL,
    - or base64/image bytes represented as a string,
    depending on how the concrete implementation is designed.

    The orchestration layer can decide how to persist or further
    process the asset.
    """

    content_type: str
    data_base64: str | None = None
    url: str | None = None

    width: int | None = None
    height: int | None = None

    alt_text: str | None = None


@dataclass(slots=True)
class ProviderImageGenerationResult:
    """
    Result returned when a provider generates one image.
    """

    image: ProviderGeneratedImage
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    raw_response: dict[str, Any] | None = None


@dataclass(slots=True)
class ImageCandidate:
    """
    Normalized representation of a sourced/retrieved image
    candidate from a search provider such as Openverse.
    """

    source: str
    source_url: str

    external_id: str | None = None
    title: str | None = None

    image_url: str | None = None
    thumbnail_url: str | None = None

    creator: str | None = None
    attribution_text: str | None = None

    license_name: str | None = None
    license_url: str | None = None

    width: int | None = None
    height: int | None = None
    mime_type: str | None = None



class BaseProvider(ABC):
    """
    Base provider class for all CBT AI providers
    """


    provider_name : str

    @abstractmethod
    def is_configured(self)->bool:
        """
        Return True if the provider has the minimum configuration
        required to operate

        This should NOT crash applications startup. It is meant to 
        support runtime checks because provider credentials are 
        allowed to be absent in environments where CBT AI is not being 
        used
        """

        raise NotImplementedError




class BaseQuestionGenerationProvider(BaseProvider , ABC):
    """
    Contract for providers that generate or transform CBT 
    question drafts
    """



    @abstractmethod
    async def generate_questions(
        self,
        *,
        request : Mapping[str , Any]
    )->ProviderQuestionGenerationResult:
        """
        Generate a batch of draft questions

        Expected request payload (roughly)
        - subject / class / level context
        - allowed topics
        - question types
        - free-form author instruction
        - image preference/policy
        """
        raise NotImplementedError




    @abstractmethod
    async def regenerate_question(
        self,
        *,
        request : Mapping[str, Any]
    )->ProviderQuestionRegenerationResult:
        """
        Regenerate/transform a single existing draft question


        Expected request payload (roughly):
        - current question draft
        - subject / class / topic context
        - transformation instruction
        - image policy
        """
        raise NotImplementedError


class BaseImageGenerationProvider(BaseProvider, ABC):
    """
    Contract for providers that generate new images
    (e.g. diagrams, illustrations, visual options).
    """

    @abstractmethod
    async def generate_image(
        self,
        *,
        prompt: str,
        metadata: Mapping[str, Any] | None = None,
        reference_images: Sequence[str] | None = None,
    ) -> ProviderImageGenerationResult:
        """
        Generate a single image.

        `metadata` can carry implementation-specific but still
        provider-agnostic instructions such as:
        - image role: stem / option
        - style hint
        - size hint
        - educational context
        """
        raise NotImplementedError


class BaseImageSearchProvider(BaseProvider, ABC):
    """
    Contract for providers that retrieve/reference suitable
    existing images instead of generating them.
    """

    @abstractmethod
    async def search(
        self,
        *,
        query: str,
        limit: int = 10,
        metadata: Mapping[str, Any] | None = None,
    ) -> list[ImageCandidate]:
        """
        Search for candidate images.

        `metadata` can later be used to refine retrieval with
        additional constraints such as:
        - safe educational usage
        - preferred orientation
        - preferred license requirements
        - subject/topic hints
        """
        raise NotImplementedError