const { expect } = require("chai");
const { loadFixture, time } = require("@nomicfoundation/hardhat-network-helpers");
const { deployVotingFixture } = require("../helpers/deploy");

describe("SecureVoting - Unit Tests", function () {
  async function fixture() {
    return deployVotingFixture();
  }

  it("deploys with correct initial configuration", async function () {
    const { voting, owner, candidateNames, initialVoters, startTime, endTime } = await loadFixture(fixture);

    expect(await voting.owner()).to.equal(owner.address);
    expect(await voting.electionTitle()).to.equal("Student Council Vote");
    expect(await voting.candidateCount()).to.equal(candidateNames.length);
    expect(await voting.startTime()).to.equal(startTime);
    expect(await voting.endTime()).to.equal(endTime);

    for (const voter of initialVoters) {
      expect(await voting.isRegisteredVoter(voter)).to.equal(true);
    }
  });

  it("allows only owner to register voters", async function () {
    const { voting, voters } = await loadFixture(fixture);

    await expect(voting.connect(voters[0]).registerVoter(voters[2].address)).to.be.revertedWithCustomError(
      voting,
      "NotOwner"
    );

    await expect(voting.registerVoter(voters[2].address)).to.emit(voting, "VoterRegistered").withArgs(voters[2].address);
  });

  it("rejects zero address and duplicate registration", async function () {
    const { voting, voters } = await loadFixture(fixture);

    await expect(voting.registerVoter("0x0000000000000000000000000000000000000000")).to.be.revertedWithCustomError(
      voting,
      "ZeroAddress"
    );

    await expect(voting.registerVoter(voters[0].address)).to.be.revertedWithCustomError(voting, "AlreadyRegistered");
  });

  it("prevents voting before start time", async function () {
    const { voting, voters } = await loadFixture(fixture);

    await expect(voting.connect(voters[0]).vote(0)).to.be.revertedWithCustomError(voting, "ElectionNotStarted");
  });

  it("allows one valid vote per registered voter", async function () {
    const { voting, voters, startTime } = await loadFixture(fixture);
    await time.increaseTo(startTime + 1n);

    await expect(voting.connect(voters[0]).vote(1)).to.emit(voting, "VoteCast").withArgs(voters[0].address, 1);
    expect(await voting.totalVotes()).to.equal(1);

    const candidate = await voting.getCandidate(1);
    expect(candidate[1]).to.equal(1);

    await expect(voting.connect(voters[0]).vote(1)).to.be.revertedWithCustomError(voting, "AlreadyVoted");
  });

  it("allows registered voter to abstain exactly once", async function () {
    const { voting, voters, startTime } = await loadFixture(fixture);
    await time.increaseTo(startTime + 1n);

    await expect(voting.connect(voters[1]).abstain()).to.emit(voting, "Abstained").withArgs(voters[1].address);
    expect(await voting.totalVotes()).to.equal(0);
    expect(await voting.totalAbstentions()).to.equal(1);
    expect(await voting.hasVoted(voters[1].address)).to.equal(true);

    await expect(voting.connect(voters[1]).vote(0)).to.be.revertedWithCustomError(voting, "AlreadyVoted");
  });

  it("rejects vote from unregistered voter", async function () {
    const { voting, voters, startTime } = await loadFixture(fixture);
    await time.increaseTo(startTime + 1n);

    await expect(voting.connect(voters[5]).vote(0)).to.be.revertedWithCustomError(voting, "NotRegistered");
  });

  it("rejects invalid candidate id", async function () {
    const { voting, voters, startTime } = await loadFixture(fixture);
    await time.increaseTo(startTime + 1n);

    await expect(voting.connect(voters[0]).vote(999)).to.be.revertedWithCustomError(voting, "InvalidCandidateId");
  });

  it("rejects voting after election end", async function () {
    const { voting, voters, endTime } = await loadFixture(fixture);
    await time.increaseTo(endTime + 1n);

    await expect(voting.connect(voters[0]).vote(0)).to.be.revertedWithCustomError(voting, "ElectionEnded");
    await expect(voting.connect(voters[1]).abstain()).to.be.revertedWithCustomError(voting, "ElectionEnded");
  });

  it("returns status transitions correctly", async function () {
    const { voting, startTime, endTime } = await loadFixture(fixture);

    expect(await voting.getElectionStatus()).to.equal("PENDING");
    await time.increaseTo(startTime + 1n);
    expect(await voting.getElectionStatus()).to.equal("ACTIVE");
    await time.increaseTo(endTime + 1n);
    expect(await voting.getElectionStatus()).to.equal("ENDED");
  });
});
