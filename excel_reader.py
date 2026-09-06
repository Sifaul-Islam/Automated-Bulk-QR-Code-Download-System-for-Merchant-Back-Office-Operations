import pandas as pd

def load_agents(filepath):
    df = pd.read_excel(filepath)

    print(f"  Excel columns found: {list(df.columns)}")

    agents = []
    for _, row in df.iterrows():
        raw_wallet = str(row["Wallet No."]).strip()
        if raw_wallet.endswith(".0"):
            raw_wallet = raw_wallet[:-2]

        parent = "N/A"
        if "Parent Merchant" in df.columns:
            parent = str(row["Parent Merchant"]).strip()

        agent_type = str(row["Parent/Child"]).strip().lower()

        # Add leading zero for PRA wallet numbers (11 digits starting with 0)
        if agent_type == "pra" and len(raw_wallet) == 10 and raw_wallet.startswith("1"):
            raw_wallet = "0" + raw_wallet

        agents.append({
            "type":   str(row["Parent/Child"]).strip(),
            "wallet": raw_wallet,
            "name":   str(row["DBA"]).strip(),
            "parent": parent,
        })

    print(f"Total agents loaded: {len(agents)}")
    return agents


def split_by_type(agents):
    parents  = [a for a in agents if a["type"].lower() == "parent"]
    children = [a for a in agents if a["type"].lower() == "child"]
    pras     = [a for a in agents if a["type"].lower() == "pra"]

    print(f"  Parent merchants: {len(parents)}")
    print(f"  Child merchants:  {len(children)}")
    print(f"  PRA merchants:    {len(pras)}")

    return parents, children, pras


def split_into_batches(agents, batch_size=30):
    batches = [agents[i:i+batch_size] for i in range(0, len(agents), batch_size)]
    print(f"  Total batches:    {len(batches)}")
    return batches