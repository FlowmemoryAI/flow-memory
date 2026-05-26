"""Chain metadata for local dry-run planning."""

BASE_SEPOLIA: dict[str, object] = {
    "chain_id": 84532,
    "name": "Base Sepolia",
    "currency": "ETH",
    "rpc_env": "BASE_SEPOLIA_RPC_URL",
}
BASE_MAINNET: dict[str, object] = {"chain_id": 8453, "name": "Base", "currency": "ETH", "rpc_env": "BASE_RPC_URL"}


def chain_by_name(name: str) -> dict[str, object]:
    if name in {"base-sepolia", "Base Sepolia"}:
        return dict(BASE_SEPOLIA)
    if name in {"base", "Base"}:
        return dict(BASE_MAINNET)
    raise KeyError(f"unknown chain: {name}")
