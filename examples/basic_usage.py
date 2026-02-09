"""
Basic usage example of Perplexity API. / Perplexity API 的基础使用示例。

This example demonstrates the simplest way to use the library / 此示例演示了使用该库的最简单方法，
for making queries without account management. / 用于在不进行账号管理的情况下进行查询。
"""

import perplexity


def main():
    """Run basic example. / 运行基础示例。"""
    print("=" * 60)
    print("Perplexity API - Basic Usage Example")
    print("=" * 60)

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
        '__cflb': '02DiuDyvFMmK5p9jVbVnMNSKYZhUL9aGmzjVRNndciJyS',
        'cf_clearance': 'KrfkYTZisOBb4n0iFpXycLPpxUTWgo.K3QlJ9AxvMyw-1770615563-1.2.1.1-q6iRDLoIALTicR4y3MW2c1jZ.d8QwruIzYkD1o.eXILNyrPSSznOtzm6AE0pBeVcvDeyLByuzuGI7aLRisD2DOgU6E4i7RXJRYfHo.4Bs.gfOApRBGMLfogxaH2W8VHRzUwzsbp7zXFNZgL.qT0hE.V4kHrq76eqTy4m9iHbwB5ulWWEXWPd02zSUt4_4B0gxANygr2HMcDd30LW.ce_fXRBP8lvVnq1qFynlZrRJLk',
        '__Secure-next-auth.session-token': 'eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..Vkjc1h_kB5wjB0oJ.OniFpNHqEJxoH3owwbxn3IruUSmJkrVH1G3tKgTqF_Fv3TrQgJR06cYkO2W_prBpA21Ig3lS-uiQPS4AMzyu1fbAP_eHfFnZIXLpjjF_xCSLq-0QQt2W_S1NjjbXe_kBQ0C-lgNx7aIkeukBsJfJS-QXyEjeEMoOjx4OOzkj_AxvORxY3nkaOcO0LoLEjJK5IYiSJoOxFY6sOLu0DACjqPDOw--R28f8AXr-_kCC_xWvzKKJgVcZ8FqizPH-4WlNBkO3WQRrA4dW3Y_EjeEJq15yP5mwCdnG94XpARTLufL69j9RJKJDfcOEWmhEc-UfQqUvdHD0pSDDPYPN_Rkvh0UDW5IiteqRPpVRvW-GDIRF_Hk41IVMP0hnCFjSrljd7OkQ0Fot7zUVWiMbyM_5QRCfXEFwmAEQbSr4VsUw9GlI3kdET0g5.UZ1VyvIdDGjnjeeVBhSpMg',
        '__cf_bm': '4UTYRloMffDoZS8QLb3ksodYfzZKI9VNtVBfhmI7rZk-1770616173-1.0.1.1-kTv7Y0cj530pafqLvjV6yHDmr148yWSqmoWaXollayXsKD2jreCjcDnAVoa60x4kMP67SEQQykyg6H8GKdnd2ZaYwYUcrHVR.8ukzPNggBI',
        'pplx.metadata': '{%22qc%22:7%2C%22qcu%22:692%2C%22qcm%22:23%2C%22qcc%22:629%2C%22qcco%22:0%2C%22qccol%22:0%2C%22qcdr%22:0%2C%22qcs%22:0%2C%22qcd%22:0%2C%22hli%22:true%2C%22hcga%22:true%2C%22hcds%22:false%2C%22hso%22:true%2C%22hfo%22:true%2C%22hsco%22:false%2C%22hfco%22:false%2C%22hsma%22:false%2C%22hdc%22:true%2C%22hdttb%22:false%2C%22qcr%22:0%2C%22fqa%22:1770616192586%2C%22lqa%22:1770616192586}',
        '_dd_s': 'aid=9294629c-5cf2-4938-9d6c-62efa1815c12&rum=2&id=a0f1000f-d3c0-4060-8623-6403c1bc931d&created=1770615554715&expire=1770617954747&logs=0'
    }

    # Create client (no authentication needed for basic queries) / 创建客户端（基础查询不需要身份验证）
    print("\n[1/3] Creating client...")
    client = perplexity.Client(cookies)
    print(f"Client created. Available queries: {client.copilot}")

    # Simple query / 简单查询
    print("\n[2/3] Making query...")
    query = "你是什么模型,中文回答我?"
    response = client.search(query, mode="reasoning", model="kimi-k2.5-thinking")

    print("\nQuery:", query)
    print("\nResponse:")
    print("-" * 60)
    if "answer" in response:
        print(response["answer"])
    else:
        print("No answer field found in response")
    print("-" * 60)

    # Query with different sources / 使用不同来源的查询
    print("\n[3/3] Query with specific sources...")
    query = "Latest AI research 2024"
    response = client.search(query, mode="auto", sources=["scholar"])  # Academic papers only

    print("\nQuery:", query)
    print("Sources: Academic papers")
    print("\nResponse:")
    print("-" * 60)
    if "answer" in response:
        print(response["answer"][:300] + "...")
    print("-" * 60)

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
