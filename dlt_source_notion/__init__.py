"""A source loading entities and lists from notion  (notion.com)"""

from enum import StrEnum
import json
from typing import Any, Callable, Generator, Iterable, List, Sequence, TypeVar
import dlt
from pydantic import TypeAdapter

from dlt.common import json
from dlt.common.json import JsonSerializable
from dlt.sources import DltResource
from pydantic_api.notion.models import (
    UserObject,
    StartCursor,
    NotionPaginatedData,
    Database,
    Page,
    PageProperty,
    # TODO: replace this with `BaseDatabaseProperty` when https://github.com/stevieflyer/pydantic-api-models-notion/pull/8 lands
    DatabaseProperty
)
from dlt.common.normalizers.naming.snake_case import NamingConvention


# from notion_client.helpers import iterate_paginated_api
from pydantic import AnyUrl, BaseModel

from .client import get_notion_client


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


def use_id(entity: UserObject, **kwargs) -> dict:
    return pydantic_model_dump(entity, **kwargs) | {"_dlt_id": __get_id(entity)}


def __get_id(obj):
    if isinstance(obj, dict):
        return obj.get("id")
    return getattr(obj, "id", None)


R = TypeVar("R", bound=BaseModel)


def iterate_paginated_api(
    function: Callable[..., NotionPaginatedData[R]], **kwargs: Any
) -> Generator[List[R], None, None]:
    """Return an iterator over the results of any paginated Notion API."""
    next_cursor: StartCursor = kwargs.pop("start_cursor", None)

    while True:
        response = function(**kwargs, start_cursor=next_cursor)
        yield response.results

        next_cursor = response.next_cursor
        if not response.has_more or not next_cursor:
            return


@dlt.resource(
    selected=True,
    parallelized=True,
    primary_key="id",
)
def list_users() -> Iterable[UserObject]:
    client = get_notion_client()

    yield from iterate_paginated_api(client.users.list)


@dlt.transformer(
    parallelized=True,
    name="users",
)
def split_user(users: List[UserObject]):
    """
    Split users into two tables: persons and bots.
    """
    for user in users:
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


page_property_adapter = TypeAdapter(PageProperty)

naming_convention = NamingConvention()


@dlt.resource(
    selected=True,
    parallelized=True,
    primary_key="id",
    max_table_nesting=1,
)
def database_resource(
    database_id: str,
    property_filter: Callable[[DatabaseProperty], bool] = lambda _: True,
    column_name_projection: Callable[[DatabaseProperty], str] = lambda x: naming_convention.normalize_path(x.name),
) -> Iterable[Page]:

    client = get_notion_client()

    db: Database = client.databases.retrieve(database_id=database_id)

    all_properties = list(db.properties.values())
    selected_properties = list(filter(property_filter, all_properties))

    target_key_mapping = {
        p.name: column_name_projection(p)
        for p in selected_properties
    }
    target_keys = list(target_key_mapping.values())

    if len(target_keys) != len(set(target_keys)):
        raise ValueError(
            "The column name projection function must produce unique column names. Current column names: "
            + ", ".join(target_keys)
        )

    for pages in iterate_paginated_api(client.databases.query, database_id=database_id):
        for page in pages:
            assert isinstance(page, Page)

            row = {}
            for selected_property in selected_properties:
                selected_key = selected_property.name
                prop_raw = page.properties[selected_key]
                # TODO: remove this cast, once https://github.com/stevieflyer/pydantic-api-models-notion/pull/6 lands
                prop: PageProperty = page_property_adapter.validate_python(prop_raw)

                target_key = target_key_mapping[selected_key]

                match prop.type:
                    case "title":
                        row[target_key] = " ".join([t.text.content for t in prop.title])
                    case "rich_text":
                        row[target_key] = " ".join(
                            [t.text.content for t in prop.rich_text]
                        )
                    case "number":
                        row[target_key] = prop.number
                    case "select":
                        if prop.select is None:
                            row[target_key] = None
                            continue
                        row[target_key] = prop.select.id
                    case "multi_select":
                        row[target_key] = [s.id for s in prop.multi_select]
                    case "date":
                        if prop.date is None:
                            row[target_key] = None
                            continue
                        if prop.date.end:
                            # we have a range
                            row[target_key] = prop.date
                        else:
                            row[target_key] = prop.date.start
                    case "people":
                        row[target_key] = [p.id for p in prop.people]
                    case "last_edited_by":
                        row[target_key] = prop.last_edited_by.id
                    case "last_edited_time":
                        row[target_key] = prop.last_edited_time
                    case "relation":
                        row[target_key] = [r.id for r in prop.relation]
                    case _:
                        # See https://developers.notion.com/reference/page-property-values
                        raise ValueError(
                            f"Unsupported property type: {prop.type}; Please open a pull request."
                        )
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
