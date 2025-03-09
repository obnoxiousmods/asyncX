import random

import anyio
import uvicorn
from colorama import Fore, init
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from asyncX.x import AsyncX

init(autoreset=True)  # Enable colored console output

# ✅ Set up Starlette app & templates
app = Starlette()
templates = Jinja2Templates(directory="templates")

# ✅ Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ✅ MongoDB Setup
MONGO_URI = "mongodb://localhost:27017"
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["followers"]
accounts_collection = db["accounts"]

# ✅ Load all accounts into memory
accounts_cache = []


async def load_accounts():
    """Loads Twitter accounts from MongoDB into memory."""
    # global accounts_cache
    accounts_cache = await accounts_collection.find({}).to_list(None)
    print(Fore.GREEN + f"✅ Loaded {len(accounts_cache)} Twitter accounts.")


async def get_working_account():
    """Randomly selects an account and ensures it is not rate-limited."""
    if not accounts_cache:
        await load_accounts()
    random.shuffle(accounts_cache)

    asyncx = AsyncX()

    for account in accounts_cache:
        print(Fore.YELLOW + f"🔄 Trying account: {account['auth_token'][:10]}...")
        await asyncx.authenticate(account)

        # ✅ Test if this account is rate-limited
        test_rest_id = "44196397"  # Elon Musk's Twitter ID (or use another known valid ID)
        if await asyncx.check_followers_rate_limit(test_rest_id):
            return account  # ✅ This account is usable!

    print(Fore.RED + "❌ No working accounts found.")
    return None


async def homepage(request):
    """Render the main frontend page."""
    return templates.TemplateResponse("index.html", {"request": request})


async def import_accounts(request: Request):
    """Handles Twitter account imports."""
    data = await request.json()
    accounts = data.get("accounts", [])

    if not accounts:
        return JSONResponse({"message": "No accounts provided"}, status_code=400)

    # ✅ Parse & Store Unique Accounts
    existing_auth_tokens = {
        acc["auth_token"]
        for acc in await accounts_collection.find({}, {"auth_token": 1}).to_list(None)
    }
    new_accounts = [
        acc for acc in accounts if acc["auth_token"] not in existing_auth_tokens
    ]

    if new_accounts:
        await accounts_collection.insert_many(new_accounts)
        await load_accounts()  # ✅ Refresh cache
        return JSONResponse(
            {"message": f"Imported {len(new_accounts)} accounts successfully!"}
        )
    else:
        return JSONResponse(
            {"message": "⚠️ No new accounts added. All were duplicates."}
        )


class FollowerScraper(WebSocketEndpoint):
    encoding = "text"

    async def on_connect(self, websocket):
        """Accepts WebSocket connections."""
        await websocket.accept()
        print(Fore.GREEN + "✅ WebSocket Connection Established")

    async def on_receive(self, websocket, data):
        """Receives a username from the WebSocket and scrapes followers."""
        username = data.strip()
        print(Fore.CYAN + f"🔍 Scraping followers for @{username}...")

        asyncx = AsyncX()
        await asyncx.authenticate(
            {
                "auth_token": "4ac359bfbe7196fe85a9c3e6300659bfef472ade",
                "kdt": "bhJXX0dmtlSf1ZgtVp0gCzlHURJlJDHTgcZeRDiC",
                "ct0": "4dca27a92fe1d77d9d926e019a5b31326b74b145fa6625d8c01cae9a6e06378095d28534e9eb78e98987c7ad0c31511fd8dfd9a68a03082b5031cc4f56eb7f9ff61cf2c29492c20810dc75612784142a",
            }
        )

        rest_id = await asyncx.convert_screenName_to_restid(username)
        if not rest_id:
            await websocket.send_text(
                f"❌ Failed to retrieve user rest_id for @{username}"
            )
            await websocket.close()
            return

        print(Fore.YELLOW + f"✅ Found rest_id: {rest_id} - Fetching followers...")

        async for batch in asyncx.followers(rest_id=rest_id):
            # if batch is a dict, it's a ratelimit message
            if isinstance(batch, dict):
                await websocket.send_text(
                    f"⏳ Rate limit exceeded! Resets at {batch['reset_time']}."
                )
                await anyio.sleep(batch["wait_time"])
                continue

            for follower_id in batch:
                await websocket.send_text(follower_id)  # ✅ Send each `rest_id` live
                print(Fore.BLUE + f"📦 Sent: {follower_id}")

        print(Fore.GREEN + f"🎉 Completed! Sent all followers for @{username}")
        await websocket.close()

    async def on_disconnect(self, websocket, close_code):
        """Handles WebSocket disconnection."""
        print(Fore.RED + "❌ WebSocket Disconnected")


# ✅ Define routes
app.routes.extend(
    [
        Route("/", homepage),  # Serve index.html
        WebSocketRoute("/ws", FollowerScraper),  # WebSocket route
        Route(
            "/import_accounts", methods=["POST"], endpoint=import_accounts
        ),  # Import accounts
    ]
)

# ✅ Run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
