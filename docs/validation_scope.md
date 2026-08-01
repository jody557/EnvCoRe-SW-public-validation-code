# Validation scope and limits

The software validates the integrity and public semantics of the release artifacts. The default `public_payload` profile checks the exact 19-file public payload, pinned formal artifacts, the metadata checksum register, tabular schemas, identifiers, joins, controlled vocabularies, pollutant dictionary, disclosed unit exceptions, aggregate validation files, and privacy sentinels.

The separate `candidate_qa` profile additionally checks the five candidate-control files: root checksums, CSV/JSON candidate manifests, technical gates, and publication-metadata status. Candidate-only controls are not required in the public distribution payload.

Hash-pinned artifacts are intentionally strict. A change to the formal measurement table, public inventory, dictionaries, known-issue register, or aggregate validation tables requires a reviewed configuration update and a new software patch or minor version.

The software does not have access to source reports or private review evidence. A passing result therefore means that the distributed public candidate matches the frozen, reviewed artifacts and is internally consistent; it is not an independent re-review of every source measurement.

Publication metadata is separate from public data integrity. The public profile neither invents nor requires an unassigned DOI. The candidate profile rejects a contradictory state in which publication metadata is declared incomplete but a DOI, license, author list, citation, or publication gate is populated as final.
