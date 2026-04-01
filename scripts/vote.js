const { getCandidateId, getVotingContract } = require("./utils");

async function main() {
  const { voting, contractAddress, signer } = await getVotingContract();
  const candidateId = getCandidateId(0);

  const tx = await voting.vote(candidateId);
  const receipt = await tx.wait();
  const [candidateName, candidateVotes] = await voting.getCandidate(candidateId);

  console.log("Contract:", contractAddress);
  console.log("Voter signer:", signer.address);
  console.log("Candidate ID:", candidateId);
  console.log("Candidate name:", candidateName);
  console.log("Candidate votes after tx:", candidateVotes.toString());
  console.log("Transaction hash:", receipt.hash);
  console.log("Block number:", receipt.blockNumber);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
