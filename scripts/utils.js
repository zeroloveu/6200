const hre = require("hardhat");

function sanitizeEnv(value) {
  if (!value) return "";
  const trimmed = value.trim();
  return trimmed && !trimmed.includes("YOUR_") ? trimmed : "";
}

function getContractAddress() {
  const address = sanitizeEnv(process.env.CONTRACT_ADDRESS || process.env.SECURE_VOTING_ADDRESS);
  if (!address) {
    throw new Error("Set CONTRACT_ADDRESS in .env or pass SECURE_VOTING_ADDRESS.");
  }
  return address;
}

function getTargetVoterAddress(fallbackAddress) {
  return sanitizeEnv(process.env.VOTER_ADDRESS) || fallbackAddress;
}

function getCandidateId(defaultValue = 0) {
  const raw = sanitizeEnv(process.env.VOTE_CANDIDATE_ID);
  if (!raw) return defaultValue;
  const candidateId = Number(raw);
  if (!Number.isInteger(candidateId) || candidateId < 0) {
    throw new Error("VOTE_CANDIDATE_ID must be a non-negative integer.");
  }
  return candidateId;
}

async function getSigner() {
  const [signer] = await hre.ethers.getSigners();
  if (!signer) {
    throw new Error("No signer available. Check PRIVATE_KEY in .env.");
  }
  return signer;
}

async function getVotingContract(signer) {
  const contractAddress = getContractAddress();
  const connectedSigner = signer || (await getSigner());
  const voting = await hre.ethers.getContractAt("SecureVoting", contractAddress, connectedSigner);
  return { voting, contractAddress, signer: connectedSigner };
}

function formatTimestamp(timestampSeconds) {
  const date = new Date(Number(timestampSeconds) * 1000);
  return {
    utc: date.toISOString(),
    shanghai: new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    }).format(date)
  };
}

module.exports = {
  formatTimestamp,
  getCandidateId,
  getContractAddress,
  getSigner,
  getTargetVoterAddress,
  getVotingContract
};
