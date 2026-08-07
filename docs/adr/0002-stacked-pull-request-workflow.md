# ADR 0002: Manage the Tauri migration with short pull request stacks

- Status: Accepted
- Date: 2026-08-05
- Last revised: 2026-08-07
- Decision owners: Yasumi Clock maintainers
- Parent epic: [#12](https://github.com/MrXnneHang/Yasumi-Clock/issues/12)
- Architecture baseline: [ADR 0001](0001-tauri-rust-migration-architecture.md)
- Related CI issue: [#16](https://github.com/MrXnneHang/Yasumi-Clock/issues/16)

## Context

ADR 0001 originally divided the Tauri migration into implementation phases
covering the scaffold, Rust timer domain, Tauri integration, React UI, persistence,
auxiliary windows, platform adapters, packaging, and final Python retirement. The
first vertical slice is now merged through PR #26. ADR 0001's 2026-08-06 revision
removed preset-driven work/rest cycles and added a dedicated main-window
visual-polish workstream. Its 2026-08-07 correction keeps cycle removal while
restoring automatic, duration-derived rest after natural focus completion.

The remaining work is grouped as `A`, `B`, `C`, `C(UI)`, `D`, and `D(release)`.
These names express product delivery checkpoints, not a requirement that every
checkpoint become one linear stack.

Several early changes do have a strict dependency chain. The pure Rust timer
requires a Rust workspace, the Tauri runtime integration requires the timer
domain, and the main React UI requires an IPC contract. Reviewing all of that in
one pull request would produce a large diff, while opening every pull request
independently against `dev` would temporarily duplicate prerequisite changes or
prevent dependent work from being reviewed until its parent merges.

Other work can proceed independently after a shared contract lands. Audio,
autostart, power events, platform-specific overlay behavior, and packaging do
not have a natural total order. Treating them as one stack would create false
dependencies and force unrelated branches through repeated cascade rebases.

The repository uses `dev` as its integration trunk and has adopted the
`github/gh-stack` GitHub CLI extension for managing dependent branches and pull
requests. The extension models a stack as a strictly linear chain: each branch
has one parent and at most one child, and each pull request targets the branch
immediately below it.

This ADR defines when the migration uses stacked pull requests, how stacks map
to delivery workstreams, and how stacks are created, reviewed, merged, and
retired.

## Decision drivers

1. Each pull request must remain small enough to review and test as one coherent
   change.
2. A reviewer must be able to see only the diff introduced by the current
   implementation layer.
3. Real implementation dependencies must be visible in branch and pull request
   bases.
4. Independent platform work must remain parallel rather than acquire an
   artificial merge order.
5. Long-lived branch chains and repeated cascade conflicts must be avoided.
6. Every merged layer must keep `dev` in a coherent, testable state.
7. Existing issue workstreams must continue to express milestones without being
   constrained to one pull request each.
8. Pull request descriptions and GitHub operations must continue to follow the
   repository template and contributor identity conventions.

## Decision

### 1. Use a hybrid model

The migration will use a combination of:

- **independent pull requests** for changes that can merge directly into `dev`;
- **short linear stacks** for two or more pull requests with real code
  dependencies;
- **separate parallel stacks** when multiple dependent workstreams share an
  already-merged foundation but do not depend on each other.

A delivery workstream is a milestone, not a stack layer. One workstream may
contain one independent pull request, one stack, multiple stacks, or a combination
of them. A stack may cross adjacent workstream boundaries when that is the clearest
expression of the implementation dependency. A workstream with one review concern
uses one independent pull request; empty layers are never created to imitate a
stack.

The default maximum is four active pull requests in one stack. Exceeding four
requires a documented reason in the stack's bottom pull request. When a coherent
vertical slice reaches that limit, it should merge before the next stack starts.

### 2. Record the completed foundation

The architecture baseline merged through
[PR #15](https://github.com/MrXnneHang/Yasumi-Clock/pull/15), and the quality-gate
replacement merged through
[PR #18](https://github.com/MrXnneHang/Yasumi-Clock/pull/18).

The first implementation stack is also complete:

```text
dev
 └── migration/tauri-scaffold          # PR #23
      └── migration/rust-timer-domain  # PR #24
           └── migration/tauri-runtime-ipc  # PR #25
                └── migration/main-react-ui # PR #26
```

Its branches are historical review units, not parents for future work. New stacks
start from the synchronized `dev` merge commit after PR #26.

### 3. Use workstream A for focus with derived rest

```text
dev
 └── timer/on-demand-sessions
```

This atomic layer replaces presets, cycle progress, short/long rest, and
non-dismissible forced-rest modes across the Rust domain, application effects,
Tauri IPC, shared JSON fixtures, TypeScript wire types, and tests on both sides.
It retains the simple Focus/Rest phases: natural focus completion always starts an
endable rest whose duration is derived from that focus, while manually ending focus
returns directly to idle. Contract changes stay together because splitting them
would leave at least one layer failing its contract checks.

The proposed `ui/rest-duration-control` layer was cancelled when manual rest and
its independently adjustable duration were removed from the product contract. A
workstream does not keep an empty stacked layer after its concern is eliminated.

### 4. Use workstream B for lightweight persistence

```text
dev
 └── persistence/versioned-settings
      └── persistence/session-history
```

The bottom layer atomically stores versioned settings and logical-day completed
focus progress. The upper layer appends CSV session history and records an active
activity as interrupted during orderly exit.

No layer scans or imports legacy YAML, and no layer restores an unfinished
activity. Legacy Python files remain untouched.

### 5. Use workstream C for auxiliary windows

```text
dev
 └── desktop/window-lifecycle
      └── desktop/rest-overlay
           └── desktop/reminder-overlays
                └── desktop/window-orchestration-tests
```

The first layer owns window registration, singleton policy, creation, visibility,
and close semantics. The rest overlay follows and remains dismissible even though
rest starts automatically after natural focus completion. Last-minute, idle-reminder, and audio-control overlays
then reuse those policies. The final layer exists only for genuinely cross-window
acceptance coverage that cannot live naturally in a preceding layer.

Tests that belong solely to one layer remain in that layer.

### 6. Use workstream C(UI) for window and visual polish

```text
dev
 └── ui/acrylic-design-foundation
      └── desktop/custom-titlebar
           └── ui/focused-session-presentation
```

The foundation introduces shared cartoon-acrylic visual tokens, layout and button
hierarchy, and a thicker accessible range-control primitive. The title-bar layer
integrates minimize, maximize/restore, close, and dragging into the main window.
The presentation layer fixes focus/rest media selection and removes duration
controls, settings entry points, and other secondary UI from running or paused
compositions.

This workstream follows functional auxiliary-window behavior so its visual changes
can cover the real window set. It precedes platform adapters so window and media
spikes validate the intended product UI rather than a temporary shell.

### 7. Keep workstream D platform adapters parallel

Shared platform port traits, application effects, mocks, and test adapters land in
one independent foundation pull request:

```text
platform/adapter-contracts -> dev
```

After that foundation merges, all retained D capabilities proceed, but unrelated
concerns remain independent or use their own short stacks:

```text
dev
 ├── platform/audio-core
 │    └── platform/audio-device-selection
 ├── platform/power-event-adapter
 │    └── platform/sleep-reconciliation-integration
 ├── platform/autostart
 ├── platform/macos-overlay-spike
 └── platform/linux-media-spike
```

Audio, autostart, power, macOS overlays, and Linux media support are not placed
sequentially in one stack merely because workstream D requires all of them.
`gh stack` is strictly linear and must not model a branching work graph.

### 8. Use workstream D(release) only after retained parity

The final replacement may use this stack:

```text
dev
 └── release/tauri-build-matrix
      └── release/cross-platform-smoke-tests
           └── release/python-retirement
```

The Python retirement branch must not be created until all of these are true:

- Windows, macOS, and Linux Tauri builds succeed;
- installation and startup smoke tests pass on the supported platforms;
- versioned settings, daily progress, and session-history behavior is verified;
- the migration epic's retained product parity is demonstrated;
- release artifacts can be produced and retained independently of the Python
  source tree.

The final layer removes legacy Python source, PyInstaller specifications, and
Python-only dependencies. It does not delete published tags or release assets;
`v1.5.1` remains the final Python release and remains available through GitHub
Releases.

If one platform remains blocked, the build and smoke-test work may proceed as
separate platform pull requests instead of forcing an unmergeable release stack.
Python retirement remains blocked until the accepted release matrix is satisfied
or a scoped limitation is explicitly approved and documented.

## Stack construction rules

### Dependency test

Two pull requests belong in the same stack only when the upper pull request
cannot be implemented, compiled, or meaningfully reviewed without the lower pull
request's unmerged commits.

A practical inverse test also applies: if two pull requests could safely merge in
either order, they should normally be independent.

### Branch naming

Stack branch names use a concern prefix and a specific kebab-case outcome:

```text
timer/on-demand-sessions
ui/rest-duration-control
persistence/versioned-settings
ui/acrylic-design-foundation
desktop/custom-titlebar
platform/audio-core
release/tauri-build-matrix
```

Names identify implementation concerns rather than workstream labels. Workstream
labels express roadmap order and do not explain a branch's code ownership.

### Branch contents

Each branch must:

- contain one coherent review concern;
- include the tests required for its own behavior;
- avoid unrelated cleanup;
- preserve a buildable and testable state for all affected targets;
- update contracts or documentation when its externally visible behavior
  changes.

A higher branch must not contain a correction that logically belongs to a lower
branch. Such a correction is committed on the lower branch and propagated with
an up-stack rebase.

### Stack initialization

Before creating a stack:

1. merge or close the preceding stack;
2. synchronize local `dev` with `origin/dev`;
3. confirm the working tree is clean;
4. enable recorded conflict resolution with `git config rerere.enabled true`;
5. configure `git config remote.pushDefault origin` when multiple remotes exist;
6. plan the dependency order from foundation to consumer.

`gh stack init` and `gh stack add` must always receive explicit branch names.
Uncommitted changes must not be carried accidentally from an unrelated branch
into a new stack.

### Submission and pull request metadata

All automated stack operations must be non-interactive:

- submit with `gh stack submit --auto`;
- inspect with `gh stack view --json`;
- provide `--remote origin` where remote selection would otherwise be ambiguous.

`gh stack submit --auto` generates pull request titles and bodies from branch and
commit metadata. After submission, each pull request will be updated with
`gh pr edit` to follow [the repository pull request template](../../.github/PULL_REQUEST_TEMPLATE.md),
link the relevant migration issue, identify its position and dependencies in the
stack, and select the applicable change types.

GitHub issue and pull request publication for this migration uses the authorized
`xnne-bot` account. Authentication and repository permission must be verified
before any outward-facing operation.

The bottom pull request description must include a stack overview in bottom-to-top
order. Every upper pull request must link its immediate dependency and explain
that reviewers should review the parent first. Draft pull requests are preferred
while an incomplete upper layer cannot pass its relevant checks; ready status is
set only when the layer is reviewable.

### Review and change propagation

Review proceeds from the bottom of a stack upward. Reviewers may inspect upper
pull requests early, but approval and merge order follow dependency order.

When a lower layer changes:

1. check out the branch where the change logically belongs;
2. commit and test the correction there;
3. run `gh stack rebase --upstack`;
4. resolve and test every affected layer;
5. run `gh stack push` or `gh stack sync` to update the remote branches.

Force updates are limited to stack-managed branches and must use the extension's
force-with-lease behavior. Shared trunk branches are never force-pushed.

### Synchronization and conflicts

Routine synchronization uses `gh stack sync`. Explicit `--prune` is used only
after merged local branches are no longer needed. A rebase conflict is resolved
on the correct layer and continued with `gh stack rebase --continue`; if the
resolution cannot be established confidently, the rebase is aborted with
`gh stack rebase --abort`.

A local and remote stack that have diverged will not be resolved through an
interactive prompt in automated work. Local tracking is inspected and, when
appropriate, removed with `gh stack unstack --local` before checking out the
known remote stack again. Removing a remote stack grouping requires explicit
confirmation because it changes shared GitHub metadata.

### Merge and retirement

Stacked pull requests are merged through `gh stack merge --yes`, scoped to the
intended stack or pull request and using the repository's approved merge method.
Ordinary `gh pr merge` is not used to merge a managed stack.

After a stack merges:

1. run `gh stack sync --prune` to retire merged local stack branches;
2. update the corresponding migration issues and acceptance checklist;
3. synchronize local `dev` with `origin/dev` and confirm a clean tree;
4. create the next independent pull request or stack from that new trunk.

These steps happen between A, B, C, C(UI), D, and D(release). A later workstream is
never pre-created as an empty branch chain.

A new concern is not appended to an already complete stack solely to preserve a
single migration history. Completed stacks remain historical review units.

## CI policy for stacks

Path-filtered TypeScript and Rust quality gates remain authoritative for each
stack layer. A branch may inherit code from its lower layers, but its pull request
must pass every check GitHub schedules for the cumulative head.

A successful lower pull request does not waive checks on an upper pull request.
Commit-message CI skip markers are exceptional GitHub behavior, not the normal
stack workflow, and must not be used to bypass a relevant TypeScript, Rust, build,
persistence, or release check.

Because upper pull requests target their immediate parent branches, branch
protection and required-check configuration must support dependent pull request
bases. If repository settings cannot require checks consistently on non-`dev`
bases, the same workflows must still run through their pull request triggers and
results must be reviewed before merge.

## Tool availability fallback

Stacked pull requests require the `gh-stack` extension and repository support for
GitHub stacks. If the extension reports that stacks are unavailable, the branch
chain may still be represented by regular GitHub pull requests whose base
branches follow the same bottom-to-top dependency order.

In that fallback:

- dependencies and stack order remain documented in each pull request;
- branches are rebased and updated with standard Git commands;
- pull requests merge bottom-to-top;
- each remaining pull request is retargeted or rebased onto `dev` after its parent
  merges;
- no tool-specific stack metadata is assumed.

Tool availability does not change the dependency test or justify combining the
work into one large pull request.

## Consequences

### Positive

- Review diffs follow the architecture's dependency direction.
- Dependent frontend and runtime work can be reviewed before every prerequisite
  has merged.
- Core migration work is divided into small, coherent, testable layers.
- Independent platform work remains parallel and avoids unnecessary cascade
  rebases.
- Each completed stack leaves `dev` at a meaningful migration checkpoint.
- Python retirement remains visibly and technically gated on cross-platform
  parity.

### Costs and risks

- Updating a lower branch requires rebasing and retesting every upper branch.
- Pull request bases, descriptions, and ready/draft state require active
  maintenance.
- Very long-lived stacks are vulnerable to conflicts as `dev` advances.
- GitHub stack availability and branch-protection behavior must be verified before
  relying on stack metadata.
- Reviewers unfamiliar with stacked pull requests must follow bottom-to-top links
  rather than treating every pull request as independently mergeable.

These costs are bounded by short stacks, a maximum of four active layers by
default, and merging complete vertical slices before beginning unrelated work.

## Alternatives considered

### One pull request per delivery workstream

Rejected as a general rule. Some workstreams contain several reviewer concerns and
would produce very large diffs, while others contain parallel platform work that
should not share one pull request.

### One stack for the complete migration

Rejected. The migration is not a total order, and a months-long stack would
create false dependencies, repeated conflict propagation, and a permanently
blocked Python-retirement branch.

### Only independent pull requests

Rejected for the core path. Scaffold, timer domain, runtime IPC, and UI have real
sequential dependencies. Independent pull requests would either duplicate
prerequisite commits or delay review of every consumer until its dependency
merged.

### One branch per issue with no stacks

Rejected as the default. Issues express outcomes and acceptance criteria, not
necessarily review-sized code units. A single issue may require several layers,
and one branch may legitimately satisfy part of two adjacent milestone issues.

### Merge lower branches while leaving upper pull request bases unchanged

Rejected. Once a lower branch merges, active upper branches must be synchronized
through the stack workflow so their ancestry and pull request bases continue to
represent the intended diff.

## Acceptance checklist

- [x] Preparatory CI and the first scaffold/domain/IPC/UI stack are merged.
- [ ] Workstream A removes preset/cycle behavior atomically before adding its rest
      duration UI layer.
- [ ] Workstream B persists only Tauri settings, daily progress, and session
      history; it does not import legacy YAML or restore unfinished activities.
- [ ] Workstream C establishes window lifecycle before its overlays, and C(UI)
      follows as a separate visual-polish stack.
- [ ] No active stack exceeds four pull requests without a documented reason.
- [ ] Every stack layer passes its relevant TypeScript, Rust, and build checks.
- [ ] Every pull request uses the repository template and links its issue and
      immediate dependency.
- [ ] Platform adapters without real code dependencies are developed in parallel
      rather than placed in one linear stack.
- [ ] The Python-retirement branch is created only after retained parity,
      persistence, packaging, and smoke-test gates pass.
- [ ] Each merged workstream is pruned before `dev` is synchronized and the next
      workstream is created.
- [ ] Managed stacks are inspected and operated non-interactively.
- [ ] Stack merges use `gh stack merge --yes` rather than ordinary pull request
      merge commands.
