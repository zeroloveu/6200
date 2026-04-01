# Secure Voting Smart Contract (Course Project)

This repository provides a simple, secure, and transparent voting system based on Ethereum smart contracts.
It is designed for coursework: small enough to understand quickly, but with practical security and testing basics.

Detailed project introduction:
`docs/PROJECT_INTRODUCTION.md`

## 1. Features

- Whitelist-based voters (`registerVoter`, `batchRegisterVoters`)
- One wallet can vote only once
- Time-bounded election (`startTime`, `endTime`)
- Public and immutable on-chain vote counts
- End-of-election result query (`getAllResults`, `getWinner`)
- Gas-focused contract style (custom errors, bounded loops)

## 2. Security and Efficiency Practices Used

- Solidity `^0.8.24` (built-in overflow/underflow checks)
- Custom errors instead of long revert strings
- Explicit access control (`onlyOwner`)
- Strict state validation (time window, voter status, candidate id)
- Batch-size cap for registration to avoid block gas risks
- No external calls in vote flow (reduces reentrancy surface)

## 3. Legal/Compliance Notes (Important)

This demo contract supports compliance-oriented design, but legal compliance depends on your real deployment process:

- On-chain data minimization: do not store personal identity data on chain.
- Identity verification should be done off chain by authorized administrators.
- Election operators should publish clear rules (voter eligibility, vote period, dispute handling).
- Follow local laws/regulations for elections, privacy, and cybersecurity in your jurisdiction.

For a class assignment, this implementation is usually sufficient to discuss integrity, transparency, and tamper-resistance.

## 4. Project Structure

```text
contracts/
  SecureVoting.sol
scripts/
  deploy.js
test/
  helpers/
    deploy.js
  unit/
    SecureVoting.unit.test.js
  integration/
    SecureVoting.integration.test.js
  performance/
    SecureVoting.performance.test.js
```

## 5. Install and Run

### Install dependencies

```bash
npm install
```

### Compile

```bash
npm run compile
```

### Run all tests

```bash
npm test
```

### Run test categories

```bash
npm run test:unit
npm run test:integration
npm run test:performance
```

### Optional gas report

```bash
npm run test:gas
```

## 6. Deployment

### Local deployment

Terminal 1:

```bash
npm run node
```

Terminal 2:

```bash
npm run deploy:local
```

### Sepolia deployment

1. Copy `.env.example` to `.env`
2. Fill values for `SEPOLIA_RPC_URL`, `PRIVATE_KEY`, `ETHERSCAN_API_KEY`
3. Optional: adjust `VERIFICATION_CONFIRMATIONS` if your RPC provider is slow
4. Run:

```bash
npm run deploy:sepolia
```

The deploy script will automatically wait for confirmations and submit source verification to Etherscan when `ETHERSCAN_API_KEY` is set.

### Interact with a Sepolia deployment

Set `CONTRACT_ADDRESS` in `.env` to your deployed contract address.
Optionally set `VOTER_ADDRESS` for registration and `VOTE_CANDIDATE_ID` for the vote target.

```bash
npm run status:sepolia
npm run register:sepolia
npm run vote:sepolia
```

## 7. Demo Workflow

1. Deploy contract with candidates and initial voter list.
2. Owner registers more voters if needed.
3. Voters cast votes during election time window.
4. After election end, query final results and winner.

## 8. Disclaimer

This code is intended for educational use and coursework demonstration, not production election infrastructure.
