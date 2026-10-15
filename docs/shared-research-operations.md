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

### Selected snapshots and version-aware map changes

The helper supports full-text snapshots of explicitly selected documents, with
per-document SHA256 revisions and a stable observed index/UI generation:

```sh
python3 shared_research.py --config client.json snapshot \
  --document mapa/proyectos/topic.md --document research/topic/participant/source.md
```

Each capture declares its selection and missing documents. It includes no Atlas
graph and never claims a complete corpus or semantic coverage. The maximum is
32 selected documents per capture, each bounded by the existing contribution
size; split larger selections explicitly. A generation change during reading
fails instead of mixing generations. Preserve the result outside public Git when
the selected corpus is private. Nexus can project these exact documents and
locators without inheriting a capped Atlas view as its complete inventory.

Canonical map edits use the same curator authority and writer lock as acceptance
and the finite librarian. `research_updates.py` must accompany the helper in the
installed client directory; possessing it grants no curator paths or authority.
Prepare a selected update as JSON:

```json
{
  "schema": "collective-research.map-update/v1",
  "operation": "selected-iteration-1",
  "document": "mapa/proyectos/topic.md",
  "expected_sha256": "the exact 64-character lowercase SHA256 of the previous map",
  "body": "the complete revised authored map, including its existing frontmatter",
  "reason": "Which selected interpretation or relationship changes, and why"
}
```

```sh
python3 tools/shared_research.py --config curator.json apply-map --file selected-update.json
python3 tools/shared_research.py --config curator.json map-update selected-iteration-1
```

This does not edit Atlas JSON or the live published snapshot. The allowlist is
`mapa/index.md` and Markdown under `mapa/proyectos/`, resolved into canonical
overlays. Existing map identity/project remain stable. `source_paths` stays a
bounded JSON list within the selected research/map namespace. A new map requires
`expected_sha256: null` and an absent target; an existing map requires its exact
current digest. If a Nexus view uses an older map, inspect/reconcile the new source
before authoring another operation; never silently substitute the latest base.

Before replacement, the helper retains immutable intended/prior bytes and the
curator's reason outside the served corpus. The update then installs atomically
under the existing writer lock, followed by an acceptance receipt. An identical
retry recovers interruption after installation without repeating the effect.
Once accepted, later retries report historical acceptance plus current source
status, never overwrite a subsequent version. A conflicting ID/base fails closed.
Unchanged bytes are explicitly reported with `changed: false` and cannot be
counted as a new research result.

This tool edits **authored interpretations**. An extracted relationship needing
correction must identify its owning source; accepted originals remain immutable.
Submit/accept a new attributed correction using the existing contribution route,
then update the authored map to relate both versions. A semantic neighbor is not
independent evidence, and a map revision does not validate its source claims.

Acceptance still leaves `index_generation: null`. Perform the maintained finite
rebuild/recovery below, then observe publication separately:

```sh
python3 tools/shared_research.py --config curator.json observe-map selected-iteration-1 \
  --observation after-rebuild-1 --reader-config client.json
```

An observation checks exact published-snapshot and reader bytes, matching stable
non-stale index/UI generations and the configured instance. Source acceptance,
source currentness and reader visibility are separate fields. An unavailable
reader, mismatched bytes or failed/stale UI never becomes success because a shell
command exited zero. Keep failed observations; use a new observation ID after
repair while retaining the same update operation ID. Reusing an observation ID
returns its original observation, not a fresh check. Published document/map bytes
do not prove that a capped Atlas graph displays every relationship; that separate
limit is explicit in the receipt. Exact Nexus projection remains source-based.

These are finite manual/owner operations. No scheduler, native model loop, peer
attention or service-stop permission is created by a snapshot or update command.

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
