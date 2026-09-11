# AutoE2E
Source code for "AutoE2E: Feature-Driven End-To-End Test Generation."

![AutoE2E Workflow](./workflow.png)

## Requirements
Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then create the
environment and install the locked dependencies:

```bash
uv sync
uv run playwright install chromium
```

## Usage
Before running the project, configure the target application and models in `.env`:

1. `BASE_URL`: The URL of the application for which you want to generate E2E tests.
2. `LLM_MODEL`: The Hugging Face-style model identifier or local server alias used for every chat
   inference. Because state context uses screenshots, this model must support image input.
3. `LLM_BASE_URL` and `LLM_API_KEY`: Connection settings for the chat model.
4. `EMBEDDING_MODEL`: The Hugging Face-style model identifier or local server alias used for vector
   search.
5. `EMBEDDING_BASE_URL` and `EMBEDDING_API_KEY`: Optional overrides when embeddings use a
   different endpoint; otherwise the corresponding LLM connection values are reused.

The application derives its namespace from the target domain and writes to `./output`. Browser
mode, database location, model timeouts, retries, token limits, and temperature are maintained as
internal developer settings rather than environment options.

AutoE2E communicates with both models through an OpenAI-compatible API. The provider adapter is
selected internally, so model names should not include an `openai:` prefix. `LLM_BASE_URL`
determines where the models are hosted; a separate embedding endpoint remains optional.

Then you can run the project using the following command:

```bash
uv run python main.py
```

Each crawl writes state snapshots and transition network logs below
`output/<domain>/runs/<run-id>/`. SQLite is the authoritative graph and artifact index; a small
`run.json` tells standalone tools how to open it. See [the output format](docs/output-format.md)
for the complete schema. Functionality and action mappings use the same local database, with
`sqlite-vec` providing vector similarity search; no database server is required.
Each run writes all log levels to its single `run.log` file in the same run directory.

All analysis and classification tasks share the same configured chat model. The embedding model
remains separate because it produces vectors rather than chat responses. AutoE2E probes it once at
startup and uses the returned vector size to initialize the `sqlite-vec` index schema.

Persistence is isolated under `autoe2e/storage`: `Database` owns the SQLite connection and schema,
`FunctionalityStore` exposes functionality and action-index operations, and `RunStore` serializes
run metadata and browser artifacts. `main.py` constructs and injects these dependencies explicitly;
importing a module no longer opens a database connection.

Feature inference is isolated under `autoe2e/features`. `FeatureService` coordinates state-context
and action-feature extraction, semantic matching, indexing, and scoring. Crawler-specific
LLM decisions remain under `autoe2e/crawler`: `action_policy.py` guards irreversible actions and
`form_filling.py` generates values for executable forms.

## Development

Lint and format the Python source with Ruff:

```bash
uv run ruff check .
uv run ruff format .
```

## LLM Prompts
Each system and user prompt is stored as an individual Jinja template under
`autoe2e/llm/prompts/templates`. The colocated renderer uses strict handling for undefined
variables, and the templates are included as Python package data.
