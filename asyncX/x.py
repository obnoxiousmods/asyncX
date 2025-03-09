import httpx
import anyio
from typing import Dict, Any, List, Tuple
from asyncX.constants import DEFAULT_HEADERS, Operation  # ✅ Import Operation
from asyncX.utils import build_params, find_rest_ids, get_cursor  # ✅ Import utility functions
from typing import AsyncGenerator

class AsyncX:
    def __init__(self):
        self.session: httpx.AsyncClient | None = None

    async def authenticate(self, cookies: Dict[str, str]) -> None:
        """
        Authenticates and sets up an HTTPX session with provided cookies.
        """
        headers = DEFAULT_HEADERS.copy()  # ✅ Make a copy so we don’t modify the original

        # ✅ Dynamically update authentication-specific headers
        headers.update({
            "x-csrf-token": cookies.get("ct0", ""),
            "x-guest-token": cookies.get("guest_token", ""),
            "x-twitter-auth-type": "OAuth2Session" if cookies.get("auth_token") else "",
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "en",
        })

        self.session = httpx.AsyncClient(
            cookies=cookies,
            timeout=20,
            http2=True,
            headers=headers
        )

    async def _query(self, operation: Tuple[Dict[str, type], str, str], **kwargs) -> Any:
        """
        Performs a GET request to the Twitter GraphQL API.
        Ensures `Operation.default_variables` is included.
        """
        if self.session is None:
            raise ValueError("Authenticate first using `authenticate(cookies)`")

        params, qid, name = operation

        # ✅ Merge default variables with the request parameters
        query_params = Operation.default_variables | {key: kwargs[key] for key in params if key in kwargs}

        encoded_params = build_params({
            "variables": query_params,
            "features": Operation.default_features
        })

        url = f"https://api.twitter.com/graphql/{qid}/{name}"

        try:
            response = await self.session.get(url, params=encoded_params)  # ✅ Use GET
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"[Error] HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            print(f"[Error] Request failed: {e}")

    async def get_user_by_screen_name(self, screen_name: str) -> Dict[str, Any]:
        """ Get user details by screen name. """
        if not screen_name or not isinstance(screen_name, str):
            raise ValueError("Invalid screen_name provided")

        data = await self._query(Operation.UserByScreenName, screen_name=screen_name)
        return data.get("data", {}) if data else {}

    async def convert_screenName_to_restid(self, screen_name: str) -> str:
        """
        Converts a screen name to a rest_id.
        
        @param screen_name: The Twitter username (without @)
        @return: Dictionary {screen_name: rest_id}, or empty dict if not found.
        """
        user_data = await self.get_user_by_screen_name(screen_name)

        rest_id = user_data.get('user', {}).get('result', {}).get('rest_id')
        return rest_id if rest_id else None

    async def _query_paginated(self, operation: Tuple[Dict[str, type], str, str], **kwargs) -> AsyncGenerator:
        """
        A version of `_query()` that handles pagination by following the cursor.
        Includes `Operation.default_variables` in every request.
        """
        cursor = None
        dups = 0
        DUP_LIMIT = 3
        ids = set()

        while dups < DUP_LIMIT:
            query_params = Operation.default_variables | {key: kwargs[key] for key in operation[0] if key in kwargs}
            if cursor:
                query_params["cursor"] = cursor  # ✅ Use cursor for pagination

            encoded_params = build_params({
                "variables": query_params,
                "features": Operation.default_features
            })

            url = f"https://api.twitter.com/graphql/{operation[1]}/{operation[2]}"

            try:
                response = await self.session.get(url, params=encoded_params)  # ✅ Use GET for paginated requests
                response.raise_for_status()
                data = response.json()

                # ✅ Extract rest_ids and return batch
                batch_ids = find_rest_ids(data)
                yield batch_ids

                prev_len = len(ids)
                ids |= set(batch_ids)

                # ✅ Extract cursor for the next page
                cursor = get_cursor(data)

                if not cursor or prev_len == len(ids):
                    dups += 1  # If no new data, increment duplicate counter
                else:
                    dups = 0  # Reset duplicate counter if new data is found

            except httpx.HTTPStatusError as e:
                print(f"[Error] HTTP {e.response.status_code}: {e.response.text}")
                break
            except Exception as e:
                print(f"[Error] Request failed: {e}")
                break

    async def followers(self, rest_id: str) -> AsyncGenerator:
        """
        Async generator that fetches followers of a user using pagination.

        @param rest_id: The Twitter user ID
        @return: Yields lists of followers' rest_ids in batches
        """
        async for followers_batch in self._query_paginated(Operation.Followers, userId=rest_id):
            yield followers_batch



    async def close(self):
        """Closes the session."""
        if self.session:
            await self.session.aclose()
