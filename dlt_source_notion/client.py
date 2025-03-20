import dlt
from pydantic_api.notion.sdk import NotionClient


def get_notion_client() -> NotionClient:
    if not hasattr(get_notion_client, "client"):
        get_notion_client.client = NotionClient(auth=dlt.secrets["notion_token"])
    return get_notion_client.client
