"""A source loading entities and lists from notion  (notion.com)"""

from enum import StrEnum
from typing import Dict, Iterable, List, Sequence
import dlt
from dlt.sources import DltResource, TDataItem

from dlt_source_notion.client import get_notion_client
from notion_client.helpers import iterate_paginated_api


# logging.basicConfig(level=logging.DEBUG)

# if is_logging():
#     logger = logging.getLogger("dlt")

#     class HideSinglePagingNonsense(logging.Filter):
#         def filter(self, record):
#             msg = record.getMessage()
#             if (
#                 "Extracted data of type list from path _data with length 1" in msg
#                 or re.match(
#                     r"Paginator JSONLinkPaginator at [a-fA-F0-9]+: next_url_path: _meta\.links\.next\.href does not have more pages",
#                     msg,
#                 )
#             ):
#                 return False
#             return True

#     logger.addFilter(HideSinglePagingNonsense())


# def anyurl_encoder(obj: Any) -> JsonSerializable:
#     if isinstance(obj, AnyUrl):
#         return obj.unicode_string()
#     raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# json.set_custom_encoder(anyurl_encoder)


# def pydantic_model_dump(model: BaseModel, **kwargs):
#     """
#     Dumps a Pydantic model to a dictionary, using the model's field names as keys and NOT observing the field aliases,
#     which is important for DLT to correctly map the data to the destination.
#     """
#     return model.model_dump(by_alias=True, **kwargs)


class Table(StrEnum):
    PERSONS = "persons"
    BOTS = "bots"


def use_id(entity: Dict, **kwargs) -> Dict:
    return filter_dict(entity, **kwargs) | {"_dlt_id": __get_id(entity)}


# @dlt.resource(
#     selected=True,
#     parallelized=True,
#     primary_key="id",
# )
# def persons(rest_client: RESTClient) -> Iterable[TDataItem]:
#     for persons_raw in rest_client.paginate(
#         V2_PERSONS, params={"limit": V2_MAX_PAGE_LIMIT}, hooks=hooks
#     ):
#         yield persons_adapter.validate_python(persons_raw)


# async def person_employments(
#     person: Person,
#     rest_client: RESTClient,
# ):
#     href = jmespath.search("links.employments.href", person.field_meta)
#     if not href:
#         return
#     for employments_raw in rest_client.paginate(
#         href, params={"limit": V2_MAX_PAGE_LIMIT}, hooks=hooks
#     ):
#         employments = employments_adapter.validate_python(employments_raw)
#         for employment in employments:
#             yield dlt.mark.with_hints(
#                 item=use_id(employment, exclude=["field_meta", "org_units"]),
#                 hints=dlt.mark.make_hints(
#                     table_name=Table.EMPLOYMENTS.value,
#                 ),
#                 # needs to be a variant due to https://github.com/dlt-hub/dlt/pull/2109
#                 create_table_variant=True,
#             )


def __get_id(obj):
    if isinstance(obj, dict):
        return obj.get("id")
    return getattr(obj, "id", None)


# @dlt.transformer(
#     max_table_nesting=1,
#     parallelized=True,
#     table_name=Table.PERSONS.value,
# )
# async def person_details(persons: List[Person], rest_client: RESTClient):
#     yield [
#         use_id(person, exclude=["field_meta", "custom_attributes", "employments"])
#         for person in persons
#     ]
#     for person in persons:
#         yield person_employments(person, rest_client)
#         yield dlt.mark.with_hints(
#             item={"person_id": person.id}
#             | {cas.root.id: cas.root.value for cas in person.custom_attributes},
#             hints=dlt.mark.make_hints(
#                 table_name=Table.CUSTOM_ATTRIBUTES.value,
#                 primary_key="person_id",
#                 merge_key="person_id",
#                 write_disposition="merge",
#             ),
#             # needs to be a variant due to https://github.com/dlt-hub/dlt/pull/2109
#             create_table_variant=True,
#         )


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
