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
Before running the project, you need to set the environment variables in the `.env` file. This includes:

1. `BASE_URL`: The URL of the application for which you want to generate E2E tests.
2. `APP_NAME`: An identifier used to namespace that application's local database records.
3. `OUTPUT_DIR`: The root for domain-scoped crawl artifacts (defaults to `./output`).
4. `HEADLESS`: Whether Chromium runs without a visible window (defaults to `false`).
5. `LLM_MODEL`: The single LangChain `provider:model` identifier used for every chat inference.
   Because state context uses screenshots, this model must support image input.
6. `LLM_BASE_URL` and `LLM_API_KEY`: Optional connection settings for a local or hosted model.
7. `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT`, and `LLM_MAX_RETRIES`: Optional invocation
   settings.
8. `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS`: The embedding model and its exact output size.
9. `EMBEDDING_BASE_URL` and `EMBEDDING_API_KEY`: Optional local embedding endpoint settings.
10. Provider-specific keys such as `OPENAI_API_KEY` remain supported by LangChain integrations.
11. `DATABASE_PATH`: An optional SQLite database path. By default it is
   `output/<domain>/autoe2e.sqlite3`.

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
remains separate because it produces vectors rather than chat responses, and its configured
dimension defines the `sqlite-vec` index schema.

Persistence is isolated under `autoe2e/storage`: `Database` owns the SQLite connection and schema,
`FunctionalityStore` exposes functionality and action-index operations, and `RunStore` serializes
run metadata and browser artifacts. `main.py` constructs and injects these dependencies explicitly;
importing a module no longer opens a database connection.

Feature inference is isolated under `autoe2e/features`. `FeatureService` coordinates state-context
and action-feature extraction, semantic matching, indexing, scoring, and finality. Crawler-specific
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
