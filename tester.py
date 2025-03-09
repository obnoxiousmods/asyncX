import anyio
from colorama import Fore, Style, init
from asyncX.x import AsyncX

# ✅ Initialize colorama for Windows compatibility
init(autoreset=True)

async def main():
    cookies = {
        "auth_token": "4ac359bfbe7196fe85a9c3e6300659bfef472ade",
        "kdt": "bhJXX0dmtlSf1ZgtVp0gCzlHURJlJDHTgcZeRDiC",
        "ct0": "4dca27a92fe1d77d9d926e019a5b31326b74b145fa6625d8c01cae9a6e06378095d28534e9eb78e98987c7ad0c31511fd8dfd9a68a03082b5031cc4f56eb7f9ff61cf2c29492c20810dc75612784142a",
    }

    asyncx = AsyncX()
    await asyncx.authenticate(cookies)

    print(Fore.CYAN + "🔍 Fetching user rest_id for @elonmusk...")

    rest_id = await asyncx.convert_screenName_to_restid("elonmusk")

    if not rest_id:
        print(Fore.RED + "❌ Failed to retrieve user rest_id.")
        await asyncx.close()
        return

    print(Fore.GREEN + f"✅ Elon Musk rest_id: {rest_id}")

    unique_followers = set()
    batch_count = 0

    print(Fore.YELLOW + "\n🚀 Fetching followers...")

    async for batch in asyncx.followers(rest_id=rest_id):
        batch_count += 1
        unique_followers.update(batch)
        print(
            Fore.BLUE
            + f"📦 Batch {batch_count}: {len(batch)} new followers | Total unique followers: {len(unique_followers)}"
        )

    print(Fore.GREEN + f"\n🎉 Completed! Total unique followers retrieved: {len(unique_followers)}")

    await asyncx.close()

anyio.run(main)
