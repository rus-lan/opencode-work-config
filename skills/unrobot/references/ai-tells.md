# AI-tells rewrite playbook

How to remove each tell by hand while keeping facts and adding voice. The scorer
(`scripts/score.mjs`) flags these; this file says how to fix them. Language-specific
marker lists live in `markers/<lang>.json` — this playbook is the cross-language logic.

## The one lever that matters most: rhythm

Detectors and human readers both react first to **flat sentence rhythm**. AI prose
keeps every sentence near the same length. Humans don't.

- Target sentence-length CV 0.55–0.95. Below 0.30 reads robotic; the scorer
  penalizes that as hard as marker overuse, so you cannot win by deleting words alone.
- Technique: deliberately write one very short sentence (3-6 words), then a long
  winding one, then a medium. Read it aloud — if it drones, it is still flat.

## Content tells

| Tell | Fix |
|---|---|
| Significance inflation ("a testament to", "pivotal moment", "ever-evolving landscape") | Cut it. State the plain fact. |
| Copula avoidance ("serves as", "stands as", "boasts") | Use is / are / has. |
| Rule of three ("fast, reliable, and scalable") | Drop one item, or rewrite as a real clause. Two is fine; three-in-a-row everywhere is the tell. |
| Negative parallelism ("not just X, it's Y" / "not only … but also") | Say the positive claim once, directly. |
| Vague attribution ("experts say", "studies show") | Name the source or delete the claim. |
| -ing pseudo-analysis ("highlighting…, ensuring…, reflecting…") | Make it a real verb in a real clause, or cut. |
| Marketing adjectives (robust, seamless, cutting-edge, groundbreaking, vibrant) | Replace with a concrete, checkable detail. |
| Generic upbeat conclusion ("the future looks bright") | Replace with a specific next fact, or end on the last real point. |

## Structure & typography tells

| Tell | Fix |
|---|---|
| Inflated transitions (Additionally, Moreover, Furthermore) | Delete. Let meaning connect the sentences. |
| Em/en dashes (— –) | Comma, period, or parentheses. |
| Curly quotes (" " ' ') and unicode ellipsis (…) | Straight quotes (" ') and three dots (...). |
| Title Case Headings | Sentence case. |
| Bold-header bullet lists ("**Speed:** …") | Fold into prose or plain bullets. |
| Emojis in headings/bullets | Remove. |
| Uniform bullet openers (every bullet starts the same word) | Vary the openings. |
| Repeated sentence openers (3+ in a row) | Restructure. |

## Chatbot artifacts (ERROR severity — always remove)

"I hope this helps", "Great question!", "You're absolutely right", "feel free to",
"as of my last knowledge update", "let me know if". These are conversation leftovers
pasted into content. Delete on sight.

## Hard rules — never break

1. **Facts are sacred.** Numbers, code (fenced + inline), hex, URLs, snake_case
   identifiers, method names, frontmatter keys, JSX/MDX tags — survive verbatim.
   Run `--factcheck --before --after`; any lost token means revert that edit.
2. **Do not invent.** If the rewrite needs a fact you don't have, leave the claim
   out and flag the gap. A confident wrong number is worse than the AI original.
3. **Do not over-edit into monotone.** Removing every marker but flattening the
   rhythm just trades one tell for another. Voice and varied rhythm are the point.
4. **Match the language.** Each language has its own AI-tells; use the right
   `markers/<lang>.json`. English fixes do not transfer to Russian or Arabic.
5. **Frontmatter is YAML, not prose.** The `---` fences that open and close the
   frontmatter are structural delimiters — never edit, move, or remove them. Inside
   the block you only touch the human-readable VALUES of title/description/navLabel,
   never the keys. And when reducing em dashes there, never replace a dash with a
   bare colon — an unquoted colon breaks YAML parsing and drops the whole
   frontmatter. Use a comma, or wrap the value in single quotes
   (`description: 'Foo: bar'`).

## Voice (the other half of the job)

Clean ≠ human. Add a real point of view where the genre allows it: an opinion, a
specific example, a small aside, an admission of a tradeoff. For dry technical docs,
"voice" means concrete specifics and plain direct sentences, not personality —
but still varied rhythm and zero filler.
