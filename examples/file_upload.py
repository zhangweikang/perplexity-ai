"""
File upload example. / 文件上传示例。

This example demonstrates how to upload files with queries / 此示例演示了如何通过查询上传文件，
for document analysis and Q&A. / 用于文档分析和问答。
"""

import perplexity
from pathlib import Path


def main():
    """Run file upload example. / 运行文件上传示例。"""
    print("=" * 60)
    print("Perplexity API - File Upload Example")
    print("=" * 60)

    # Note: File uploads require an account with cookies / 注意：文件上传需要带有 cookies 的账号
    # This example shows the API structure / 此示例展示了 API 结构

    print("\nNote: This example requires Perplexity account cookies")
    print("See README for instructions on obtaining cookies\n")

    # Example with cookies (replace with actual cookies) / 使用 cookies 的示例（请替换为实际的 cookies）
    cookies = {
        'pplx.visitor-id': '3fd5142f-0de4-49c2-8e38-25e7f9caa17c',
    'pplx.search-mode': 'search',
    '__podscribe_perplexityai_referrer': '_',
    '__podscribe_perplexityai_landing_url': 'https://www.perplexity.ai/',
    'intercom-device-id-l2wyozh0': 'c0a89bbd-afcb-4960-ab98-f61b05a06cdc',
    '__stripe_mid': '8dd3af99-d6f0-4062-9c47-18dedacec965e797ae',
    'pplx.side-upsell-enterprise-dismissed': 'true',
    'pplx.search-models': '{%22search%22:%22claude2%22%2C%22research%22:%22pplx_alpha%22}',
    'IndrX2c1OFdjNG9oXzgxd1JocUVVWGFadkNMVEZaYlkzeGRCUlRlR1JldWhCX2Fub255bW91c1VzZXJJZCI%3D': 'IjYwMzU1ZGVjLWFkZDQtNDhjZS04N2E2LTllZmI5NzM2ZTlmNCI=',
    'segmented-control-popover-studio': '1',
    'sidebarHiddenHubs': '[%22SIDEBAR_FINANCE%22%2C%22SIDEBAR_SHOPPING%22%2C%22SIDEBAR_TRAVEL%22%2C%22SIDEBAR_ACADEMIC%22]',
    'pplx.personal-search-badge-seen': '{%22sidebar%22:true%2C%22settingsSidebar%22:false%2C%22personalize%22:false}',
    'ph_phc_TXdpocbGVeZVm5VJmAsHTMrCofBQu3e0kN8HGMNGTVW_posthog': '%7B%22distinct_id%22%3A%220197c895-93b1-70e1-bf9b-1ae66ca85d5b%22%2C%22%24sesid%22%3A%5B1751417530678%2C%220197c895-93b0-7535-89d8-64168839a40e%22%2C1751416935344%5D%7D',
    '__ps_fva': '1762407677889',
    '_fbp': 'fb.1.1762407678309.905207218777665437',
    '_ga_SH9PRBQG23': 'GS2.1.s1765444231$o1$g0$t1765444231$j60$l0$h0',
    '_ga': 'GA1.1.1168252117.1765444231',
    'gov-badge': '3',
    'sidebar-upgrade-badge': '2',
    '_rdt_uuid': '1762407677875.fee7782e-0104-4257-84f3-2f21b9c72cf3',
    '_gcl_au': '1.1.1251418162.1765444246',
    'g_state': '{"i_l":0,"i_ll":1770461021681,"i_e":{"enable_itp_optimization":0}}',
    'next-auth.csrf-token': '1eb3c379ba609e31cb32c04562a29289d971ac4e7319bd76e1a6a2f9a19f7f5d%7Cb1c7912e214a0d3404a67bc78a3715c3666399944ca60b1f441c54771c4051ca',
    'next-auth.callback-url': 'https%3A%2F%2Fwww.perplexity.ai%2Fapi%2Fauth%2Fsignin-callback%3Fredirect%3Dhttps%253A%252F%252Fwww.perplexity.ai%252F%253Flogin-source%253DoneTapHome',
    'cf_clearance': 'hMfIpy49EKhPCbnxFkown7mwf7haQKXbMsFoP1ayxAc-1770469890-1.2.1.1-0qB1A3s9E9KhA_sYIga_.3eX323Z6TZHDLOyU57cCthTlcnJz_Fgwh1Mr8qD8fgCVKXNsoKdG4EDk60wrPZ7JufOnLco7wsMNCl4JQS9qA5t4TUwabYa6mr5A0c_OxdNXKGucpYbTeCoE0WuvjNWCLEI9MQYGzqjpGSQZSkHigJ.riITNPNPkHoN._QQqClTC0ml_KTOzsMtwXxW0FrjF6EG0pClp0HXL_4tgHjT4P4',
    'pplx.metadata': '{%22qc%22:6%2C%22qcu%22:683%2C%22qcm%22:23%2C%22qcc%22:627%2C%22qcco%22:0%2C%22qccol%22:0%2C%22qcdr%22:0%2C%22qcs%22:0%2C%22qcd%22:0%2C%22hli%22:true%2C%22hcga%22:true%2C%22hcds%22:false%2C%22hso%22:true%2C%22hfo%22:true%2C%22hsco%22:false%2C%22hfco%22:false%2C%22hsma%22:false%2C%22hdc%22:true%2C%22hdttb%22:false%2C%22qcr%22:0}',
    '__cflb': '02DiuDyvFMmK5p9jVbVnMNSKYZhUL9aGmzjVRNndciJyS',
    '__cf_bm': 'aztHbq8cRWFuYKBFM77WxMWBtFvL1iEWVGQW0lAoj5s-1770603465-1.0.1.1-P.XHQUwEnOOPCesCVgf1GDHbN8zoG5_eFH.aI.fhT4MDGO45gsVoC17BBuY.jTjICvFOSbTYWflojW1Pwj8rD6QLzjkPC0jPG6hQPJPR0cg',
    '__Secure-next-auth.session-token': 'eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..aDux40tu_BPLKpYR.mtR0NUlxxf4FjuqCG0-Izk0BqEcJZb-pKDDq_zOwvU7wskf6gHmpi7uIKldSanHtrFyydZyzWnQj7cCjYf5KyKbptau3oljGOp6JsUEJ3OI-IS6L-mNRMi7uvULOhRXtMQoyBDws78mLvAazSWohbUZT5CfjWPfdXwkxhY43Ku6mO6O3TkNjW93LPh__txvH097EC0ic180bvv5zm-vVj1Pc5f25CyXUCfl7ZPOgHUe1EjuvBtFs7MYfv3Nu2s8q5r1X7TjYIJ_GSmXEbsz6qj_dheitLmGVhsmx80O9q8IRZI6keAjG9msEkfYDhl5H2qkuNdRvTn-qagZwn8DsBm-LigymIAZRySVRbRFDW9kma6dmqhwGdJCT2zqpWL9IiUY18oXmfUTGvTkUTFa09crNjivALkqXfNQ1ELiIaKb36PM7Q5Yc.xB9goV2Y-oFGSRzjViafow',
    '_dd_s': 'isExpired=1&aid=9294629c-5cf2-4938-9d6c-62efa1815c12',
    }

    if not cookies or not any(cookies.values()):
        print("No cookies provided. Showing example code only.\n")
        print("Example code:")
        print("-" * 60)
        print(
            """
# With actual cookies: / 使用实际 cookies：
client = perplexity.Client(cookies)

# Upload a text file / 上传文本文件
with open('document.txt', 'r') as f:
    response = client.search(
        'Summarize this document',
        files={'document.txt': f.read()}
    )

# Upload a PDF (as bytes) / 上传 PDF（作为字节流）
with open('report.pdf', 'rb') as f:
    response = client.search(
        'What are the key findings in this report?',
        files={'report.pdf': f.read()}
    )

# Multiple files / 多个文件
files = {
    'doc1.txt': open('doc1.txt').read(),
    'doc2.txt': open('doc2.txt').read(),
}
response = client.search(
    'Compare these two documents',
    files=files
)
        """
        )
        print("-" * 60)
        return

    # Actual implementation with cookies / 使用 cookies 的实际实现
    client = perplexity.Client(cookies)

    print(f"Client created with account")
    print(f"File uploads available: {client.file_upload}")

    # Create a sample file / 创建一个示例文件
    sample_file = Path("C:\\Users\\ya9557\\Desktop\\企业微信截图_17703468907360.png")
    sample_file.write_text("This is a sample document about artificial intelligence.")

    try:
        with open(sample_file, "r") as f:
            response = client.search("识别图中的股票代码", files={"sample.txt": f.read()})

        if "answer" in response:
            print("\nResponse:")
            print("-" * 60)
            print(response["answer"])
            print("-" * 60)

    finally:
        # Cleanup / 清理
        if sample_file.exists():
            sample_file.unlink()

    print("\n" + "=" * 60)
    print("File upload example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
