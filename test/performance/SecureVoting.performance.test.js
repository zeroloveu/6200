const { expect } = require("chai");
const { loadFixture, time } = require("@nomicfoundation/hardhat-network-helpers");
const { deployVotingFixture } = require("../helpers/deploy");

describe("SecureVoting - Performance Tests", function () {
  async function performanceFixture() {
    return deployVotingFixture({
      candidateNames: ["A", "B", "C", "D", "E"]
    });
  }

  it("keeps batch registration gas in a reasonable range", async function () {
    const { voting, voters } = await loadFixture(performanceFixture);
    const extraVoters = voters.slice(2, 12).map((v) => v.address);

    const tx = await voting.batchRegisterVoters(extraVoters);
    const receipt = await tx.wait();
    const gasUsed = receipt.gasUsed;
    const gasPerVoter = gasUsed / BigInt(extraVoters.length);

    expect(gasUsed).to.be.lessThan(900000n);
    expect(gasPerVoter).to.be.lessThan(90000n);
  });

  it("keeps single vote gas in a reasonable range", async function () {
    const { voting, voters, startTime } = await loadFixture(performanceFixture);
    const extraVoters = voters.slice(2, 10).map((v) => v.address);
    await voting.batchRegisterVoters(extraVoters);

    await time.increaseTo(startTime + 1n);

    let totalGas = 0n;
    const allVoters = voters.slice(0, 10);

    for (let i = 0; i < allVoters.length; i++) {
      const tx = await voting.connect(allVoters[i]).vote(i % 5);
      const receipt = await tx.wait();
      totalGas += receipt.gasUsed;
    }

    const avgGas = totalGas / BigInt(allVoters.length);
    expect(avgGas).to.be.lessThan(120000n);
  });
});
