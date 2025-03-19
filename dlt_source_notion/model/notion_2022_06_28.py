from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any, Annotated
from uuid import UUID
from pydantic import AnyUrl, BaseModel, ConfigDict, Field, constr
from pydantic_extra_types.pendulum_dt import DateTime, Date


class Empty(BaseModel):
    ...
    model_config = ConfigDict(extra="forbid")


# Define a custom type for Notion property IDs.
PropertyID = constr(pattern=r"^[A-Za-z0-9%~\\]+$")


class UserReference(BaseModel):
    object: Literal["user"]
    id: UUID


class UserBase(UserReference):
    name: str
    avatar_url: Optional[AnyUrl] = None


class PersonProperties(BaseModel):
    email: str


# Person model
class Person(UserBase):
    type: Literal["person"]
    person: PersonProperties


class WorkspaceBotOwner(BaseModel):
    type: Literal["workspace"] = None
    workspace: Optional[bool] = None


class UserBotOwner(BaseModel):
    type: Literal["user"] = None
    user: User


# The discriminated union using the "type" field as the discriminator
BotOwner = Annotated[
    UserBotOwner | WorkspaceBotOwner,
    Field(discriminator="type"),
]


class BotProperties(BaseModel):
    owner: BotOwner
    workspace_name: Optional[str] = None


# Bot model
class Bot(UserBase):
    type: Literal["bot"]
    bot: BotProperties | Empty


# The discriminated union for User using the "type" field as the discriminator
User = Annotated[Person | Bot, Field(discriminator="type")]


class Link(BaseModel):
    url: AnyUrl


# Models for the title field
class TextContent(BaseModel):
    content: str
    link: Optional[Link] = None


class TextItemAnnotations(BaseModel):
    bold: bool
    italic: bool
    strikethrough: bool
    underline: bool
    code: bool
    color: str


class TextItem(BaseModel):
    type: Literal["text"]
    text: TextContent
    annotations: TextItemAnnotations
    plain_text: str
    href: Optional[AnyUrl] = None


class ReferenceBase(BaseModel):
    type: str  # This field is used as the discriminator


class PageReference(ReferenceBase):
    type: Literal["page_id"]
    page_id: UUID


class DatabaseReference(ReferenceBase):
    type: Literal["database_id"]
    database_id: UUID


# The discriminated union for Property using the "type" field as the discriminator
Reference = Annotated[PageReference | DatabaseReference, Field(discriminator="type")]


# Base class for Property (used as discriminator)
class PropertyBase(BaseModel):
    id: PropertyID  # type: ignore
    name: Optional[str] = None  # This is only available in the database item itself
    type: str  # This field is used as the discriminator


# People property model
class EmptyPeopleProperty(PropertyBase):
    type: Literal["people"]
    people: Empty


class PeopleProperty(EmptyPeopleProperty):
    people: List[User]


# Rich text property model
class EmptyRichTextProperty(PropertyBase):
    type: Literal["rich_text"]
    rich_text: Empty


class RichTextProperty(EmptyRichTextProperty):
    rich_text: List[TextItem]


NamedColor = Literal[
    "default",
    "gray",
    "brown",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
    "red",
]


# Multi-select property models
class MultiSelectOption(BaseModel):
    id: PropertyID | UUID  # type: ignore
    name: str
    color: NamedColor
    description: Optional[str] = None


class MultiSelectData(BaseModel):
    options: List[MultiSelectOption]


class MultiSelectPropertyBase(PropertyBase):
    type: Literal["multi_select"]


class EmptyMultiSelectProperty(MultiSelectPropertyBase):
    multi_select: MultiSelectData


class MultiSelectProperty(MultiSelectPropertyBase):
    multi_select: List[MultiSelectOption]


# Last edited time property model
class EmptyLastEditedTimeProperty(PropertyBase):
    type: Literal["last_edited_time"]
    last_edited_time: Empty


class LastEditedTimeProperty(EmptyLastEditedTimeProperty):
    last_edited_time: DateTime


class DateData(BaseModel):
    """
    https://developers.notion.com/reference/page-property-values#date
    """

    start: DateTime | Date
    end: Optional[DateTime] = None
    time_zone: Optional[Any] = None  # TODO: Update type when structure is known


# Date property model
class EmptyDateProperty(PropertyBase):
    type: Literal["date"]
    date: Empty


class DateProperty(EmptyDateProperty):
    date: Optional[DateData] = None


# Number property models
class EmptyNumberData(BaseModel):
    format: Literal["number"]


class EmptyNumberProperty(PropertyBase):
    type: Literal["number"]
    number: EmptyNumberData


class NumberProperty(EmptyNumberProperty):
    number: Optional[int | float] = None


# Select property models
class SelectOptionBase(BaseModel):
    id: UUID
    name: str
    color: NamedColor


class EmptySelectOption(SelectOptionBase):
    description: Optional[str] = None


class SelectOption(SelectOptionBase):
    pass


class SelectData(BaseModel):
    options: List[EmptySelectOption]


class SelectPropertyBase(PropertyBase):
    type: Literal["select"]


class EmptySelectProperty(SelectPropertyBase):
    select: SelectData


class SelectProperty(SelectPropertyBase):
    select: Optional[SelectOption] = None


# Last edited by property model
class EmptyLastEditedByProperty(PropertyBase):
    type: Literal["last_edited_by"]
    last_edited_by: Empty


class LastEditedByProperty(EmptyLastEditedByProperty):
    last_edited_by: User


# Title property model


class EmptyTitleProperty(PropertyBase):
    type: Literal["title"]
    title: Empty


class TitleProperty(EmptyTitleProperty):
    title: List[TextItem]


class IdReference(BaseModel):
    id: UUID


class RelationProperty(PropertyBase):
    type: Literal["relation"]
    relation: List[IdReference]
    has_more: bool


# The discriminated union for Property using the "type" field as the discriminator
Property = Annotated[
    PeopleProperty
    | RichTextProperty
    | MultiSelectProperty
    | LastEditedTimeProperty
    | DateProperty
    | NumberProperty
    | SelectProperty
    | LastEditedByProperty
    | TitleProperty
    | RelationProperty,
    Field(discriminator="type"),
]

# The discriminated union for GenericProperty using the "type" field as the discriminator
GenericProperty = Annotated[
    EmptyPeopleProperty
    | EmptyRichTextProperty
    | EmptyMultiSelectProperty
    | EmptyLastEditedTimeProperty
    | EmptyDateProperty
    | EmptyNumberProperty
    | EmptySelectProperty
    | EmptyLastEditedByProperty
    | EmptyTitleProperty,
    Field(discriminator="type"),
]


class ObjectBase(BaseModel):
    object: str  # This field is used as the discriminator
    id: UUID
    cover: Optional[Any] = None  # TODO: Update type when structure is known
    icon: Optional[Any] = None  # TODO: Update type when structure is known
    created_time: DateTime
    created_by: UserReference
    last_edited_by: UserReference
    last_edited_time: DateTime
    parent: Reference
    archived: bool
    in_trash: bool
    url: AnyUrl
    public_url: Optional[AnyUrl] = None


class Page(ObjectBase):
    object: Literal["page"]
    properties: Dict[str, Property]


# Main model for the database object
class Database(ObjectBase):
    object: Literal["database"]
    title: List[TextItem]
    description: List[Any]  # TODO: Update type when structure is known
    is_inline: bool
    properties: Dict[str, GenericProperty]
    request_id: UUID


NotionObject = Annotated[Page | Database, Field(discriminator="object")]
