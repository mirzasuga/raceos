# Architectural Review: Monorepo vs Separate Repo

> **Reviewer:** AI Principal Architect
> **Question:** Should raceos-factory live inside the parent RaceOS repo as a monorepo?
> **Secondary:** How should Brain changes propagate to the factory?

---

## Current Situation

```
RaceOS/ (parent repo — github.com/mirzasuga/RaceOS, branch: factory/...)
├── .raceos/          ← Brain (source of truth)
├── .ai/              ← AI steering
├── openspec/         ← Behavioral specs
├── adr/              ← Architecture decisions
├── firmware/         ← Embedded code
├── hardware/         ← Hardware docs
├── mobile/           ← Mobile app (empty)
├── brain/            ← RAG system (existing)
└── raceos-factory/   ← AI Factory (SEPARATE git repo, .gitignored)
       ↑
       Has its own .git, pushed to github.com/mirzasuga/raceos
       References parent via "../" relative paths
```

**Problem:** Two separate git repos where one (factory) directly depends on the other (parent) via `../` paths. This creates:
1. Version drift (Brain changes, factory doesn't know)
2. Can't `pip install` and point to a different project
3. CI can't test factory against Brain (different repos)
4. Contributor confusion (which repo to clone?)

---

## Recommendation: MONOREPO

**Move `raceos-factory/` INTO the parent RaceOS repo as a first-class package.**

```
RaceOS/ (single repo)
├── .raceos/              ← Brain (source of truth)
├── .ai/                  ← AI steering
├── openspec/             ← Specs
├── adr/                  ← Decisions
├── firmware/             ← Embedded code
├── hardware/             ← Hardware docs
├── mobile/               ← Mobile app
├── factory/              ← AI Factory (renamed from raceos-factory/)
│   ├── src/factory/
│   ├── config/
│   ├── pyproject.toml
│   └── ...
└── brain/                ← RAG system
```

### Why Monorepo

| Concern | Separate Repos | Monorepo |
|---|---|---|
| Brain→Factory sync | Manual, can drift | **Atomic: same commit** |
| CI test factory+brain | Impossible without checkout both | **Single workflow tests all** |
| Relative paths `../` | Fragile (depends on directory layout) | **Stable (always same tree)** |
| Developer setup | Clone 2 repos, align directories | **Clone 1 repo, everything works** |
| `pip install` from external project | Factory only works inside parent | Same (factory is a tool for THIS project) |
| Atomic changes (spec + impl + factory) | 3 commits across repos | **1 commit, 1 PR, 1 review** |
| Version coherence | Factory v1.0.1 vs Brain at commit X? | **Same git SHA = coherent state** |

### Why NOT Separate Repo

The only benefit of a separate repo is: "Factory is reusable across multiple projects."

**But RaceOS Factory is NOT generic.** It:
- Hardcodes `.raceos/` as Brain path
- Reads `openspec/specs/` directly
- Firmware adapter points to `../firmware/`
- Knowledge Agent indexes from parent's `adr/`

This factory is PURPOSE-BUILT for RaceOS. Making it "reusable" would require abstracting all paths — which adds complexity for zero current benefit.

**Future:** If you want a generic AI factory framework (usable by other projects), extract the engine as a separate library THEN. Not now.

---

## Brain Change Propagation (Monorepo Solution)

### Problem: "Brain changes, how does factory know?"

In a monorepo, this is trivially solved:

```
Developer edits .raceos/03-engineering/engineering-principles.md
    ↓
Same commit can update factory tests/expectations
    ↓
CI runs factory tests against updated Brain
    ↓
If factory behavior needs adjustment → same PR
    ↓
One review, one merge, everything coherent
```

### Specific Mechanisms

| When Brain Changes | Factory Impact | Handled By |
|---|---|---|
| New principle added | Tier 1 context includes it automatically | Context cache TTL (5 min) |
| Spec updated | Tier 2 context includes it automatically | Context cache TTL (5 min) |
| ADR added | Referenced in planning/review prompts | Automatic (reads from dir) |
| Architecture rule changed | Engineering constraints in adapter | Manual adapter update (same PR) |
| New domain added | New adapter needed | Add adapter file (same PR) |

### Cache Invalidation

The factory's Tier 1+2 cache has a 5-minute TTL. After a Brain edit:
- Within 5 min: factory uses old cached context (acceptable)
- After 5 min: factory reads fresh Brain files

For immediate invalidation: `raceos config set cache.invalidate true` or restart shell.

---

## Migration Plan (if you want to monorepo)

### Option A: Keep raceos-factory as-is, fix paths (MINIMAL)

Keep the current structure but:
1. Remove `raceos-factory/.gitignore` entry from parent
2. Remove `raceos-factory/.git/` (fold into parent repo)
3. All `../` paths stay the same (already correct)

```bash
cd /Users/mirza/Documents/MIRZA/RaceOS
rm -rf raceos-factory/.git
# Remove "raceos-factory/" from .gitignore
git add raceos-factory/
git commit -m "feat: integrate AI Factory into monorepo"
```

**Effort:** 5 minutes
**Risk:** PyPI package (`raceos-factory`) still works — it's built from `raceos-factory/` subdir.

### Option B: Rename to `factory/` (CLEANER)

```bash
mv raceos-factory factory
# Update pyproject.toml paths
# Update CI workflow paths
git add -A
git commit -m "refactor: rename raceos-factory/ to factory/ (monorepo)"
```

**Effort:** 30 minutes (path updates)
**Risk:** Breaks existing `raceos-factory` references in docs

### My Recommendation: Option A

Keep `raceos-factory/` name (PyPI package is already published as `raceos-factory`). Just remove its separate `.git` and fold into the parent. Zero path changes needed.

---

## PyPI Package from Monorepo

The PyPI package still works from a monorepo. The build system (`hatchling`) builds from `raceos-factory/` directory specifically. CI workflow just needs:

```yaml
# .github/workflows/release.yaml
jobs:
  publish:
    steps:
      - uses: actions/checkout@v4
      - run: cd raceos-factory && uv build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: raceos-factory/dist/
```

---

## Verdict

| Aspect | Recommendation |
|---|---|
| Repo structure | **Monorepo** (factory inside parent) |
| Migration | **Option A** (remove .git, add to parent, zero path changes) |
| PyPI package | Still works (build from subdirectory) |
| Brain sync | Automatic (same commit, cache TTL handles runtime) |
| CI | Single workflow tests factory + brain coherence |
| Naming | Keep `raceos-factory/` directory name |

**The factory was DESIGNED to live inside the parent.** All `../` paths prove it. The separate repo was a premature optimization. Merge it back.
