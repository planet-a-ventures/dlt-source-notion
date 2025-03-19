"""A source loading entities and lists from notion  (notion.com)"""

from enum import StrEnum
import json
from typing import Any, Iterable, Sequence
import dlt

from dlt.common import json
from dlt.common.json import JsonSerializable
from dlt.sources import DltResource, TDataItem


from notion_client.helpers import iterate_paginated_api
from pydantic import AnyUrl, BaseModel

from .client import get_notion_client
from .model.notion_2022_06_28 import Database, Page, User
from .type_adapters import user_adapter, object_adapter


def anyurl_encoder(obj: Any) -> JsonSerializable:
    if isinstance(obj, AnyUrl):
        return obj.unicode_string()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


json.set_custom_encoder(anyurl_encoder)


def pydantic_model_dump(model: BaseModel, **kwargs):
    """
    Dumps a Pydantic model to a dictionary, using the model's field names as keys and NOT observing the field aliases,
    which is important for DLT to correctly map the data to the destination.
    """
    return model.model_dump(by_alias=True, **kwargs)


class Table(StrEnum):
    PERSONS = "persons"
    BOTS = "bots"


def use_id(entity: User | Page | Database, **kwargs) -> dict:
    return pydantic_model_dump(entity, **kwargs) | {"_dlt_id": __get_id(entity)}


def __get_id(obj):
    if isinstance(obj, dict):
        return obj.get("id")
    return getattr(obj, "id", None)


@dlt.resource(
    selected=True,
    parallelized=True,
    primary_key="id",
)
def list_users() -> Iterable[TDataItem]:

    notion = get_notion_client()

    for user in iterate_paginated_api(notion.users.list):
        yield user_adapter.validate_python(user)


@dlt.transformer(
    parallelized=True,
    name="users",
)
def split_user(user: User):

    match user.type:
        case "bot":
            yield dlt.mark.with_hints(
                item=use_id(user, exclude=["type", "object"]),
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
                item=use_id(user, exclude=["bot", "type", "object"]),
                hints=dlt.mark.make_hints(
                    table_name=Table.PERSONS.value,
                    primary_key="id",
                    write_disposition="merge",
                ),
                # needs to be a variant due to https://github.com/dlt-hub/dlt/pull/2109
                create_table_variant=True,
            )


@dlt.resource(
    selected=True,
    parallelized=True,
    primary_key="id",
    max_table_nesting=1,
)
def database_resource(
    database_id: str,
) -> Iterable[TDataItem]:

    notion = get_notion_client()

    db_raw = notion.databases.retrieve(database_id)
    db: Database = object_adapter.validate_python(db_raw)
    assert isinstance(db, Database)

    selected_properties = [p.name for p in db.properties.values() if p.name is not None]

    for page_raw in iterate_paginated_api(
        notion.databases.query, database_id=database_id
    ):
        page: Page = object_adapter.validate_python(page_raw)
        assert isinstance(page, Page)

        row = {}
        for selected_property in selected_properties:
            prop = page.properties[selected_property]

            match prop.type:
                case "title":
                    row[selected_property] = " ".join(
                        [t.text.content for t in prop.title]
                    )
                case "rich_text":
                    row[selected_property] = " ".join(
                        [t.text.content for t in prop.rich_text]
                    )
                case "number":
                    row[selected_property] = prop.number
                case "select":
                    if prop.select is None:
                        row[selected_property] = None
                        continue
                    row[selected_property] = prop.select.id
                case "multi_select":
                    row[selected_property] = [s.id for s in prop.multi_select]
                case "date":
                    if prop.date is None:
                        row[selected_property] = None
                        continue
                    if prop.date.end:
                        # we have a range
                        row[selected_property] = prop.date
                    else:
                        row[selected_property] = prop.date.start
                case "people":
                    row[selected_property] = [p.id for p in prop.people]
                case "last_edited_by":
                    row[selected_property] = prop.last_edited_by.id
                case "last_edited_time":
                    row[selected_property] = prop.last_edited_time
                case "relation":
                    row[selected_property] = [r.id for r in prop.relation]
                case _:
                    # See https://developers.notion.com/reference/page-property-values
                    raise ValueError(f"Unsupported property type: {prop.type}")
        yield use_id(page, exclude=["properties", "object"]) | row


@dlt.source(name="notion")
def source(
    limit: int = -1,
) -> Sequence[DltResource]:
    users = list_users()
    if limit != -1:
        users.add_limit(limit)

    db_rs = database_resource(database_id="...")

    return (
        users | split_user,
        db_rs,
    )


__all__ = ["source", "database_resource"]
