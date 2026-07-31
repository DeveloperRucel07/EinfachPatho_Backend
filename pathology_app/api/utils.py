import json
import logging
import os
import re
import uuid
from django.conf import settings
from google import genai
from google.genai import types

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
                "link": "https://www.thieme.de/de/pflege/i-care-pflege-150352.htm"
            }
        ]
    },

    }

    """


def check_content_formatting(disease_content):
    try:
        return json.loads(disease_content)
    except json.JSONDecodeError:
        '''
        If the model mixes text with JSON → look for JSON part
        '''
        start = disease_content.find('{')
        end = disease_content.rfind('}') + 1
        if start != -1 and end != -1:
            return json.loads(disease_content[start:end])
        else:
            raise ValueError('Gemini output was not valid JSON.')

def find_disease_by_prompt(prompt):
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
    config=types.GenerateContentConfig(system_instruction="du bist ein hochspezialisierter Experte fur deutsche Medizin und Notfall medizin. finde heraus welche Krankheit am besten zu der angebene Text passt.:"),
    contents=prompt,
    )
    
    disease_name = response.text.strip()
    return disease_name

def create_disease_image_with_nanobanana(disease_name):
    prompt_image = f"generiere ein medizinisches Bild, das die Krankheit {disease_name} repräsentiert. Das Bild soll informativ und didaktisch sein, um die wichtigsten Merkmale der Krankheit zu veranschaulichen. Es sollte klare visuelle Elemente enthalten, die die Symptome, betroffenen Organe oder andere relevante Aspekte der Krankheit darstellen. Das Bild soll in einem Stil gehalten sein, der für medizinische Lehrmaterialien geeignet ist."
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash-image",
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
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
        config=types.GenerateContentConfig(system_instruction=prompt_json),
        contents=disease_name,
        )
        disease_json = response.text.strip()
        disease = check_content_formatting(disease_json)
        return disease
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
    """Persist a disease document returned by the AI.

    The function delegates to :class:`DiseaseCreateSerializer` so that the
    complete nested structure is handled in one shot.  ``owner`` may be passed in
    (usually the request user); if omitted the serializer will raise when it
    tries to access ``self.context['request']``.

    The older transform logic remains available but is no longer used.
    """
    from pathology_app.api.serializers import DiseaseCreateSerializer

    # the JSON coming from the model is already expected to match the create
    # serializer's structure, so we can forward it directly.
    context = {} if owner is None else {'request': type('O', (), {'user': owner})}
    serializer = DiseaseCreateSerializer(data=disease_json, context=context)
    if serializer.is_valid():
        return serializer.save()
    else:
        raise ValueError(f"Invalid disease data: {serializer.errors}")







