const hre = require("hardhat");

function parseListEnv(key, fallback) {
  const raw = process.env[key];
  if (!raw) return fallback;
  const values = raw
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
  return values.length > 0 ? values : fallback;
}

async function maybeVerify(contract, contractAddress, constructorArguments) {
  const isLocalNetwork = hre.network.name === "hardhat" || hre.network.name === "localhost";
  if (isLocalNetwork) return;

  if (!process.env.ETHERSCAN_API_KEY || process.env.ETHERSCAN_API_KEY.includes("YOUR_")) {
    console.log("Skipping Etherscan verification: ETHERSCAN_API_KEY is not set.");
    return;
  }

  console.log("Waiting for deployment confirmations before verification...");
  const confirmations = Number(process.env.VERIFICATION_CONFIRMATIONS || "6");
  const deploymentTx = contract.deploymentTransaction();
  if (deploymentTx) {
    await deploymentTx.wait(confirmations);
  }

  console.log("Submitting source verification to Etherscan...");
  try {
    await hre.run("verify:verify", {
      address: contractAddress,
      constructorArguments
    });
    console.log("Etherscan verification submitted successfully.");
  } catch (error) {
    const message = error && error.message ? error.message : String(error);
    if (message.toLowerCase().includes("already verified")) {
      console.log("Contract is already verified on Etherscan.");
      return;
    }
    throw error;
  }
}

async function main() {
  const signers = await hre.ethers.getSigners();
  const deployer = signers[0];
  if (!deployer) {
    throw new Error("No deployer account found. Please set PRIVATE_KEY in .env for live networks.");
  }

  const title = process.env.ELECTION_TITLE || "Course Election 2026";
  const candidates = parseListEnv("CANDIDATES", ["Alice", "Bob", "Charlie"]);
  if (candidates.length < 2) {
    throw new Error("At least 2 candidates are required.");
  }

  const now = Math.floor(Date.now() / 1000);
  const startDelaySeconds = Number(process.env.START_DELAY_SECONDS || "60");
  const durationHours = Number(process.env.ELECTION_DURATION_HOURS || "24");

  if (!Number.isFinite(startDelaySeconds) || startDelaySeconds < 0) {
    throw new Error("START_DELAY_SECONDS must be a non-negative number.");
  }
  if (!Number.isFinite(durationHours) || durationHours <= 0) {
    throw new Error("ELECTION_DURATION_HOURS must be a positive number.");
  }

  const startTime = now + Math.floor(startDelaySeconds);
  const endTime = startTime + Math.floor(durationHours * 3600);

  const envVoters = parseListEnv("INITIAL_VOTERS", []);
  const fallbackVoters = signers.slice(1, 3).map((s) => s.address);
  const initialVoters = [...new Set(envVoters.length > 0 ? envVoters : fallbackVoters)];
  if (initialVoters.length === 0) {
    initialVoters.push(deployer.address);
  }

  const Voting = await hre.ethers.getContractFactory("SecureVoting");
  const voting = await Voting.deploy(title, candidates, startTime, endTime, initialVoters);
  await voting.waitForDeployment();
  const contractAddress = await voting.getAddress();

  await maybeVerify(voting, contractAddress, [title, candidates, startTime, endTime, initialVoters]);

  console.log("Network:", hre.network.name);
  console.log("Deployer:", deployer.address);
  console.log("SecureVoting deployed to:", contractAddress);
  console.log("Election title:", title);
  console.log("Candidates:", candidates.join(", "));
  console.log("Initial voters:", initialVoters.join(", "));
  console.log("Start time:", startTime);
  console.log("End time:", endTime);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
