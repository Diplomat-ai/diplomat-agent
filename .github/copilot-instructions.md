# Copilot Agent Instructions — Diplomat

## Mode opératoire
- Tu travailles en mode autonome : enchaîne les étapes sans demander confirmation à chaque outil.
- Quand tu dois installer des dépendances, lancer des tests, builder ou linter : exécute directement.
- Ne demande pas de validation intermédiaire sauf si tu détectes une ambiguïté bloquante sur le périmètre fonctionnel.

## Stack
- Backend : Python 3.11+, FastAPI, LangGraph, PostgreSQL, Poetry
- Frontend : Node.js, TypeScript
- Infrastructure : Docker, GitHub Actions
- Qualité : pytest, ruff, mypy, pre-commit

## Règles de sécurité (ne jamais auto-approuver)
- Toute commande git push --force ou git reset --hard
- Toute suppression récursive (rm -rf)
- Toute commande sudo
- Tout appel réseau externe non lié au build (curl, wget vers des URLs inconnues)

## Workflow standard
1. Analyse le contexte et les fichiers concernés
2. Propose un plan en 3 lignes max
3. Exécute sans interruption
4. Signale le résultat final avec les fichiers modifiés
