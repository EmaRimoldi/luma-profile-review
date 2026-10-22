# Version 1 data contract

## Markdown criteria

Set `Status: active`, then use a five-column table inside `## Criteria`:
`ID | Type | Weight | Criterion | Required evidence`. Each ID must be unique.
Types are `must` (weight 0) and `prefer` (integer weight 1–10). The goal,
instructions and other Markdown prose are supplied to the model as context.
The report score is derived only from the table. Italian `Stato: attivo`,
`## Criteri`, `indispensabile`, and `preferenza` are also supported.

The SHA-256 of the UTF-8 Markdown text identifies the criteria version.

## Personal workspaces and agent tasks

The product UI, CLI, and MCP server share one local workspace. It contains
`brief.json`, editable `criteria.md`, and an `events/<event-id>/` directory with
profile snapshots, validated structures, criterion assessments, errors, feedback,
and the latest guide projection. By default this is inside ignored `data/`.
Event IDs are hashes of canonical event URLs; arbitrary filesystem paths are
not accepted as event IDs.

Onboarding records the five self-reported fields `work`, `interests`,
`looking_for`, `connect_with`, and `can_offer`, plus optional explicit
`must_haves`. The profile is identified by a content hash. Generated criteria
remain editable. Free-form interests are not inferred from unrelated user data.

Attendee records can also contain `collection_complete` and `source_attempts`
with inaccessible URLs and reasons. `record_profile_sources` gives each read
page a stable source ID. Sources may contain observed `links` identifying
other attendee profiles; these are necessary to ground explicit relationships.

`inference_tasks` returns a stage (`structure` or `matching`), a schema,
requests keyed by profile URL, and `request_hash`. Echo that hash when submitting
responses. It identifies the current profile/criteria/brief snapshot and, for
matching, the structured profile state. A changed input rejects stale batches.

Structured professional profiles have `summary`, `facts`, and `relationships`.
Each fact contains `kind`, `value`, and exact source evidence. Kinds are role,
organization, interest, skill, project, seeking, or offers. Explicit relationship
records contain a known `target_profile_url`, kind, and evidence. They must
reference an identity present in their cited source text or recorded links.
Source presence does not independently verify the truth of a relationship.

The guide contains per-person why-to-meet reasons, uncertainties, a grounded
conversation starter, source excerpts, conclusive criterion coverage, local
feedback, backend provenance, and a graph. Graph edges reference their source
URL, person URL, quote, and source ID; onboarding interests are labeled as
self-reported. Shared-context groups never imply a personal acquaintance.

## Collected profiles

See [examples/profiles.json](../examples/profiles.json) for a complete synthetic
dataset. The root object contains:

- `version`: 1.
- `event`: `name`, `url`, `displayed_guest_count` (integer or null),
  `collection_scope` (a description), and `roster_complete` (explicit boolean).
- `people`: a nonempty list of unique profiles.

Each person has `name`, `profile_url`, `sources`, optional `outbound_links`,
and optional `notes`. The canonical Luma profile URL is the identity key;
two people can have the same name. Known Luma URL aliases are canonicalized
and query strings/fragments are removed. Hosts must be luma.com or lu.ma.

Each source has `id` (unique within that person's sources), `url`, `title`,
`retrieved_at` (ISO timestamp with timezone), and `text` (relevant excerpts
actually read from the page). Empty source arrays are allowed. The engine
marks all criteria unknown without making a model request in that case.

`outbound_links` are discovered links, not read sources. The inference backend
does not fetch those links or browse: collection belongs to the Codex skill or
another importer. A partial sample must be described as such in collection_scope.

## Model response

The same JSON Schema is used for all backends:

```json
{
  "summary": "Relevant current professional background, with limitations.",
  "assessments": [
    {
      "criterion_id": "M1",
      "verdict": "yes",
      "reason": "The current role is explicitly stated in the source.",
      "evidence": [{"source_id": "s1", "quote": "I currently build LLM inference systems."}]
    }
  ]
}
```

There must be exactly one assessment per criterion. Verdicts are `yes`, `no`,
`unknown`, and `conflict`. Each yes/no requires evidence. A conflict requires
two distinct `(source_id, quote)` pairs. Every quote must occur in the cited
source excerpt after whitespace normalization. No extra assessment fields
are accepted. Quotes must be semantically relevant; validation checks their
presence, not truth or logical sufficiency.

For the host backend, put responses in:

```json
{
  "criteria_sha256": "hash from export-prompts",
  "profiles_sha256": "profile data hash from export-prompts",
  "responses": {
    "https://luma.com/user/person-id": {
      "summary": "...",
      "assessments": []
    }
  }
}
```

The empty assessments above are structural illustration only; real responses
must cover every criterion. [examples/responses.json](../examples/responses.json)
is an executable offline example.

## Run results

`results.json` records criteria hash, backend identity, collection scope,
selected/input counts, and per-person `pending`, `reviewed`, or `failed` state.
Reviewed records contain the original profile, validated response, cached flag,
and deterministic aggregate. Failed records contain an error and remain visible.
The file is replaced atomically after each processed person.

Required conditions govern the status. Only preference weights create points.
Unknown/conflicting preference weights become uncertain points, not confirmed
negative evidence. Coverage is the count of yes/no outcomes divided by the
number of criteria. Reports are ordered by status, confirmed preference points,
then name. It is a relevance ranking, not an estimate of a person's worth.

## Card presentation metadata

Each attendee may carry an observed `photo_url` (HTTP(S)) and a `contact_links`
object with `email` (plain published address), `linkedin`, and/or `x` (HTTP(S)
profile URLs on their respective services). `record_attendees` accepts these
optional fields; repeat a known identity to update presentation metadata.
Only save values actually observed on the person's published profile. Missing
fields produce initials / unavailable contact icons. Discovered LinkedIn and X
outbound links are also displayed without claiming that the page was read.
Photos and contact fields are excluded from model prompts and inference hashes.

Feedback statuses: `saved`, `meet` (a private plan), `met` (already met),
`not_relevant`, and `none` (return to discovery / undo). No action sends a message.
