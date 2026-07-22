from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class ShopifyError(RuntimeError):
    pass


PRODUCTS_QUERY = """
query HulaProducts($first: Int!, $after: String, $query: String!) {
  products(first: $first, after: $after, query: $query, sortKey: UPDATED_AT, reverse: true) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      title
      handle
      description
      productType
      vendor
      tags
      status
      createdAt
      updatedAt
      onlineStoreUrl
      totalInventory
      priceRangeV2 {
        minVariantPrice { amount currencyCode }
        maxVariantPrice { amount currencyCode }
      }
      featuredMedia {
        preview { image { url altText } }
      }
    }
  }
}
"""


@dataclass
class _Token:
    value: str = ""
    expires_at: float = 0.0


def _retrying_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def normalize_shop(shop: str) -> str:
    raw = shop.strip().lower()
    if not raw:
        raise ShopifyError("SHOPIFY_SHOP is missing.")
    if "://" in raw:
        raw = urlparse(raw).netloc
    raw = raw.split("/")[0]
    if raw.endswith(".myshopify.com"):
        raw = raw[: -len(".myshopify.com")]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", raw):
        raise ShopifyError("SHOPIFY_SHOP must be the store's myshopify subdomain.")
    return raw


class ShopifyConnector:
    def __init__(
        self,
        shop: str,
        client_id: str = "",
        client_secret: str = "",
        admin_access_token: str = "",
        api_version: str = "2026-07",
        storefront_url: str = "https://thehula.com",
    ) -> None:
        self.shop = normalize_shop(shop)
        self.client_id = client_id
        self.client_secret = client_secret
        self.admin_access_token = admin_access_token
        self.api_version = api_version
        self.storefront_url = storefront_url.rstrip("/")
        self.session = _retrying_session()
        self._token = _Token()

    @property
    def shop_domain(self) -> str:
        return f"{self.shop}.myshopify.com"

    def _access_token(self) -> str:
        if self.admin_access_token:
            return self.admin_access_token
        if self._token.value and time.time() < self._token.expires_at - 60:
            return self._token.value
        if not self.client_id or not self.client_secret:
            raise ShopifyError(
                "Set SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET, or a legacy "
                "SHOPIFY_ADMIN_ACCESS_TOKEN."
            )
        response = self.session.post(
            f"https://{self.shop_domain}/admin/oauth/access_token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if not response.ok:
            raise ShopifyError(
                f"Shopify token request failed ({response.status_code}). "
                "Check that the app is installed and its version is released."
            )
        payload = response.json()
        value = payload.get("access_token", "")
        if not value:
            raise ShopifyError("Shopify did not return an access token.")
        self._token = _Token(
            value=value,
            expires_at=time.time() + int(payload.get("expires_in", 86399)),
        )
        return value

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json",
            json={"query": query, "variables": variables},
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": self._access_token(),
            },
            timeout=60,
        )
        if not response.ok:
            raise ShopifyError(
                f"Shopify GraphQL request failed ({response.status_code})."
            )
        payload = response.json()
        errors = payload.get("errors") or []
        if errors:
            message = "; ".join(str(item.get("message", item)) for item in errors)
            raise ShopifyError(f"Shopify GraphQL error: {message}")
        return payload.get("data") or {}

    def test_connection(self) -> dict[str, Any]:
        data = self.graphql(
            "query { shop { name myshopifyDomain } products(first: 1) { nodes { id } } }",
            {},
        )
        shop = data.get("shop") or {}
        return {
            "ok": True,
            "shop_name": shop.get("name", self.shop),
            "domain": shop.get("myshopifyDomain", self.shop_domain),
        }

    def fetch_products(
        self,
        max_products: int = 750,
        query_filter: str = "status:active",
    ) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        after: str | None = None
        while len(products) < max_products:
            page_size = min(100, max_products - len(products))
            data = self.graphql(
                PRODUCTS_QUERY,
                {
                    "first": page_size,
                    "after": after,
                    "query": query_filter,
                },
            )
            connection = data.get("products") or {}
            nodes = connection.get("nodes") or []
            products.extend(self._normalize_product(node) for node in nodes)
            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage") or not nodes:
                break
            after = page_info.get("endCursor")
        return products[:max_products]

    def _normalize_product(self, node: dict[str, Any]) -> dict[str, Any]:
        price = ((node.get("priceRangeV2") or {}).get("minVariantPrice") or {})
        featured = node.get("featuredMedia") or {}
        image = ((featured.get("preview") or {}).get("image") or {})
        product_id = str(node.get("id", ""))
        numeric_id = product_id.rsplit("/", 1)[-1] if product_id else ""
        handle = str(node.get("handle", ""))
        description = html.unescape(str(node.get("description", "")))
        return {
            "id": product_id,
            "numeric_id": numeric_id,
            "title": str(node.get("title", "")),
            "handle": handle,
            "description": re.sub(r"\s+", " ", description).strip(),
            "product_type": str(node.get("productType", "")),
            "vendor": str(node.get("vendor", "")),
            "tags": [str(tag) for tag in node.get("tags") or []],
            "status": str(node.get("status", "")),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
            "inventory": int(node.get("totalInventory") or 0),
            "price": float(price.get("amount") or 0),
            "currency": str(price.get("currencyCode", "HKD")),
            "image_url": str(image.get("url", "")),
            "image_alt": str(image.get("altText") or node.get("title", "")),
            "product_url": str(node.get("onlineStoreUrl") or (
                f"{self.storefront_url}/products/{handle}" if handle else ""
            )),
            "admin_url": (
                f"https://admin.shopify.com/store/{self.shop}/products/{numeric_id}"
                if numeric_id
                else ""
            ),
            "is_demo": False,
        }
