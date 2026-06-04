# Security

DreamCatcher is safe to read as source code, but runtime credentials and generated
artifacts must stay outside git.

Do not commit real values for:

- `HF_TOKEN`
- `RUNPOD_API_TOKEN`
- `RUNPOD_API_KEY`
- private registry credentials
- generated bundles such as `DreamCatcher.zip`
- user uploads, outputs, logs, benchmark runs, or local runtime state

Use environment variables or the ignored `app/runtime/private_config.json` file
for local/runtime credentials. Before changing repository visibility or cutting a
release, scan both the current tree and git history for secrets.
