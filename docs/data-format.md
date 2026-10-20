# Version 1 data contract

## Markdown criteria

Set `Status: active`, then use a five-column table inside `## Criteria`:
`ID | Type | Weight | Criterion | Required evidence`. Each ID must be unique.
Types are `must` (weight 0) and `prefer` (integer weight 1–10). The goal,
instructions and other Markdown prose are supplied to the model as context.
The report score is derived only from the table. Italian `Stato: attivo`,
`## Criteri`, `indispensabile`, and `preferenza` are also supported.

The SHA-256 of the UTF-8 Markdown text identifies the criteria version.

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
