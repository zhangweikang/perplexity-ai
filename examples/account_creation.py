"""
Account creation example. / 账号创建示例。

This example demonstrates how to create new accounts / 此示例演示了如何使用 Emailnator
automatically using Emailnator for unlimited queries. / 自动创建新账号以实现无限查询。
"""

import perplexity


def main():
    """Run account creation example. / 运行账号创建示例。"""
    print("=" * 60)
    print("Perplexity API - Account Creation Example")
    print("=" * 60)

    print("\nNote: This example requires Emailnator cookies")
    print("See README for instructions on obtaining cookies\n")

    # Example with Emailnator cookies (replace with actual cookies) / 使用 Emailnator cookies 的示例（请替换为实际的 cookies）
    emailnator_cookies = {
        # 'XSRF-TOKEN': 'your-xsrf-token',
        # 'laravel_session': 'your-session',
    }

    if not emailnator_cookies or not any(emailnator_cookies.values()):
        print("No Emailnator cookies provided. Showing example code only.\n")
        print("Example code:")
        print("-" * 60)
        print(
            """
# With actual Emailnator cookies:
client = perplexity.Client()

print("Creating new account...")
client.create_account(emailnator_cookies)

print(f"Account created successfully!")
print(f"Enhanced queries available: {client.copilot}")
print(f"File uploads available: {client.file_upload}")

# Now you can use enhanced modes
response = client.search(
    'Complex query here',
    mode='pro',  # or 'reasoning', 'deep research'
    model='gpt-4.5'
)
        """
        )
        print("-" * 60)
        return

    # Actual implementation / 实际实现
    client = perplexity.Client()

    print("[1/3] Client created (no queries available)")
    print(f"Enhanced queries: {client.copilot}")

    print("\n[2/3] Creating new account with Emailnator...")
    try:
        client.create_account(emailnator_cookies)
        print("Account created successfully!")
    except Exception as e:
        print(f"Error creating account: {e}")
        print("\nTip: Make sure Emailnator cookies are fresh")
        print("Visit https://emailnator.com/ and get new cookies")
        return

    print(f"\n[3/3] Account ready!")
    print(f"Enhanced queries available: {client.copilot}")
    print(f"File uploads available: {client.file_upload}")

    # Test with enhanced mode / 使用增强模式进行测试
    print("\nTesting with enhanced mode...")
    response = client.search("What is quantum entanglement?", mode="pro")

    if "answer" in response:
        print("\nResponse:")
        print("-" * 60)
        print(response["answer"][:300] + "...")
        print("-" * 60)

    print(f"\nQueries remaining: {client.copilot}")

    print("\n" + "=" * 60)
    print("Account creation example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
