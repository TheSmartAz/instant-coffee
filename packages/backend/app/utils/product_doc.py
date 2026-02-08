from __future__ import annotations

import json
import re
from typing import Any, List, Optional


_PAGE_HEADING_RE = re.compile(
    r"^#{2,4}\s*(?:\d+\.)?\s*(.+?)\s*\((`?)([^)]+)\2\)\s*$",
    re.IGNORECASE,
)
_PAGE_BULLET_RE = re.compile(
    r"^[-*]\s*(.+?)\s*\((`?)([^)]+)\2\)\s*$",
    re.IGNORECASE,
)
_SECTION_HEADING_RE = re.compile(r"^##(?!#)\s*(?:\d+\.)?\s*(.+?)\s*$", re.IGNORECASE)
_PURPOSE_RE = re.compile(r"^\*+\s*Purpose\s*\*+:?\s*(.+)$", re.IGNORECASE)
_PURPOSE_CN_RE = re.compile(r"^\*+\s*(\u76ee\u7684|\u7528\u9014)\s*\*+:?\s*(.+)$")
_SECTIONS_RE = re.compile(r"^\*+\s*Sections\s*\*+:?\s*(.*)$", re.IGNORECASE)
_SECTIONS_CN_RE = re.compile(r"^\*+\s*(\u90e8\u5206|\u677f\u5757|\u7ae0\u8282)\s*\*+:?\s*(.*)$")
_REQUIRED_RE = re.compile(r"^\*+\s*Required\s*\*+:?\s*(.+)$", re.IGNORECASE)
_REQUIRED_CN_RE = re.compile(r"^\*+\s*(\u5fc5\u9700|\u5fc5\u987b|\u662f\u5426\u5fc5\u9700)\s*\*+:?\s*(.+)$")

_PAGE_SECTION_KEYWORDS = (
    "page structure",
    "page structures",
    "pages",
    "page list",
    "screen map",
    "screen maps",
    "screens",
    "routes",
    "sitemap",
    "\u9875\u9762\u7ed3\u6784",
    "\u9875\u9762\u5217\u8868",
    "\u9875\u9762",
    "\u8def\u7531",
    "\u7ad9\u70b9\u5730\u56fe",
)

_NON_PAGE_SLUGS = {
    "must-follow",
    "recommended",
    "nice-to-have",
    "hard-rules",
    "soft-rules",
    "future-considerations",
    "navigation-structure",
    "core-requirements",
}

_PAGE_KEYWORDS = {
    "home",
    "index",
    "search",
    "discover",
    "browse",
    "favourite",
    "favorite",
    "profile",
    "account",
    "settings",
    "watch",
    "play",
    "player",
    "video",
    "detail",
    "details",
    "library",
    "tab",
    "screen",
    "page",
    "about",
    "contact",
    "pricing",
    "price",
    "product",
    "products",
    "service",
    "services",
    "blog",
    "faq",
    "cart",
    "checkout",
    "login",
    "signup",
    "dashboard",
    "admin",
    "feed",
}

_COMPONENT_HINT_KEYWORDS = {
    "header",
    "footer",
    "nav",
    "navbar",
    "row",
    "card",
    "grid",
    "input",
    "form",
    "button",
    "widget",
    "component",
    "module",
    "item",
    "chip",
    "badge",
    "banner",
    "hero",
    "carousel",
    "slider",
    "list",
    "tile",
    "state",
    "info",
    "label",
    "icon",
}

_KNOWN_SIMPLE_PAGE_SLUGS = {
    "index",
    "home",
    "search",
    "favourite",
    "favorite",
    "profile",
    "play",
    "watch",
    "video",
    "details",
    "detail",
    "settings",
    "about",
    "contact",
}


def extract_pages_from_markdown(content: str) -> List[dict]:
    if not content:
        return []

    lines = content.splitlines()
    headings = _collect_page_entries(lines, require_page_section=True)
    if not headings:
        headings = _collect_page_entries(lines, require_page_section=False)

    if not headings:
        return []

    pages: List[dict] = []
    for page_index, (start_idx, title, raw_path) in enumerate(headings):
        end_idx = headings[page_index + 1][0] if page_index + 1 < len(headings) else len(lines)
        section_lines = lines[start_idx + 1 : end_idx]

        purpose = ""
        sections: List[str] = []
        required: bool | None = None
        in_sections = False

        for line in section_lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("###") or stripped.startswith("##"):
                break

            match = _PURPOSE_RE.match(stripped) or _PURPOSE_CN_RE.match(stripped)
            if match:
                purpose = match.group(match.lastindex).strip()
                continue

            match = _SECTIONS_RE.match(stripped) or _SECTIONS_CN_RE.match(stripped)
            if match:
                in_sections = True
                inline = match.group(match.lastindex).strip()
                if inline:
                    sections.extend(_split_inline_list(inline))
                continue

            match = _REQUIRED_RE.match(stripped) or _REQUIRED_CN_RE.match(stripped)
            if match:
                value = match.group(match.lastindex).strip().lower()
                required = _truthy(value)
                continue

            if in_sections and stripped.startswith("-"):
                item = stripped.lstrip("-").strip()
                if item:
                    sections.append(item)

        slug = _coerce_slug(raw_path, title, page_index)
        if not _is_page_slug_allowed(slug):
            continue
        pages.append(
            {
                "title": title or slug or f"Page {page_index + 1}",
                "slug": slug,
                "purpose": purpose,
                "sections": sections,
                "required": bool(required),
            }
        )

    return _dedupe_pages(pages)


def _collect_page_entries(lines: List[str], *, require_page_section: bool) -> List[tuple[int, str, str]]:
    entries: List[tuple[int, str, str]] = []
    in_page_section = False

    for idx, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped:
            continue

        section_match = _SECTION_HEADING_RE.match(stripped)
        if section_match:
            section_title = section_match.group(1).strip()
            in_page_section = _is_page_section_heading(section_title)
            continue

        if require_page_section and not in_page_section:
            continue

        table_entry = _parse_page_table_entry(stripped)
        if table_entry is not None:
            title, raw_path = table_entry
            entries.append((idx, title, raw_path))
            continue

        match = _PAGE_HEADING_RE.match(stripped) or _PAGE_BULLET_RE.match(stripped)
        if not match:
            continue

        title = match.group(1).strip()
        raw_path = match.group(3).strip()
        slug_hint = _resolve_slug_hint(title, raw_path)
        if not slug_hint:
            continue

        entries.append((idx, title, slug_hint))

    return entries


def _parse_page_table_entry(line: str) -> Optional[tuple[str, str]]:
    stripped = line.strip()
    if not stripped.startswith("|") or stripped.count("|") < 3:
        return None

    cells = [_strip_backticks(cell.strip()) for cell in stripped.strip("|").split("|")]
    if len(cells) < 2:
        return None

    first_cell = cells[0].strip()
    second_cell = cells[1].strip()
    if not first_cell or not second_cell:
        return None

    first_lower = first_cell.lower()
    second_lower = second_cell.lower()
    if first_lower in {"page", "screen", "title", "name"} and second_lower in {
        "slug",
        "path",
        "route",
        "url",
    }:
        return None

    if all(re.fullmatch(r"[:\-\s`]+", cell or "") for cell in cells[:2]):
        return None

    if not (_is_path_like(second_cell) or _is_slug_like(second_cell)):
        return None

    slug_hint = _resolve_slug_hint(first_cell, second_cell)
    if not slug_hint:
        return None

    return first_cell, slug_hint


def _is_page_section_heading(title: str) -> bool:
    if not title:
        return False
    normalized = re.sub(r"\s+", " ", title.strip().lower())
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = re.sub(r"^[\d\s.:-]+", "", normalized).strip()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in _PAGE_SECTION_KEYWORDS)


def _resolve_slug_hint(title: str, raw_path: str) -> str:
    cleaned_title = _strip_backticks(title)
    cleaned_raw_path = _strip_backticks(raw_path)

    if _is_path_like(cleaned_raw_path):
        return cleaned_raw_path
    if _is_slug_like(cleaned_title) and _looks_like_page_identifier(cleaned_title):
        return cleaned_title
    if _is_slug_like(cleaned_raw_path) and _looks_like_page_identifier(cleaned_raw_path):
        return cleaned_raw_path
    if _is_path_like(cleaned_title):
        return cleaned_title
    return ""


def _is_slug_like(value: str) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    if not lowered or " " in lowered:
        return False
    if lowered.isdigit():
        return False
    return bool(re.fullmatch(r"[a-z0-9/_-]+", lowered))


def _is_path_like(value: str) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    if not lowered:
        return False
    if lowered in {"/", "index", "/index", "home", "/home"}:
        return True
    if lowered.startswith("/") and bool(re.fullmatch(r"/[a-z0-9/_-]+", lowered)):
        return True
    if "/" in lowered and bool(re.fullmatch(r"[a-z0-9/_-]+", lowered)):
        return True
    return False


def _strip_backticks(value: str) -> str:
    return value.strip().strip("`").strip()


def _is_page_slug_allowed(slug: str) -> bool:
    if not slug:
        return False
    if slug[0].isdigit():
        return False
    return slug not in _NON_PAGE_SLUGS


def is_valid_page_slug(slug: str) -> bool:
    normalized = _slugify(slug or "")
    if not _is_page_slug_allowed(normalized):
        return False

    if normalized in _KNOWN_SIMPLE_PAGE_SLUGS:
        return True

    has_page_keyword = any(keyword in normalized for keyword in _PAGE_KEYWORDS)
    has_component_hint = any(keyword in normalized for keyword in _COMPONENT_HINT_KEYWORDS)

    if has_component_hint and not has_page_keyword:
        return False

    if has_component_hint and has_page_keyword:
        if normalized.endswith("-page") or normalized.endswith("-tab"):
            return True
        if _is_compound_page_slug(normalized):
            return True
        return False

    return True


def _looks_like_page_identifier(value: str) -> bool:
    normalized = _slugify(value)
    if not normalized:
        return False
    if normalized in _KNOWN_SIMPLE_PAGE_SLUGS:
        return True

    has_page_keyword = any(keyword in normalized for keyword in _PAGE_KEYWORDS)
    if not has_page_keyword:
        return False

    has_component_hint = any(keyword in normalized for keyword in _COMPONENT_HINT_KEYWORDS)
    if not has_component_hint:
        return True

    if normalized.endswith("-page") or normalized.endswith("-tab"):
        return True
    return _is_compound_page_slug(normalized)


def _is_compound_page_slug(slug: str) -> bool:
    if "-" not in slug:
        return False
    prefix = slug.split("-", 1)[0]
    return prefix in {
        "home",
        "search",
        "favourite",
        "favorite",
        "profile",
        "about",
        "contact",
        "pricing",
        "product",
        "products",
        "service",
        "services",
        "blog",
        "faq",
        "cart",
        "checkout",
        "dashboard",
        "watch",
        "play",
        "video",
        "detail",
        "details",
    }


def _split_inline_list(value: str) -> List[str]:
    parts = re.split(r"[,\uFF0C]", value)
    return [part.strip() for part in parts if part.strip()]


def _truthy(value: str) -> bool:
    if not value:
        return False
    return value in {"yes", "true", "required", "\u2705", "\u662f", "\u9700\u8981", "\u5fc5\u987b"}


def _coerce_slug(raw_path: str, title: str, index: int) -> str:
    path = (raw_path or "").strip()
    normalized_path = path.lower()
    if normalized_path in {"/", "/index", "index", "home", "/home"}:
        return "index"
    if path.startswith("/"):
        path = path[1:]
    path = path.replace("/", "-").replace(":", "-")
    path = path.strip()
    slug = _slugify(path)
    if not slug:
        slug = _slug_from_title(title)
    if not slug:
        slug = f"page-{index + 1}"
    return slug


def _slug_from_title(title: str) -> str:
    if not title:
        return ""
    lower = title.lower()
    if "\u9996\u9875" in title or "\u4e3b\u9875" in title or "home" in lower:
        return "index"
    if "\u5173\u4e8e" in title or "about" in lower:
        return "about"
    if "\u8054\u7cfb" in title or "contact" in lower:
        return "contact"
    if "\u670d\u52a1" in title or "service" in lower:
        return "services"
    if "\u4ea7\u54c1" in title or "product" in lower:
        return "products"
    if "\u6848\u4f8b" in title or "case" in lower:
        return "cases"
    if "\u4ef7\u683c" in title or "pricing" in lower or "price" in lower:
        return "pricing"
    if "\u535a\u5ba2" in title or "blog" in lower:
        return "blog"
    if "\u56e2\u961f" in title or "team" in lower:
        return "team"
    if "\u529f\u80fd" in title or "feature" in lower:
        return "features"
    if "\u5e38\u89c1\u95ee\u9898" in title or "faq" in lower:
        return "faq"
    return _slugify(title)


def _slugify(text: str) -> str:
    value = text.strip().lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value)
    value = value.strip("-")
    return value[:40].rstrip("-")


def _dedupe_pages(pages: List[dict]) -> List[dict]:
    seen = set()
    deduped: List[dict] = []
    for page in pages:
        slug = page.get("slug")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        deduped.append(page)
    return deduped


def build_data_store_script(
    contract: dict,
    *,
    debounce_ms: int = 350,
    max_events: int = 200,
    max_records: int = 200,
) -> str:
    contract_json = json.dumps(contract or {}, ensure_ascii=True, separators=(",", ":"))
    template = """(function() {
  "use strict";

  var CONTRACT = __CONTRACT__;
  var DEFAULT_DEBOUNCE_MS = __DEBOUNCE_MS__;
  var MAX_EVENTS = __MAX_EVENTS__;
  var MAX_RECORDS = __MAX_RECORDS__;

  function hasLocalStorage() {
    try {
      return typeof localStorage !== "undefined";
    } catch (err) {
      return false;
    }
  }

  function safeParse(value, fallback) {
    if (!value) return fallback;
    try {
      var parsed = JSON.parse(value);
      return parsed == null ? fallback : parsed;
    } catch (err) {
      return fallback;
    }
  }

  function clone(value) {
    try {
      return JSON.parse(JSON.stringify(value));
    } catch (err) {
      return {};
    }
  }

  function isObject(value) {
    return value && typeof value === "object" && !Array.isArray(value);
  }

  function setByPath(target, path, value) {
    if (!isObject(target)) return;
    if (!path) return;
    var parts = Array.isArray(path) ? path : String(path).split(".");
    var cursor = target;
    for (var i = 0; i < parts.length; i += 1) {
      var key = parts[i];
      if (!key) continue;
      if (i === parts.length - 1) {
        cursor[key] = value;
        return;
      }
      if (!isObject(cursor[key])) {
        cursor[key] = {};
      }
      cursor = cursor[key];
    }
  }

  function getByPath(target, path) {
    if (!isObject(target) || !path) return undefined;
    var parts = Array.isArray(path) ? path : String(path).split(".");
    var cursor = target;
    for (var i = 0; i < parts.length; i += 1) {
      var key = parts[i];
      if (!key) continue;
      if (cursor == null || typeof cursor !== "object") return undefined;
      cursor = cursor[key];
    }
    return cursor;
  }

  function pathExists(target, path) {
    return typeof getByPath(target, path) !== "undefined";
  }

  function normalizeKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  }

  function buildStateKeyIndex(schema) {
    var index = {};
    if (!schema || typeof schema !== "object") return index;
    var keys = Object.keys(schema);
    for (var i = 0; i < keys.length; i += 1) {
      var key = String(keys[i]);
      index[normalizeKey(key)] = key;
    }
    return index;
  }

  var ENTITY_STATE_PATH_HINTS = {
    cartitem: "cart.items",
    cart: "cart.items",
    order: "orders",
    booking: "booking.draft",
    form: "forms.submissions",
    formsubmission: "forms.submissions",
    user: "user.profile",
    product: "products",
    category: "categories",
    trip: "trip.current",
    dayplan: "day_plans",
    activity: "activities",
    location: "locations",
    bookmark: "bookmarks",
    manual: "manual.current",
    section: "sections",
    page: "pages",
    board: "board.current",
    column: "columns",
    task: "tasks",
    tag: "tags",
    widget: "widgets",
    insight: "insights",
    filter: "filters"
  };

  function resolveStatePathForEntity(entityName) {
    var schema = CONTRACT.schema || {};
    var normalized = normalizeKey(entityName);

    var singular = normalized;
    var plural = normalized;
    if (normalized.endsWith("s") && normalized.length > 1) {
      singular = normalized.slice(0, -1);
    } else {
      plural = normalized + "s";
    }

    var explicitMap = CONTRACT.entity_state_map;
    if (explicitMap && typeof explicitMap === "object") {
      var explicitKeys = Object.keys(explicitMap);
      for (var mapIndex = 0; mapIndex < explicitKeys.length; mapIndex += 1) {
        var mapKey = explicitKeys[mapIndex];
        var normalizedMapKey = normalizeKey(mapKey);
        if (
          normalizedMapKey === normalized ||
          normalizedMapKey === singular ||
          normalizedMapKey === plural
        ) {
          var mappedPath = explicitMap[mapKey];
          if (mappedPath) {
            return String(mappedPath);
          }
        }
      }
    }

    var index = buildStateKeyIndex(schema);

    if (index[normalized]) {
      return index[normalized];
    }
    if (index[singular]) {
      return index[singular];
    }
    if (index[plural]) {
      return index[plural];
    }

    var hinted = ENTITY_STATE_PATH_HINTS[normalized] || ENTITY_STATE_PATH_HINTS[singular];
    if (hinted && pathExists(schema, hinted.split(".")[0])) {
      return hinted;
    }
    if (hinted) {
      return hinted;
    }

    if (index[normalized + "list"]) {
      return index[normalized + "list"];
    }

    return singular ? singular + "s" : "records";
  }

  function applyEntityRecordsToState(state, statePath, entityName, records) {
    var normalizedRecords = Array.isArray(records) ? records : [];
    var current = getByPath(state, statePath);

    if (Array.isArray(current)) {
      setByPath(state, statePath, normalizedRecords);
      return;
    }

    if (isObject(current)) {
      var next = clone(current);
      if (Array.isArray(next.items)) {
        next.items = normalizedRecords;
        setByPath(state, statePath, next);
        return;
      }
      if (isObject(next.current)) {
        next.current = normalizedRecords[0] || {};
        setByPath(state, statePath, next);
        return;
      }
      if (isObject(next.profile)) {
        next.profile = normalizedRecords[0] || {};
        setByPath(state, statePath, next);
        return;
      }
      if (isObject(next.draft)) {
        next.draft = normalizedRecords[0] || {};
        setByPath(state, statePath, next);
        return;
      }
      if (Array.isArray(next.records)) {
        next.records = normalizedRecords;
        setByPath(state, statePath, next);
        return;
      }
      next.records = normalizedRecords;
      setByPath(state, statePath, next);
      return;
    }

    var lastKey = String(statePath || "").split(".").pop() || "";
    var treatAsList = normalizeKey(lastKey).endsWith("s") || normalizedRecords.length > 1;
    if (treatAsList) {
      setByPath(state, statePath, normalizedRecords);
    } else {
      setByPath(state, statePath, normalizedRecords[0] || {});
    }
  }

  function mapProductTypeToScene(value) {
    var type = String(value || "").toLowerCase();
    if (type === "ecommerce") return "ecommerce";
    if (type === "booking" || type === "travel") return "travel";
    if (type === "manual" || type === "documentation" || type === "docs") return "manual";
    if (type === "dashboard" || type === "kanban") return "kanban";
    if (type === "landing" || type === "card" || type === "invitation") return "landing";
    return "";
  }

  function resolvePage() {
    if (typeof window === "undefined" || !window.location) return "index";
    var path = window.location.pathname || "";
    var parts = path.split("/").filter(Boolean);
    if (!parts.length) return "index";
    var slug = parts[parts.length - 1];
    return slug.replace(/\.html?$/i, "") || "index";
  }

  function normalizeType(value) {
    if (!value) return "event";
    return String(value)
      .trim()
      .replace(/([a-z])([A-Z])/g, "$1_$2")
      .replace(/[\s-]+/g, "_")
      .toLowerCase();
  }

  function buildEvent(type, payload) {
    var normalized = normalizeType(type);
    return {
      id: "evt_" + String(Date.now()) + "_" + String(Math.floor(Math.random() * 10000)),
      name: String(type || normalized),
      type: normalized,
      payload: payload,
      data: payload,
      timestamp: new Date().toISOString(),
      timestamp_ms: Date.now(),
      page: resolvePage(),
      scene: mapProductTypeToScene(CONTRACT.product_type)
    };
  }

  function cloneDefaultState() {
    return clone(CONTRACT.schema || {});
  }

  function mergeState(current, path, value) {
    var next = isObject(current) ? clone(current) : cloneDefaultState();
    setByPath(next, path, value);
    return next;
  }

  function normalizeEntityMap() {
    var entities = {};
    var dataModel = CONTRACT.data_model;
    if (!dataModel || !isObject(dataModel.entities)) return entities;
    var keys = Object.keys(dataModel.entities || {});
    for (var i = 0; i < keys.length; i += 1) {
      var entityName = String(keys[i]);
      entities[entityName.toLowerCase()] = entityName;
    }
    return entities;
  }

  function defaultEntityFromType(type) {
    var mapping = {
      add_to_cart: "Cart",
      remove_item: "Cart",
      update_qty: "Cart",
      clear_cart: "Cart",
      submit_order: "Order",
      submit_booking: "Booking",
      submit_form: "Form",
      checkout_draft: "Form"
    };
    return mapping[normalizeType(type)] || "Record";
  }

  function normalizeEntity(type) {
    var map = normalizeEntityMap();
    var candidate = defaultEntityFromType(type);
    var key = candidate.toLowerCase();
    return map[key] || candidate;
  }

  function buildApiPath(path) {
    var base = String(CONTRACT.api_base_url || "").trim();
    var normalizedPath = path.charAt(0) === "/" ? path : "/" + path;
    if (base) {
      return base.replace(/\/$/, "") + normalizedPath;
    }
    return normalizedPath;
  }

  function canUseApi() {
    return !!(CONTRACT.session_id && typeof fetch === "function");
  }

  function postMessageUpdate(payload) {
    if (typeof window !== "undefined" && window.parent && window.parent.postMessage) {
      window.parent.postMessage(payload, "*");
    }
  }

  function InstantCoffeeDataStore(contract) {
    this.contract = contract || {};
    this.stateKey = this.contract.shared_state_key || "instant-coffee:state";
    this.recordsKey = this.contract.records_key || "instant-coffee:records";
    this.eventsKey = this.contract.events_key || "instant-coffee:events";
    this.previewDebounceMs = DEFAULT_DEBOUNCE_MS;
    this._previewTimer = null;
    this._pendingPreview = null;
    this._storageAvailable = hasLocalStorage();
    this.state = this.loadState();
    this.records = this.loadRecords();
    this.events = this.loadEvents();
    this.listeners = [];
    this._apiEnabled = canUseApi();
  }

  InstantCoffeeDataStore.prototype.loadState = function() {
    if (!this._storageAvailable) {
      return cloneDefaultState();
    }
    try {
      var value = localStorage.getItem(this.stateKey);
      return safeParse(value, cloneDefaultState());
    } catch (err) {
      return cloneDefaultState();
    }
  };

  InstantCoffeeDataStore.prototype.loadRecords = function() {
    if (!this._storageAvailable) {
      return [];
    }
    try {
      var value = localStorage.getItem(this.recordsKey);
      var parsed = safeParse(value, []);
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      return [];
    }
  };

  InstantCoffeeDataStore.prototype.loadEvents = function() {
    if (!this._storageAvailable) {
      return [];
    }
    try {
      var value = localStorage.getItem(this.eventsKey);
      var parsed = safeParse(value, []);
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      return [];
    }
  };

  InstantCoffeeDataStore.prototype.get_state = function() {
    return clone(this.state || cloneDefaultState());
  };

  InstantCoffeeDataStore.prototype.getState = function() {
    return this.get_state();
  };

  InstantCoffeeDataStore.prototype.getRecords = function() {
    return this.records;
  };

  InstantCoffeeDataStore.prototype.getEvents = function() {
    return this.events;
  };

  InstantCoffeeDataStore.prototype.set_state = function(path, value) {
    this.state = mergeState(this.state, path, value);
    this.persistState();
    this.logEvent("state_update", { path: path });
    this.notifyPreview(false);
  };

  InstantCoffeeDataStore.prototype.setState = function(path, value) {
    return this.set_state(path, value);
  };

  InstantCoffeeDataStore.prototype.persistState = function() {
    if (!this._storageAvailable) return;
    try {
      localStorage.setItem(this.stateKey, JSON.stringify(this.state));
    } catch (err) {
    }
  };

  InstantCoffeeDataStore.prototype.persistRecords = function() {
    if (!this._storageAvailable) return;
    try {
      localStorage.setItem(this.recordsKey, JSON.stringify(this.records));
    } catch (err) {
    }
  };

  InstantCoffeeDataStore.prototype.persistEvents = function() {
    if (!this._storageAvailable) return;
    try {
      localStorage.setItem(this.eventsKey, JSON.stringify(this.events));
    } catch (err) {
    }
  };

  InstantCoffeeDataStore.prototype.addRecord = function(type, payload) {
    var record = {
      type: type,
      payload: payload,
      created_at: new Date().toISOString()
    };
    this.records.push(record);
    if (this.records.length > MAX_RECORDS) {
      this.records = this.records.slice(this.records.length - MAX_RECORDS);
    }
    this.persistRecords();

    var self = this;
    if (this._apiEnabled) {
      var table = normalizeEntity(type);
      var sessionId = this.contract.session_id;
      var path = buildApiPath("/api/sessions/" + encodeURIComponent(sessionId) + "/data/" + encodeURIComponent(table));
      fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {})
      }).then(function(response) {
        if (!response || !response.ok) return null;
        return response.json().catch(function() { return null; });
      }).then(function(body) {
        if (body && body.record) {
          record.server_record = body.record;
          self.records[self.records.length - 1] = record;
          self.persistRecords();
          self.notifyPreview(true);
        }
      }).catch(function() {
      });
    }

    this.logEvent("record_added", { type: type }, true);
    return record;
  };

  InstantCoffeeDataStore.prototype.add_record = function(type, payload) {
    return this.addRecord(type, payload);
  };

  InstantCoffeeDataStore.prototype.logEvent = function(name, data, immediate) {
    var event = buildEvent(name, data);
    this.events.push(event);
    if (this.events.length > MAX_EVENTS) {
      this.events = this.events.slice(this.events.length - MAX_EVENTS);
    }
    this.persistEvents();
    var shouldImmediate = !!immediate || event.type.indexOf("submit") !== -1 || event.type.indexOf("checkout") !== -1;
    this.notifyPreview(shouldImmediate);
    return event;
  };

  InstantCoffeeDataStore.prototype.log_event = function(name, data, immediate) {
    return this.logEvent(name, data, immediate);
  };

  InstantCoffeeDataStore.prototype._notifyListeners = function() {
    if (!this.listeners || !this.listeners.length) return;
    var snapshot = this.getState ? this.getState() : this.state;
    for (var i = 0; i < this.listeners.length; i += 1) {
      var listener = this.listeners[i];
      if (typeof listener === "function") {
        try {
          listener(snapshot);
        } catch (err) {
        }
      }
    }
  };

  InstantCoffeeDataStore.prototype.subscribe = function(listener) {
    if (typeof listener !== "function") {
      return function() {};
    }
    this.listeners.push(listener);
    var self = this;
    return function() {
      self.listeners = self.listeners.filter(function(fn) {
        return fn !== listener;
      });
    };
  };

  InstantCoffeeDataStore.prototype.notifyPreview = function(immediate) {
    var self = this;
    var payload = {
      type: "instant-coffee:update",
      state: this.state || {},
      events: this.events || [],
      records: this.records || [],
      timestamp: Date.now()
    };
    var send = function(nextPayload) {
      postMessageUpdate(nextPayload);
      self._notifyListeners();
    };
    if (immediate) {
      if (this._previewTimer) {
        clearTimeout(this._previewTimer);
        this._previewTimer = null;
      }
      this._pendingPreview = null;
      send(payload);
      return;
    }
    this._pendingPreview = payload;
    if (this._previewTimer) {
      return;
    }
    this._previewTimer = setTimeout(function() {
      self._previewTimer = null;
      if (!self._pendingPreview) return;
      var next = self._pendingPreview;
      self._pendingPreview = null;
      send(next);
    }, this.previewDebounceMs);
  };

  InstantCoffeeDataStore.prototype.refresh = function() {
    var self = this;
    if (this._apiEnabled && CONTRACT.session_id) {
      var tablePath = buildApiPath("/api/sessions/" + encodeURIComponent(CONTRACT.session_id) + "/data/tables");
      fetch(tablePath, { method: "GET" })
        .then(function(response) {
          if (!response || !response.ok) return null;
          return response.json();
        })
        .then(function(body) {
          if (!body || !Array.isArray(body.tables)) return null;
          return body.tables;
        })
        .then(function(tables) {
          if (!tables || !tables.length) return null;
          var requests = [];
          for (var i = 0; i < tables.length; i += 1) {
            var table = tables[i];
            if (!table || !table.name) continue;
            (function(tableName) {
              var url = buildApiPath(
                "/api/sessions/" + encodeURIComponent(CONTRACT.session_id) + "/data/" + encodeURIComponent(tableName) + "?limit=200&offset=0"
              );
              requests.push(
                fetch(url, { method: "GET" })
                  .then(function(resp) {
                    if (!resp || !resp.ok) return null;
                    return resp.json();
                  })
                  .then(function(payload) {
                    if (!payload || !Array.isArray(payload.records)) return null;
                    return {
                      table: tableName,
                      records: payload.records
                    };
                  })
              );
            })(String(table.name));
          }
          if (!requests.length) return null;
          return Promise.all(requests);
        })
        .then(function(results) {
          if (!results || !results.length) return;

          var nextState = clone(self.state || cloneDefaultState());
          var merged = [];
          var syncedTables = 0;

          for (var i = 0; i < results.length; i += 1) {
            var result = results[i];
            if (!result || !Array.isArray(result.records)) continue;
            syncedTables += 1;

            var tableName = String(result.table || "");
            var records = result.records;
            var statePath = resolveStatePathForEntity(tableName);
            applyEntityRecordsToState(nextState, statePath, tableName, records);

            for (var j = 0; j < records.length; j += 1) {
              merged.push(records[j]);
            }
          }

          if (!syncedTables) return;

          self.state = nextState;
          self.records = merged.slice(0, MAX_RECORDS);
          self.persistState();
          self.persistRecords();
          self.notifyPreview(true);
        })
        .catch(function() {
        });
    }

    this.state = this.loadState();
    this.records = this.loadRecords();
    this.events = this.loadEvents();
    this._notifyListeners();
  };

  if (typeof window !== "undefined") {
    var resolvedContract = window.__instantCoffeeContract || CONTRACT;
    if (!window.__instantCoffeeContract) {
      window.__instantCoffeeContract = resolvedContract;
    }
    if (!window.InstantCoffeeStateContract) {
      window.InstantCoffeeStateContract = resolvedContract;
    }
    var store = window.__instantCoffeeStore || window.InstantCoffeeDataStore;
    if (!store) {
      store = new InstantCoffeeDataStore(resolvedContract);
    }
    window.__instantCoffeeStore = store;
    if (!window.InstantCoffeeDataStore) {
      window.InstantCoffeeDataStore = store;
    }
    if (typeof store.refresh === "function") {
      store.refresh();
    }
  }
})();"""
    return (
        template.replace("__CONTRACT__", contract_json)
        .replace("__DEBOUNCE_MS__", str(int(debounce_ms)))
        .replace("__MAX_EVENTS__", str(int(max_events)))
        .replace("__MAX_RECORDS__", str(int(max_records)))
    )

def build_data_client_script(product_type: str, contract: dict) -> str:
    normalized_type = str(product_type or "").strip().lower()
    contract_json = json.dumps(contract or {}, ensure_ascii=True, separators=(",", ":"))
    template = """(function() {
  "use strict";

  if (typeof window === "undefined") {
    return;
  }

  var PRODUCT_TYPE = "__PRODUCT_TYPE__";
  var CONTRACT = __CONTRACT__;
  if (!window.__instantCoffeeProductType) {
    window.__instantCoffeeProductType = PRODUCT_TYPE;
  }
  var store = window.__instantCoffeeStore || window.InstantCoffeeDataStore;
  if (!store) {
    if (typeof console !== "undefined" && console.error) {
      console.error("Data store not initialized");
    }
    return;
  }

  function isObject(value) {
    return value && typeof value === "object" && !Array.isArray(value);
  }

  function ensureArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function ensureObject(value) {
    return isObject(value) ? value : {};
  }

  function readState() {
    if (typeof store.get_state === "function") return store.get_state();
    if (typeof store.getState === "function") return store.getState();
    return {};
  }

  function writeState(path, value) {
    if (typeof store.set_state === "function") return store.set_state(path, value);
    if (typeof store.setState === "function") return store.setState(path, value);
  }

  function logEvent(name, data, immediate) {
    if (typeof store.logEvent === "function") return store.logEvent(name, data, immediate);
    if (typeof store.log_event === "function") return store.log_event(name, data, immediate);
  }

  function addRecord(type, payload) {
    if (typeof store.addRecord === "function") return store.addRecord(type, payload);
    if (typeof store.add_record === "function") return store.add_record(type, payload);
  }

  function subscribe(listener) {
    if (typeof store.subscribe === "function") return store.subscribe(listener);
    return function() {};
  }

  function getContractDataModel() {
    var model = CONTRACT && CONTRACT.data_model;
    return model && typeof model === "object" ? model : null;
  }

  function normalizeEntityMap() {
    var entities = {};
    var model = getContractDataModel();
    if (!model || !model.entities || typeof model.entities !== "object") return entities;
    var keys = Object.keys(model.entities);
    for (var i = 0; i < keys.length; i += 1) {
      entities[String(keys[i]).toLowerCase()] = String(keys[i]);
    }
    return entities;
  }

  function firstMatchingEntity(candidates) {
    var map = normalizeEntityMap();
    for (var i = 0; i < candidates.length; i += 1) {
      var key = String(candidates[i] || "").toLowerCase();
      if (map[key]) return map[key];
    }
    return null;
  }

  function resolveEntityName(kind, fallback) {
    var map = normalizeEntityMap();
    var normalized = String(kind || "").toLowerCase();
    if (map[normalized]) return map[normalized];
    return firstMatchingEntity([kind, fallback]) || fallback;
  }

  function computeTotals(items, currency, existingTotals) {
    var totals = ensureObject(existingTotals);
    var subtotal = 0;
    for (var i = 0; i < items.length; i += 1) {
      var item = items[i] || {};
      var price = Number(item.price || 0);
      var qty = Number(item.qty || item.quantity || 1);
      if (isNaN(price) || isNaN(qty)) continue;
      subtotal += price * qty;
    }
    totals.subtotal = Number(subtotal.toFixed(2));
    totals.tax = Number((totals.tax || 0).toFixed(2));
    totals.total = Number((totals.subtotal + totals.tax).toFixed(2));
    totals.currency = currency || totals.currency || "USD";
    return totals;
  }

  function addToCart(item, qtyOverride) {
    var state = readState();
    var cart = ensureObject(state.cart);
    var items = ensureArray(cart.items);
    var next = ensureObject(item);
    var qty = Number(qtyOverride || next.qty || next.quantity || 1);
    if (!qty || isNaN(qty)) qty = 1;
    var matched = false;
    for (var i = 0; i < items.length; i += 1) {
      var existing = items[i];
      if (!existing) continue;
      if (existing.id === next.id || existing.sku === next.sku) {
        var existingQty = Number(existing.qty || existing.quantity || 0);
        existing.qty = existingQty + qty;
        matched = true;
        break;
      }
    }
    if (!matched) {
      next.qty = qty;
      items.push(next);
    }
    var totals = computeTotals(items, cart.currency, cart.totals);
    writeState("cart", {
      items: items,
      totals: totals,
      currency: totals.currency
    });
    logEvent("add_to_cart", { item: next, qty: qty });

    var cartEntity = resolveEntityName("CartItem", "Cart");
    addRecord(cartEntity, { item: next, qty: qty, totals: totals });

    return items;
  }

  function updateCartTotals(items, cart) {
    var totals = computeTotals(items, cart.currency, cart.totals);
    writeState("cart", {
      items: items,
      totals: totals,
      currency: totals.currency
    });
  }

  var formApi = {
    saveDraft: function(formId, payload) {
      var state = readState();
      var forms = ensureObject(state.forms);
      var draft = ensureObject(forms.draft);
      var key = formId ? String(formId) : "default";
      draft[key] = Object.assign({}, ensureObject(draft[key]), ensureObject(payload));
      forms.draft = draft;
      writeState("forms", forms);
      logEvent("checkout_draft", { form_id: formId, payload: draft[key] });
    },
    submit: function(formId, payload) {
      var state = readState();
      var forms = ensureObject(state.forms);
      var draft = ensureObject(forms.draft);
      var key = formId ? String(formId) : "default";
      var submission = Object.assign({}, ensureObject(draft[key]), ensureObject(payload));
      var formEntity = resolveEntityName("FormSubmission", "Form");
      addRecord(formEntity, { form_id: formId, payload: submission });
      logEvent("submit_form", { form_id: formId, payload: submission }, true);
      if (draft[key]) {
        delete draft[key];
      }
      forms.draft = draft;
      writeState("forms", forms);
      return submission;
    }
  };
  formApi.updateDraft = formApi.saveDraft;

  var cartApi = {
    add: function(item, qty) {
      return addToCart(item, qty);
    },
    addItem: function(item, qty) {
      return addToCart(item, qty);
    },
    update: function(id, updates) {
      var state = readState();
      var cart = ensureObject(state.cart);
      var items = ensureArray(cart.items);
      var found = false;
      for (var i = 0; i < items.length; i += 1) {
        var item = items[i];
        if (!item) continue;
        if (item.id === id || item.sku === id) {
          items[i] = Object.assign({}, item, ensureObject(updates));
          found = true;
          break;
        }
      }
      if (!found) return items;
      updateCartTotals(items, cart);
      logEvent("update_qty", { id: id, updates: updates });
      return items;
    },
    updateQty: function(id, qty) {
      var state = readState();
      var cart = ensureObject(state.cart);
      var items = ensureArray(cart.items);
      var nextQty = Number(qty);
      if (isNaN(nextQty)) return items;
      var updatedItems = [];
      for (var i = 0; i < items.length; i += 1) {
        var item = items[i];
        if (!item) continue;
        if (item.id === id || item.sku === id) {
          if (nextQty > 0) {
            item.qty = nextQty;
            updatedItems.push(item);
            logEvent("update_qty", { id: id, qty: nextQty });
          } else {
            logEvent("remove_item", { id: id });
          }
        } else {
          updatedItems.push(item);
        }
      }
      updateCartTotals(updatedItems, cart);
      return updatedItems;
    },
    remove: function(id) {
      var state = readState();
      var cart = ensureObject(state.cart);
      var items = ensureArray(cart.items).filter(function(item) {
        return item && item.id !== id && item.sku !== id;
      });
      updateCartTotals(items, cart);
      logEvent("remove_item", { id: id });
      return items;
    },
    removeItem: function(id) {
      return this.remove(id);
    },
    clear: function() {
      writeState("cart", {
        items: [],
        totals: { subtotal: 0, tax: 0, total: 0 },
        currency: "USD"
      });
      logEvent("clear_cart", {});
    },
    saveDraft: function(payload) {
      formApi.saveDraft("checkout", payload);
    },
    updateDraft: function(payload) {
      formApi.saveDraft("checkout", payload);
    },
    submit: function(payload) {
      var state = readState();
      var cart = ensureObject(state.cart);
      var order = Object.assign(
        {
          items: ensureArray(cart.items),
          totals: ensureObject(cart.totals),
          currency: cart.currency || "USD"
        },
        ensureObject(payload)
      );
      var orderEntity = resolveEntityName("Order", "Order");
      addRecord(orderEntity, order);
      logEvent("submit_order", { payload: order }, true);
      this.clear();
      return order;
    },
    submitOrder: function(payload) {
      return this.submit(payload);
    }
  };

  var bookingApi = {
    saveDraft: function(payload) {
      var state = readState();
      var booking = ensureObject(state.booking);
      var draft = ensureObject(booking.draft);
      booking.draft = Object.assign({}, draft, ensureObject(payload));
      writeState("booking", booking);
      logEvent("checkout_draft", { payload: booking.draft });
    },
    submit: function(payload) {
      var state = readState();
      var booking = ensureObject(state.booking);
      var draft = ensureObject(booking.draft);
      var submission = Object.assign({}, draft, ensureObject(payload));
      var bookingEntity = resolveEntityName("Booking", "Booking");
      addRecord(bookingEntity, submission);
      logEvent("submit_booking", { payload: submission }, true);
      booking.draft = {};
      writeState("booking", booking);
      return submission;
    }
  };
  bookingApi.updateDraft = bookingApi.saveDraft;

  var api = {
    productType: PRODUCT_TYPE,
    contract: CONTRACT,
    getState: readState,
    setState: writeState,
    subscribe: subscribe
  };

  if (PRODUCT_TYPE === "ecommerce") {
    api.cart = cartApi;
  }

  if (PRODUCT_TYPE === "booking") {
    api.booking = bookingApi;
  }

  api.forms = formApi;

  window.InstantCoffeeDataClient = api;
  var legacy = window.IC && typeof window.IC === "object" ? window.IC : {};
  if (api.cart) legacy.cart = cartApi;
  if (api.booking) legacy.booking = bookingApi;
  legacy.forms = formApi;
  legacy.getState = readState;
  legacy.subscribe = subscribe;
  window.IC = legacy;
})();"""
    return (
        template.replace("__PRODUCT_TYPE__", normalized_type)
        .replace("__CONTRACT__", contract_json)
    )

def inject_data_scripts(
    html: str,
    *,
    store_src: str,
    client_src: Optional[str] = None,
    contract: Optional[dict] = None,
    product_type: Optional[str] = None,
) -> str:
    if not html:
        return html
    scripts: List[str] = []
    if contract is not None and "__instantCoffeeContract" not in html:
        contract_json = json.dumps(contract, ensure_ascii=True, separators=(",", ":"))
        contract_json = contract_json.replace("</", "<\\/")
        scripts.append(f"<script>window.__instantCoffeeContract={contract_json};</script>")
    if product_type and "__instantCoffeeProductType" not in html:
        normalized = str(product_type or "").strip().lower()
        normalized = normalized.replace("</", "<\\/")
        scripts.append(f"<script>window.__instantCoffeeProductType=\"{normalized}\";</script>")
    if store_src and store_src not in html:
        scripts.append(f"<script src=\"{store_src}\"></script>")
    if client_src and client_src not in html:
        scripts.append(f"<script src=\"{client_src}\"></script>")
    if not scripts:
        return html
    block = "".join(scripts)

    head_close = re.search(r"</head>", html, re.IGNORECASE)
    if head_close:
        insert_at = head_close.start()
        return f"{html[:insert_at]}{block}{html[insert_at:]}"

    head_open = re.search(r"<head[^>]*>", html, re.IGNORECASE)
    if head_open:
        insert_at = head_open.end()
        return f"{html[:insert_at]}{block}{html[insert_at:]}"

    html_open = re.search(r"<html[^>]*>", html, re.IGNORECASE)
    if html_open:
        insert_at = html_open.end()
        return f"{html[:insert_at]}<head>{block}</head>{html[insert_at:]}"

    return f"{block}{html}"
