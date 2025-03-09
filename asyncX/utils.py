# asyncX/utils.py

import orjson  # Faster JSON serialization

def build_params(params: dict) -> dict:
    """
    Encodes query parameters using `orjson` for fast serialization.
    Each parameter must be individually JSON-encoded.
    """
    return {k: orjson.dumps(v).decode() for k, v in params.items()}

def find_rest_ids(data: dict) -> list:
    """
    Recursively searches a dictionary for unique 'rest_id' values.
    
    @param data: Dictionary to search
    @return: List of unique rest_id values
    """
    results = set()

    def search_dict(d):
        if isinstance(d, dict):
            for key, value in d.items():
                if key == "rest_id" and isinstance(value, str):
                    results.add(value)
                else:
                    search_dict(value)
        elif isinstance(d, list):
            for item in d:
                search_dict(item)

    search_dict(data)
    return list(results)

def find_key(data: dict | list, target_key: str):
    """
    Recursively searches a dictionary for all occurrences of a specific key.
    
    @param data: Dictionary or list to search
    @param target_key: Key to find
    @return: List of values found for the target key
    """
    results = []

    def search_dict(d):
        if isinstance(d, dict):
            for key, value in d.items():
                if key == target_key:
                    results.append(value)
                else:
                    search_dict(value)
        elif isinstance(d, list):
            for item in d:
                search_dict(item)

    search_dict(data)
    return results

def get_cursor(data: dict | list) -> str:
    """
    Extracts the cursor from paginated Twitter GraphQL responses.
    
    @param data: API response data
    @return: Cursor string or None if no cursor found
    """
    entries = find_key(data, "entries")
    if entries:
        for entry in entries.pop():
            entry_id = entry.get("entryId", "")
            if ("cursor-bottom" in entry_id) or ("cursor-showmorethreads" in entry_id):
                content = entry["content"]
                if item_content := content.get("itemContent"):
                    return item_content["value"]  # v2 cursor
                return content["value"]  # v1 cursor
    return None  # No cursor found