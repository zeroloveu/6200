const { formatTimestamp, getVotingContract } = require("./utils");

async function main() {
  const { voting, contractAddress, signer } = await getVotingContract();

  const [
    title,
    owner,
    startTime,
    endTime,
    status,
    totalVotes,
    totalRegisteredVoters,
    signerRegistered,
    signerVoted,
    candidateCount
  ] = await Promise.all([
    voting.electionTitle(),
    voting.owner(),
    voting.startTime(),
    voting.endTime(),
    voting.getElectionStatus(),
    voting.totalVotes(),
    voting.totalRegisteredVoters(),
    voting.isRegisteredVoter(signer.address),
    voting.hasVoted(signer.address),
    voting.candidateCount()
  ]);

  console.log("Contract:", contractAddress);
  console.log("Connected signer:", signer.address);
  console.log("Election title:", title);
  console.log("Owner:", owner);
  console.log("Status:", status);
  console.log("Start time (UTC):", formatTimestamp(startTime).utc);
  console.log("Start time (Asia/Shanghai):", formatTimestamp(startTime).shanghai);
  console.log("End time (UTC):", formatTimestamp(endTime).utc);
  console.log("End time (Asia/Shanghai):", formatTimestamp(endTime).shanghai);
  console.log("Total votes:", totalVotes.toString());
  console.log("Total registered voters:", totalRegisteredVoters.toString());
  console.log("Connected signer is registered:", signerRegistered);
  console.log("Connected signer has voted:", signerVoted);

  for (let i = 0; i < Number(candidateCount); i += 1) {
    const [name, voteCount] = await voting.getCandidate(i);
    console.log(`Candidate ${i}: ${name} (${voteCount.toString()} votes)`);
  }

  if (status === "ENDED") {
    const [winnerId, winnerName, winnerVotes, isTie] = await voting.getWinner();
    console.log("Winner ID:", winnerId.toString());
    console.log("Winner name:", winnerName);
    console.log("Winner votes:", winnerVotes.toString());
    console.log("Is tie:", isTie);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
