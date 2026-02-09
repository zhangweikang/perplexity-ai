"""
Batch processing example. / 批量处理示例。

This example demonstrates how to process multiple queries / 此示例演示了如何使用异步批量处理
efficiently using async batch processing. / 高效地处理多个查询。
"""

import asyncio
import perplexity_async
from time import time


async def process_queries_sequential(queries):
    """Process queries sequentially. / 按顺序处理查询。"""
    print("\n[Method 1] Sequential processing")
    print("-" * 60)

    client = await perplexity_async.Client()
    start = time()
    results = []

    for i, query in enumerate(queries, 1):
        print(f"Processing query {i}/{len(queries)}...")
        response = await client.search(query)
        results.append(response)

    elapsed = time() - start
    print(f"Completed in {elapsed:.2f}s")
    return results


async def process_queries_concurrent(queries):
    """Process queries concurrently. / 并发处理查询。"""
    print("\n[Method 2] Concurrent processing")
    print("-" * 60)

    client = await perplexity_async.Client()
    start = time()

    # Create tasks for all queries / 为所有查询创建任务
    tasks = [client.search(q) for q in queries]

    # Execute concurrently / 并发执行
    print(f"Processing {len(queries)} queries concurrently...")
    results = await asyncio.gather(*tasks)

    elapsed = time() - start
    print(f"Completed in {elapsed:.2f}s")
    return results


async def main():
    """Run batch processing example. / 运行批量处理示例。"""
    print("=" * 60)
    print("Perplexity API - Batch Processing Example")
    print("=" * 60)

    # Sample queries / 示例查询
    queries = [
        "What is Python?",
        "What is JavaScript?",
        "What is Rust?",
        "What is Go?",
        "What is TypeScript?",
    ]

    print(f"\nProcessing {len(queries)} queries...")

    # Sequential / 顺序处理
    results_seq = await process_queries_sequential(queries)

    # Concurrent / 并发处理
    results_con = await process_queries_concurrent(queries)

    # Compare results / 比较结果
    print("\n" + "=" * 60)
    print("Results comparison:")
    print("-" * 60)

    for i, query in enumerate(queries):
        print(f"\nQuery {i+1}: {query}")
        if "answer" in results_con[i]:
            print(f"Answer: {results_con[i]['answer'][:80]}...")

    print("\n" + "=" * 60)
    print("Batch processing example completed!")
    print("Note: Concurrent processing is typically 3-5x faster")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
