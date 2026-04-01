# Compliance Notes (Course Project)

## Purpose

This project is an educational voting demo for blockchain coursework.
It is not legal advice and not a production election system.

## Compliance-Friendly Design Choices

- Data minimization:
  only wallet addresses and aggregated vote counts are stored on chain.
- No personal information:
  do not put names, IDs, phone numbers, or student numbers on chain.
- Controlled eligibility:
  only owner-registered wallets can vote.
- Auditability:
  all vote transactions and final totals are transparent and immutable.

## Operational Requirements for Real Use

- Off-chain identity verification by an authorized operator.
- Public election rules (eligibility, timing, dispute process).
- Secure key management for deployer/admin wallets.
- Compliance with local election, privacy, and cybersecurity regulations.

## Recommended Statement for Report

"This implementation demonstrates tamper-resistance and transparency via smart contracts,
while legal compliance in real deployments requires off-chain governance, identity checks,
and adherence to applicable jurisdictional regulations."
