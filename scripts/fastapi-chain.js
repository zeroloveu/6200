const fs = require("fs");
const path = require("path");
const { ethers } = require("ethers");

const ARTIFACT_PATH = path.join(__dirname, "..", "artifacts", "contracts", "SecureVoting.sol", "SecureVoting.json");
const INITIAL_CONFIRMATION_TIMEOUT_MS = 120000;
const DEPLOYMENT_RECOVERY_TIMEOUT_MS = 480000;
const RECEIPT_POLL_INTERVAL_MS = 5000;

function loadArtifact() {
  if (!fs.existsSync(ARTIFACT_PATH)) {
    throw new Error("Contract artifact not found. Run `npm run compile` first.");
  }

  return JSON.parse(fs.readFileSync(ARTIFACT_PATH, "utf8"));
}

function requirePayload(rawPayload) {
  if (!rawPayload) {
    throw new Error("Missing JSON payload.");
  }
  return JSON.parse(rawPayload);
}

function normalizeAddress(value) {
  return value ? ethers.getAddress(value) : "";
}

function isAlreadyKnownError(error) {
  const message = error && error.message ? error.message : String(error);
  return /already known/i.test(message);
}

function isTimeoutError(error) {
  const message = error && error.message ? error.message : String(error);
  return /timeout/i.test(message);
}

function withGasMargin(gasLimit) {
  return (gasLimit * 120n) / 100n;
}

function buildFeeFields(feeData) {
  if (feeData.maxFeePerGas != null && feeData.maxPriorityFeePerGas != null) {
    return {
      maxFeePerGas: feeData.maxFeePerGas,
      maxPriorityFeePerGas: feeData.maxPriorityFeePerGas
    };
  }

  if (feeData.gasPrice != null) {
    return {
      gasPrice: feeData.gasPrice
    };
  }

  return {};
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function fetchTransactionIfKnown(provider, txHash) {
  try {
    return await provider.getTransaction(txHash);
  } catch (error) {
    if (isTimeoutError(error)) {
      return null;
    }
    throw error;
  }
}

async function waitForReceiptWithRecovery(provider, txHash) {
  try {
    const receipt = await provider.waitForTransaction(txHash, 1, INITIAL_CONFIRMATION_TIMEOUT_MS);
    if (receipt) {
      return receipt;
    }
  } catch (error) {
    if (!isTimeoutError(error)) {
      throw error;
    }
  }

  const deadline = Date.now() + DEPLOYMENT_RECOVERY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const receipt = await provider.getTransactionReceipt(txHash);
      if (receipt) {
        return receipt;
      }
    } catch (error) {
      if (!isTimeoutError(error)) {
        throw error;
      }
    }

    await sleep(RECEIPT_POLL_INTERVAL_MS);
  }

  return null;
}

async function deploy(payload) {
  const artifact = loadArtifact();
  const provider = new ethers.JsonRpcProvider(payload.rpcUrl);
  const wallet = new ethers.Wallet(payload.privateKey.startsWith("0x") ? payload.privateKey : `0x${payload.privateKey}`, provider);
  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, wallet);

  const voters = (payload.initialVoters || []).map(normalizeAddress);
  const network = await provider.getNetwork();
  const nonce = await provider.getTransactionCount(wallet.address, "pending");
  const feeData = await provider.getFeeData();
  const deployTx = await factory.getDeployTransaction(
    payload.title,
    payload.candidateNames,
    BigInt(payload.startTime),
    BigInt(payload.endTime),
    voters
  );
  const estimatedGas = await provider.estimateGas({
    ...deployTx,
    from: wallet.address
  });
  const signedDeployTx = await wallet.signTransaction({
    ...deployTx,
    chainId: Number(network.chainId),
    nonce,
    gasLimit: withGasMargin(estimatedGas),
    ...buildFeeFields(feeData)
  });
  const txHash = ethers.keccak256(signedDeployTx);
  const predictedContractAddress = ethers.getCreateAddress({ from: wallet.address, nonce });

  try {
    await provider.broadcastTransaction(signedDeployTx);
  } catch (error) {
    if (!isAlreadyKnownError(error)) {
      if (!isTimeoutError(error)) {
        throw error;
      }

      const knownTransaction = await fetchTransactionIfKnown(provider, txHash);
      if (!knownTransaction) {
        throw new Error(`Deployment broadcast timed out before the node acknowledged the transaction: ${txHash}`);
      }
    }
  }

  const receipt = await waitForReceiptWithRecovery(provider, txHash);
  if (!receipt) {
    return {
      contractAddress: predictedContractAddress,
      deployTxHash: txHash,
      deployBlock: null,
      chainId: network.chainId.toString(),
      networkName: payload.networkName || network.name || "unknown",
      ownerAddress: wallet.address,
      deploymentStatus: "PENDING",
      deploymentStatusMessage: `部署交易已发送到链上，正在等待区块确认：${txHash}`
    };
  }

  return {
    contractAddress: receipt.contractAddress || predictedContractAddress,
    deployTxHash: txHash,
    deployBlock: Number(receipt.blockNumber),
    chainId: network.chainId.toString(),
    networkName: payload.networkName || network.name || "unknown",
    ownerAddress: wallet.address,
    deploymentStatus: "MINED",
    deploymentStatusMessage: null
  };
}

async function summary(payload) {
  const artifact = loadArtifact();
  const provider = new ethers.JsonRpcProvider(payload.rpcUrl);
  const contractAddress = normalizeAddress(payload.contractAddress);
  const contract = new ethers.Contract(contractAddress, artifact.abi, provider);
  const network = await provider.getNetwork();

  const [
    electionTitle,
    owner,
    startTime,
    endTime,
    status,
    totalVotes,
    totalAbstentions,
    totalRegisteredVoters,
    candidateCount
  ] = await Promise.all([
    contract.electionTitle(),
    contract.owner(),
    contract.startTime(),
    contract.endTime(),
    contract.getElectionStatus(),
    contract.totalVotes(),
    contract.totalAbstentions(),
    contract.totalRegisteredVoters(),
    contract.candidateCount()
  ]);

  const candidates = [];
  for (let index = 0; index < Number(candidateCount); index += 1) {
    const [name, voteCount] = await contract.getCandidate(index);
    candidates.push({
      id: index,
      name,
      voteCount: Number(voteCount)
    });
  }

  let viewer = null;
  if (payload.viewerAddress) {
    const viewerAddress = normalizeAddress(payload.viewerAddress);
    const [isRegistered, hasVoted] = await Promise.all([
      contract.isRegisteredVoter(viewerAddress),
      contract.hasVoted(viewerAddress)
    ]);
    viewer = {
      address: viewerAddress,
      isRegistered,
      hasVoted
    };
  }

  let winner = null;
  if (status === "ENDED") {
    const [winnerId, winnerName, winnerVotes, isTie] = await contract.getWinner();
    winner = {
      winnerId: Number(winnerId),
      winnerName,
      winnerVotes: Number(winnerVotes),
      isTie
    };
  }

  return {
    contractAddress,
    electionTitle,
    owner,
    startTime: startTime.toString(),
    endTime: endTime.toString(),
    status,
    totalVotes: Number(totalVotes),
    totalAbstentions: Number(totalAbstentions),
    totalRegisteredVoters: Number(totalRegisteredVoters),
    candidates,
    viewer,
    winner,
    chainId: network.chainId.toString(),
    networkName: payload.networkName || network.name || "unknown"
  };
}

async function voterAction(payload) {
  const artifact = loadArtifact();
  const provider = new ethers.JsonRpcProvider(payload.rpcUrl);
  const contractAddress = normalizeAddress(payload.contractAddress);
  const voterAddress = normalizeAddress(payload.voterAddress);
  const contract = new ethers.Contract(contractAddress, artifact.abi, provider);

  const fromBlock = payload.fromBlock ?? 0;
  const voteEvents = await contract.queryFilter(contract.filters.VoteCast(voterAddress), fromBlock);
  const abstainEvents = await contract.queryFilter(contract.filters.Abstained(voterAddress), fromBlock);

  const merged = [
    ...voteEvents.map((event) => ({
      actionType: "vote",
      candidateId: event.args && event.args.candidateId !== undefined ? Number(event.args.candidateId) : null,
      txHash: event.transactionHash,
      blockNumber: Number(event.blockNumber),
      logIndex: event.index ?? 0
    })),
    ...abstainEvents.map((event) => ({
      actionType: "abstain",
      candidateId: null,
      txHash: event.transactionHash,
      blockNumber: Number(event.blockNumber),
      logIndex: event.index ?? 0
    }))
  ].sort((left, right) => {
    if (left.blockNumber !== right.blockNumber) {
      return left.blockNumber - right.blockNumber;
    }
    return left.logIndex - right.logIndex;
  });

  return merged.length > 0 ? merged[merged.length - 1] : { actionType: null };
}

async function main() {
  const command = process.argv[2];
  const payload = requirePayload(process.argv[3]);

  if (!command) {
    throw new Error("Missing bridge command.");
  }

  let result;
  if (command === "deploy") {
    result = await deploy(payload);
  } else if (command === "summary") {
    result = await summary(payload);
  } else if (command === "voter-action") {
    result = await voterAction(payload);
  } else {
    throw new Error(`Unsupported bridge command: ${command}`);
  }

  process.stdout.write(JSON.stringify(result));
}

main().catch((error) => {
  process.stderr.write(error && error.message ? error.message : String(error));
  process.exitCode = 1;
});
