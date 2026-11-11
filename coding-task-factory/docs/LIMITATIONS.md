# LIMITATIONS.md

Honest limits are scored under "engineering judgement". Keep this accurate: confirm each item against real behaviour, delete what is untrue, add what you discover.

## Known limitations (confirm during development)
1. **Equivalent mutants.** Some mutants do not change behaviour; they cannot be detected automatically, so kill rate underestimates test strength slightly.
2. **Shared blind spots.** The same LLM writes the reference and the tests; both may miss the same edge case. Mutation and the independent solver reduce but do not remove this.
3. **Solver nondeterminism.** A single solver attempt budget gives a signal, not a proof of difficulty or solvability.
4. **Generic behaviour taxonomy.** Axes are generic; they may not capture domain-specific variation of an unusual repo.
5. **Simple mutation operators.** Only basic operators; no language-specific or semantic mutants.
6. **Scope of regression checks.** Characterization tests cover adjacent behaviour only, not the whole system.
7. **Stack assumptions.** Validated on the supplied repo's stack (and a small fixture). Other stacks need config changes and may need code changes.
8. **Cost and rate limits.** Number of tasks is bounded by the provided usage limits.
9. **Not built:** UI, hosted service, learning from solver feedback, multi-repo orchestration.

## Failure modes seen during development (FILL)
| What failed | How often | Mitigation |
|---|---|---|
| | | |

## Future work
- Domain-aware behaviour axes mined from the repo's history
- Difficulty calibration from multi-model solve rates
- Richer mutation operators
- Support for more languages out of the box
