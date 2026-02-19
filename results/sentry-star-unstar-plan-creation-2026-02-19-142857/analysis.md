# Plan Generation Benchmark Analysis

**Experiment:** plan-gen-star-views  
**Task:** Generate implementation plans for "Star/Unstar Shared Issue Views" feature  
**Ground Truth:** [sentry PR #87463](https://github.com/getsentry/sentry/pull/87463)  
**Agents:** sonnet-4.5, sonnet-4.6, opus-4.6, gpt-5-mini  
**Runs per agent:** 3  
**Analysis model:** github-copilot/claude-opus-4.6

---

## Executive Summary

Four AI coding agents were tasked with generating implementation plans for a Sentry feature (starring/unstarring shared issue views) after a structured research phase. Plans were evaluated against the actual merged PR #87463. **opus-4.6** produced the highest-quality plans overall — most accurate to the real implementation, highly consistent across runs, and deeply aligned with Sentry conventions. **sonnet-4.6** was a close second with the best consistency-to-cost ratio. **sonnet-4.5** produced the most verbose plans but was the least consistent across runs. **gpt-5-mini** was the fastest and cheapest but produced the lowest-quality plans, failing to discover that the data model already existed.

### Rankings

| Rank | Agent | Completeness | Accuracy | Convention Adherence | Consistency | Overall |
|------|-------|-------------|----------|---------------------|-------------|---------|
| 1 | opus-4.6 | 9/10 | 8.5/10 | 9.5/10 | 9/10 | **9.0/10** |
| 2 | sonnet-4.6 | 8.5/10 | 8/10 | 9/10 | 9.5/10 | **8.5/10** |
| 3 | sonnet-4.5 | 7.5/10 | 6.5/10 | 7/10 | 5/10 | **6.5/10** |
| 4 | gpt-5-mini | 5/10 | 4/10 | 4/10 | 6/10 | **4.5/10** |

---

## What the Real PR Actually Implemented

Before analyzing agent plans, it is essential to understand what PR #87463 actually did:

- **Single POST endpoint** `OrganizationGroupSearchViewStarredEndpoint` at `/organizations/{org}/group-search-view/{view_id}/starred/`
- **StarViewSerializer** with `starred` (bool, required) and `position` (int, optional) fields
- **POST** with `starred=true` inserts; `starred=false` deletes — idempotent (HTTP 200 on change, HTTP 204 on no-op)
- **MemberPermission** with `POST: ["member:read", "member:write"]`
- Feature flagged with `organizations:issue-view-sharing`
- Manager methods (`insert_starred_view`, `delete_starred_view`, `num_starred_views`, `get_starred_view`) added to `GroupSearchViewStarredManager` in existing `groupsearchviewstarred.py`
- Used `transaction.atomic` for both insert and delete
- URL pattern uses **singular** `group-search-view` (not plural `group-search-views`)
- Files: new endpoint file in `src/sentry/issues/endpoints/`, URL registration in `urls.py`, model manager updates, new test file
- No new migrations needed (model already existed)

---

## Agent-by-Agent Analysis

### 1. opus-4.6

**Runs:** 3 | **Avg Duration:** 526s | **Avg Tokens:** 1,350,444 | **Plan Length:** 78–99 lines

#### Strengths
- **Most accurate endpoint naming:** All 3 runs correctly identified `OrganizationGroupSearchViewStarredEndpoint` — the exact class name used in the PR.
- **Correct file placement:** All runs placed the endpoint in `src/sentry/issues/endpoints/organization_group_search_view_starred.py`, matching the PR exactly.
- **Deep convention awareness:** Correctly identified `@region_silo_endpoint`, `ApiOwner.ISSUES`, `ApiPublishStatus.EXPERIMENTAL`, `MemberPermission`, and the feature flag `organizations:issue-view-sharing`.
- **Model reuse recognized:** All runs correctly identified that `GroupSearchViewStarred` already exists and no migrations are needed.
- **Manager method details:** Specified adding methods to `GroupSearchViewStarredManager` including `insert_starred_view`, `delete_starred_view`, `num_starred_views` — close to the actual implementation.
- **Run 1 constitution check:** Included a post-design re-evaluation step to verify the plan against research decisions, catching potential issues early.

#### Weaknesses
- Proposed PUT+DELETE instead of single POST with `starred` boolean. This follows the research spec's suggestion, so it is a reasonable divergence but does not match the actual PR design.
- Slightly more token-heavy than sonnet-4.6 due to deeper codebase exploration.

#### Consistency
Very high. All 3 runs converged on the same architecture, file paths, endpoint naming, and implementation approach. Minor differences were in ordering and level of detail, not substance.

---

### 2. sonnet-4.6

**Runs:** 3 | **Avg Duration:** 514s | **Avg Tokens:** 1,088,828 | **Plan Length:** 73–81 lines

#### Strengths
- **Best consistency:** The 3 runs were nearly identical in structure and content — the most consistent agent in the experiment.
- **Concise and focused:** Plans were the shortest (73–81 lines) while still covering all necessary implementation details. No filler or template artifacts.
- **Correct technical details:** All runs identified the existing model, correct file placement in `src/sentry/issues/endpoints/`, `MemberPermission`, `transaction.atomic`, and the feature flag.
- **Specific implementation details:** Referenced migration number 0836, MAX_STARRED_VIEWS=50 limit, deferred constraints for position reordering.
- **Best cost-efficiency:** Lowest token usage among Claude models while maintaining high quality.

#### Weaknesses
- Proposed PUT+DELETE (same as opus-4.6, following research spec) rather than the PR's single POST approach.
- Endpoint naming was slightly less precise than opus-4.6 — used `OrganizationGroupSearchViewStarEndpoint` (missing "d" in "Starred") in some runs.
- URL pattern used plural `group-search-views` in some runs vs the PR's singular `group-search-view`.

#### Consistency
Highest of all agents. Plans across runs were structurally and substantively nearly identical.

---

### 3. sonnet-4.5

**Runs:** 3 | **Avg Duration:** 711s | **Avg Tokens:** 1,250,548 | **Plan Length:** 134–184 lines

#### Strengths
- Most detailed/verbose plans with thorough step-by-step breakdowns.
- Correctly identified the existing `GroupSearchViewStarred` model and that no migrations were needed.
- Run 2 and Run 3 showed reasonable understanding of the endpoint structure.

#### Weaknesses
- **Worst consistency:** Each run proposed a materially different architecture:
  - **Run 1:** Proposed separate star/unstar endpoint files in wrong directories, included "NEEDS CLARIFICATION" items despite the research phase having resolved those questions. Failed to integrate research findings into the plan.
  - **Run 2:** Proposed two separate endpoints (star endpoint + unstar endpoint) rather than a single endpoint.
  - **Run 3:** Confused about file locations, mixing `src/sentry/api/endpoints/` and `src/sentry/issues/endpoints/`.
- **Template artifacts:** Some runs contained placeholder/boilerplate text in the "Project Structure" section that was never filled in properly.
- **Wrong feature flags:** Some runs proposed incorrect flags like `issue-stream-custom-views` or `issue-views-starring` instead of the correct `organizations:issue-view-sharing`.
- **Slowest execution:** Averaged 711s — 37% slower than sonnet-4.6 and 35% slower than opus-4.6 — while producing lower-quality output.
- **Verbose without proportional value:** 134–184 lines of plan text, but the additional length came from boilerplate and uncertainty markers rather than useful detail.

#### Consistency
Lowest of all agents. The three runs would lead to three meaningfully different implementations.

---

### 4. gpt-5-mini

**Runs:** 3 | **Avg Duration:** 217s | **Avg Tokens:** 345,465 | **Plan Length:** 75–110 lines

#### Strengths
- **Fastest execution:** 217s average — 2.4x faster than the next-fastest agent.
- **Lowest token usage:** 345,465 average — 3.1x cheaper than opus-4.6.
- Basic plan structure was present in all runs.

#### Weaknesses
- **Critical failure — missed existing model:** All 3 runs failed to discover that `GroupSearchViewStarred` already exists in the codebase. Proposed creating a new model (`StarredSearchView` or a new `starred.py` file) and new migrations — fundamentally incorrect.
- **Template artifacts:** Plans retained template placeholder text:
  - Option 1/2/3 structure blocks that were never resolved
  - "ACTION REQUIRED" comments left in output
  - Run 2 didn't even fill in the plan title — left as "Implementation Plan: [FEATURE]"
- **Wrong file locations:** Proposed `src/sentry/api/endpoints/` instead of `src/sentry/issues/endpoints/`.
- **Poor convention adherence:** Did not identify Sentry-specific patterns like `@region_silo_endpoint`, `ApiOwner`, `ApiPublishStatus`, or the correct base classes.
- **Insufficient codebase research:** The speed advantage came at the cost of inadequate exploration of the existing codebase, leading to the model-existence miss.

#### Consistency
Moderate. All 3 runs made the same fundamental error (missing the existing model), so they were "consistently wrong." Structural consistency between runs was moderate — similar overall approach but varying details.

---

## Comparative Rankings

### 1. Completeness (Does the plan cover all necessary implementation steps?)

| Rank | Agent | Score | Notes |
|------|-------|-------|-------|
| 1 | opus-4.6 | 9/10 | Covers endpoint, model manager, URL registration, tests, error handling |
| 2 | sonnet-4.6 | 8.5/10 | Equally complete but slightly less detail on edge cases |
| 3 | sonnet-4.5 | 7.5/10 | Verbose but inconsistent — some runs miss key details while over-specifying others |
| 4 | gpt-5-mini | 5/10 | Missing the existing model means the entire plan foundation is wrong |

### 2. Accuracy (How closely does the plan match the actual PR implementation?)

| Rank | Agent | Score | Notes |
|------|-------|-------|-------|
| 1 | opus-4.6 | 8.5/10 | Correct endpoint name, file path, model reuse. PUT+DELETE vs POST is only divergence |
| 2 | sonnet-4.6 | 8/10 | Very close; minor naming differences (Star vs Starred) |
| 3 | sonnet-4.5 | 6.5/10 | Correct model reuse but inconsistent file paths and endpoint designs across runs |
| 4 | gpt-5-mini | 4/10 | Proposed new model + migrations for something that already exists |

### 3. Convention Adherence (Does the plan follow Sentry's established patterns?)

| Rank | Agent | Score | Notes |
|------|-------|-------|-------|
| 1 | opus-4.6 | 9.5/10 | Identified all Sentry decorators, base classes, permission patterns, feature flags |
| 2 | sonnet-4.6 | 9/10 | Same patterns identified; slightly less explicit about some decorators |
| 3 | sonnet-4.5 | 7/10 | Inconsistent — some runs got patterns right, others proposed wrong flags/paths |
| 4 | gpt-5-mini | 4/10 | Minimal awareness of Sentry-specific patterns |

### 4. Consistency (How similar are the plans across the 3 runs?)

| Rank | Agent | Score | Notes |
|------|-------|-------|-------|
| 1 | sonnet-4.6 | 9.5/10 | Nearly identical plans across all 3 runs |
| 2 | opus-4.6 | 9/10 | Very consistent; minor detail-level variation |
| 3 | gpt-5-mini | 6/10 | Consistently wrong but structurally similar |
| 4 | sonnet-4.5 | 5/10 | Three materially different architectures across 3 runs |

### 5. Overall Quality

| Rank | Agent | Score | Notes |
|------|-------|-------|-------|
| 1 | opus-4.6 | 9.0/10 | Best balance of accuracy, completeness, and consistency |
| 2 | sonnet-4.6 | 8.5/10 | Excellent quality with best efficiency |
| 3 | sonnet-4.5 | 6.5/10 | Undermined by inconsistency and verbosity without value |
| 4 | gpt-5-mini | 4.5/10 | Speed advantage negated by fundamental research failures |

---

## Notable Observations

### 1. Research Integration is the Key Differentiator
The most impactful difference between agents was not raw intelligence but **how well they integrated the research phase findings** into their plans. opus-4.6 and sonnet-4.6 both correctly absorbed that the `GroupSearchViewStarred` model already exists, that no migrations are needed, and that the endpoint should go in `src/sentry/issues/endpoints/`. gpt-5-mini failed at this fundamental step, and sonnet-4.5 was inconsistent.

### 2. Conciseness Correlates with Quality
sonnet-4.6's plans (73–81 lines) and opus-4.6's plans (78–99 lines) were both shorter and better than sonnet-4.5's plans (134–184 lines). The additional verbosity in sonnet-4.5 came from uncertainty markers, template boilerplate, and redundant detail rather than useful content.

### 3. PUT+DELETE vs POST — A Reasonable Design Divergence
All high-quality agents (opus-4.6, sonnet-4.6) proposed PUT for starring and DELETE for unstarring, following the research spec's suggestion. The actual PR used a single POST with a `starred` boolean field. Both are valid REST designs. The agents' approach is arguably more RESTful, while the PR's approach is simpler. This should not be penalized heavily.

### 4. Speed vs Quality Tradeoff
gpt-5-mini was 2.4x faster and 3.1x cheaper than the Claude models, but the quality gap is too large for this to be a worthwhile tradeoff for implementation planning tasks. A plan that proposes creating an already-existing model would lead to wasted implementation effort and potential conflicts.

### 5. sonnet-4.5's Inconsistency is Concerning
For a plan-generation task where reliability matters, sonnet-4.5's three runs producing three materially different architectures is a significant issue. If a team is relying on AI-generated plans, they need confidence that the same input produces consistent output.

### 6. Template Discipline
Both sonnet-4.5 and gpt-5-mini left template artifacts in their plans (placeholder text, unresolved options, "NEEDS CLARIFICATION" markers). opus-4.6 and sonnet-4.6 produced clean, finalized plans with no artifacts — suggesting better instruction-following and self-review.

### 7. Token Efficiency
sonnet-4.6 achieved the second-best quality while using 19% fewer tokens than opus-4.6. For teams optimizing cost, sonnet-4.6 offers the best quality-per-token ratio. opus-4.6 is worth the premium when maximum accuracy matters.

---

## Efficiency Analysis

| Agent | Avg Duration (s) | Avg Total Tokens | Quality Score | Tokens per Quality Point | Duration per Quality Point |
|-------|-----------------|-----------------|---------------|------------------------|--------------------------|
| opus-4.6 | 526 | 1,350,444 | 9.0 | 150,049 | 58s |
| sonnet-4.6 | 514 | 1,088,828 | 8.5 | 128,097 | 60s |
| sonnet-4.5 | 711 | 1,250,548 | 6.5 | 192,392 | 109s |
| gpt-5-mini | 217 | 345,465 | 4.5 | 76,770 | 48s |

While gpt-5-mini has the lowest absolute cost, **sonnet-4.6 has the best cost-adjusted quality** (lowest tokens per quality point among agents scoring above 8.0). opus-4.6 is the premium choice when accuracy is paramount.
