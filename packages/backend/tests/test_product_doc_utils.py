from app.utils.product_doc import extract_pages_from_markdown, is_valid_page_slug


def test_extract_pages_from_markdown_ignores_non_page_sections():
    content = """
## 3. Page Structure

### index (Home Tab)
### search (Search Tab)
### favourite (Favourite Tab)
### profile (Profile Tab)
### play (Video Player)

## 9. Constraints & Rules

### Hard Rules (Must Follow)
### Soft Rules (Recommended)

## 11. Future Considerations (Nice-to-Have)
"""

    pages = extract_pages_from_markdown(content)
    slugs = [page["slug"] for page in pages]

    assert slugs == ["index", "search", "favourite", "profile", "play"]
    assert "must-follow" not in slugs
    assert "recommended" not in slugs
    assert "nice-to-have" not in slugs


def test_extract_pages_from_markdown_supports_bullet_route_list():
    content = """
## Pages

- Home (/)
- Search (/search)
- Favourite (/favourite)
- Profile (/profile)
- Video Player (/play)
- Future Considerations (Nice-to-Have)
"""

    pages = extract_pages_from_markdown(content)
    slugs = [page["slug"] for page in pages]

    assert slugs == ["index", "search", "favourite", "profile", "play"]


def test_extract_pages_from_markdown_ignores_component_like_headings():
    content = """
## Page Structure

### Home (index)
### AppHeader (appheader)
### CategoryRow (categoryrow)
### Search (search)
### Video Player (videoplayer)
"""

    pages = extract_pages_from_markdown(content)
    slugs = [page["slug"] for page in pages]

    assert slugs == ["index", "search", "videoplayer"]


def test_is_valid_page_slug_filters_non_page_labels():
    assert is_valid_page_slug("index")
    assert is_valid_page_slug("search")
    assert not is_valid_page_slug("must-follow")
    assert not is_valid_page_slug("recommended")
    assert not is_valid_page_slug("nice-to-have")


def test_extract_pages_from_markdown_supports_page_structure_table():
    content = """
## Page Structure

| Page | Slug | Role | Description |
|------|------|------|-------------|
| Home | `index` | landing | Main browsing with category rows |
| Search | `search` | search | Find shows by keyword |
| Favorites | `favorites` | collection | Saved shows list |
| Profile | `profile` | settings | User account management |
| Video Player | `player` | detail | Watch show with controls |

## Data Flow

[index] --(tap show cover)--> [player]
[search] --(tap show cover)--> [player]
"""

    pages = extract_pages_from_markdown(content)
    slugs = [page["slug"] for page in pages]

    assert slugs == ["index", "search", "favorites", "profile", "player"]
