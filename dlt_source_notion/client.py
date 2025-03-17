import dlt
from notion_client import Client


def get_notion_client():
    return Client(auth=dlt.secrets["notion_token"])
