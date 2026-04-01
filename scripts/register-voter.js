const { getTargetVoterAddress, getVotingContract } = require("./utils");

async function main() {
  const { voting, contractAddress, signer } = await getVotingContract();
  const voterAddress = getTargetVoterAddress(signer.address);

  const alreadyRegistered = await voting.isRegisteredVoter(voterAddress);
  if (alreadyRegistered) {
    console.log("Contract:", contractAddress);
    console.log("Owner signer:", signer.address);
    console.log("Voter already registered:", voterAddress);
    return;
  }

  const tx = await voting.registerVoter(voterAddress);
  const receipt = await tx.wait();

  console.log("Contract:", contractAddress);
  console.log("Owner signer:", signer.address);
  console.log("Registered voter:", voterAddress);
  console.log("Transaction hash:", receipt.hash);
  console.log("Block number:", receipt.blockNumber);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
