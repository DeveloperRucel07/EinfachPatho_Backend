import json
import hashlib
import logging
import os
import re
import uuid
from typing import Optional

from django.core.cache import cache
from django.core.validators import URLValidator
from django.conf import settings
from django.db import IntegrityError, OperationalError, ProgrammingError, transaction
from django.db.models import Prefetch
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from google import genai
from google.genai import types

from pathology_app.models import (
    Disease,
    DiseaseGenerationState,
    DurstData,
    ImmediateAction,
    Question,
    Quiz,
    RiskFactor,
    Source,
    Symptom,
    UrsacheKeyword,
)

logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
prompt_json ="""
    Rolle: Du bist ein hochspezialisierter Experte für deutsche Medizin-Didaktik und Notfallmedizin.
    Aufgabe: Erstelle für den eingegebenen Krankheitsnamen einen Datensatz im DURST-Schema.
    Strikte Regeln:

    Sprache: Deutsch. Verwende medizinische Fachbegriffe, aber erkläre sie im Kontext präzise.
    Struktur: Halte dich zwingend an das D-U-R-S-T System.
    Quellen: Nutze ausschließlich aktuelle deutsche Standards (AWMF-Leitlinien, Pschyrembel, I care Krankeitlehre und I care Pflege). Gib den exakten Link zur AWMF-Leitlinie an.
    Pflege/Notfall: Liste klare, menschliche Sofortmaßnahmen auf (Lagerung, Betreuung).
    Quiz: - Erstelle 5 Multiple choice Fragen.
    - Jede Frage musst exakt 4 optinen haben.
    Format: Antworte ausschließlich im JSON-Format, damit die API die Daten direkt verarbeiten kann.
    {
        {
        "disease_id": "AP-2026-004",
        "name": "Apoplex (Schlaganfall)",
        "image": "https://googleusercontent.com/image_generation_content/3",
        "category": "Notfallmedizin / Neurologie",
        "durst_data": {
            "definition": "Ein Apoplex ist eine schlagartig auftretende Durchblutungsstörung im Gehirn (ischämisch, ca. 80 %) oder eine intrazerebrale Blutung (hämorrhagisch, ca. 20 %), die zu einem regionalen Mangel an Sauerstoff und Nährstoffen sowie konsekutiven neurologischen Ausfällen führt.",
            "ursachen": {
                "text": "Häufigste Ursache ist der Verschluss einer Hirnarterie durch Thromboembolien (oft bei Vorhofflimmern) oder lokale Arteriosklerose. Seltener sind Gefäßrupturen bei Hypertonie.",
                "keywords": [
                    "Ischämie",
                    "Thromboembolie",
                    "Arteriosklerose",
                    "Vorhofflimmern"
                ]
            },
            "risikofaktoren": [
                "Arterielle Hypertonie (Bluthochdruck) - wichtigster Faktor",
                "Vorhofflimmern (Herzrhythmusstörungen)",
                "Diabetes mellitus",
                "Rauchen und Bewegungsmangel",
                "Hohes Alter"
            ],
            "symptome": {
                "list": [
                    "Plötzliche Hemiparese (halbseitige Lähmung) oder Taubheitsgefühl",
                    "Aphasie (Sprachstörungen) oder Dysarthrie (Sprechstörungen)",
                    "Fazialisparese (hängender Mundwinkel)",
                    "Visusstörungen (Doppelbilder, Gesichtsfeldausfälle)",
                    "Schwindel und Gangunsicherheit"
                ],
                "red_flags": "FAST-Schema positiv (Face, Arms, Speech, Time), Bewusstseinsverlust, stärkste Vernichtungskopfschmerzen (Hinweis auf Blutung)"
            },
            "therapie_massnahmen": {
                "immediate_actions": [
                    "Sofortiger Notruf (112) - 'Time is Brain'",
                    "Oberkörperhochlagerung um 30° (zur Senkung des Hirndrucks, sofern kreislaufstabil)",
                    "Nüchtern lassen (Aspirationsgefahr bei Schluckstörungen!)",
                    "Engmaschige Überwachung (Bewusstsein, Blutdruck, Blutzucker)",
                    "Beruhigende Betreuung und Schutz gelähmter Körperteile"
                ],
                "diagnostic_gold_standard": "Cranial-CT (CCT) zum Ausschluss einer Blutung vor Lyse-Therapie",
                "guideline_link": "https://register.awmf.org/de/leitlinien/detail/030-046"
            }
        },
        "quiz": [
            {
                "id": 1,
                "question": "Wofür steht das 'S' im klinisch angewandten FAST-Schema?",
                "options": [
                    "Schmerz (Pain)",
                    "Sprache (Speech)",
                    "Schwindel (Dizziness)",
                    "Sehstörung (Vision)"
                ],
                "correct_index": 1,
                "explanation": "FAST steht für Face (Gesicht), Arms (Arme), Speech (Sprache) und Time (Zeit). Es dient der schnellen Identifikation von Schlaganfallsymptomen."
            },
            {
                "id": 2,
                "question": "Warum dürfen Patienten mit Schlaganfallverdacht bis zur ärztlichen Klärung nichts essen oder trinken?",
                "options": [
                    "Wegen der anstehenden Operation.",
                    "Um den Blutdruck nicht zu erhöhen.",
                    "Wegen der hohen Aspirationsgefahr durch mögliche Schluckstörungen (Dysphagie).",
                    "Damit die Labortests nicht verfälscht werden."
                ],
                "correct_index": 2,
                "explanation": "Viele Schlaganfallpatienten leiden unter Schluckstörungen. Eine Aspiration kann eine lebensgefährliche Pneumonie auslösen."
            },
            {
                "id": 3,
                "question": "Welches ist die wichtigste pflegerische Maßnahme zur Senkung des intrakraniellen Drucks?",
                "options": [
                    "Flachlagerung ohne Kissen.",
                    "Oberkörperhochlagerung um ca. 30 Grad.",
                    "Beine hochlagern (Schocklagerung).",
                    "Lagerung auf der betroffenen Seite."
                ],
                "correct_index": 1,
                "explanation": "Die 30°-Oberkörperhochlagerung verbessert den venösen Abfluss aus dem Gehirn und reduziert so den Hirndruck."
            },
            {
                "id": 4,
                "question": "Innerhalb welches Zeitfensters ist eine systemische Thrombolyse meist effektiv?",
                "options": [
                    "Innerhalb der ersten 4,5 Stunden nach Symptombeginn.",
                    "Nur in den ersten 30 Minuten.",
                    "Bis zu 24 Stunden nach Symptombeginn.",
                    "Es gibt kein Zeitlimit."
                ],
                "correct_index": 0,
                "explanation": "Die systemische Lyse zur Auflösung des Gerinnsels ist leitliniengemäß meist bis zu 4,5 Stunden nach dem Symptombeginn wirksam."
            },
            {
                "id": 5,
                "question": "Welche Herzrhythmusstörung ist ein Hauptrisikofaktor für ischämische Schlaganfälle?",
                "options": [
                    "Sinusbradykardie",
                    "Extrasystolen",
                    "Vorhofflimmern",
                    "Rechtsschenkelblock"
                ],
                "correct_index": 2,
                "explanation": "Bei Vorhofflimmern können sich Thromben im Herzen bilden, die ins Gehirn wandern und dort Gefäße verschließen."
            }
        ],
        "sources": [
            {
                "source_name": "AWMF S2e-Leitlinie Akuttherapie des ischämischen Schlaganfalls",
                "link": "https://register.awmf.org/de/leitlinien/detail/030-046"
            },
            {
                "source_name": "Pschyrembel Online - Apoplex",
                "link": "https://www.pschyrembel.de/Apoplex/K02G8"
            },
            {
                "source_name": "I care Pflege - Thieme Verlag",
                "link": "https://icare.thieme.de/ebooks/cs_11485596?context=#/ebook_cs_11485596__23626D5D_73D4_4440_9203_15E297B8F361"
            }
        ]
    },

    }

    """


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


def normalize_disease_name(name: Optional[str]) -> str:
    return (name or "").strip().casefold()


def disease_queryset():
    return (
        Disease.objects.select_related("durst_data")
        .prefetch_related(
            "durst_data__ursache_keywords",
            "durst_data__risk_factors",
            "durst_data__symptoms",
            "durst_data__immediate_actions",
            "quizzes__questions",
            "sources",
        )
    )


def disease_cache_key(normalized_name: str, owner_id: Optional[int] = None) -> str:
    digest = hashlib.sha256(normalized_name.encode("utf-8")).hexdigest()
    owner_part = owner_id if owner_id is not None else "global"
    return f"disease-generation:{owner_part}:{digest}"


class DiseaseGenerationError(Exception):
    pass


class GeneratedPayloadValidationError(DiseaseGenerationError):
    pass


class BaseDiseaseProvider:
    model_name = DEFAULT_GEMINI_MODEL

    def resolve_disease_name(self, prompt_text: str) -> str:
        raise NotImplementedError

    def generate_disease_payload(self, disease_name: str) -> dict:
        raise NotImplementedError


class GeminiProvider(BaseDiseaseProvider):
    model_name = DEFAULT_GEMINI_MODEL

    def resolve_disease_name(self, prompt_text: str) -> str:
        response = gemini_client.models.generate_content(
            model=self.model_name,
            config=types.GenerateContentConfig(
                system_instruction="du bist ein hochspezialisierter Experte fur deutsche Medizin und Notfall medizin. finde heraus welche Krankheit am besten zu der angebene Text passt.:"
            ),
            contents=prompt_text,
        )
        response_text = getattr(response, "text", None)
        if not isinstance(response_text, str) or not response_text.strip():
            raise GeneratedPayloadValidationError("Gemini did not return a disease name.")
        return response_text.strip()

    def generate_disease_payload(self, disease_name: str) -> dict:
        response = gemini_client.models.generate_content(
            model=self.model_name,
            config=types.GenerateContentConfig(system_instruction=prompt_json),
            contents=disease_name,
        )
        response_text = getattr(response, "text", None)
        if not isinstance(response_text, str) or not response_text.strip():
            raise GeneratedPayloadValidationError("Gemini did not return disease data.")
        disease_json = response_text.strip()
        return check_content_formatting(disease_json)


class OpenAIProvider(BaseDiseaseProvider):
    model_name = "openai"

    def resolve_disease_name(self, prompt_text: str) -> str:
        raise NotImplementedError("OpenAIProvider is a future extension point.")

    def generate_disease_payload(self, disease_name: str) -> dict:
        raise NotImplementedError("OpenAIProvider is a future extension point.")


class LocalLlamaProvider(BaseDiseaseProvider):
    model_name = "local-llama"

    def resolve_disease_name(self, prompt_text: str) -> str:
        raise NotImplementedError("LocalLlamaProvider is a future extension point.")

    def generate_disease_payload(self, disease_name: str) -> dict:
        raise NotImplementedError("LocalLlamaProvider is a future extension point.")


class DiseaseGenerationService:
    def __init__(self, provider=None, cache_backend=None):
        self.provider = provider or GeminiProvider()
        self.cache = cache_backend or cache
        self.url_validator = URLValidator()

    def get_or_generate(self, disease_name, requesting_user, prompt_text=None):
        requested_name = (disease_name or "").strip()

        cached = self._get_cached_disease(requested_name, requesting_user)
        if cached is not None:
            return cached

        existing = self._find_owner_disease(requested_name, requesting_user)
        if existing is not None:
            self._cache_disease(existing)
            return existing

        reusable = self._find_reusable_disease(requested_name)
        if reusable is not None:
            cloned = self._clone_disease_for_owner(reusable, requesting_user)
            self._cache_disease(cloned)
            return cloned

        canonical_name = requested_name
        if prompt_text:
            canonical_name = self.provider.resolve_disease_name(prompt_text)
            existing = self._find_owner_disease(canonical_name, requesting_user)
            if existing is not None:
                self._cache_disease(existing)
                return existing

            reusable = self._find_reusable_disease(canonical_name)
            if reusable is not None:
                cloned = self._clone_disease_for_owner(reusable, requesting_user)
                self._cache_disease(cloned)
                return cloned

        if not canonical_name:
            raise GeneratedPayloadValidationError("Disease name is required.")

        fallback_generation = None
        try:
            return self._generate_with_state(canonical_name, requesting_user)
        except (OperationalError, ProgrammingError) as exc:
            if not self._is_missing_generation_state_table(exc):
                raise
            logger.warning(
                "DiseaseGenerationState table unavailable; continuing without generation-state tracking",
                extra={"disease_name": canonical_name, "user_id": getattr(requesting_user, "id", None)},
            )
            fallback_generation = self._generate_without_state(canonical_name, requesting_user)

        return fallback_generation

    def persist_ai_payload(self, ai_payload, requesting_user, ai_model=None):
        self._validate_generated_payload(ai_payload)
        disease_name = ai_payload.get("name", "")

        cached = self._get_cached_disease(disease_name, requesting_user)
        if cached is not None:
            return cached

        existing = self._find_owner_disease(disease_name, requesting_user)
        if existing is not None:
            self._cache_disease(existing)
            return existing

        reusable = self._find_reusable_disease(disease_name)
        if reusable is not None:
            cloned = self._clone_disease_for_owner(reusable, requesting_user)
            self._cache_disease(cloned)
            return cloned

        ai_model = ai_model or self.provider.model_name

        fallback_generation = None
        try:
            return self._persist_with_state(ai_payload, requesting_user, ai_model)
        except (OperationalError, ProgrammingError) as exc:
            if not self._is_missing_generation_state_table(exc):
                raise
            logger.warning(
                "DiseaseGenerationState table unavailable during persistence; continuing without generation-state tracking",
                extra={"disease_name": disease_name, "user_id": getattr(requesting_user, "id", None)},
            )
            fallback_generation = self._persist_without_state(ai_payload, requesting_user)

        return fallback_generation

    def _generate_with_state(self, canonical_name, requesting_user):
        with transaction.atomic():
            state = self._lock_generation_state(canonical_name)
            existing = self._find_owner_disease(canonical_name, requesting_user)
            if existing is not None:
                self._attach_existing_disease(state, existing)
                self._cache_disease(existing)
                return existing

            reusable = self._find_reusable_disease(canonical_name)
            if reusable is not None:
                disease = self._clone_disease_for_owner(reusable, requesting_user)
                self._attach_existing_disease(state, reusable)
                self._cache_disease(disease)
                return disease

            state.original_name = canonical_name
            state.status = DiseaseGenerationState.Status.GENERATING
            state.ai_model = self.provider.model_name
            state.generation_error = ""
            state.save(update_fields=["original_name", "status", "ai_model", "generation_error", "updated_at"])

            try:
                ai_payload = self.provider.generate_disease_payload(canonical_name)
                self._validate_generated_payload(ai_payload)
                disease = self._store_validated_payload(ai_payload, requesting_user)
            except GeneratedPayloadValidationError as exc:
                state.status = DiseaseGenerationState.Status.FAILED
                state.ai_model = self.provider.model_name
                state.generation_error = str(exc)
                state.save(update_fields=["status", "ai_model", "generation_error", "updated_at"])
                logger.info(
                    "Disease generation validation failed",
                    extra={"disease_name": canonical_name, "user_id": getattr(requesting_user, "id", None)},
                )
                raise
            except Exception as exc:
                state.status = DiseaseGenerationState.Status.FAILED
                state.ai_model = self.provider.model_name
                state.generation_error = str(exc)
                state.save(update_fields=["status", "ai_model", "generation_error", "updated_at"])
                logger.exception("Disease generation failed", extra={"disease_name": canonical_name, "user_id": getattr(requesting_user, "id", None)})
                raise

            self._attach_ready_disease(state, disease)
            self._cache_disease(disease)
            return disease

    def _persist_with_state(self, ai_payload, requesting_user, ai_model):
        disease_name = ai_payload.get("name", "")
        with transaction.atomic():
            state = self._lock_generation_state(disease_name)
            existing = self._find_owner_disease(disease_name, requesting_user)
            if existing is not None:
                self._attach_existing_disease(state, existing)
                self._cache_disease(existing)
                return existing

            reusable = self._find_reusable_disease(disease_name)
            if reusable is not None:
                disease = self._clone_disease_for_owner(reusable, requesting_user)
                self._attach_existing_disease(state, reusable)
                self._cache_disease(disease)
                return disease

            state.original_name = disease_name
            state.status = DiseaseGenerationState.Status.GENERATING
            state.ai_model = ai_model
            state.generation_error = ""
            state.save(update_fields=["original_name", "status", "ai_model", "generation_error", "updated_at"])

            try:
                disease = self._store_validated_payload(ai_payload, requesting_user)
            except GeneratedPayloadValidationError as exc:
                state.status = DiseaseGenerationState.Status.FAILED
                state.ai_model = ai_model
                state.generation_error = str(exc)
                state.save(update_fields=["status", "ai_model", "generation_error", "updated_at"])
                logger.info(
                    "Disease persistence validation failed",
                    extra={"disease_name": disease_name, "user_id": getattr(requesting_user, "id", None)},
                )
                raise
            except Exception as exc:
                state.status = DiseaseGenerationState.Status.FAILED
                state.ai_model = ai_model
                state.generation_error = str(exc)
                state.save(update_fields=["status", "ai_model", "generation_error", "updated_at"])
                logger.exception("Disease persistence failed", extra={"disease_name": disease_name, "user_id": getattr(requesting_user, "id", None)})
                raise

            self._attach_ready_disease(state, disease)
            self._cache_disease(disease)
            return disease

    def _generate_without_state(self, canonical_name, requesting_user):
        existing = self._find_owner_disease(canonical_name, requesting_user)
        if existing is not None:
            self._cache_disease(existing)
            return existing

        reusable = self._find_reusable_disease(canonical_name)
        if reusable is not None:
            cloned = self._clone_disease_for_owner(reusable, requesting_user)
            self._cache_disease(cloned)
            return cloned

        with transaction.atomic():
            existing = self._find_owner_disease(canonical_name, requesting_user)
            if existing is not None:
                self._cache_disease(existing)
                return existing

            reusable = self._find_reusable_disease(canonical_name)
            if reusable is not None:
                cloned = self._clone_disease_for_owner(reusable, requesting_user)
                self._cache_disease(cloned)
                return cloned

            ai_payload = self.provider.generate_disease_payload(canonical_name)
            self._validate_generated_payload(ai_payload)
            disease = self._store_validated_payload(ai_payload, requesting_user)

        self._cache_disease(disease)
        return disease

    def _persist_without_state(self, ai_payload, requesting_user):
        disease_name = ai_payload.get("name", "")
        existing = self._find_owner_disease(disease_name, requesting_user)
        if existing is not None:
            self._cache_disease(existing)
            return existing

        reusable = self._find_reusable_disease(disease_name)
        if reusable is not None:
            cloned = self._clone_disease_for_owner(reusable, requesting_user)
            self._cache_disease(cloned)
            return cloned

        with transaction.atomic():
            existing = self._find_owner_disease(disease_name, requesting_user)
            if existing is not None:
                self._cache_disease(existing)
                return existing

            reusable = self._find_reusable_disease(disease_name)
            if reusable is not None:
                cloned = self._clone_disease_for_owner(reusable, requesting_user)
                self._cache_disease(cloned)
                return cloned

            disease = self._store_validated_payload(ai_payload, requesting_user)

        self._cache_disease(disease)
        return disease

    def _is_missing_generation_state_table(self, exc):
        return "pathology_app_diseasegenerationstate" in str(exc).casefold()

    def _get_cached_disease(self, disease_name, requesting_user=None):
        normalized_name = normalize_disease_name(disease_name)
        if not normalized_name:
            return None

        owner_id = getattr(requesting_user, "id", None)
        cache_value = self.cache.get(disease_cache_key(normalized_name, owner_id))
        if cache_value is None:
            return None

        disease = self._fetch_disease_by_id(cache_value)
        if disease is None:
            self.cache.delete(disease_cache_key(normalized_name, owner_id))
            return None

        if owner_id is not None and disease.owner_id != owner_id:
            self.cache.delete(disease_cache_key(normalized_name, owner_id))
            return None

        return disease

    def _cache_disease(self, disease):
        normalized_name = normalize_disease_name(disease.name)
        if normalized_name:
            self.cache.set(disease_cache_key(normalized_name, disease.owner_id), disease.id, timeout=None)

    def _fetch_disease_by_id(self, disease_id):
        return disease_queryset().filter(id=disease_id).first()

    def _find_owner_disease(self, disease_name, requesting_user):
        normalized_name = normalize_disease_name(disease_name)
        if not normalized_name:
            return None

        return (
            disease_queryset()
            .annotate(normalized_name_db=Lower(Trim("name")))
            .filter(normalized_name_db=normalized_name, owner=requesting_user)
            .first()
        )

    def _find_reusable_disease(self, disease_name):
        normalized_name = normalize_disease_name(disease_name)
        if not normalized_name:
            return None

        return (
            disease_queryset()
            .annotate(normalized_name_db=Lower(Trim("name")))
            .filter(normalized_name_db=normalized_name)
            .order_by("created_at", "id")
            .first()
        )

    def _clone_disease_for_owner(self, source_disease, requesting_user):
        if source_disease.owner_id == getattr(requesting_user, "id", None):
            return source_disease

        existing = Disease.objects.filter(owner=requesting_user, disease_id=source_disease.disease_id).first()
        if existing is not None:
            return self._fetch_disease_by_id(existing.id)

        cloned_disease = Disease.objects.create(
            owner=requesting_user,
            disease_id=source_disease.disease_id,
            name=source_disease.name,
            image=source_disease.image,
            category=source_disease.category,
        )

        source_durst = getattr(source_disease, "durst_data", None)
        if source_durst is not None:
            cloned_durst = DurstData.objects.create(
                disease=cloned_disease,
                definition=source_durst.definition,
                ursachen=source_durst.ursachen,
                red_flags=source_durst.red_flags,
                diagnostic_gold_standard=source_durst.diagnostic_gold_standard,
                guideline_link=source_durst.guideline_link,
            )

            UrsacheKeyword.objects.bulk_create([
                UrsacheKeyword(durst_data=cloned_durst, keyword=item.keyword)
                for item in source_durst.ursache_keywords.all()
            ])
            RiskFactor.objects.bulk_create([
                RiskFactor(durst_data=cloned_durst, text=item.text)
                for item in source_durst.risk_factors.all()
            ])
            Symptom.objects.bulk_create([
                Symptom(durst_data=cloned_durst, text=item.text)
                for item in source_durst.symptoms.all()
            ])
            ImmediateAction.objects.bulk_create([
                ImmediateAction(durst_data=cloned_durst, text=item.text)
                for item in source_durst.immediate_actions.all()
            ])

        Source.objects.bulk_create([
            Source(disease=cloned_disease, source_name=source.source_name, link=source.link)
            for source in source_disease.sources.all()
        ])

        for source_quiz in source_disease.quizzes.all():
            cloned_quiz = Quiz.objects.create(disease=cloned_disease, title=source_quiz.title)
            Question.objects.bulk_create([
                Question(
                    quiz=cloned_quiz,
                    question=question.question,
                    options=question.options,
                    correct_index=question.correct_index,
                    explanation=question.explanation,
                )
                for question in source_quiz.questions.all()
            ])

        return self._fetch_disease_by_id(cloned_disease.id)

    def _lock_generation_state(self, disease_name):
        normalized_name = normalize_disease_name(disease_name)
        try:
            state, _ = DiseaseGenerationState.objects.select_for_update().get_or_create(
                normalized_name=normalized_name,
                defaults={
                    "original_name": disease_name.strip(),
                    "status": DiseaseGenerationState.Status.PENDING,
                },
            )
        except IntegrityError:
            state = DiseaseGenerationState.objects.select_for_update().get(normalized_name=normalized_name)

        return state

    def _attach_existing_disease(self, state, disease):
        state.disease = disease
        state.original_name = disease.name
        state.status = DiseaseGenerationState.Status.READY
        state.generated_at = disease.created_at
        if not state.ai_model:
            state.ai_model = self.provider.model_name
        state.generation_error = ""
        state.save(
            update_fields=[
                "disease",
                "original_name",
                "status",
                "generated_at",
                "ai_model",
                "generation_error",
                "updated_at",
            ]
        )

    def _attach_ready_disease(self, state, disease):
        state.disease = disease
        state.original_name = disease.name
        state.status = DiseaseGenerationState.Status.READY
        state.generated_at = timezone.now()
        state.ai_model = self.provider.model_name
        state.generation_error = ""
        state.save(
            update_fields=[
                "disease",
                "original_name",
                "status",
                "generated_at",
                "ai_model",
                "generation_error",
                "updated_at",
            ]
        )

    def _validate_generated_payload(self, ai_payload):
        if not isinstance(ai_payload, dict):
            raise GeneratedPayloadValidationError("Gemini output must be a JSON object.")

        required_fields = ["disease_id", "name", "image", "category", "durst_data", "quiz", "sources"]
        missing_fields = [field for field in required_fields if field not in ai_payload]
        if missing_fields:
            raise GeneratedPayloadValidationError(f"Missing required fields: {', '.join(missing_fields)}")

        for field_name in ["disease_id", "name", "image", "category"]:
            value = ai_payload.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise GeneratedPayloadValidationError(f"Field '{field_name}' must be a non-empty string.")

        self._validate_url(ai_payload.get("image"), "image")

        durst_data = ai_payload.get("durst_data")
        if not isinstance(durst_data, dict):
            raise GeneratedPayloadValidationError("Field 'durst_data' must be an object.")

        self._validate_durst_data(durst_data)

        quiz_items = ai_payload.get("quiz")
        if not isinstance(quiz_items, list) or len(quiz_items) != 5:
            raise GeneratedPayloadValidationError("Field 'quiz' must contain exactly 5 questions.")
        self._validate_quiz_items(quiz_items)

        sources = ai_payload.get("sources")
        if not isinstance(sources, list):
            raise GeneratedPayloadValidationError("Field 'sources' must be a list.")
        self._validate_sources(sources)

    def _validate_durst_data(self, durst_data):
        required = ["definition", "ursachen", "risikofaktoren", "symptome", "therapie_massnahmen"]
        missing = [field for field in required if field not in durst_data]
        if missing:
            raise GeneratedPayloadValidationError(f"Missing DURST fields: {', '.join(missing)}")

        definition = durst_data.get("definition")
        if not isinstance(definition, str) or not definition.strip():
            raise GeneratedPayloadValidationError("durst_data.definition must be a non-empty string.")

        ursachen = durst_data.get("ursachen")
        if not isinstance(ursachen, dict):
            raise GeneratedPayloadValidationError("durst_data.ursachen must be an object.")
        if not isinstance(ursachen.get("text"), str) or not ursachen.get("text", "").strip():
            raise GeneratedPayloadValidationError("durst_data.ursachen.text must be a non-empty string.")
        keywords = ursachen.get("keywords")
        if not isinstance(keywords, list) or any(not isinstance(item, str) or not item.strip() for item in keywords):
            raise GeneratedPayloadValidationError("durst_data.ursachen.keywords must be a list of strings.")
        if len({normalize_disease_name(item) for item in keywords}) != len(keywords):
            raise GeneratedPayloadValidationError("durst_data.ursachen.keywords must not contain duplicates.")

        risk_factors = durst_data.get("risikofaktoren")
        if not isinstance(risk_factors, list) or any(not isinstance(item, str) or not item.strip() for item in risk_factors):
            raise GeneratedPayloadValidationError("durst_data.risikofaktoren must be a list of strings.")

        symptoms = durst_data.get("symptome")
        if not isinstance(symptoms, dict):
            raise GeneratedPayloadValidationError("durst_data.symptome must be an object.")
        symptom_list = symptoms.get("list")
        if not isinstance(symptom_list, list) or any(not isinstance(item, str) or not item.strip() for item in symptom_list):
            raise GeneratedPayloadValidationError("durst_data.symptome.list must be a list of strings.")
        red_flags = symptoms.get("red_flags")
        if red_flags is not None and not isinstance(red_flags, str):
            raise GeneratedPayloadValidationError("durst_data.symptome.red_flags must be a string.")

        therapy = durst_data.get("therapie_massnahmen")
        if not isinstance(therapy, dict):
            raise GeneratedPayloadValidationError("durst_data.therapie_massnahmen must be an object.")
        immediate_actions = therapy.get("immediate_actions")
        if not isinstance(immediate_actions, list) or any(not isinstance(item, str) or not item.strip() for item in immediate_actions):
            raise GeneratedPayloadValidationError("durst_data.therapie_massnahmen.immediate_actions must be a list of strings.")
        diagnostic_gold_standard = therapy.get("diagnostic_gold_standard")
        if diagnostic_gold_standard is not None and not isinstance(diagnostic_gold_standard, str):
            raise GeneratedPayloadValidationError("durst_data.therapie_massnahmen.diagnostic_gold_standard must be a string.")
        guideline_link = therapy.get("guideline_link")
        if not isinstance(guideline_link, str) or not guideline_link.strip():
            raise GeneratedPayloadValidationError("durst_data.therapie_massnahmen.guideline_link must be a URL string.")
        self._validate_url(guideline_link, "durst_data.therapie_massnahmen.guideline_link")

    def _validate_quiz_items(self, quiz_items):
        seen_questions = set()
        for index, question in enumerate(quiz_items, start=1):
            if not isinstance(question, dict):
                raise GeneratedPayloadValidationError(f"Quiz item {index} must be an object.")

            question_text = question.get("question")
            if not isinstance(question_text, str) or not question_text.strip():
                raise GeneratedPayloadValidationError(f"Quiz item {index} needs a question string.")
            normalized_question = normalize_disease_name(question_text)
            if normalized_question in seen_questions:
                raise GeneratedPayloadValidationError("Quiz questions must not be duplicated.")
            seen_questions.add(normalized_question)

            options = question.get("options")
            if not isinstance(options, list) or len(options) != 4:
                raise GeneratedPayloadValidationError(f"Quiz item {index} must contain exactly 4 options.")
            if any(not isinstance(option, str) or not option.strip() for option in options):
                raise GeneratedPayloadValidationError(f"Quiz item {index} contains invalid options.")
            if len({normalize_disease_name(option) for option in options}) != len(options):
                raise GeneratedPayloadValidationError(f"Quiz item {index} contains duplicate options.")

            correct_index = question.get("correct_index")
            if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= len(options):
                raise GeneratedPayloadValidationError(f"Quiz item {index} has an invalid correct_index.")

            explanation = question.get("explanation")
            if explanation is not None and not isinstance(explanation, str):
                raise GeneratedPayloadValidationError(f"Quiz item {index} explanation must be a string.")

    def _validate_sources(self, sources):
        seen_links = set()
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                raise GeneratedPayloadValidationError(f"Source item {index} must be an object.")

            source_name = source.get("source_name")
            link = source.get("link")
            if not isinstance(source_name, str) or not source_name.strip():
                raise GeneratedPayloadValidationError(f"Source item {index} must include source_name.")
            if not isinstance(link, str) or not link.strip():
                raise GeneratedPayloadValidationError(f"Source item {index} must include a URL link.")
            self._validate_url(link, f"sources[{index - 1}].link")

            normalized_link = link.strip().casefold()
            if normalized_link in seen_links:
                raise GeneratedPayloadValidationError("Duplicate source links are not allowed.")
            seen_links.add(normalized_link)

    def _validate_url(self, value, field_name):
        try:
            self.url_validator(value)
        except Exception as exc:
            raise GeneratedPayloadValidationError(f"{field_name} must be a valid URL.") from exc

    def _store_validated_payload(self, ai_payload, requesting_user):
        disease = Disease.objects.create(
            owner=requesting_user,
            disease_id=ai_payload.get("disease_id", "").strip(),
            name=ai_payload.get("name", "").strip(),
            image=ai_payload.get("image", "").strip(),
            category=ai_payload.get("category", "").strip(),
        )

        durst_data_payload = ai_payload.get("durst_data", {})
        durst_data = DurstData.objects.create(
            disease=disease,
            definition=durst_data_payload.get("definition", "").strip(),
            ursachen=durst_data_payload.get("ursachen", {}).get("text", "").strip(),
            red_flags=durst_data_payload.get("symptome", {}).get("red_flags", "") or "",
            diagnostic_gold_standard=durst_data_payload.get("therapie_massnahmen", {}).get("diagnostic_gold_standard", "") or "",
            guideline_link=durst_data_payload.get("therapie_massnahmen", {}).get("guideline_link", "").strip(),
        )

        UrsacheKeyword.objects.bulk_create([
            UrsacheKeyword(durst_data=durst_data, keyword=keyword.strip())
            for keyword in durst_data_payload.get("ursachen", {}).get("keywords", [])
        ])

        RiskFactor.objects.bulk_create([
            RiskFactor(durst_data=durst_data, text=risk_factor.strip())
            for risk_factor in durst_data_payload.get("risikofaktoren", [])
        ])

        Symptom.objects.bulk_create([
            Symptom(durst_data=durst_data, text=symptom.strip())
            for symptom in durst_data_payload.get("symptome", {}).get("list", [])
        ])

        ImmediateAction.objects.bulk_create([
            ImmediateAction(durst_data=durst_data, text=action.strip())
            for action in durst_data_payload.get("therapie_massnahmen", {}).get("immediate_actions", [])
        ])

        sources = []
        seen_links = set()
        for source in ai_payload.get("sources", []):
            normalized_link = source["link"].strip().casefold()
            if normalized_link in seen_links:
                raise GeneratedPayloadValidationError("Duplicate source links are not allowed.")
            seen_links.add(normalized_link)
            sources.append(
                Source(
                    disease=disease,
                    source_name=source["source_name"].strip(),
                    link=source["link"].strip(),
                )
            )
        Source.objects.bulk_create(sources)

        quiz = Quiz.objects.create(disease=disease, title=f"Quiz for {disease.name}")
        questions = [
            Question(
                quiz=quiz,
                question=item["question"].strip(),
                options=item["options"],
                correct_index=item["correct_index"],
                explanation=(item.get("explanation", "") or "").strip(),
            )
            for item in ai_payload.get("quiz", [])
        ]
        Question.objects.bulk_create(questions)

        return disease


def check_content_formatting(disease_content):
    if not isinstance(disease_content, str) or not disease_content.strip():
        raise GeneratedPayloadValidationError('Gemini output was empty.')

    try:
        return json.loads(disease_content)
    except json.JSONDecodeError:
        # If the model mixes prose with JSON, extract the object body.
        start = disease_content.find('{')
        end = disease_content.rfind('}') + 1
        if start != -1 and end > start:
            try:
                return json.loads(disease_content[start:end])
            except json.JSONDecodeError as exc:
                raise GeneratedPayloadValidationError('Gemini output was not valid JSON.') from exc

        raise GeneratedPayloadValidationError('Gemini output was not valid JSON.')

def find_disease_by_prompt(prompt):
    return GeminiProvider().resolve_disease_name(prompt)

def create_disease_image_with_nanobanana(disease_name):
    prompt_image = f"generiere ein medizinisches Bild, das die Krankheit {disease_name} repräsentiert. Das Bild soll informativ und didaktisch sein, um die wichtigsten Merkmale der Krankheit zu veranschaulichen. Es sollte klare visuelle Elemente enthalten, die die Symptome, betroffenen Organe oder andere relevante Aspekte der Krankheit darstellen. Das Bild soll in einem Stil gehalten sein, der für medizinische Lehrmaterialien geeignet ist."
    response = gemini_client.models.generate_content(
        model="gemini-3.1-flash-image",
        contents=prompt_image,
    )
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if part.inline_data:
                image = part.as_image()
                safe_name = re.sub(r'[^A-Za-z0-9_-]', '_', disease_name)[:80]
                image_path = os.path.join(
                    settings.MEDIA_ROOT,
                    "generated",
                    f"{safe_name}-{uuid.uuid4().hex[:8]}.png",
                )
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                image.save(image_path)
                return image_path

    return None

def create_disease_json_for_durst(disease_name):
    try:
        return GeminiProvider().generate_disease_payload(disease_name)
    except Exception as e:
        logging.error(f"Error generating disease JSON for {disease_name}: {e}")
        raise
    finally:
        pass

def transform_ai_json(ai_json):
    durst = ai_json.get("durst_data", {})

    durst_data =  {
        "disease_id": ai_json.get("disease_id"),
        "name": ai_json.get("name"),
        "image": ai_json.get("image"),
        "category": ai_json.get("category"),

        "durst_data": {
            "definition": durst.get("definition"),

            "ursachen_text": durst.get("ursachen", {}).get("text"),
            "ursache_keywords": durst.get("ursachen", {}).get("keywords", []),

            "risk_factors": durst.get("risikofaktoren", []),

            "symptoms": durst.get("symptome", {}).get("list", []),
            "red_flags": durst.get("symptome", {}).get("red_flags"),

            "immediate_actions": durst.get("therapie_massnahmen", {}).get("immediate_actions", []),
            "diagnostic_gold_standard": durst.get("therapie_massnahmen", {}).get("diagnostic_gold_standard"),
            "guideline_link": durst.get("therapie_massnahmen", {}).get("guideline_link"),
        }
    }
    return durst_data

def transform_quiz(ai_json, disease_instance):
    quiz_data = {
        "title": f"Quiz for {ai_json.get('name')}",
        "disease": disease_instance.id,
        "questions": [
            {
                "question": q.get("question"),
                "options": q.get("options"),
                "correct_index": q.get("correct_index"),
                "explanation": q.get("explanation"),
            }
            for q in ai_json.get("quiz", [])
        ]
    }

    return quiz_data


def save_disease_json_in_database(disease_json, owner=None):
    if owner is None:
        raise ValueError("owner is required to persist a disease.")

    return DiseaseGenerationService().persist_ai_payload(disease_json, owner)







