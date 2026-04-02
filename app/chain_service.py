import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SCRIPT = PROJECT_ROOT / "scripts" / "fastapi-chain.js"


class ChainServiceError(RuntimeError):
    pass


@dataclass
class ChainConfig:
    rpc_url: str
    private_key: str
    network_name: str


def get_chain_config() -> ChainConfig:
    return ChainConfig(
        rpc_url=(os.getenv("APP_CHAIN_RPC_URL") or "").strip(),
        private_key=(os.getenv("APP_CHAIN_PRIVATE_KEY") or "").strip(),
        network_name=(os.getenv("APP_CHAIN_NETWORK_NAME") or "sepolia").strip() or "sepolia",
    )


def is_chain_ready() -> bool:
    config = get_chain_config()
    return bool(config.rpc_url and config.private_key)


def get_explorer_base_url(chain_id: str | None, network_name: str | None) -> str:
    if chain_id == "11155111" or (network_name or "").lower() == "sepolia":
        return "https://sepolia.etherscan.io"
    if chain_id == "1" or (network_name or "").lower() == "mainnet":
        return "https://etherscan.io"
    return ""


def build_address_url(address: str | None, chain_id: str | None, network_name: str | None) -> str | None:
    if not address:
        return None
    base_url = get_explorer_base_url(chain_id, network_name)
    return f"{base_url}/address/{address}" if base_url else None


def build_tx_url(tx_hash: str | None, chain_id: str | None, network_name: str | None) -> str | None:
    if not tx_hash:
        return None
    base_url = get_explorer_base_url(chain_id, network_name)
    return f"{base_url}/tx/{tx_hash}" if base_url else None


def deploy_poll_contract(
    title: str,
    candidate_names: list[str],
    starts_at: datetime,
    ends_at: datetime,
    voter_addresses: list[str],
) -> dict:
    config = get_chain_config()
    if not (config.rpc_url and config.private_key):
        raise ChainServiceError("区块链配置不完整，缺少 RPC URL 或部署私钥。")

    payload = {
        "rpcUrl": config.rpc_url,
        "privateKey": config.private_key,
        "networkName": config.network_name,
        "title": title,
        "candidateNames": candidate_names,
        "startTime": int(starts_at.timestamp()),
        "endTime": int(ends_at.timestamp()),
        "initialVoters": voter_addresses,
    }
    return _run_bridge_command("deploy", payload)


def fetch_contract_summary(contract_address: str, viewer_address: str | None = None) -> dict:
    config = get_chain_config()
    if not config.rpc_url:
        raise ChainServiceError("区块链配置不完整，缺少 RPC URL。")

    payload = {
        "rpcUrl": config.rpc_url,
        "networkName": config.network_name,
        "contractAddress": contract_address,
        "viewerAddress": viewer_address,
    }
    return _run_bridge_command("summary", payload)


def fetch_voter_action(contract_address: str, voter_address: str, from_block: int | None = None) -> dict:
    config = get_chain_config()
    if not config.rpc_url:
        raise ChainServiceError("区块链配置不完整，缺少 RPC URL。")

    payload = {
        "rpcUrl": config.rpc_url,
        "networkName": config.network_name,
        "contractAddress": contract_address,
        "voterAddress": voter_address,
        "fromBlock": from_block,
    }
    return _run_bridge_command("voter-action", payload)


def _run_bridge_command(command: str, payload: dict) -> dict:
    if not BRIDGE_SCRIPT.exists():
        raise ChainServiceError("链路桥接脚本不存在，无法与合约交互。")

    process = subprocess.run(
        ["node", str(BRIDGE_SCRIPT), command, json.dumps(payload, ensure_ascii=False)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )

    stdout = process.stdout or ""
    stderr = process.stderr or ""

    if process.returncode != 0:
        message = (stderr or stdout or "未知链路错误").strip()
        raise ChainServiceError(message)

    if not stdout.strip():
        raise ChainServiceError("链路桥接没有返回可解析的数据。")

    try:
        return json.loads(stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ChainServiceError("链路桥接返回了无法解析的结果。") from exc
