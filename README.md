# nexus-cli

## Configuration

Copy `.env.example` to `~/.config/nexus/.env` and adapt the paths. Variables set in the shell take precedence over the file.

- `NEXUS_PARAMETER_FILE` – acquisition parameter state file, default `~/nexus-console/acquisition-parameter.state`.
- `NEXUS_EXPORT_DIR` – directory for exported acquisition data, required unless `--export-dir` is given.
