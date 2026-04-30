# data/local

This directory is reserved for machine-local runtime state.

Examples of files that may appear here:

- `cogs_overrides.json`
- `entity_history_index.json`
- `product_content_cache.json`
- transient session or synthetic sample files

These files should not be tracked in canonical git because they may contain:

- machine-specific paths
- runtime caches
- local workflow state
- synthetic or temporary data

Rebuild or regenerate them locally with the relevant project scripts when needed.
