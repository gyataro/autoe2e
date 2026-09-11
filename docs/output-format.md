# Crawl output format

SQLite is the authoritative graph and artifact index. The filesystem contains only a tiny run
descriptor and artifacts that are better handled as files.

```text
output/
└── www.wms.com/
    ├── autoe2e.sqlite3
    ├── latest.json
    └── runs/
        └── 20260911T120000Z-a1b2c3d4/
            ├── run.json
            ├── run.log
            ├── states/
            │   ├── _root/_states/state-0214fa31/
            │   │   ├── dom.json
            │   │   ├── screenshot.png
            │   │   └── snapshot.mhtml
            │   └── products/details/_states/state-a83c9102/
            │       └── ...
            └── transitions/
                └── 000001-a17b42e019a3/
                    └── network.json
```

## Domain, run, and route boundaries

The normalized hostname from `BASE_URL` is the domain directory. Each execution creates an
independent run. `latest.json` points to the newest completed run's `run.json`; failed runs remain
queryable in SQLite but do not replace that pointer.

State folders mirror sanitized URL path segments for human navigation. The root path uses
`_root`, and a reserved `_states` directory prevents a route from conflicting with its child
routes. Query strings do not become directory names. Every state directory uses a stable hash
prefix, extended automatically if a prefix conflicts. The complete state ID and URL remain in
SQLite and are never inferred from the folder name.

## State artifacts

- `dom.json` is Chromium's flattened DOM and layout snapshot, including frames, template
  contents, shadow DOM, paint order, and element rectangles.
- `screenshot.png` is the full-page visual reference used for context inference.
- `snapshot.mhtml` is the canonical offline snapshot containing the rendered document, frames,
  styles, images, fonts, and other loaded resources.

MHTML makes separate HTML and CSS files redundant for reconstruction. DOM JSON remains because
it is substantially faster and easier to query for structural analysis than parsing MHTML.

## Transition artifacts

Each executed action receives an ordered transition directory. `network.json` records requests
that begin during that action, including method, URL, resource type, redirects, timing, transfer
sizes, status, and response headers. Its source, target, action, status, ordering, and relative
network path are indexed in SQLite.

Authorization, cookie, API-key, and token headers are replaced with `[REDACTED]`. Request and
response bodies are intentionally excluded because they commonly contain credentials or personal
data. Traffic generated while replaying a path to an existing state is not attributed to a
transition.

State artifacts can still contain information visible in the browser, including populated form
fields. Treat the domain output directory as potentially sensitive.

## SQLite index

`autoe2e.sqlite3` contains:

- `crawl_runs`: lifecycle, application, domain, base URL, and schema version.
- `crawl_states`: complete state IDs, URLs, routes, context, predecessor, and artifact directory.
- `crawl_state_actions`: ordered actions belonging to each state.
- `crawl_transitions`: the graph edges and their network-log paths.
- `crawl_artifacts`: relative paths, media types, sizes, and SHA-256 checksums.
- `functionalities` and `action_functionalities`: inferred feature data.
- `functionality_vectors`: the `sqlite-vec` nearest-neighbor index.

Foreign keys are enabled and crawl writes use WAL mode. Completed and failed runs are marked
atomically, and the WAL is checkpointed when a run closes. Consumers can reconstruct an in-memory
graph with indexed queries and load DOM, MHTML, screenshots, or network logs lazily. The built-in
`RunStore.load_graph(database, run_id)` performs that reconstruction without reading large
artifacts.

## Bootstrap descriptor

`run.json` is intentionally small:

```json
{
  "schema_version": "1.0",
  "run_id": "20260911T120000Z-a1b2c3d4",
  "status": "completed",
  "database": "../../autoe2e.sqlite3",
  "log": "run.log",
  "error": null
}
```

There is no full JSON manifest. Relative paths in SQLite and `run.json` keep the domain directory
portable. Consumers should reject unknown schema major versions and tolerate additional fields
within a known major version.

## Logging

Every run has exactly one `run.log` in its run directory. It receives debug, informational,
warning, error, and exception records in chronological order. Console output remains available
but is not a second log file. The logger creates no project-level or package-level `logs`
directory, and a browser startup failure is still recorded because the run begins first.
