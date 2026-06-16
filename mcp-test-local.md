# MCP Corpus Test Report — diplomat-agent v0.5.0

> Date : 2026-06-08  
> Tool : `diplomat-agent 0.5.0`  
> Méthode : clone `--depth=1` → `diplomat-agent scan <dir> --format json`

---

## Repos testés

| Repo | Stars (approx.) | Langage principal | Sous-dossier scanné |
|---|---|---|---|
| `rohitg00/kubectl-mcp-server` | ~600 | Python | racine |
| `alexei-led/k8s-mcp-server` | ~700 | Python | racine |
| `QuantGeekDev/docker-mcp` | ~1k | Python | racine |
| `modelcontextprotocol/servers` | ~86k | TypeScript + Python | `src/` (Python uniquement) |
| `stuzero/pg-mcp-server` | ~100 | Python | racine |
| `westonplatter/mcp-terraform-python` | ~50 | Python | racine |
| `stripe/agent-toolkit` | ~1.5k | TS + Python | `tools/python/` |

---

## Résultats par repo

### 1. `rohitg00/kubectl-mcp-server`

| Métrique | Valeur |
|---|---|
| Total findings | 416 |
| UNGUARDED | 337 |
| PARTIALLY_GUARDED | 76 |
| GUARDED | **3** |
| LOW_RISK | 0 |

**Fichiers les plus actifs :** `tools/helm.py` (37), `tools/kind.py` (36), `tools/kubevirt.py` (29), `tools/browser.py` (27)

**Ce qui fonctionne bien :**
- Les 3 fonctions correctement GUARDED utilisent `confirm_destructive()` — pattern bien détecté.
  - `label_resource`, `annotate_resource`, `taint_node` dans `operations.py`
- Les `subprocess.run(...)` nu (sans timeout, sans validation) sont flaggés comme UNGUARDED — légitime.
- La propagation inter-procedurale fonctionne : `kind_detect → _kind_available → subprocess.run` remonte dans le rapport.

**Problèmes détectés :**

1. **Bruit sur les helpers privés** : `_kind_available`, `_get_kind_version`, `_run_kind` sont des fonctions internes (préfixées `_`), pas des outils MCP exposés à l'IA. Ils apparaissent en UNGUARDED au même titre que les vrais `@mcp.tool`. Le ratio signal/bruit s'en trouve dégradé (337 UNGUARDED pour ~30 outils réels).

2. **`@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))` non reconnu** : kubectl-mcp-server annote ses outils read-only avec `ToolAnnotations(readOnlyHint=True, destructiveHint=False)`. Ce metadata MCP officiel n'est pas interprété comme un guard. Ces fonctions sont flaggées UNGUARDED à tort.

3. **`asyncio.create_subprocess_exec` manquant dans les patterns** : k8s-mcp-server utilise `asyncio.create_subprocess_exec` plutôt que `subprocess.run`. Zéro détection sur kubectl-mcp-server pour cette variante.

**Extrait représentatif (UNGUARDED légitime) :**
```python
# kubectl_mcp_tool/tools/kind.py:52
def _run_kind(self, *args):
    result = subprocess.run(...)  # aucune validation args, aucun timeout
```

**Extrait (faux positif probable) :**
```python
# @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def kind_list_clusters(ctx: Context) -> str:
    ...  # flaggé UNGUARDED alors que readOnlyHint=True
```

---

### 2. `alexei-led/k8s-mcp-server`

| Métrique | Valeur |
|---|---|
| Total findings | 2 |
| UNGUARDED | 0 |
| PARTIALLY_GUARDED | **2** |
| GUARDED | 0 |

**Ce qui fonctionne bien :**
- Les 2 findings sur `execute_command` et `get_command_help` autour de `process.kill()` sont légitimes.

**Problème majeur — faux négatif :**

Les vrais outils MCP (`@mcp.tool`) de ce repo utilisent `asyncio.create_subprocess_exec` pour exécuter `kubectl`, `helm`, `argocd`, etc. **Aucun d'eux n'est détecté.**

```python
# server.py
@mcp.tool(annotations=ToolAnnotations(title="kubectl", readOnlyHint=False))
async def execute_kubectl(command: str, ctx: Context) -> str:
    process = await asyncio.create_subprocess_exec(*cmd_args, stdout=PIPE, stderr=PIPE)
    # ← jamais détecté par diplomat-agent v0.5.0
```

**Gap critique :** `asyncio.create_subprocess_exec` / `asyncio.create_subprocess_shell` absents de `patterns.py`. Ces appels exécutent des commandes système au même titre que `subprocess.run`.

---

### 3. `QuantGeekDev/docker-mcp`

| Métrique | Valeur |
|---|---|
| Total findings | 4 |
| UNGUARDED | **4** |
| PARTIALLY_GUARDED | 0 |
| GUARDED | 0 |

**Avertissement émis sur stderr :**
```
⚠ low-level MCP dispatcher detected (@server.call_tool) in docker_mcp/server.py
  — per-tool analysis not supported in v1; FastMCP @mcp.tool is fully supported.
```

Ce repo utilise le pattern bas niveau `@server.call_tool()` (MCP SDK v0.x). Diplomat-agent détecte quand même 4 findings dans les fichiers de handlers (`handlers.py`, `docker_executor.py`).

**Findings détectés :**

| Fonction | Action détectée | Verdict | Légitimité |
|---|---|---|---|
| `handle_call_tool` | `DockerHandlers.handle_deploy_compose(arguments)` | UNGUARDED | ✅ Légitime — aucune validation d'input |
| `run_command` | `self.executor.execute(cmd)` | UNGUARDED | ✅ Légitime — cmd non validé |
| `handle_deploy_compose` | `_save_compose_file` + `_deploy_stack` | UNGUARDED | ✅ Légitime — docker compose deploy sans auth |
| `_cleanup_files` | `os.remove(compose_path)`, `os.rmdir(compose_dir)` | UNGUARDED | ⚠️ Faux positif probable — cleanup interne |

**Problème majeur — faux négatif :**

Le dispatcher `@server.call_tool` route les appels vers `create_container`, `start_container`, `stop_container`, `remove_container`, `deploy_compose`, `get_logs`... sans aucune validation. Ces tools individuels NE sont PAS analysés par diplomat-agent v0.5.0 (limitation documentée). Dans la pratique, les appels Docker destructifs passent inaperçus.

**Pattern manquant attendu :**
```python
@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> ...:
    if name == "remove-container":
        return await DockerHandlers.handle_remove_container(arguments)
    # ← chaque branche devrait être analysée
```

---

### 4. `modelcontextprotocol/servers` (Python subdirs)

| Métrique | Valeur |
|---|---|
| Total findings | 4 |
| UNGUARDED | **4** |
| PARTIALLY_GUARDED | 0 |
| GUARDED | 0 |

Sous-dossiers Python scannés : `src/git/`, `src/fetch/`, `src/time/`, `src/memory/`, `src/filesystem/`

**Avertissements :**
```
⚠ low-level MCP dispatcher (@server.call_tool) in mcp_server_time/server.py
⚠ low-level MCP dispatcher (@server.call_tool) in mcp_server_fetch/server.py
⚠ low-level MCP dispatcher (@server.call_tool) in mcp_server_git/server.py
```

**Findings détectés :**

Tous les 4 findings concernent `git_create_branch` dans `mcp_server_git/server.py` — et sa propagation à `serve`, `call_tool`, `main`. Le `repo.create_head(branch_name, base)` (gitpython) est correctement identifié comme une action de modification.

**Faux négatifs par pattern manquant :**

| Server | Action réelle | Raison du manque |
|---|---|---|
| `mcp_server_fetch` | `httpx.AsyncClient.get()` / `urllib` fetch sans rate-limit | Dans `@server.call_tool` dispatcher non analysé |
| `mcp_server_fetch` | Absence de validation `robots.txt` contournable | Pas encore un pattern diplomat-agent |
| `mcp_server_time` | `datetime.now()` — intentionnellement LOW_RISK | Correct |
| `mcp_server_git` | `repo.git.checkout()`, `repo.index.commit()` | Propagation partielle seulement |

**Bruit détecté :**
`serve()` et `main()` en UNGUARDED par propagation de `git_create_branch` — ces entrées de programme sont rarement des "tools" au sens agent.

---

### 5. `stuzero/pg-mcp-server`

| Métrique | Valeur |
|---|---|
| Total findings | 20 |
| UNGUARDED | **20** |
| PARTIALLY_GUARDED | 0 |
| GUARDED | 0 |

**Findings légitimes (example-clients) :**

| Fonction | Action | Manquant |
|---|---|---|
| `generate_sql_with_ollama` | `client.post(ollama_url)` | no rate limit, no auth check |
| `generate_sql_with_anthropic` | `client.messages.create()` | no rate limit |
| `process_user_query` | `self.agent.run(...)` | no rate limit |

Ces 5 findings (+ leurs `main()`) sont légitimes — les clients exemple font des appels LLM sans rate-limiting.

**Faux positifs critiques — `SET TRANSACTION READ ONLY` :**

Les 15 findings restants proviennent de `execute_query` et de ses appelants (`pg_query`, `pg_explain`, ressources schema/data). La fonction execute `SET TRANSACTION READ ONLY` avant toute requête SQL — c'est un guard de niveau base de données.

```python
async def execute_query(query: str, ...):
    async with db.get_connection(conn_id) as conn:
        await conn.execute("SET TRANSACTION READ ONLY")  # ← guard DB réel
        records = await conn.fetch(query, *(params or []))
```

**Bug** : diplomat-agent détecte `conn.execute("SET TRANSACTION READ ONLY")` comme une **action** (DB write pattern), alors que c'est une **instruction de sécurité transactionnelle**. Le scanner devrait reconnaître ce pattern comme un guard DB.

**Gap suggéré** : ajouter `"SET TRANSACTION READ ONLY"` (et `BEGIN READ ONLY`, `ISOLATION LEVEL SERIALIZABLE`) dans les guards DB de `patterns.py`.

---

### 6. `westonplatter/mcp-terraform-python`

| Métrique | Valeur |
|---|---|
| Total findings | 0 | 

Repo **vide** (skeleton). Seul fichier : `main.py` contenant `print("Hello from mcp-terraform-python!")`. Résultat correct.

---

### 7. `stripe/agent-toolkit` — Python (`tools/python/`)

| Métrique | Valeur |
|---|---|
| Total findings | **0** |
| UNGUARDED | 0 |

**Faux négatif majeur :**

Stripe agent-toolkit expose une abstraction `session.call_tool(name, args)` qui dispatche des appels vers le MCP server Stripe (charges, payment intents, customers, refunds...). L'appel critique est :

```python
# stripe_agent_toolkit/shared/mcp_client.py:195
async with self._create_session() as session:
    result = await session.call_tool(name, final_args)  # ← appel Stripe API réel
```

**Zéro finding** parce que :
1. `session.call_tool()` est un pattern MCP client — non dans `patterns.py` (effets côté SDK MCP)
2. `streamablehttp_client` et `ClientSession` ne sont pas identifiés comme sources d'effets
3. Les outils Stripe réels (charge, refund, delete) sont définis côté serveur distant, jamais en Python local

**Pattern à ajouter** : `session.call_tool(...)` depuis `mcp.client` devrait être traité comme un appel à effet indéterminé (UNGUARDED par défaut si pas de validation d'input autour).

---

## Synthèse des gaps par catégorie

### 🔴 Faux négatifs (non détectés, dangereux)

| Pattern | Repos affectés | Impact |
|---|---|---|
| `asyncio.create_subprocess_exec` | k8s-mcp-server, kubectl-mcp-server | Exécution de commandes système non détectée |
| `@server.call_tool()` dispatcher body | docker-mcp, mcp/servers (fetch, git, time) | Per-tool analysis absente pour low-level SDK |
| `session.call_tool()` (MCP client SDK) | stripe/agent-toolkit | Appels API avec effets réels ignorés |
| `httpx` calls dans `@server.call_tool` body | mcp/servers fetch | HTTP outbound non détecté |

### 🟡 Faux positifs (détectés à tort ou bruyants)

| Pattern | Repos affectés | Impact |
|---|---|---|
| `SET TRANSACTION READ ONLY` comme action | pg-mcp-server | 15 findings invalides |
| Helpers privés `_underscore` | kubectl-mcp-server | ~200 findings sur helpers internes |
| `@mcp.tool(readOnlyHint=True)` non reconnu | kubectl-mcp-server, k8s-mcp-server | Outils read-only flaggés UNGUARDED |
| Propagation vers `main()` / `serve()` | mcp/servers git, pg-mcp-server | Fonctions d'entrée polluent le rapport |
| `_cleanup_files` (os.remove interne) | docker-mcp | Cleanup interne flaggé UNGUARDED |

### 🟢 Ce qui fonctionne bien

| Fonctionnalité | Validation |
|---|---|
| Détection `subprocess.run` nu | ✅ kubectl-mcp-server (409 subprocess findings) |
| `confirm_destructive()` reconnu comme guard | ✅ 3 fonctions GUARDED dans operations.py |
| Propagation inter-procedurale `A → B → subprocess` | ✅ kubectl-mcp-server kind tools |
| Détection `os.remove` / `os.rmdir` | ✅ docker-mcp handlers.py |
| Détection `repo.create_head()` (gitpython) | ✅ mcp/servers git |
| Avertissement `@server.call_tool` dispatcher | ✅ Émis sur stderr (docker-mcp, mcp/servers) |
| Repo vide → 0 findings | ✅ mcp-terraform-python |

---

## Améliorations prioritaires suggérées

### P0 — Faux négatifs critiques

**1. Ajouter `asyncio.create_subprocess_exec` / `asyncio.create_subprocess_shell` dans `patterns.py`**

```python
# patterns.py — subprocess_effects
SUBPROCESS_EFFECTS = [
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "asyncio.create_subprocess_exec",   # ← MANQUANT
    "asyncio.create_subprocess_shell",  # ← MANQUANT
    "os.system",
    "os.popen",
]
```

**2. Analyser le corps du dispatcher `@server.call_tool`**

Actuellement : warning émis, analyse arrêtée.  
Cible : parser les branches `if name == "..."` du dispatcher et appliquer l'analyse à chaque handler référencé.

**3. Reconnaître `session.call_tool()` (MCP client) comme side-effect**

```python
# Ajouter dans patterns.py
MCP_CLIENT_EFFECTS = [
    "session.call_tool",
    "ClientSession.call_tool",
]
```

### P1 — Réduction des faux positifs

**4. `SET TRANSACTION READ ONLY` comme guard DB**

```python
# patterns.py — db_guards
DB_GUARDS = [
    "SET TRANSACTION READ ONLY",
    "BEGIN READ ONLY",
    "READ ONLY",
    "ISOLATION LEVEL SERIALIZABLE",
]
```

**5. Reconnaître `ToolAnnotations(readOnlyHint=True)` comme guard**

Les annotations MCP officielles `readOnlyHint=True` / `destructiveHint=False` sont de la sémantique de sécurité. Les tools avec `readOnlyHint=True` devraient être LOW_RISK si aucune action d'écriture n'est détectée dans leur corps.

**6. Filtrer les helpers privés des findings primaires**

Les fonctions préfixées `_` ne devraient pas apparaître comme findings de premier niveau. Elles peuvent rester dans les call chains mais ne devraient pas générer de ligne indépendante dans le rapport, sauf si directement décorées `@mcp.tool`.

**7. Réduire la propagation vers `main()` / `serve()`**

Les fonctions nommées `main`, `serve`, `run` qui appellent d'autres tools flaggés ne devraient pas générer de finding séparé — leur verdict est redondant avec les findings des fonctions appelées.

### P2 — Patterns MCP spécifiques à ajouter

| Pattern | Description |
|---|---|
| `@mcp.tool()` + `subprocess.*` sans input validation | Subprocess dans un @mcp.tool directement exposable à un LLM |
| `@mcp.tool()` + DB write (INSERT/UPDATE/DELETE) sans transaction guard | Mutation DB sans isolation |
| `@mcp.tool()` + HTTP call sortant sans rate-limit ni auth | SSRF / cost-flooding potentiel |
| `@server.call_tool` branches avec actions destructives | Low-level SDK dispatcher |

---

## Table de couverture par pattern demandé

| Pattern cible | Détecté ? | Repo exemple | Notes |
|---|---|---|---|
| `@mcp.tool()` + action destructive | ✅ Partiel | kubectl-mcp-server | Oui si FastMCP, non si low-level SDK |
| `@server.call_tool()` sans validation input | ⚠️ Warning seulement | docker-mcp | Body non analysé |
| `subprocess.run` dans un tool MCP | ✅ | kubectl-mcp-server | Fonctionne bien |
| `asyncio.create_subprocess_exec` | ❌ | k8s-mcp-server | Absent de patterns.py |
| `os.system` dans un tool MCP | ✅ | (général) | Dans patterns.py |
| DB access sans guard transactionnel | ⚠️ Faux positif | pg-mcp-server | `READ ONLY` non reconnu |
| HTTP sortant sans rate-limit/auth | ✅ Partiel | pg-mcp-server exemple-clients | Manque dans dispatcher body |
| MCP client `session.call_tool()` | ❌ | stripe/agent-toolkit | Absent de patterns.py |

---

*Généré par : diplomat-agent MCP corpus test — juin 2026*
