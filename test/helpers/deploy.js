const { time } = require("@nomicfoundation/hardhat-network-helpers");
const { ethers } = require("hardhat");

async function deployVotingFixture(options = {}) {
  const signers = await ethers.getSigners();
  const owner = signers[0];
  const voters = signers.slice(1);

  const candidateNames = options.candidateNames || ["Alice", "Bob", "Charlie"];
  const initialVoters = options.initialVoters || [voters[0].address, voters[1].address];
  const title = options.title || "Student Council Vote";

  const now = await time.latest();
  const startTime = BigInt(options.startTime || now + 60);
  const endTime = BigInt(options.endTime || now + 3600);

  const Voting = await ethers.getContractFactory("SecureVoting");
  const voting = await Voting.connect(owner).deploy(title, candidateNames, startTime, endTime, initialVoters);
  await voting.waitForDeployment();

  return {
    voting,
    owner,
    voters,
    candidateNames,
    initialVoters,
    startTime,
    endTime
  };
}

module.exports = {
  deployVotingFixture
};
