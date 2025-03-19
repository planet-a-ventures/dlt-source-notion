import dlt
from notion_client import Client


def get_notion_client() -> Client:
    if not hasattr(get_notion_client, "client"):
        get_notion_client.client = Client(auth=dlt.secrets["notion_token"])
    return get_notion_client.client
