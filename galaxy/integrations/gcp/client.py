from google.cloud import asset_v1
from google.oauth2 import service_account
from google.protobuf.json_format import MessageToDict

__all__ = ["GcpClient"]


class GcpClient:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.json_account_info = config.integration.properties["serviceAccountInfo"]
        self.credentials = service_account.Credentials.from_service_account_info(self.json_account_info)
        self.client = asset_v1.AssetServiceClient(credentials=self.credentials)

    async def get_assets(self, asset_types):
        assets = []

        request = asset_v1.ListAssetsRequest(
            parent=f"projects/{self.json_account_info['project_id']}",
            read_time=None,
            asset_types=asset_types,
            content_type="RESOURCE",
            page_size=100,
        )
        response = self.client.list_assets(request)
        assets.extend(response)

        while response._response.next_page_token != "":
            request.page_token = response._response.next_page_token
            response = self.client.list_assets(request)
            assets.extend(response)

        return [MessageToDict(message=asset._pb) for asset in assets]
