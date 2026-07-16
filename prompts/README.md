# Prompt Registry Assets

Versioned prompt templates organized by feature. These YAML files are the source-controlled
counterpart of the database-backed Prompt Registry (`/api/v1/prompts`): use
`scripts/import_prompts.py` to load them into a project, and export registry prompts back to
YAML for review in pull requests.

Conventions:
- One file per prompt, `snake_case.yaml`
- `variables` use `{{name}}` placeholders
- Bump `version` and describe the change in `changelog` — never edit a shipped version in place
