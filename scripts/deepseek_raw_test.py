"""Send 1 BBEH question to DeepSeek V3.2 Thinking, dump raw JSON response."""

import asyncio
import json
import os
import time
from dotenv import load_dotenv
load_dotenv()

from regulus.data.bbeh import load_dataset


async def main():
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )

    # Load first BBEH question (same seed as benchmarks)
    items = load_dataset(n=1, seed=42)
    q = items[0]
    print(f"Question ({len(q.problem)} chars): {q.problem[:120]}...")
    print(f"Expected: {q.target}")
    print()

    start = time.time()
    response = await client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[{"role": "user", "content": q.problem}],
    )
    elapsed = time.time() - start

    # Dump raw response as dict
    raw = response.model_dump()
    print("=" * 70)
    print(f"RAW RESPONSE (elapsed={elapsed:.1f}s):")
    print("=" * 70)
    print(json.dumps(raw, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
