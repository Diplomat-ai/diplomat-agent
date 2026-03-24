# Reality Check — agent-canary scanner

Generated: 2026-03-24
Scanner version: from `~/dev/agent-canary/src`
Repos scanned: 16 (from pre-existing JSON results in `/tmp/bench/`)
Note: `results-aihawk.json` and `results-langchain-community.json` were empty (scanner error, path not found at scan time) and are excluded from all counts.

---

## 1. Patterns réels détectés sur vrais repos

### Tableau des occurrences par effect type et par repo

| Effect type       | autogpt | browser-use | composio | crewai | dify-backend | finrobot | gpt-researcher | khoj | metagpt | open-swe | openagents | openai-agents | praisonai | skyvern | stripe-toolkit | surfsense | TOTAL |
|-------------------|---------|-------------|----------|--------|--------------|----------|----------------|------|---------|----------|------------|---------------|-----------|---------|----------------|-----------|-------|
| database_write    | 132     | 44          | 1        | 88     | 1036         | 65       | 14             | 123  | 194     | 10       | 31         | 121           | 532       | 307     | 3              | 559       | **3260** |
| database_delete   | 160     | 2           | 5        | 54     | 602          | 8        | 1              | 67   | 25      | 4        | 10         | 17            | 193       | 72      | 2              | 83        | **1305** |
| http_write        | 164     | 166         | 13       | 40     | 216          | 1        | 2              | 17   | 19      | 23       | 136        | 6             | 54        | 44      | 0              | 67        | **968** |
| destructive       | 49      | 34          | 0        | 78     | 23           | 4        | 3              | 10   | 55      | 0        | 7          | 17            | 353       | 57      | 0              | 7         | **697** |
| publish           | 33      | 10          | 33       | 141    | 177          | 3        | 1              | 6    | 2       | 1        | 4          | 1             | 121       | 65      | 0              | 11        | **609** |
| llm_call          | 32      | 34          | 2        | 90     | 26           | 2        | 6              | 4    | 8       | 0        | 0          | 2             | 92        | 152     | 0              | 14        | **464** |
| email             | 19      | 5           | 1        | 9      | 49           | 0        | 0              | 36   | 0       | 0        | 0          | 4             | 53        | 5       | 1              | 68        | **250** |
| file_delete       | 19      | 20          | 2        | 4      | 2            | 0        | 4              | 3    | 21      | 0        | 5          | 4             | 105       | 10      | 0              | 26        | **225** |
| agent_invocation  | 3       | 114         | 4        | 5      | 9            | 0        | 3              | 0    | 3       | 0        | 9          | 7             | 37        | 0       | 3              | 9         | **206** |
| payment           | 3       | 0           | 0        | 0      | 6            | 0        | 0              | 0    | 0       | 0        | 0          | 0             | 0         | 0       | 32             | 0         | **41** |

### Réponse à la question clé : "payment a-t-il matché au moins une fois ?"

**Oui, payment a matché — mais les résultats doivent être interprétés avec soin.**

- **stripe-toolkit (32 occurrences)** : Ce repo est un benchmark de l'agent Stripe officiel. Toutes les occurrences sont des `stripe.PaymentIntent.create()`, `stripe.Refund.create()`, `stripe.Payout.create()` etc. dans des scripts d'environnement de test (`setup-accounts.py`, serveurs d'exemple). Ce sont de vraies opérations Stripe, mais dans un contexte de benchmark/demo, pas de production.

- **dify-backend (6 occurrences)** : Les 6 occurrences proviennent toutes de `quota_charge.refund()` dans des tâches asynchrones. Ce n'est PAS un appel Stripe — c'est une méthode métier interne sur un objet `quota_charge`. Le pattern `name_contains: ["refund"]` a matché. C'est un **faux positif sémantique** : l'opération est capturée, mais elle n'est pas de la même nature qu'un `stripe.Refund.create()`.

- **autogpt (3 occurrences)** : `top_up_refund()`, `get_refund_requests()`, `_charge_usage()` — des méthodes internes de gestion de crédits. Matchent via `name_contains: ["refund", "charge"]`. Pas de Stripe direct.

**Conclusion** : Sur 16 repos, un seul (stripe-toolkit) contient de vraies opérations de paiement Stripe. Les 9 autres occurrences sont des méthodes métier internes capturées par les patterns génériques `name_contains: ["refund", "charge"]`.

---

## 2. Distribution des fixtures de test

### Inventaire complet

| Fichier fixture | payment | llm_call | http_write | database_write | database_delete | email | file_delete | destructive | agent_invocation | publish |
|----------------|---------|----------|------------|----------------|-----------------|-------|-------------|-------------|-----------------|---------|
| `agent_calls.py` | - | - | - | - | oui | - | - | - | oui | - |
| `checked_ok_agent/tools.py` | oui | - | - | oui | oui | - | - | - | - | - |
| `crewai_agent/agent.py` | - | - | oui | - | - | - | - | - | - | - |
| `crewai_agent/support_tools.py` | - | - | oui | - | - | oui | - | - | - | oui* |
| `dynamic_code.py` | - | - | - | - | - | - | - | oui | - | - |
| `false_positives.py` | - | - | - | oui | - | - | - | - | - | - |
| `false_positives_drop.py` | - | - | - | - | - | - | - | - | - | - |
| `false_positives_short_substring.py` | - | - | - | - | - | - | - | - | - | - |
| `fastapi_depends.py` | - | - | - | oui | oui | - | - | - | - | - |
| `langgraph_agent/tools.py` | oui | - | - | oui | oui | oui | - | - | - | - |
| `langgraph_agent/workflows.py` | - | - | oui | - | - | - | - | - | - | - |
| `llm_calls.py` | - | oui | - | - | - | - | - | - | oui | - |
| `production_like/editor.py` | - | - | - | oui | - | - | - | - | - | - |
| `production_like/tasks.py` | - | - | - | oui | - | - | - | - | - | - |
| `raw_python_agent/agent_tools.py` | oui | - | - | oui | - | - | oui | - | - | - |
| `raw_python_agent/services.py` | oui | - | - | oui | oui | oui | - | - | - | - |

*`support_tools.py` utilise `httpx.post` avec `status: "published"` dans le body — capturé comme `http_write`, pas comme `publish`.

### Analyse de la sur/sous-représentation

**Sur-représentés dans les fixtures (vs réalité) :**
- `payment` : 4 fichiers sur 16 en ont, soit 25% des fixtures. Sur les vrais repos, payment représente seulement 0,6% des occurrences totales (41/7029). La fixture `langgraph_agent/tools.py` est le seul fichier avec un vrai `stripe.Refund.create`.
- `email` / SMTP : présent dans 2 fichiers. Sur les vrais repos, email est 3,6% du total.

**Sous-représentés dans les fixtures (vs réalité) :**
- `database_write` : représente 46% des findings réels mais les fixtures le traitent comme accessoire (surtout comme contexte de `commit()`). Aucune fixture ne teste des patterns ORM complexes (`bulk_create`, `update_or_create`, MongoDB `insert_many`).
- `destructive` (subprocess, exec, eval) : 9,9% des findings réels mais seulement 1 fichier fixture (`dynamic_code.py`). Les patterns `subprocess.run`, `os.system` ne sont pas testés dans les fixtures.
- `publish` : 609 occurrences réelles (8,7%) mais zéro fixture testant le pattern `attr_exact: ["publish"]` ou S3/blob. La seule fixture "publish" est un `httpx.post` qui est capturé comme `http_write`.
- `agent_invocation` : 206 occurrences réelles mais peu de couverture dans les fixtures — principalement via `llm_calls.py` (litellm, agent.ainvoke).

**Absent des fixtures :**
- Aucune fixture pour `file_delete` via `os.remove` ou `pathlib.unlink` (seul `shutil.rmtree` dans `raw_python_agent/agent_tools.py`).
- Aucune fixture pour MongoDB (`insert_one`, `delete_many`).
- Aucune fixture pour S3/cloud storage (`put_object`, `upload_file`).
- Aucune fixture pour `Runner.run_sync` (OpenAI Agents SDK) — non capturé par le scanner.

---

## 3. Patterns vivants vs morts

### Patterns qui ont matché sur au moins un vrai repo

| Pattern | Catégorie | Repos avec matches | Total occurrences | Exemple de match réel |
|---------|-----------|-------------------|-------------------|-----------------------|
| `obj_contains: ["session","db","conn"]` + `attr_contains: ["commit"]` | database_write | 15/16 | ~2000+ | `await session.commit()` |
| `attr_contains: ["save"]` | database_write | 14/16 | estimé élevé | `entity.save()` |
| `obj_contains: ["session","db"]` + `attr_contains: ["delete"]` | database_delete | 14/16 | ~900 | `session.delete(obj)` |
| `obj_contains: ["requests","httpx","session","client","http"]` + `attr_contains: ["post","put","patch","delete"]` | http_write | 14/16 | ~968 | `requests.post(...)` |
| `obj_contains: ["objects","queryset","model","repo"]` + `attr_contains: ["create","update","save"]` | database_write | 13/16 | estimé élevé | `Model.objects.create(...)` |
| `attr_contains: ["delete","destroy","purge"]` (générique) | database_delete | 12/16 | estimé large | `self.redis_client.delete(...)` |
| `obj_contains: ["subprocess"]` + `attr_contains: ["run","call","Popen"]` | destructive | 10/16 | ~697 | `subprocess.run(cmd)` |
| `func_contains: ["chat.completions.create"]` | llm_call | 8/16 | ~464 | `client.chat.completions.create(...)` |
| `obj_contains: ["graph","chain","pipeline","agent","workflow"]` + `attr_exact: ["invoke","ainvoke"]` | agent_invocation | 8/16 | ~206 | `await graph.ainvoke(state)` |
| `obj_contains: ["s3","blob","storage"]` + `attr_contains: ["put","upload"]` | publish | 7/16 | estimé dans 609 | `s3.put_object(...)` |
| `attr_exact: ["exec","eval"]` | destructive | 5/16 | estimé dans 697 | `exec(code)` |
| `name_contains: ["refund","charge","payout"]` | payment | 3/16 | 9 (sur 41 totaux) | `quota_charge.refund()` |
| `obj_contains: ["smtp","mailer","mail"]` + `attr_contains: ["send","sendmail"]` | email | 8/16 | ~250 | `smtp.sendmail(...)` |

### Patterns jamais ou quasi-jamais vus sur vrais repos

| Pattern | Catégorie | Occurrences réelles | Remarque |
|---------|-----------|---------------------|---------|
| `obj_contains: ["paypal","braintree","adyen","square","mollie"]` | payment | 0 | Aucun des 16 repos n'utilise ces SDKs |
| `func_contains: ["stripe.Refund.create","stripe.Charge.create","stripe.PaymentIntent.create",...]` | payment | 32 (stripe-toolkit uniquement) | Seulement dans un repo de benchmark Stripe, pas dans des agents de production généralistes |
| `obj_contains: ["twilio","sms","vonage","nexmo"]` | email | 0 confirmé | Non vu dans les 16 repos |
| `obj_contains: ["telegram_bot","discord_bot","telegram","discord"]` | email | probablement 0 ou faible | Non documenté dans les findings |
| `obj_contains: ["cms","wordpress","contentful","strapi","ghost"]` | publish | 0 | Aucun des 16 repos CMS-heavy |
| `obj_contains: ["docker","k8s","kubernetes"]` + `attr_contains: ["remove","kill","stop"]` | destructive | probablement 0 | Infrastructure ops absente des repos agent |
| `name_contains: ["shutdown","terminate","kill_process","reboot","format_disk","wipe"]` | destructive | 0 | Patterns trop spécifiques |
| `obj_exact: ["importlib"]` + `attr_exact: ["import_module"]` | destructive | rare | Présent dans quelques repos seulement |
| `obj_contains: ["litellm"]` + `attr_contains: ["completion"]` | llm_call | 0 sur ces 16 repos | LiteLLM absent des repos scannés |
| `name_contains: ["send_mail","send_email","sendmail","send_message"]` | email | rare | Surpassé par les patterns obj/attr |
| `obj_contains: ["anthropic","messages"]` + `attr_exact: ["create"]` | llm_call | probable mais ambigü | Peut matcher des patterns non-Anthropic |

**Observation critique sur `publish`** : les 609 occurrences réelles de `publish` proviennent très probablement du pattern `attr_exact: ["publish"]` (ex: `channel.publish()`, `client.publish()`, MQ patterns) et des patterns S3/blob. Le pattern CMS (`wordpress`, `contentful`) n'a probablement jamais matché.

---

## 4. Ce que voit le dev lambda en 30 secondes

Commande exécutée :
```
PYTHONPATH=~/dev/agent-canary/src python3 -m agent_canary /tmp/sample_agent_dir
```

Fichier scanné : `/tmp/sample_agent_dir/sample_agent.py` (agent LangGraph typique sans guards, avec `openai`, `requests`, `sqlite3`).

Output terminal exact :

```
🐤 agent-canary — governance scan

Scanned: /private/tmp/sample_agent_dir
Tools with side effects: 1

⚠ research_and_save(query, db_path)
  llm_call:               NONE
  Rate limit:             NONE
  Retry bound:            NONE
  Write protection:       NONE
  Rate limit:             NONE
  → Risk: agent could exhaust external API quota with 200 calls
  → Risk: agent loop could write 200 records unvalidated
  ⤷ no rate limit · no auth check
  Governance: ❌ UNGUARDED

────────────────────────────────────────────────────────────────────────────────
RESULT: 1 with no checks · 0 with partial checks · 0 guarded (1 total)

  Fix              → add validation in code, the next scan picks it up
  Acknowledge      → add  # checked:ok  in your source code
  Protected elsewhere → add  # checked:ok — protected by
  CI enforcement   → --fail-on-unchecked blocks PRs with new unreviewed tool calls
```

**Effets détectés (JSON) :**
- `line 9: [llm_call]` → `response = client.chat.completions.create(`
- `line 16: [http_write]` → `requests.post("https://api.example.com/results", ...)`
- `line 21: [database_write]` → `cursor.execute("INSERT INTO results ..."`
- `line 22: [database_write]` → `conn.commit()`

**Observations :**
- 3 types d'effets distincts correctement détectés (llm_call, http_write, database_write).
- `conn.commit()` crée une 2e occurrence `database_write` en plus du `cursor.execute` — doublon fonctionnel mais pas trompeur.
- L'output affiche "Rate limit: NONE" deux fois — duplication d'affichage dans le renderer.
- L'output affiche "Fix → add validation in code, the next scan picks it up" avec une ligne tronquée sur "unreviewed tool calls" — coupure due à la largeur du terminal.

---

## 5. Repos réellement scannés

| Repo | Total tools | Top 3 effect types | Finding le plus intéressant (UNGUARDED + risque le plus élevé) |
|------|-------------|-------------------|---------------------------------------------------------------|
| autogpt | 464 (355 UNGUARDED) | http_write (164), database_delete (160), database_write (132) | `add_test_result_to_report` — `database_delete` via `SingletonReportManager().REGRESSION_MANAGER.remove_test(test_name)` |
| browser-use | 267 (230 UNGUARDED) | http_write (166), agent_invocation (114), database_write (44) | `stop_tunnel` — `database_delete` via `_delete_tunnel_info(port)` |
| composio | 28 (26 UNGUARDED) | publish (33), http_write (13), database_delete (5) | `main` — `database_delete` via `session.experimental.files.delete(remote.mount_relative_path)` |
| crewai | 348 (273 UNGUARDED) | publish (141), llm_call (90), database_write (88) | `_create_table` — `database_delete` via `table.delete("id = '__schema_placeholder__'")` (LanceDB) |
| dify-backend | 1009 (759 UNGUARDED) | database_write (1036), database_delete (602), http_write (216) | `dispatch_triggered_workflow` — `payment` (faux positif sémantique: `quota_charge.refund()`) + masse de DB writes sans guards |
| finrobot | 69 (55 UNGUARDED) | database_write (65), database_delete (8), destructive (4) | `delete_user_session` — `database_delete` via `crud.delete_session(db, session_id)` |
| gpt-researcher | 31 (27 UNGUARDED) | database_write (14), llm_call (6), file_delete (4) | `delete_report` — `database_delete` via `report_store.delete_report(research_id)` |
| khoj | 181 (125 UNGUARDED) | database_write (123), database_delete (67), email (36) | `ai_update_memories` — `database_delete` via `UserMemoryAdapters.delete_memory(user, memory)` (LLM-driven memory deletion sans confirmation) |
| metagpt | 205 (186 UNGUARDED) | database_write (194), destructive (55), database_delete (25) | `_add_batch` — `database_delete` via `engine.delete_docs(filenames + delete_filenames)` |
| open-swe | 35 (34 UNGUARDED) | http_write (23), database_write (10), database_delete (4) | `check_message_queue_before_model` — `database_delete` via `store.adelete(namespace, "pending_messages")` |
| openagents | 178 (177 UNGUARDED) | http_write (136), database_write (31), database_delete (10) | `drop_item_with_id` — `database_delete` via `redis_client.delete(...)` |
| openai-agents | 93 (78 UNGUARDED) | database_write (121), destructive (17), database_delete (17) | `pop_item` — `database_delete` via `openai_client.conversations.items.delete(...)` (API OpenAI, sans confirmation) |
| praisonai | 1028 (911 UNGUARDED) | database_write (532), destructive (353), database_delete (193) | `start_monitoring` — `destructive` via `cv2.destroyAllWindows()` (faux positif probable) + 911 UNGUARDED au total |
| skyvern | 452 (345 UNGUARDED) | database_write (307), llm_call (152), database_delete (72) | `workflow_delete` — `database_delete` via `tool_workflow_delete(workflow_id=workflow_id, force=force)` |
| stripe-toolkit | 26 (14 UNGUARDED) | payment (32), agent_invocation (3), database_write (3) | `create_app` / `pay` — `payment` via `stripe.PaymentIntent.create(...)` UNGUARDED dans des benchmarks |
| surfsense | 315 (165 UNGUARDED) | database_write (559), database_delete (83), email (68) | `_index_composio_drive_delta_sync` — `database_delete` via `session.delete(existing_document)` sans guards |

**Note :** `aihawk` et `langchain-community` sont absents — leurs JSON contenaient une erreur "path not found" indiquant que les repos n'étaient pas présents lors du scan.

---

## 6. Couverture par framework

Chaque test : mini-fichier Python scanné avec agent-canary.

| Framework | Effets détectés | Effets manqués | Verdict |
|-----------|----------------|----------------|---------|
| **LangGraph** (`graph.ainvoke(state)` + `db.commit()`) | `agent_invocation` (graph.ainvoke), `database_write` (db.commit) | Import `from langgraph.graph import StateGraph` non scanné (pas un call) | Couvert si les variables suivent les patterns obj_contains |
| **CrewAI** (`agent.execute(task)` + `session.commit()`) | `agent_invocation` (agent.execute), `database_write` (session.commit) | `crew.kickoff()` non testé — `kickoff` ne matche pas `invoke/run/execute/analyze` | Couvert partiellement |
| **OpenAI SDK direct** (`client.chat.completions.create(...)`) | `llm_call` (chat.completions.create) | Rien de significatif dans ce pattern | Bien couvert |
| **OpenAI Agents SDK** (`Runner.run_sync(agent, input)`) | **Rien** — 0 findings | `Runner` (majuscule) ne matche pas `obj_contains: ["agent","graph","chain",...]` ; `run_sync` ne matche pas `attr_exact: ["invoke","ainvoke","run","arun"]` | **Pattern aveugle** |
| **LangChain** (`chain.invoke(inputs)` + `session.add()` + `session.commit()`) | `agent_invocation` (chain.invoke), `database_write` (session.add, session.commit) | `llm.predict()`, `llm(prompt)` (call direct) non testés | Couvert pour les patterns standards |

**Point aveugle confirmé** : `Runner.run_sync` du SDK OpenAI Agents est invisible pour le scanner car l'objet `Runner` (classe capitalisée) ne correspond à aucun `obj_contains` de la liste, et `run_sync` n'est pas dans les `attr_exact` couverts.

---

## 7. Recommandations pour le README

### Exemples à utiliser (patterns qui matchent vraiment)

1. **`database_write` + `database_delete`** : Les patterns les plus fréquents dans la réalité (3260 + 1305 occurrences). Les exemples avec `session.commit()`, `session.delete()`, `cursor.execute("DELETE...")` sont solides et attestés sur 14-15 repos.

2. **`http_write` (requests.post/put/patch)** : 968 occurrences, présent sur 14/16 repos. L'exemple `requests.post(...)` est le plus universel et le plus simple à comprendre.

3. **`llm_call` via OpenAI** : 464 occurrences, bien distribué. L'exemple `client.chat.completions.create(...)` est le bon exemple de référence.

4. **`destructive` via subprocess** : 697 occurrences, représentatif. `subprocess.run(cmd)` est un pattern réel vu chez autogpt, crewai, metagpt.

5. **`khoj` comme cas d'usage narratif** : `ai_update_memories` avec `database_delete` — l'agent efface des souvenirs sans confirmation humaine. C'est le scénario le plus parlant pour illustrer le risque réel.

### Patterns à ne pas sur-vendre dans le README

1. **`payment` Stripe** : Ne représente que 41 occurrences sur 7029 totaux (0,6%). Les seuls vrais appels Stripe sont dans `stripe-toolkit`, un repo de benchmark Stripe dédié. Sur une codebase agent généraliste, les chances de voir `stripe.PaymentIntent.create()` sont faibles. À réserver à un exemple spécialisé.

2. **PayPal / Braintree / Adyen / Square** : Zéro match sur les 16 repos. Ne pas les mettre en avant comme "supportés" sans caveat.

3. **Telegram / Discord bot patterns** : Non vérifiés sur les vrais repos. Probablement rares.

4. **CMS patterns** (WordPress, Contentful) : Zéro match confirmé. À retirer des exemples principaux.

5. **`file_delete` via `os.remove`** : Bien moins fréquent que database_delete (225 vs 1305). À montrer comme example secondaire, pas principal.

### Patterns à mentionner avec précision sur les limites

- **`name_contains: ["refund","charge"]`** : Ce pattern générique capture des méthodes métier internes (ex: `quota_charge.refund()` dans dify) qui ne sont pas des opérations de paiement. À documenter comme "peut produire des faux positifs sémantiques sur des domaines métier avec terminologie financière".

- **`attr_exact: ["publish"]`** : Matche 609 fois sur les vrais repos, mais le mot `publish` apparaît dans des contextes très variés (MQTT, message queues, CMS, etc.). L'impact peut surprendre.

- **`Runner.run_sync` (OpenAI Agents SDK)** : Non détecté actuellement. Si le README cible explicitement ce SDK, ajouter `Runner` à `obj_contains` des patterns `agent_invocation`.

### Meilleur exemple pour le README (30 secondes d'impact)

Le fichier `sample_agent.py` utilisé dans la Tâche 4 (openai + requests.post + sqlite3 INSERT) est l'exemple idéal : il combine 3 types d'effets courants (llm_call, http_write, database_write), est détecté complètement, et représente un pattern réaliste vu dans les vrais repos.
