import time
import httpx
import anyio
from typing import Dict, Any, List, Tuple
from colorama import Fore
from asyncX.constants import DEFAULT_HEADERS, Operation  # ✅ Import Operation
from asyncX.utils import build_params, find_rest_ids, get_cursor, find_key  # ✅ Import utility functions
from typing import AsyncGenerator

class AsyncX:
    def __init__(self):
        self.session: httpx.AsyncClient | None = None
        self.rate_limits = {}  # ✅ Stores rate limits per operation

    async def authenticate(self, cookies: Dict[str, str], proxy:str=None, **kwargs) -> None:
        """
        Authenticates and sets up an HTTPX session with provided cookies.
        """
        headers = DEFAULT_HEADERS.copy()

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
            headers=headers,
            verify=False,
            proxy=proxy,
            **kwargs,
        )

    async def _query(self, operation: Tuple[Dict[str, type], str, str], **kwargs) -> Any:
        """ 
        Performs a GET request while considering per-endpoint rate limits.
        """
        if self.session is None:
            raise ValueError("Authenticate first using `authenticate(cookies)`")

        params, qid, name = operation
        query_params = Operation.default_variables | {key: kwargs[key] for key in params if key in kwargs}
        encoded_params = build_params({"variables": query_params, "features": Operation.default_features})
        url = f"https://api.twitter.com/graphql/{qid}/{name}"

        # ✅ Check rate limits before making request
        if name in self.rate_limits:
            remaining, reset_time = self.rate_limits[name]
            if remaining == 0:
                wait_time = max(0, reset_time - time.time())
                print(Fore.RED + f"⏳ {name} rate limit exceeded! Sleeping for {int(wait_time)} seconds...")
                await anyio.sleep(wait_time)

        while True:
            try:
                response = await self.session.get(url, params=encoded_params)

                # ✅ Extract & Store Rate Limits Per Operation
                limit = int(response.headers.get("x-rate-limit-limit", -1))
                remaining = int(response.headers.get("x-rate-limit-remaining", -1))
                reset_time = int(response.headers.get("x-rate-limit-reset", time.time()))
                
                self.rate_limits[name] = (remaining, reset_time)  # ✅ Store per operation
                
                print(
                    Fore.YELLOW
                    + f"📊 {name} Rate Limit: {remaining}/{limit} | Reset at {time.strftime('%H:%M:%S', time.localtime(reset_time))}"
                )
                
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                print(Fore.RED + f"[Error] HTTP {e.response.status_code}: {e.response.text}")
                return False
            except Exception as e:
                print(Fore.RED + f"[Error] Request failed: {e}")
                return False


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
        A version of `_query()` that handles pagination while respecting per-operation rate limits.
        """
        cursor = None
        dups = 0
        DUP_LIMIT = 3
        ids = set()
        name = operation[2]  # ✅ Operation Name

        while dups < DUP_LIMIT:
            # ✅ Check rate limits before making request
            if name in self.rate_limits:
                remaining, reset_time = self.rate_limits[name]
                if remaining == 0:
                    wait_time = max(0, reset_time - time.time())
                    print(Fore.RED + f"⏳ {name} rate limit exceeded! Sleeping for {int(wait_time)} seconds...")
                    await anyio.sleep(wait_time)

            query_params = Operation.default_variables | {key: kwargs[key] for key in operation[0] if key in kwargs}
            if cursor:
                query_params["cursor"] = cursor

            encoded_params = build_params({"variables": query_params, "features": Operation.default_features})
            url = f"https://api.twitter.com/graphql/{operation[1]}/{operation[2]}"

            try:
                response = await self.session.get(url, params=encoded_params)
                
                # ✅ Extract & Store Rate Limits Per Operation
                limit = int(response.headers.get("x-rate-limit-limit", -1))
                remaining = int(response.headers.get("x-rate-limit-remaining", -1))
                reset_time = int(response.headers.get("x-rate-limit-reset", time.time()))
                stringTime = time.strftime('%H:%M:%S', time.localtime(reset_time))

                self.rate_limits[name] = (remaining, reset_time)  # ✅ Store per operation

                print(
                    Fore.YELLOW
                    + f"📊 {name} Rate Limit: {remaining}/{limit} | Reset at {stringTime}"
                )
                
                response.raise_for_status()

                data = response.json()
                screen_names = find_key(data, 'screen_name')
                yield screen_names

                prev_len = len(ids)
                ids |= set(screen_names)
                cursor = get_cursor(data)

                if not cursor or prev_len == len(ids):
                    dups += 1
                else:
                    dups = 0

            except httpx.HTTPStatusError as e:
                print(Fore.RED + f"[Error] HTTP {e.response.status_code}: {e.response.text}")
                wait_time = max(0, reset_time - time.time())
                yield {'limit': limit, 'remaining': remaining, 'reset_time': stringTime, 'wait_time': wait_time}
                break
            except Exception as e:
                print(Fore.RED + f"[Error] Request failed: {e}")
                break


    async def followers(self, rest_id: str) -> AsyncGenerator:
        """
        Async generator that fetches followers of a user using pagination.

        @param rest_id: The Twitter user ID
        @return: Yields lists of followers' rest_ids in batches
        """
        async for followers_batch in self._query_paginated(Operation.Followers, userId=rest_id):
            yield followers_batch

    async def check_followers_rate_limit(self, rest_id: str) -> bool:
        """
        Fetches the first page of followers to check if the account is rate-limited.

        @param rest_id: The Twitter user ID
        @return: True if request succeeds, False if 429 is received.
        """
        print(Fore.YELLOW + "🔍 Checking rate limit with a test request...")

        try:
            # ✅ Fetch the first page of followers
            data = await self._query(Operation.Followers, userId=rest_id)

            if data:  # ✅ Successfully retrieved data
                print(Fore.GREEN + "✅ Account is NOT rate-limited. Good to use!")
                return True
            else:
                print(Fore.RED + "❌ Account might be rate-limited or returned invalid data.")
                return False

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                print(Fore.RED + "⛔ 429 Rate Limit detected. This account cannot be used.")
                return False
            else:
                print(Fore.RED + f"[Error] HTTP {e.response.status_code}: {e.response.text}")
                return False

        except Exception as e:
            print(Fore.RED + f"[Error] Failed to check rate limit: {e}")
            return False


    async def close(self):
        """Closes the session."""
        if self.session:
            await self.session.aclose()
