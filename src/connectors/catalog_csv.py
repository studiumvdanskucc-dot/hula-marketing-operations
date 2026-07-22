from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd


class CatalogCsvError(ValueError):
    """Raised when an uploaded catalogue cannot be normalised safely."""


@dataclass(frozen=True)
class CatalogCsvResult:
    products: list[dict[str, Any]]
    source_format: str
    source_rows: int
    skipped_rows: int
    warnings: list[str]


SIMPLE_CSV_TEMPLATE = """title,vendor,product_type,status,inventory,price,currency,tags,description,image_url,product_url,handle,created_at
Example East-West Bag,Chanel,Bag,ACTIVE,1,12000,HKD,"east west, black, shoulder bag",Example product description,https://example.com/image.jpg,https://thehula.com/products/example-east-west-bag,example-east-west-bag,2026-07-01T09:00:00Z
"""


ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id", "product id", "shopify product id"),
    "handle": ("handle", "product handle", "slug"),
    "title": ("title", "product title", "product name", "name"),
    "description": (
        "body html",
        "body (html)",
        "description",
        "product description",
        "body",
    ),
    "vendor": (
        "Brand (product.metafields.wk_custom_field.brand)",
        "vendor",
        "brand",
        "designer",
        "manufacturer",
    ),
    "product_type": (
        "type",
        "product type",
        "product_type",
        "category",
        "product category",
    ),
    "tags": ("tags", "tag", "keywords", "attributes"),
    "status": ("status", "product status", "state"),
    "published": ("published", "is published", "active"),
    "inventory": (
        "variant inventory qty",
        "variant inventory quantity",
        "inventory",
        "inventory quantity",
        "quantity",
        "qty",
        "stock",
        "available",
    ),
    "price": (
        "variant price",
        "price",
        "selling price",
        "current price",
    ),
    "currency": ("currency", "currency code"),
    "image_url": (
        "image src",
        "image url",
        "image_url",
        "featured image",
        "featured image url",
    ),
    "image_alt": ("image alt text", "image alt", "alt text"),
    "product_url": (
        "product url",
        "product_url",
        "online store url",
        "url",
        "link",
    ),
    "created_at": (
        "CreatedAt (product.metafields.custom.createdat)",
        "created at",
        "created_at",
        "date added",
        "created",
    ),
    "updated_at": ("updated at", "updated_at", "last updated", "updated"),
}


def _normalise_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _column_map(frame: pd.DataFrame) -> dict[str, str]:
    normalised = {_normalise_header(column): str(column) for column in frame.columns}
    output: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            found = normalised.get(_normalise_header(alias))
            if found is not None:
                output[target] = found
                break
    return output


def _read_csv(payload: bytes | str, max_rows: int) -> pd.DataFrame:
    if isinstance(payload, bytes):
        if len(payload) > 20 * 1024 * 1024:
            raise CatalogCsvError("The catalogue CSV must be smaller than 20 MB.")
        decoded: str | None = None
        for encoding in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                decoded = payload.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise CatalogCsvError("The CSV encoding could not be read. Export it as UTF-8 CSV.")
    else:
        decoded = payload
    try:
        frame = pd.read_csv(
            io.StringIO(decoded),
            dtype=str,
            keep_default_na=False,
            on_bad_lines="error",
        )
    except (pd.errors.ParserError, UnicodeError) as exc:
        raise CatalogCsvError(f"The CSV could not be parsed: {exc}") from exc
    frame.columns = [str(column).strip() for column in frame.columns]
    frame = frame.loc[~frame.apply(lambda row: all(not str(value).strip() for value in row), axis=1)]
    if frame.empty:
        raise CatalogCsvError("The uploaded CSV has no product rows.")
    if len(frame) > max_rows:
        raise CatalogCsvError(
            f"The CSV has {len(frame):,} rows; the safety limit is {max_rows:,}."
        )
    return frame.reset_index(drop=True)


def _first(values: Iterable[Any]) -> str:
    for value in values:
        cleaned = str(value).strip()
        if cleaned:
            return cleaned
    return ""


def _clean_html(value: str) -> str:
    without_scripts = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>", " ", value, flags=re.IGNORECASE | re.DOTALL
    )
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _number(value: Any) -> float | None:
    cleaned = str(value).strip().replace(",", "")
    cleaned = re.sub(r"[^0-9.+-]", "", cleaned)
    if not cleaned or cleaned in {"+", "-", "."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _datetime(value: Any) -> str | None:
    """Return ISO time for Shopify/HULA timestamps while preserving valid ISO text."""

    cleaned = str(value).strip().lstrip("'")
    if not cleaned:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
        timestamp = float(cleaned)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return cleaned


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:100]


def _split_tags(values: Iterable[Any]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for value in values:
        for tag in re.split(r"[,;|]", str(value)):
            cleaned = tag.strip()
            key = cleaned.casefold()
            if cleaned and key not in seen:
                tags.append(cleaned)
                seen.add(key)
    return tags


def _status(status: str, published: str) -> str:
    value = status.strip().lower()
    if value in {"active", "published", "available", "in stock", "true", "yes", "1"}:
        return "ACTIVE"
    if value in {"archived", "archive"}:
        return "ARCHIVED"
    if value in {"draft", "inactive", "unpublished", "false", "no", "0"}:
        return "DRAFT"
    if not value and published.strip().lower() in {"false", "no", "0"}:
        return "DRAFT"
    return value.upper() if value else "ACTIVE"


def _values(group: pd.DataFrame, columns: dict[str, str], field: str) -> list[str]:
    column = columns.get(field)
    if column is None:
        return []
    return [str(value) for value in group[column].tolist()]


def _product_from_group(
    group: pd.DataFrame,
    columns: dict[str, str],
    *,
    group_key: str,
    storefront_url: str,
    default_currency: str,
) -> tuple[dict[str, Any] | None, bool]:
    title = _first(_values(group, columns, "title"))
    handle = _first(_values(group, columns, "handle")) or _slug(title)
    if not title:
        title = handle.replace("-", " ").strip().title()
    if not title:
        return None, False

    inventory_numbers = [
        number
        for number in (_number(value) for value in _values(group, columns, "inventory"))
        if number is not None
    ]
    inventory_defaulted = not inventory_numbers
    inventory = 1 if inventory_defaulted else max(0, int(round(sum(inventory_numbers))))

    price_numbers = [
        number
        for number in (_number(value) for value in _values(group, columns, "price"))
        if number is not None and number >= 0
    ]
    price = min(price_numbers) if price_numbers else 0.0
    raw_id = _first(_values(group, columns, "id"))
    numeric_id = raw_id.rsplit("/", 1)[-1] if raw_id else ""
    stable_id = raw_id or f"csv:{handle or group_key}"
    description = _clean_html(_first(_values(group, columns, "description")))
    image_url = _first(_values(group, columns, "image_url"))
    product_url = _first(_values(group, columns, "product_url"))
    if not product_url and handle:
        product_url = f"{storefront_url.rstrip('/')}/products/{handle}"
    status = _status(
        _first(_values(group, columns, "status")),
        _first(_values(group, columns, "published")),
    )
    currency = _first(_values(group, columns, "currency")) or default_currency
    return (
        {
            "id": stable_id,
            "numeric_id": numeric_id,
            "title": title,
            "handle": handle,
            "description": description,
            "product_type": _first(_values(group, columns, "product_type")),
            "vendor": _first(_values(group, columns, "vendor")),
            "tags": _split_tags(_values(group, columns, "tags")),
            "status": status,
            "created_at": _datetime(_first(_values(group, columns, "created_at"))),
            "updated_at": _datetime(_first(_values(group, columns, "updated_at"))),
            "inventory": inventory,
            "price": float(price),
            "currency": currency.upper(),
            "image_url": image_url,
            "image_alt": _first(_values(group, columns, "image_alt")) or title,
            "product_url": product_url,
            "admin_url": "",
            "is_demo": False,
            "catalogue_source": "csv",
        },
        inventory_defaulted,
    )


def parse_product_csv(
    payload: bytes | str,
    *,
    storefront_url: str = "https://thehula.com",
    default_currency: str = "HKD",
    max_rows: int = 50_000,
) -> CatalogCsvResult:
    """Normalise Shopify exports and simple product CSVs to the app schema."""

    frame = _read_csv(payload, max_rows=max_rows)
    columns = _column_map(frame)
    if "title" not in columns and "handle" not in columns:
        available = ", ".join(str(column) for column in frame.columns[:12])
        raise CatalogCsvError(
            "No product title or Shopify Handle column was found. "
            f"Detected columns: {available}"
        )

    normalised_headers = {_normalise_header(column) for column in frame.columns}
    is_shopify = bool(
        "handle" in columns
        and normalised_headers.intersection(
            {"variant price", "variant sku", "body html", "image src"}
        )
    )
    source_format = "Shopify product export" if is_shopify else "standard product CSV"

    groups: list[tuple[str, pd.DataFrame]] = []
    if is_shopify:
        handle_column = columns["handle"]
        frame[handle_column] = frame[handle_column].replace("", pd.NA).ffill().fillna("")
        for key, group in frame.groupby(handle_column, sort=False, dropna=False):
            groups.append((str(key).strip(), group))
    else:
        key_column = columns.get("id") or columns.get("handle")
        if key_column:
            keys = [
                str(value).strip() or f"__row_{index}"
                for index, value in enumerate(frame[key_column].tolist())
            ]
            keyed = frame.assign(__catalogue_group=keys)
            for key, group in keyed.groupby("__catalogue_group", sort=False):
                group = group.drop(columns=["__catalogue_group"])
                groups.append((str(key).strip(), group))
        else:
            groups = [(str(index), frame.iloc[[index]]) for index in range(len(frame))]

    products: list[dict[str, Any]] = []
    skipped = 0
    defaulted_inventory = 0
    seen_ids: set[str] = set()
    for group_key, group in groups:
        product, used_default_inventory = _product_from_group(
            group,
            columns,
            group_key=group_key,
            storefront_url=storefront_url,
            default_currency=default_currency,
        )
        if product is None:
            skipped += len(group)
            continue
        product_id = str(product["id"])
        if product_id in seen_ids:
            product["id"] = f"{product_id}:{len(products) + 1}"
        seen_ids.add(str(product["id"]))
        products.append(product)
        defaulted_inventory += int(used_default_inventory)

    if not products:
        raise CatalogCsvError("No usable products could be created from the CSV.")

    warnings: list[str] = []
    if defaulted_inventory:
        warnings.append(
            f"Inventory was missing for {defaulted_inventory} product(s); "
            "the importer assumed one available item so they can be tested."
        )
    if "image_url" not in columns:
        warnings.append("No image column was found; product cards will use placeholders.")
    if "created_at" not in columns:
        warnings.append("No created-date column was found; freshness uses a neutral score.")
    if skipped:
        warnings.append(f"Skipped {skipped} row(s) without a title or handle.")

    return CatalogCsvResult(
        products=products,
        source_format=source_format,
        source_rows=len(frame),
        skipped_rows=skipped,
        warnings=warnings,
    )
