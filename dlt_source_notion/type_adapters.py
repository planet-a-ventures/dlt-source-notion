from pydantic import TypeAdapter

from .model.notion_2022_06_28 import NotionObject, User


user_adapter = TypeAdapter(User)
object_adapter = TypeAdapter(NotionObject)
