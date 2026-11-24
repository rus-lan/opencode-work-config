# Project Glossary (Terminology Allowance)

ASD-STE100 allows a project glossary for technical nouns and verbs that the base dictionary does not cover. The base dictionary still comes first. A project glossary adds terms. It does not license synonyms, idioms, or marketing language.

Use a glossary in three cases. A document repeats domain terms. Two teams name the same object differently. A translation pipeline will consume the text.

## What belongs

- Technical nouns and verbs the base dictionary lacks: `endpoint`, `deploy`, `rollback`, `tenant`.
- Product and component names: `Control Plane`, `Audit Log`.
- Code identifiers, commands, and paths that must stay literal: `POST /v1/jobs`, `--dry-run`.
- Domain concepts with one agreed meaning: `incident`, `severity`, `runbook`.

## What does not belong

- Ordinary words that already have an approved STE form.
- Style variants of the same concept (`delete` / `remove` / `erase`).
- Jargon that a plain word can replace (`leverage` → `use`).
- Marketing adjectives, however official they sound.

## Template

| Source term | Approved term | Part of speech | Do not use | Note |
|---|---|---|---|---|
| deploy | deploy | verb | roll out, push, ship | Release a build to an environment |
| deployment | deployment | noun | rollout, release (as a noun) | The act or result of deploying |
| endpoint | endpoint | noun | URL, route, API path | One address that accepts requests |
| tenant | tenant | noun | customer, account, org | An isolated customer space |
| runbook | runbook | noun | playbook, guide | Steps for one operational task |
| severity | severity | noun | priority, level | Incident classification S1–S4 |

Rules:

1. One term per concept for the whole document. Do not rotate synonyms to avoid repetition.
2. Record the approved part of speech. If a word is approved only as a noun, do not use it as a verb.
3. Define the term once, at first use, if a non-native reader may not know it.
4. Keep code identifiers, commands, and product names exactly as written.
5. Record rejected variants in `Do not use`. This is what stops synonym drift.
6. Do not let the glossary override an STE rule. If the two conflict, the rule wins. Note the exception.

## Machine-readable form

Keep the same columns in CSV so a linter or translation pipeline can read them:

```csv
source_term,approved_term,part_of_speech,do_not_use,note
deploy,deploy,verb,"roll out, push, ship",Release a build to an environment
endpoint,endpoint,noun,"URL, route, API path",One address that accepts requests
```

## Interaction with the rest of this skill

- **Missing Data:** if a term is unknown, do not invent one. Use `[missing: term for …]` and add it to `Missing:`. Add the decision to the glossary after the user confirms it.
- **Synonym rotation:** the linter flags common verb rotations. A glossary entry is the durable fix, because it tells the next writer which term is approved.
- **Translation:** keep the approved term as the only translation of the source term. Put it in the glossary, not in a comment.
