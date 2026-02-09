"""
Streaming response example. / 流式响应示例。

This example demonstrates how to use streaming to receive / 此示例演示了如何使用流式传输，
responses in real-time as they are generated. / 以实时接收生成的响应。
"""

import perplexity


def main():
    """Run streaming example. / 运行流式传输示例。"""
    print("=" * 60)
    print("Perplexity API - Streaming Example")
    print("=" * 60)

    # Create client / 创建客户端
    print("\n[1/2] Creating client...")
    client = perplexity.Client()

    # Stream response / 流式传输响应
    print("\n[2/2] Streaming response...")
    query = "Explain quantum computing in simple terms"
    print(f"\nQuery: {query}")
    print("\nStreaming response:")
    print("-" * 60)

    chunk_count = 0
    last_answer = None

    for chunk in client.search(query, mode="auto", stream=True):
        chunk_count += 1

        # Print progress indicator / 打印进度指示器
        if chunk_count % 10 == 0:
            print(f"[Received {chunk_count} chunks...]")

        # Store last chunk with answer / 存储最后一个带有答案的块
        if "answer" in chunk:
            last_answer = chunk["answer"]

    print(f"\nTotal chunks received: {chunk_count}")

    if last_answer:
        print("\nFinal answer:")
        print("-" * 60)
        print(last_answer)
        print("-" * 60)

    print("\n" + "=" * 60)
    print("Streaming example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
