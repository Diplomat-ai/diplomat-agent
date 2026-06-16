# Diplomat Lead Intelligence Report
**Date :** {date}
**Fenêtre traffic :** 14 jours glissants
**Repos analysés :** diplomat-agent · diplomat-gate

---

## 0. Résumé exécutif

| Métrique | Valeur |
|---|---|
| Vues totales (agent) | |
| Vues uniques (agent) | |
| Clones totaux (agent) | |
| Clones uniques (agent) | |
| Downloads PyPI (30j) | |
| Stargazers total | |
| Watchers total | |
| Forks total | |
| **Leads qualifiés** (score ≥ 4) | |
| **Leads chauds** (score ≥ 6) | |

---

## 1. D'où viennent les visiteurs — Referrers

> Ces sources sont les canaux qui fonctionnent. Les absentes sont les canaux à activer.

| Source | Visites | Uniques | Interprétation |
|---|---|---|---|
| google.com | | | SEO organique |
| direct | | | Bouche-à-oreille / lien direct |
| github.com | | | Navigation interne GitHub |
| reddit.com | | | Communauté r/... à identifier |
| news.ycombinator.com | | | HN — si présent, priorité absolue |
| linkedin.com | | | Distribution pro |
| {autre} | | | |

**Signal principal :** {referrer dominant} génère {N}% du trafic.
**Canaux absents à activer en priorité :** {liste des canaux non représentés parmi HN/Reddit/LinkedIn}

---

## 2. Ce que les gens regardent — Paths populaires

> Indique ce qui retient l'attention une fois dans le repo.

| Page | Vues | Uniques | Interprétation |
|---|---|---|---|
| /README.md | | | |
| /releases | | | |
| {autre path} | | | |

**Insight :** Si releases est dans le top 3, les visiteurs évaluent activement la maturité du projet.

---

## 3. Signal d'adoption — PyPI Downloads

| Période | Downloads | Variation |
|---|---|---|
| Hier | | |
| 7 derniers jours | | |
| 30 derniers jours | | |

### Breakdown OS
| OS | % | Interprétation |
|---|---|---|
| Linux | | CI/CD, usage pro probable |
| macOS | | Dev individuel, exploration |
| Windows | | |

### Breakdown Python version
| Version | % | Signal |
|---|---|---|
| 3.12+ | | Early adopters, projets récents |
| 3.10-3.11 | | Projets en prod |
| < 3.10 | | Legacy — hors cible |

**Signal CI vs exploration :**
{interprétation du ratio Linux/macOS — si Linux > 40%, il y a de l'usage CI}

---

## 4. Leads chauds — Score ≥ 6

> Ces personnes ont montré une intention forte. Contacter dans les 7 jours.

| Login | Nom | Company | Signal | Score | Contact |
|---|---|---|---|---|---|
| | | | watcher + fork | | blog / twitter |

**Script d'outreach recommandé :**
> "Hi {name}, I noticed you're watching diplomat-agent — curious what you're building.
> We're working on [X] and would love 20 min to understand your setup."

---

## 5. Leads qualifiés — Score 4-5

> Pipeline moyen terme. Suivre les actions (nouvelles stars, issues).

| Login | Nom | Company | Signal | Score |
|---|---|---|---|---|
| | | | | |

---

## 6. Leads à surveiller — Score 2-3

> Pas encore chauds. Les retrouver sur LinkedIn ou Twitter pour du warm outreach indirect
> (commenter leurs posts, répondre à leurs questions sur l'écosystème agent).

| Login | Company | Bio snippet |
|---|---|---|
| | | |

---

## 7. Issues comme signal d'usage

> Chaque issue = quelqu'un qui a fait tourner le scanner sur un vrai projet.
> C'est le signal d'usage le plus fort qui soit.

| Login | Issue | Type | Statut | Interprétation lead |
|---|---|---|---|---|
| | | bug / feature / question | open/closed | |

---

## 8. Forks — Qui intègre le scanner

> Un fork = intention d'intégrer ou de contribuer. Signal d'usage technique fort.

| Login | Company | Repo forké | Dernière activité |
|---|---|---|---|
| | | | |

---

## 9. Actions recommandées cette semaine

> Classées par ROI estimé. Toutes exécutables en < 1 journée développeur.

| Priorité | Action | Déclencheur | Canal |
|---|---|---|---|
| 🔴 1 | Contacter {login} — watcher + fork + company renseignée | Signal fort identifié | LinkedIn DM |
| 🔴 2 | Poster sur {referrer manquant} — aucune visite depuis cette source | Canal non activé | Reddit / HN |
| 🟡 3 | Archiver les données trafic (expire dans {N} jours) | Fenêtre 14j | cron hebdo |
| 🟡 4 | Ajouter topic {topic manquant} sur le repo | Visibilité search GitHub | GitHub settings |
| 🟢 5 | Warm outreach {login} sur Twitter/LinkedIn | Score 3, bio pertinente | Commentaire public |

---

## 10. Données à collecter la semaine prochaine

- [ ] Relancer collect_and_report.py (données trafic périssables)
- [ ] Vérifier si {login chaud} a posé une issue ou forké depuis ce rapport
- [ ] Croiser les nouveaux stargazers avec la liste existante pour identifier les entrants
