---
description: dlt source for notion.com
keywords: [notion API, notion.com]
---

# dlt-source-notion

[![PyPI version](https://img.shields.io/pypi/v/dlt-source-notion)](https://pypi.org/project/dlt-source-notion/)

[DLT](https://dlthub.com/) source for [notion](https://www.notion.com/).

Currently loads the following data:

| Table | Contains |
| -- | -- |
| `persons` | Items of the `user` model of type `person` |
| `bots` | Items of the `user` model of type `bot` |
| `database_<name>_<shorthash>` | The database content (pages) of a given database. Columns are all global page columns + selected columns of properties |
| `databases` | All metadata of each loaded database. Has the title and a reference to the database table as well. |
| `databases__properties` | Column \<-> Label mapping for each unfiltered database property |
| `options_<name>_<shorthash>` | All options of a `select` or `multi_select` in one of the loaded databases. |

`<shorthash>` refers to the hashed `id` of an entity.
The hash is a 4-bit BLAKE2b hash.

## Why are you not using the `dlt-hub/verified-sources` notion source / Differences

The [official verified source](https://github.com/dlt-hub/verified-sources/tree/master/sources/notion)
has a few drawbacks:

- on usage of the verified source, a copy of the current state of
  the `dlt-hub/verified-sources` repository is copied into your project;
  Once you make changes to it, it effectively becomes a fork,
  making it hard to update after the fact.
- This makes use of a preexisting client implementation
- And Pydantic types for Notion entities,
  which makes this implementation a lot more stable

## Usage

Create a `.dlt/secrets.toml` with your API key and email:

```toml
notion_token = "ntn_abcd12345"
```

and then run the default source with optional list references:

```py
from dlt_source_notion import source as notion_source

pipeline = dlt.pipeline(
   pipeline_name="notion_pipeline",
   destination="duckdb",
   dev_mode=True,
)
notion_data = notion_source()
pipeline.run(notion_data)
```

## Development

This project is using [devenv](https://devenv.sh/).

Commands:

| Command | What does it do? |
| -- | -- |
| `format` | Formats & lints all code |
| `sample-pipeline-run` | Runs the sample pipeline. By default `dev_mode=True` which fetches resources with a limit of 1 (page) |
| `sample-pipeline-show` | Starts the streamlit-based dlt hub |

### Run the sample

```sh
NOTION_TOKEN=[...] \
  sample-pipeline-run
```

alternatively you can also create a `.dlt/secrets.toml`
(excluded from git) with the following content:

```toml
notion_token = "ntn_abcd12345"
```
