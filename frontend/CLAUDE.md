# Frontend Rules

These rules supplement the root `CLAUDE.md` with specific required and prohibited patterns for frontend development.

## Typed API and Streaming

- Route backend calls through `frontend/src/api/client.ts` instead of ad hoc fetch logic in pages or components.
- Keep `frontend/src/api/types.ts` aligned with backend request, response, and SSE payload shapes.
- Preserve the event contract expected by `frontend/src/hooks/useStream.ts`.

### Required Patterns

- Add new endpoints to the shared `api` client before consuming them in UI code.
- Extend existing frontend types instead of re-declaring API payloads inside components.
- Keep stream parsing resilient to partial chunks and explicit about `delta`, `final`, and `error` handling.

### Prohibited Patterns

- No duplicating backend payload types in page or component files.
- No SSE shape changes without updating `useStream.ts` and related tests.

## React Playground Patterns

- Keep route composition in `src/App.tsx`, page orchestration in `src/pages/`, and reusable UI in `src/components/`.
- Keep network and persistence concerns out of presentational components such as settings and message list components.
- Reuse existing hooks and state flows before introducing parallel state machines.

### Required Patterns

- Keep page-level coordination such as conversation loading, stream lifecycle, and API calls in page components or hooks.
- Use `import type` for TypeScript-only imports where the file already follows that pattern.
- Guard app-level one-time initialization (auth checks, analytics init, service workers) with a module-level flag or move it to the entry module; do not rely solely on `useEffect([], ...)` which re-runs on remount and runs twice under StrictMode.
- Preserve current UX constraints, such as disabling system prompt edits after a conversation starts and using the typed tool settings flow.

### Prohibited Patterns

- No burying API calls deep inside leaf UI components.
- No reorganizing route or component ownership without a clear simplification benefit.

## React Performance Patterns

- Derive computable values during render instead of syncing with `useEffect` or storing redundant state.
- Keep components defined at module scope; never define a component inside another component's render body.
- Use functional `setState` when the new value depends on the current state to prevent stale closures and remove state from dependency arrays.
- Use `useRef` for transient values that change frequently but do not drive rendering (scroll positions, timers, flags).

### Required Patterns

- If a value can be computed from current props or state, compute it inline during render instead of storing it in a separate `useState` + `useEffect` sync.
- Use lazy state initialization (`useState(() => expensive())`) when the initial value involves parsing, I/O, or data structure construction.
- Use functional `setState` updates (`setItems(prev => [...prev, item])`) when updating based on current state, especially inside `useCallback`.
- Narrow effect dependencies to primitives: depend on `user.id` rather than `user`, and on derived booleans rather than continuous values like pixel widths.
- Put interaction-triggered side effects in event handlers directly; do not model user actions as state + `useEffect`.
- Split combined `useMemo` or `useEffect` computations when they contain independent sub-computations with different dependency sets.
- Extract default non-primitive parameter values from `memo`'d components to module-level constants (e.g., `const NOOP = () => {}`).
- Use explicit conditional rendering (`count > 0 ? <Badge /> : null`) instead of `&&` when the left-hand side is a number or could be `0` / `NaN`.
- Use non-mutating array methods (`toSorted`, `toReversed`, `toSpliced`) instead of `sort` / `reverse` / `splice` to avoid mutating props or state.

### Prohibited Patterns

- No defining React components or hooks inside the body of another component; this causes a full remount on every parent render.
- No wrapping simple primitive-result expressions (boolean OR, numeric comparison) in `useMemo` when dependency comparison costs more than the expression itself.
- No `useEffect` that exists solely to derive or sync state from other props/state changes; derive the value inline instead.

## Bundle Size and Loading

- Import from specific module paths, not barrel or index files, to avoid pulling in unused code.
- Use `React.lazy` with dynamic `import()` for components not needed on initial render.
- Preload lazy components on hover or focus to reduce perceived latency when the user is likely to need them.

### Required Patterns

- Import directly from module paths instead of barrel files (e.g., `import Button from '@mui/material/Button'` not `import { Button } from '@mui/material'`). Vite does not have `optimizePackageImports`, so barrel imports pull in entire libraries.
- Use `React.lazy(() => import('./HeavyComponent'))` for components that exceed ~50KB or render below the fold or behind user interaction. Wrap with a `<Suspense>` boundary and appropriate fallback.
- Use conditional `import()` for feature-gated or platform-specific modules; load them in a `useEffect` guarded by the feature condition.
- Preload heavy bundles on hover or focus of the trigger element by calling `void import('./module')` in `onMouseEnter` / `onFocus` handlers.
- Apply `content-visibility: auto` with `contain-intrinsic-size` on scrollable list items (message lists, run history tables) to defer off-screen rendering.
- Defer non-critical third-party scripts (analytics, error tracking) by loading them after initial render via dynamic import in a `useEffect`.

### Prohibited Patterns

- No static top-level imports of heavy third-party libraries (>100KB) in components that render on initial page load, unless the library is needed for above-the-fold content.
- No `import *` or wildcard re-exports from local barrel files.
