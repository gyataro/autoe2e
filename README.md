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
6. `REMOTE_VIEW_ENABLED`: Set to `true` to expose the headed crawl browser through noVNC.
7. `REMOTE_STARTUP_INTERVENTION`: Set to `true` to pause before crawling so a human can
   authenticate or prepare the application in that browser. This requires remote viewing.

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

### Remote browser and startup intervention

The Docker image packages Chromium, Xvfb, x11vnc, noVNC, and websockify. Start an interactive
container so the startup intervention can wait for Enter:

```bash
docker build -t autoe2e .
docker run --rm -it --env-file .env --shm-size=1g \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/output:/app/output" \
  -p 127.0.0.1:6080:6080 \
  autoe2e
```

From your computer, open an SSH tunnel to the server:

```bash
ssh -N -L 6080:127.0.0.1:6080 <user>@<server>
```

Then visit `http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale`. When startup
intervention is enabled, authenticate or prepare the application in the remote browser, return to
the AutoE2E terminal, and press Enter. Crawling continues in the same live browser context; no
cookie or authentication-state file is written. Keep port 6080 bound to loopback and do not expose
the VNC port. Running as your host UID and GID keeps bind-mounted crawl artifacts owned by your
SSH user.

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
