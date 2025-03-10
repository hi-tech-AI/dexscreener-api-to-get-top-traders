# Get top 100 traders using Bitquery.

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
bitquery_api = os.getenv("BITQUERY_API_KEY")


def get_top_trader_address(contract_addresses):
    post_url = "https://streaming.bitquery.io/eap"

    for item in contract_addresses:
        print(
            f"--------------------- {contract_addresses.index(item) + 1} ---------------------"
        )

        payload = json.dumps(
            {
                "query": """query TopTradersByPnL($token: String!, $base: String!) {
                    Solana {
                        DEXTradeByTokens(
                            orderBy: { descendingByField: "pnl" }
                            limit: { count: 100 }
                            where: {Trade: {Currency: {MintAddress: {is: $token}}, Side: {Amount: {gt: "0"}, Currency: {MintAddress: {is: $base}}}}, Transaction: {Result: {Success: true}}}
                        ) {
                            Trade {
                                Account {
                                    Owner
                                }
                            }
                            pnl: sum(of: Trade_Side_AmountInUSD)
                        }
                    }
                }
                """,
                "variables": {
                    "token": item["contract_address"],
                    "base": "So11111111111111111111111111111111111111112",
                },
            }
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bitquery_api}",
        }

        response = requests.request("POST", post_url, headers=headers, data=payload)

        json_data = json.loads(response.text)["data"]["Solana"]["DEXTradeByTokens"]

        print(len(json_data))

        os.makedirs("./top_trader", exist_ok=True)

        with open(
            f"./top_trader/{item["token_name"]}.json", "w", encoding="utf-8"
        ) as data:
            json.dump(json_data, data, indent=4)
