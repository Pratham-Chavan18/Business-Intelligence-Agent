import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the same directory as this file
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

MONDAY_URL = "https://api.monday.com/v2"
MAX_RETRIES = 3
RETRY_DELAY = 2


def _get_api_key() -> str:
    """Get the Monday API key, reading fresh from env."""
    key = os.getenv("MONDAY_API_KEY", "")
    if not key:
        raise ConnectionError("MONDAY_API_KEY environment variable is not set.")
    return key


def _get_headers() -> dict:
    return {
        "Authorization": _get_api_key(),
        "Content-Type": "application/json",
    }


def _execute_query(query: str, variables: dict = None, retries: int = MAX_RETRIES) -> dict:
    """Execute a Monday.com GraphQL query with retry logic."""
    headers = _get_headers()
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    last_error = None
    for attempt in range(retries):
        try:
            response = requests.post(
                MONDAY_URL, json=payload, headers=headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                error_msg = "; ".join(
                    e.get("message", str(e)) for e in data["errors"]
                )
                if "rate limit" in error_msg.lower() or "complexity" in error_msg.lower():
                    if attempt < retries - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                raise Exception(f"Monday.com API error: {error_msg}")

            return data

        except requests.exceptions.Timeout:
            last_error = "Request timed out"
        except requests.exceptions.ConnectionError:
            last_error = "Connection failed"
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                time.sleep(RETRY_DELAY * (attempt + 1))
                last_error = "Rate limited"
                continue
            raise

        if attempt < retries - 1:
            time.sleep(RETRY_DELAY * (attempt + 1))

    raise ConnectionError(
        f"Monday.com API failed after {retries} attempts: {last_error}"
    )


def health_check() -> dict:
    """Check if the Monday.com connection is healthy."""
    try:
        result = get_boards()
        boards = result.get("data", {}).get("boards", [])
        return {"status": "connected", "boards_found": len(boards)}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


def get_boards() -> dict:
    """Fetch all boards from Monday.com."""
    query = """
    query {
        boards(limit: 50) {
            id
            name
            board_kind
            columns {
                id
                title
                type
            }
        }
    }
    """
    return _execute_query(query)


def find_board_by_name(name: str):
    """Find a board by its name (case-insensitive partial match)."""
    result = get_boards()
    boards = result.get("data", {}).get("boards", [])
    name_lower = name.lower()

    for board in boards:
        if name_lower in board["name"].lower():
            return board

    return None


def get_board_columns(board_id) -> list:
    """Fetch column metadata for a board."""
    query = f"""
    query {{
        boards(ids: {board_id}) {{
            columns {{
                id
                title
                type
                settings_str
            }}
        }}
    }}
    """
    result = _execute_query(query)
    try:
        return result["data"]["boards"][0]["columns"]
    except (KeyError, IndexError):
        return []


def get_board_items(board_id, limit: int = 500) -> dict:
    """Fetch all items from a board with pagination support."""
    all_items: list = []
    cursor = None

    # First page
    query = f"""
    query {{
        boards(ids: {board_id}) {{
            id
            name
            columns {{
                id
                title
                type
            }}
            items_page(limit: {limit}) {{
                cursor
                items {{
                    id
                    name
                    group {{
                        id
                        title
                    }}
                    column_values {{
                        id
                        text
                        value
                        type
                    }}
                }}
            }}
        }}
    }}
    """

    result = _execute_query(query)

    try:
        board_data = result["data"]["boards"][0]
        page_data = board_data["items_page"]
        all_items.extend(page_data["items"])
        cursor = page_data.get("cursor")
        columns = board_data.get("columns", [])
    except (KeyError, IndexError):
        return result

    # Paginate through remaining items
    while cursor:
        next_query = f"""
        query {{
            next_items_page(limit: {limit}, cursor: "{cursor}") {{
                cursor
                items {{
                    id
                    name
                    group {{
                        id
                        title
                    }}
                    column_values {{
                        id
                        text
                        value
                        type
                    }}
                }}
            }}
        }}
        """
        next_result = _execute_query(next_query)
        try:
            next_page = next_result["data"]["next_items_page"]
            all_items.extend(next_page["items"])
            cursor = next_page.get("cursor")
        except (KeyError, IndexError):
            break

    # Reconstruct the response format
    return {
        "data": {
            "boards": [{
                "id": board_data["id"],
                "name": board_data["name"],
                "columns": columns,
                "items_page": {
                    "items": all_items
                }
            }]
        }
    }
