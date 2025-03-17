"""A source loading entities and lists from notion  (notion.com)"""

from enum import StrEnum
from typing import Dict, Iterable, List, Sequence
import dlt
from dlt.sources import DltResource, TDataItem

from dlt_source_notion.client import get_notion_client
from notion_client.helpers import iterate_paginated_api


class Table(StrEnum):
    PERSONS = "persons"
    BOTS = "bots"


def use_id(entity: Dict, **kwargs) -> Dict:
    return filter_dict(entity, **kwargs) | {"_dlt_id": __get_id(entity)}


def __get_id(obj):
    if isinstance(obj, dict):
        return obj.get("id")
    return getattr(obj, "id", None)


@dlt.resource(
    selected=True,
    parallelized=True,
    primary_key="id",
)
def users() -> Iterable[TDataItem]:

    notion = get_notion_client()

    yield from iterate_paginated_api(notion.users.list)


def filter_dict(d: Dict, exclude_keys: List[str]) -> Dict:
    return {k: v for k, v in d.items() if k not in exclude_keys}


@dlt.transformer(
    parallelized=True,
)
def split_user(user: Dict):

    match user["type"]:
        case "bot":
            yield dlt.mark.with_hints(
                item=use_id(user, exclude_keys=["type", "object"]),
                hints=dlt.mark.make_hints(
                    table_name=Table.BOTS.value,
                    primary_key="id",
                    write_disposition="merge",
                ),
                # needs to be a variant due to https://github.com/dlt-hub/dlt/pull/2109
                create_table_variant=True,
            )
        case "person":
            yield dlt.mark.with_hints(
                item=use_id(user, exclude_keys=["bot", "type", "object"]),
                hints=dlt.mark.make_hints(
                    table_name=Table.PERSONS.value,
                    primary_key="id",
                    write_disposition="merge",
                ),
                # needs to be a variant due to https://github.com/dlt-hub/dlt/pull/2109
                create_table_variant=True,
            )


@dlt.source(name="notion")
def source() -> Sequence[DltResource]:

    return users | split_user


__all__ = ["source"]
