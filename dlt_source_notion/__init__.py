"""A source loading entities and lists from notion  (notion.com)"""

from enum import StrEnum
from typing import Any, Callable, Generator, Iterable, List, Sequence, TypeVar
from uuid import UUID
import dlt
from pydantic import Field, TypeAdapter

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
    BaseDatabaseProperty,
    MultiSelectPropertyConfig,
    SelectPropertyConfig,
)
from dlt.common.normalizers.naming.snake_case import NamingConvention

# from notion_client.helpers import iterate_paginated_api
from pydantic import AnyUrl, BaseModel

from .client import get_notion_client

import hashlib


def short_hash(input: str | UUID, digest_size: int = 4) -> str:
    # Using BLAKE2b with an x-byte digest (64 bits)
    h = hashlib.blake2b(str(input).encode(), digest_size=digest_size)
    return h.hexdigest()


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
    DATABASES = "databases"


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

DatabaseProperty = BaseDatabaseProperty

ColumnNameProjection = Callable[[DatabaseProperty, Callable[[str], str]], str | None]
"""
A function that determines the resulting column name for a given property. Return `None` to exclude the property. Fails if the resulting column names are not unique.
"""


@dlt.resource(
    selected=True,
    parallelized=True,
    primary_key="id",
    max_table_nesting=1,
)
def database_resource(
    database_id: str,
    column_name_projection: ColumnNameProjection,
) -> Iterable[Page]:
    client = get_notion_client()

    db: Database = client.databases.retrieve(database_id=database_id)

    db_table_name = naming_convention.normalize_path(
        "database_" + db.plain_text_title + "_" + short_hash(db.id)
    )

    all_properties = list(db.properties.values())

    target_key_mapping = {
        p.name: proj
        for p in all_properties
        if (proj := column_name_projection(p, naming_convention.normalize_path))
        is not None
    }

    properties = [
        {"column": column, "label": label}
        for label, column in target_key_mapping.items()
    ]

    yield dlt.mark.with_hints(
        item={
            "title": db.plain_text_title,
            "db_table_name": db_table_name,
            "properties": properties,
        }
        | use_id(db, exclude=["object", "properties", "title"]),
        hints=dlt.mark.make_hints(
            table_name=Table.DATABASES.value,
            primary_key="id",
            write_disposition="merge",
        ),
        # needs to be a variant due to https://github.com/dlt-hub/dlt/pull/2109
        create_table_variant=True,
    )

    for p in all_properties:
        if p.type not in ["multi_select", "select"]:
            continue

        data: MultiSelectPropertyConfig | SelectPropertyConfig = getattr(p, p.type)
        for option in data.options:
            yield dlt.mark.with_hints(
                item=use_id(option, exclude=["object", "color"]),
                hints=dlt.mark.make_hints(
                    table_name="options_" + p.name + "_" + short_hash(p.id),
                    primary_key="id",
                    write_disposition="merge",
                ),
            )

    target_column_names = list(target_key_mapping.values())
    selected_properties = list(target_key_mapping.keys())

    if len(target_column_names) != len(set(target_column_names)):
        raise ValueError(
            "The column name projection function must produce unique column names. Current column names: "
            + ", ".join(target_column_names)
        )

    for pages in iterate_paginated_api(client.databases.query, database_id=database_id):
        for page in pages:
            assert isinstance(page, Page)

            row = {}
            for selected_key in selected_properties:
                prop = page.properties[selected_key]
                target_key = target_key_mapping[selected_key]

                match prop.type:
                    case "title":
                        row[target_key] = "".join([t.text.content for t in prop.title])
                    case "rich_text":
                        row[target_key] = "".join(
                            [t.text.content for t in prop.rich_text]
                        )
                    case "number":
                        row[target_key] = prop.number
                    case "select":
                        if prop.select is None:
                            row[target_key] = None
                            continue
                        row[target_key + "_" + short_hash(prop.id)] = prop.select.id
                    case "multi_select":
                        row[target_key + "_" + short_hash(prop.id)] = [
                            s.id for s in prop.multi_select
                        ]
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
                        row[target_key + "_users"] = [p.id for p in prop.people]
                    case "last_edited_by":
                        row[target_key] = prop.last_edited_by.id
                    case "last_edited_time":
                        row[target_key] = prop.last_edited_time
                    case "relation":
                        row[target_key + "_relations"] = [r.id for r in prop.relation]
                    case _:
                        # See https://developers.notion.com/reference/page-property-values
                        raise ValueError(
                            f"Unsupported property type: {prop.type}; Please open a pull request."
                        )
            yield dlt.mark.with_hints(
                item=use_id(page, exclude=["properties"]) | row,
                hints=dlt.mark.make_hints(
                    table_name=db_table_name,
                    primary_key="id",
                    write_disposition="merge",
                ),
                # needs to be a variant due to https://github.com/dlt-hub/dlt/pull/2109
                create_table_variant=True,
            )


class DatabaseResourceBase:
    column_name_projection: ColumnNameProjection = lambda x, normalize: normalize(
        x.name
    )


class DatabaseResource(DatabaseResourceBase):
    def __init__(
        self, database_id: str, column_name_projection: ColumnNameProjection = None
    ):
        self.database_id = database_id
        if column_name_projection is not None:
            self.column_name_projection = column_name_projection

    def get_resource(self):
        return database_resource(
            database_id=self.database_id,
            column_name_projection=self.column_name_projection,
        )

    def __str__(self):
        return f"DatabaseResource(database_id={self.database_id})"


@dlt.source(name="notion")
def source(
    limit: int = -1,
    database_resources: List[DatabaseResource] = Field(default_factory=list),
) -> Sequence[DltResource]:
    users = list_users()
    if limit != -1:
        users.add_limit(limit)

    return (
        users | split_user,
        *[d.get_resource() for d in database_resources],
    )


__all__ = ["source", "DatabaseResource", "ColumnNameProjection", "DatabaseProperty"]
