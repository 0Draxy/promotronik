from __future__ import annotations
from typing import Optional, Dict, Any
import paapi5_python_sdk as paapi
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models import SearchItemsRequest, Condition, PartnerType, SearchItemsResource

class PaapiClient:
    def __init__(self, access_key: str, secret_key: str, marketplace: str, partner_tag: str):
        self.cfg = paapi.configuration.Configuration()
        self.cfg.access_key = access_key
        self.cfg.secret_key = secret_key
        self.cfg.host = marketplace
        self.partner_tag = partner_tag
        self.api = DefaultApi(paapi.ApiClient(self.cfg))

    def search_items(self, keywords: str, browse_node: Optional[str], sort_by: str, page: int = 1) -> Dict[str, Any]:
        try:
            req = SearchItemsRequest(
                partner_tag=self.partner_tag,
                partner_type=PartnerType("Associates"),
                marketplace=self.cfg.host,
                keywords=keywords,
                browse_node_id=browse_node,
                sort_by=sort_by,
                condition=Condition("New"),
                item_page=page,
                resources=[
                    SearchItemsResource.ITEMINFO_TITLE,
                    SearchItemsResource.IMAGES_PRIMARY_MEDIUM,
                    SearchItemsResource.OFFERS_LISTINGS_PRICE,
                    SearchItemsResource.OFFERS_SUMMARIES_LOWESTPRICE,
                    SearchItemsResource.OFFERS_SUMMARIES_HIGHESTPRICE,
                    SearchItemsResource.OFFERS_SUMMARIES_OFFERCOUNT,
                    SearchItemsResource.OFFERS_SUMMARIES_SAVINGS,
                ],
            )
            return self.api.search_items(req).to_dict()
        except Exception as e:
            print(f"[paapi] search_items error: {e}")
            return {}

def paapi_client(access_key: str, secret_key: str, marketplace: str, partner_tag: str) -> PaapiClient:
    return PaapiClient(access_key, secret_key, marketplace, partner_tag)
