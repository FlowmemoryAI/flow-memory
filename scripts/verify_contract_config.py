from flow_memory.web3 import chain_by_name


if __name__ == "__main__":
    chain = chain_by_name("base-sepolia")
    print({"ok": chain["chain_id"] == 84532, "chain": chain["name"]})
