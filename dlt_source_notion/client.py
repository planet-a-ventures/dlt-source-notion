import dlt
from notion_client import Client


def get_notion_client():
    return Client(auth=dlt.secrets["notion_token"])


# Share a session (and thus pool) between all rest clients
# session: Session = Session(raise_for_status=False)

# auth: notionOAuth2ClientCredentials = None


# def get_rest_client(
#     api_base: str = API_BASE,
# ):
#     global session
#     global auth

#     if auth is None:
#         auth = notionOAuth2ClientCredentials(
#             api_base=api_base,
#             client_id=dlt.secrets["notion_client_id"],
#             client_secret=dlt.secrets["notion_client_secret"],
#             default_token_expiration=86400,
#             session=session,
#         )

#     client = RESTClient(
#         base_url=api_base,
#         headers={
#             "Accept": "application/json",
#             "X-notion-App-ID": X_notion_APP_ID,
#         },
#         auth=auth,
#         data_selector="_data",
#         paginator=JSONLinkPaginator(next_url_path="_meta.links.next.href"),
#         session=session,
#     )
#     return client, auth


# def debug_response(response: Response, *args: Any, **kwargs: Any) -> None:
#     if logging.getLogger().isEnabledFor(logging.DEBUG):
#         logging.debug(
#             f"Response: {response.status_code} {response.reason} {response.url} {response.text}"
#         )


# def raise_for_status(response: Response, *args: Any, **kwargs: Any) -> None:
#     # TODO: Add more detailed error handling, using the notion error response model
#     response.raise_for_status()


# hooks = {
#     "response": [
#         debug_response,
#         raise_for_status,
#     ]
# }
# V2_MAX_PAGE_LIMIT = 50
# V1_BASE_PAGE = 0
