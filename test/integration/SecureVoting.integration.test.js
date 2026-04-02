const { expect } = require("chai");
const { loadFixture, time } = require("@nomicfoundation/hardhat-network-helpers");
const { deployVotingFixture } = require("../helpers/deploy");

describe("SecureVoting - Integration Tests", function () {
  async function integrationFixture() {
    return deployVotingFixture({
      candidateNames: ["Alice", "Bob", "Charlie", "Diana"],
      title: "Campus Representative Election"
    });
  }

  it("runs a full election flow end-to-end", async function () {
    const { voting, voters, startTime, endTime } = await loadFixture(integrationFixture);

    await voting.batchRegisterVoters([voters[2].address, voters[3].address, voters[4].address]);

    await time.increaseTo(startTime + 1n);

    await voting.connect(voters[0]).vote(0);
    await voting.connect(voters[1]).vote(1);
    await voting.connect(voters[2]).vote(1);
    await voting.connect(voters[3]).vote(1);
    await voting.connect(voters[4]).abstain();

    expect(await voting.totalVotes()).to.equal(4);
    expect(await voting.totalAbstentions()).to.equal(1);

    await expect(voting.getAllResults()).to.be.revertedWithCustomError(voting, "ElectionNotEnded");

    await time.increaseTo(endTime + 1n);

    const [names, votes] = await voting.getAllResults();
    expect(names[0]).to.equal("Alice");
    expect(names[1]).to.equal("Bob");
    expect(names[2]).to.equal("Charlie");
    expect(votes[0]).to.equal(1);
    expect(votes[1]).to.equal(3);
    expect(votes[2]).to.equal(0);

    const winner = await voting.getWinner();
    expect(winner[0]).to.equal(1);
    expect(winner[1]).to.equal("Bob");
    expect(winner[2]).to.equal(3);
    expect(winner[3]).to.equal(false);
  });

  it("marks tie correctly", async function () {
    const { voting, voters, startTime, endTime } = await loadFixture(integrationFixture);

    await voting.batchRegisterVoters([voters[2].address, voters[3].address, voters[4].address]);
    await time.increaseTo(startTime + 1n);

    await voting.connect(voters[0]).vote(0);
    await voting.connect(voters[1]).vote(1);
    await voting.connect(voters[2]).vote(0);
    await voting.connect(voters[3]).abstain();
    await voting.connect(voters[4]).vote(1);

    await time.increaseTo(endTime + 1n);

    const winner = await voting.getWinner();
    expect(winner[2]).to.equal(2);
    expect(winner[3]).to.equal(true);
  });
});
