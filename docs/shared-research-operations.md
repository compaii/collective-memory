# Selected shared research operations

The reader, curated index, semantic overlays and Atlas use upstream mechanisms:
`mapa/serve.py`, `mapa/tier1.py`, `scripts/librarian.sh` and
`mapa/ui_builder.py`. The reader exposes no write endpoints. No Director,
watcher, schedule, Lab service or reasoning model is required.

Exact deployment paths, service unit, receiver device names and access commands
belong in the private receiving operations record, discoverable through Shared
Resources. Do not commit private corpus material or access topology here.

## Contribution and curation

`tools/shared_research.py` is a stdlib client and manual curator helper. The
upstream administrative inbox only retains notes; it does not implement bounded
selected-source contribution, source hash receipts or participant routes. This
helper supplies that seam without replacing indexing, exchange or Matrix.

The operator provisions a participant-specific writable outbox and read-only
client/configuration. Filesystem access identifies the **route**, not a signed
being. A host operator can write every route. Tests run by that operator in a
receiver are infrastructure qualification, never that being's independent work.
Do not expose curator configuration, another participant's outbox, personal homes
or HMK through these mounts. The reader serves the instance's selected audience;
it has no per-document audience authentication.

Every submitted document is deliberately selected for **instance participants**.
Do not submit material requiring a narrower audience. Preserve original author,
source revision/digest and original observation date in the body/references.
Sources must already be authorized for that audience. The scanner rejects some
credential shapes; it does not determine privacy, rights or source accuracy.
HMK-derived publication still uses its separate reviewed publication contract.

```sh
python3 shared_research.py --config client.json submit \
  --id chosen-stable-operation --title 'Research question' \
  --file selected-source.md --source 'source-qualified-reference@revision'
python3 tools/shared_research.py --config curator.json inspect participant chosen-stable-operation
python3 tools/shared_research.py --config curator.json accept participant chosen-stable-operation \
  --research chosen-topic --reason 'Source and audience inspected; retain stated uncertainty'
```

Submission writes a complete, bounded proposal with no-overwrite publication.
Retry the same ID with identical bytes; changed content needs a new ID. The
curator checks attribution, audience, evidence limits and useful retention before
accepting. Acceptance stores immutable Markdown and a separate receipt, using
the upstream writer lock. A crash after document installation can be recovered
by repeating the same acceptance. Conflicting bytes or post-acceptance drift
fail closed. Preserve earlier operations when correcting a finding; explicitly
reference what the new operation corrects. Retraction requires curator removal
from the selected corpus, map update and rebuild; preserve private source and
receipt history outside the served corpus. A retained receipt is historical
acceptance, not a claim that a retracted document remains served.

## Semantic map and publication

Author interpretations under `$MAPA_DATA/overlays/mapa/proyectos/*.md`, with
stable `id`, explicit `project` and JSON `source_paths` in frontmatter. Relate
questions, methods, evidence, alternatives and uncertainty. Index/map wrappers
are derivatives of the same sources, not independent corroboration. Maintain
`overlays/mapa/index.md` as the entry. Never edit the published snapshot in place.

With the installed finite runtime environment loaded:

```sh
MAPA_DIRECTOR=0 MAPA_INDEX_SCOPE=curated bash scripts/librarian.sh
```

Use `MAPA_UI_MODE=full` when refreshing semantic edges/communities. Embeddings
use the pinned offline model cache; cap CPU threads and batch sizes to available
resources. A successful shell exit alone is insufficient: the upstream harness
can report `Tier1 FALLO` or `UI FALLO` without failing its exit status. Inspect
its result, `/health`, scope, manifest, non-stale matching index/UI generations,
search and exact `/doc` bytes. Record the observed generation separately from
the immutable acceptance receipt's `index_generation: null`.

## Reader, rebuild and recovery

Run only the supported read service with a loopback bind, provisioned receiver
loopback proxies and read-only data/code. A service restart must preserve index,
accepted sources, receipts and the same receiver routes. Record the rendered
unit and its exact restart/health commands privately. FTS serving avoids a
persistent embedding-model allocation; a hybrid on-disk index does not mean
vector serving is enabled. Keep that mode visible in health and discovery.

Before a rebuild, stop **only this reader** so a failed intermediate index/UI
publication cannot be served as current. This is ordinary service maintenance,
not a global session Stop. Preserve the last coherent index/UI/snapshot and
canonical sources/overlays; invoke the finite harness and verify its outputs
before restarting. On failure leave the reader stopped, inspect the actual
failure, and rerun supported index/UI commands or restore the coherent local
rollback. Never erase accepted sources to repair a derived index.

Retain exact source hashes, proposals, receipts, overlays, corpus policy and
runtime/model revision for reconstruction. If exchange publication has ever
been enabled and its publication fence exists, follow `docs/exchange-v1.md`
and `publication-recover` before reopening reads; do not remove the fence by hand.
No exchange is enabled merely by deploying this filesystem workflow.
