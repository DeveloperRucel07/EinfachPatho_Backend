# Disease Generation Workflow

## Goal
Generate each disease once, reuse the stored disease forever, and avoid duplicate Gemini calls under concurrent load.

## Flow
1. The API view forwards the request to `DiseaseGenerationService`.
2. The service normalizes the disease name and checks cache first.
3. If cache misses, it checks the database for an existing disease using case-insensitive matching and trimmed input.
4. If a disease already exists, it is returned immediately and Gemini is not called.
5. If no disease exists, the service locks or creates a `DiseaseGenerationState` row with `select_for_update()` inside a PostgreSQL transaction.
6. The service marks the row `GENERATING`, calls the provider, validates the JSON, and saves the full disease graph in one atomic write.
7. If anything fails, the transaction rolls back for the disease graph, and the generation-state row is updated to `FAILED` with the error message.
8. On success, the generation-state row becomes `READY`, the disease is cached, and the existing disease is reused on future requests.

## Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant API as GenerateDiseaseView
    participant SVC as DiseaseGenerationService
    participant CACHE as Cache
    participant DB as PostgreSQL
    participant AI as GeminiProvider

    Client->>API: POST /api/generate_disease/
    API->>SVC: get_or_generate(name, user, prompt_text?)
    SVC->>CACHE: lookup(normalized_name)
    alt cache hit
        CACHE-->>SVC: disease_id
        SVC->>DB: load disease with related data
        SVC-->>API: disease
        API-->>Client: 200/201 disease payload
    else cache miss
        SVC->>DB: search existing disease (trim + case-insensitive)
        alt disease exists
            DB-->>SVC: disease
            SVC->>CACHE: store disease_id
            SVC-->>API: disease
            API-->>Client: 200/201 disease payload
        else disease missing
            SVC->>DB: BEGIN; lock/create DiseaseGenerationState
            SVC->>DB: mark GENERATING
            SVC->>AI: resolve/generate payload
            AI-->>SVC: JSON payload
            SVC->>SVC: validate schema and URLs
            SVC->>DB: save Disease, DurstData, RiskFactors, Symptoms, Sources, Quiz, Questions
            alt success
                SVC->>DB: mark READY + link disease
                SVC->>CACHE: store disease_id
                SVC-->>API: disease
                API-->>Client: 201 disease payload
            else failure
                SVC->>DB: mark FAILED + store error
                SVC-->>API: error
                API-->>Client: 500 error payload
            end
        end
    end
```

## Architectural Decisions
- The generation state is stored separately from `Disease` so the existing public schema stays compatible and the locking record can coordinate concurrent requests.
- The service owns the business logic and validation; the view only routes input and translates exceptions into HTTP responses.
- PostgreSQL row locking is used to prevent two concurrent requests from generating the same disease at the same time.
- The provider is abstracted behind an interface so Gemini can be replaced later with OpenAI or a local model without changing the view contract.
- Cache access is isolated behind helper methods so Redis can be added later without changing the service flow.
- Validation rejects malformed AI output before anything is written, and the entire disease graph is saved with one transaction so partial writes cannot leak into the database.

## Notes
- The current implementation uses the Django cache framework as a placeholder for Redis-ready caching.
- The migration is additive and keeps existing tables intact; no table drops or rebuilds are required.
- The schema sync migration also brings the app models back in line with the existing database history so the current serializer paths work again.
