from flow_memory.blockchain import LocalSettlementChain
from flow_memory.economy import DID


def test_local_chain_registers_agent_and_reputation() -> None:
    did = DID()
    chain = LocalSettlementChain()
    receipt = chain.register_agent(did.uri(), "ipfs://manifest", owner="0xabc")
    assert receipt.status == "success"
    assert receipt.block_number == 1
    rep = chain.apply_reputation_delta("0xabc", 1.5, "0xdeadbeef")
    assert rep.block_number == 2
    assert chain.reputation["0xabc"] == 1.5
