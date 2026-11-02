# Architect brief 2: final roadmap pass (roadmap stage 4c)

Status: brief, 2026-11-02. This pass revises `docs/roadmap/target-architecture.md` in place into its final form and writes
two new files: `docs/roadmap/roadmap.md` and `docs/adr/0057-roadmap-target-architecture.md`. Frank reviews them next,
in stage 5.

## The question

Turn the target architecture into a final, reviewed plan. That means four things:
- apply the foundation rulings, including their Amendment 1;
- fix the architect-side review findings;
- test the v2 grammar against sketches of the hardest future packages before it is frozen;
- produce a short roadmap and the ADR that records it.

## Inputs, all committed

- `docs/roadmap/target-architecture.md`: your draft. It was written against
  `docs/roadmap/brief-architect-1-target-architecture.md`, which still holds for scope, constraints and what is out of
  scope.
- `docs/roadmap/foundation-rulings.md`: the specifier's rulings Q1–Q9 plus Amendment 1. Its §12 and Amendment 1 list the
  edits this note must take. The rulings are authoritative on scientific semantics. If one makes a part of your design
  unworkable, say so in the note's risks section; do not rule differently.
- `docs/roadmap/review-roadmap.md`: the independent review. Its verdict is "finalise after the listed fixes".
- `docs/roadmap/decisions.md`: Frank's answers and the orchestrator's decisions since the draft.
- `docs/roadmap/00-core-inventory.md`: today's code, for reference.

## Review findings assigned to you

Read each one in `review-roadmap.md` §2–§3. You may adopt the reviewer's fix or design differently, with the reason
recorded in the note.

- **M1 (must fix):** ProcessRevision v2 lacks energy and signal connections, controllers, and homes for reaction sets
  and utilities. The v1 schema already has those port kinds, but forces `nTP-v1` on every connection
  (`schemas/process-revision.schema.json:116-122`).
- **M2 (must fix):** the F4 and F6 exit criteria contradict Q1 and Q2:
  - the convention shift makes F4's bitwise re-composition identity impossible;
  - F6's std↔legacy equivalence over "every certificate quantity" is undefined across coordinates and conventions.

  Define the equivalence.
- **S1:** the legacy freeze must be byte-level, and self-hashes must not depend on line endings. There is no
  `.gitattributes`, so Windows CRLF checkouts change `implementation_sha256`.
- **S2:** define the boundaries between state definitions:
  - how a v2 flowsheet mixes `nTP-v1` and `ĥ` connections;
  - how ports with different definitions meet;
  - how a specification or decision targets a stream `T` that is no longer a variable.
- **S5:** EOS methods do not fit the vapour/liquid family split.
- **S6:** show that variable ids are injective; the `.` separator can collide.
- **S7:** scaling and step limits taken from `|ĥ|` are distorted by formation offsets.
- **S8:** Frank chose to do this in this pass. Write short state-structure sketches showing how each of these packages
  is carried by the v2 grammar and F2–F7, and fix the grammar wherever a sketch breaks it:
  - X18 electrolytes, X19 solids, X20 polymers, X21 assays, X22 rate-based columns;
  - TX, including controllers and co-simulation;
  - per M1, also X12 economics, X14 heat exchange and pinch, X25 batch and X26 relief.

  Each sketch takes half a page to a page. Its purpose is falsification: what does the package carry, where does it
  live, which foundation hook does it use, and what breaks.
- **S11:** ST's artifact is built before F2's grammar exists.
- **N1–N4, N9, N11, N12:** apply them or answer each in the note.
- **U1–U4:** the reviewer's simplifications. Adopt them or give the reason not to.
- **§3 judgements:** reflect them in the note:
  - (b): a byte-level freeze, a defined equivalence and a retirement rule;
  - (c): follow DASSL/IDA closely with an IDAS cross-check gate; LOA with a reduced-space master and one superstructure
    small enough to check against full enumeration;
  - the v2 freeze: the core at the end of W1, with the F4–F6 slots as `preview` until the end of 0.6.

## Settled; apply, do not reopen

These are in `docs/roadmap/decisions.md`:
- mass-specific `ĥ`;
- water is the first liquid key;
- a legacy family closes to new v2 work at `std.*` parity;
- the freeze timing above;
- FB-04 (1) is dropped as a 0.4 legacy quick fix and solved by F5 and `std.turbine`; MSG explains the limitation
  meanwhile;
- MSG stays in 0.4 ahead of X04 (Frank);
- the full scope (R-927).

## Deliverables

1. **`docs/roadmap/target-architecture.md`**, revised in place. Keep its eight sections and add a §9 with the S8
   sketches. Keep the whole note to at most about 1300 lines. Put a "Revision 2 (2026-11-02)" changelog at its top that
   lists each finding and rulings edit applied, by id.
2. **`docs/roadmap/roadmap.md`**, at most about 150 lines, for Frank and for agents starting a package. It gives:
   - the foundations and packages in order, by release line;
   - one line per package: what it delivers, what it depends on, and its design pass (architect, specifier or none);
   - the design waves;
   - the gates (F0 and the rest);
   - what would change the plan.

   Plain words; no derivations.
3. **`docs/adr/0057-roadmap-target-architecture.md`**, Status **Proposed**. It records:
   - the decision to build foundations F0–F8 before the features that need them;
   - the v2 grammar and its freeze points;
   - legacy freeze and retirement;
   - the owned integrator and LOA;
   - which existing ADRs it amends or will amend: 0001, 0005, 0011 and others, each with the foundation ADR that carries
     the amendment.

   Follow the house ADR form (see `docs/adr/0056-capability-extension-plan.md`): status, reason, affected requirements,
   migration impact, acceptance evidence. ADR 0057 makes ADR 0056's release lines subordinate to the roadmap.

Write only these three files and do not commit; the orchestrator commits. Write no production code. Do not start
subagents. Never send personal identifiers (names, e-mail addresses) to external services. Never read, stat or touch
anything under `~/.config/procsim/`. Do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/` or
`~/.cache/seider4/`. Read code narrowly (grep -n, sed -n ranges), only to check a specific claim.

## Out of scope

- Production code.
- Per-package specifications.
- Choices of correlations.
- Rewriting the rulings.
- Release-procedure mechanics.
