# Campus Collab — Design Doc

Status: draft
Last updated: 2026-09-02

## 1. Goals

**Product goal.** Let students at one campus find each other for side projects. A
student posts a project idea and the roles they need; other students browse,
apply, and get accepted. Once a team forms, they move to Discord or wherever —
the site's job is the match, not the collaboration.

**Learning goal.** This project exists to understand how the pieces of a backend
system fit together, not to ship a startup. Specifically:

- Python backend (FastAPI) talking to a relational database
- SQL and schema design done deliberately — indexes, joins, and query plans
  understood rather than hidden behind an ORM
- Background job processing (the GitHub sync is genuinely async)
- Caching, added at the point where a real read-path problem appears
- OAuth as a third-party integration with real constraints (rate limits, token
  storage)
- Container orchestration (Kubernetes) as a deliberate late-stage rebuild, not
  as the day-one deployment story

Components get added when a problem demands them. Nothing is in the stack
because it looks good on a resume. The one exception is Kubernetes in M7, which
is explicitly for learning — and the doc says so out loud rather than
pretending it's load-bearing.

## 2. Scope

**In scope**

1. GitHub OAuth login; profile auto-populated from GitHub repos and languages
2. Post a project: title, description, skills needed, roles open, spot count
3. Browse and filter projects by skill, tag, and status
4. Apply to a project; owner accepts or rejects

**Out of scope (deliberate)**

- In-app chat or messaging — teams move off-platform
- Email or push notifications
- Multi-campus / tenancy
- Free-text search over descriptions (filters only for v1)
- Ratings, reviews, reputation
- Project progress tracking

**Scale assumptions**

Single campus, ~30k students. Realistic active use: ~2k users, ~500 projects,
maybe 50 applications a day. This is small. A single Postgres instance handles
it without breathing hard.

This is worth stating plainly: nothing here is forced by volume. Any
infrastructure beyond one API server and one database is justified by learning,
by latency, or by an external constraint (GitHub's rate limit) — not by traffic.
Where that's the case, the doc says so.

## 3. Non-functional requirements

| Requirement             | Target                     | Why                                                 |
| ----------------------- | -------------------------- | --------------------------------------------------- |
| Browse latency          | p95 < 300ms                | Browsing _is_ the product. Slow browse = dead site. |
| Browse consistency      | Eventual OK                | A project showing up 30s late costs nothing.        |
| Application consistency | Strong                     | Double-accepting past the spot limit is a real bug. |
| Login latency           | < 1s                       | GitHub sync must not block the login response.      |
| GitHub API budget       | 5000 req/hr per user token | Hard external ceiling. Shapes the sync design.      |

## 4. Core entities

- **User** — id, github_id, github_login, avatar, display_name, bio, created_at
- **Project** — id, owner_id, title, description, status (open/closed), spots,
  created_at
- **Skill** — id, name (canonical, deduped: "Python" not "python"/"python3")
- **UserSkill** — user_id, skill_id, source (github_sync | manual)
- **ProjectSkill** — project_id, skill_id
- **Application** — id, project_id, user_id, status (pending/accepted/rejected),
  message, created_at, decided_at
- **ProjectMember** — project_id, user_id, joined_at

Notes:

- Skills are a shared table with join tables on both sides, not a text array.
  Filtering "projects needing Python" is then an indexed join instead of a
  string scan.
- `Application` and `ProjectMember` are separate. An application is a request
  with a lifecycle; membership is a fact. Accepting flips one and creates the
  other, in a single transaction.
- Unique constraint on `(project_id, user_id)` in Application — one application
  per person per project. Let the database enforce it, not the API layer.

## 5. API sketch

```
POST   /auth/github/callback      # exchange code, create session
GET    /users/me
PATCH  /users/me
GET    /users/{id}

POST   /projects
GET    /projects?skills=py,react&status=open&cursor=...
GET    /projects/{id}
PATCH  /projects/{id}             # owner only
DELETE /projects/{id}             # owner only

POST   /projects/{id}/applications
GET    /projects/{id}/applications # owner only
PATCH  /applications/{id}          # owner only: accept | reject
GET    /users/me/applications      # applicant's own view
```

Pagination is keyset (cursor), not offset. `OFFSET 5000` re-scans 5000 rows;
`WHERE (created_at, id) < (?, ?)` uses the index. At 500 projects this does not
matter — it's here because doing it right costs nothing now and rewriting later
costs a day.

## 6. High-level architecture

```
                      ┌──────────┐
   Client (React) ───▶│ FastAPI  │───▶ Postgres
                      └────┬─────┘
                           │
                    enqueue│              ┌────────┐
                           ▼              │ Redis  │◀── cache reads
                      ┌─────────┐         └────────┘
                      │ Worker  │───▶ GitHub API
                      └─────────┘
```

**Three request paths worth tracing:**

_Login._ GitHub redirects back with a code → API exchanges it for a token →
upserts the user → enqueues a sync job → returns a session immediately. The
worker then pulls repos, calls the languages endpoint per repo, maps byte counts
to skills, and writes UserSkill rows. Login does not wait on any of this. First
login shows an empty skill list that fills in seconds later.

_Browse._ Filter query hits the API, checks cache, falls through to Postgres.
The open question is the cache key: filters are arbitrary combinations, so
naively keying on the full query string gives a near-zero hit rate. Options are
caching only the unfiltered default feed (which is likely most traffic anyway),
or caching project objects individually and letting the DB return just IDs.
Decide this with real numbers, not upfront.

_Apply and accept._ The write path. Accepting must check remaining spots and
insert a membership atomically — `SELECT ... FOR UPDATE` on the project row, or
a check constraint on member count. Two browser tabs accepting the last spot
simultaneously is the case to design against.

## 7. Open questions

- Cache key strategy for filtered browse (see above) — resolve with measurement
- How stale can GitHub-derived skills be? Sync on every login, or daily, or on
  demand?
- Skill canonicalization: GitHub's language names are clean, but manually-added
  skills ("ML", "machine learning", "Machine Learning") need normalizing
- Does a rejected applicant get to re-apply?

## 8. Build order

Each milestone is deployable and does something a user can see.

- **M0** — FastAPI skeleton, Postgres, migrations, health endpoint, Docker
  Compose for local dev
- **M1** — GitHub OAuth end to end. Log in, see your own profile. Sync runs
  inline and slowly; that's fine for now.
- **M2** — Projects CRUD, skill join tables, filter query. No cache.
- **M3** — Applications and the accept/reject flow, including the concurrency
  handling.
- **M4** — Move GitHub sync to a background worker. This is the first component
  added because a measured problem demanded it.
- **M5** — Measure the browse path. Add caching only if the numbers justify it,
  and write down what the numbers were.
- **M6** — Frontend, deploy.
- **M7** — Rebuild deployment on Kubernetes. Explicitly a learning milestone,
  not a scale requirement (see §9).

M4 and M5 are the interesting ones. M0–M3 are the foundation that makes them
possible to talk about honestly.

## 9. M7: Kubernetes (learning milestone)

**Framing.** At this project's scale Docker Compose is enough. Kubernetes is not
required by traffic, cost, or reliability targets. It's here to build a bullet
that can be defended in an interview, not because the site outgrew Compose.

**What it does for this architecture that Compose doesn't.** The API and worker
scale independently. If the GitHub sync queue backs up, worker replicas can
grow without touching the API. Rolling deploys happen without downtime.
Restart-on-crash and health checks are declarative instead of scripted.

**Scope.**

- Dockerfiles for API and worker (needed regardless — this comes earlier in the
  build)
- Manifests: Deployment (API), Deployment (worker), Service, ConfigMap, Secret,
  Ingress. Roughly 200 lines of YAML.
- Postgres and Redis stay external (managed or Compose) — running stateful
  workloads on k8s is a rabbit hole and adds no learning value here
- Run locally on minikube or kind. No managed cluster, no cloud bill
- One HorizontalPodAutoscaler on the worker Deployment, so scaling the worker
  independently is demonstrated, not just theoretical
- Watch a rolling deploy actually happen

**Explicitly out of scope for M7.** Helm, service mesh, GitOps, operators,
managed cloud clusters, custom controllers, network policies, observability
stack. These are the next layer of depth and belong to a different project.

**The honest interview line.** "I deployed with Docker Compose first, then
rebuilt on Kubernetes to learn it. API and worker are separate Deployments so
they scale independently. I ran it on minikube. I haven't operated k8s in
production and know there's a lot I don't know about networking and
observability at scale."