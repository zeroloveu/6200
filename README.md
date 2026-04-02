# Secure Voting Project

This repository now contains a hybrid voting application:

1. FastAPI handles accounts, sessions, poll creation, allowed-user management, and public result pages.
2. Solidity contracts store the actual ballot records on chain.

Detailed smart contract introduction:
`docs/PROJECT_INTRODUCTION.md`

## Hybrid Architecture

The current app works like this:

- Users register and log in on the FastAPI website.
- Each user binds one wallet address to their account.
- Any logged-in user can publish a poll from the web UI.
- When a poll is created, the backend deploys a dedicated `SecureVoting` contract for that poll.
- Allowed users vote through a browser wallet such as MetaMask, so the actual vote transaction is written on chain.
- The website reads on-chain status and result data back from the contract.
- After the poll ends, everyone can open the result page and see the on-chain outcome.

This means the web app is the management layer, while the contract is the source of truth for ballots and results.

## FastAPI App

### Main features

- User registration and login
- Password hashing and verification
- Wallet binding per user
- Poll creation, editing, and deletion from the web UI
- Configurable topic, time window, candidate options, and allowed usernames
- Browser-wallet voting on chain
- Explicit abstain support on chain
- Public result pages backed by on-chain contract reads

### App stack

- FastAPI
- SQLAlchemy
- Jinja2 templates
- SQLite by default
- Session-based login
- Ethers.js in the browser
- Node bridge script for contract deployment and contract reads

### FastAPI project structure

```text
app/
  chain_service.py
  database.py
  main.py
  models.py
  security.py
  static/
    styles.css
    vendor/
      ethers.umd.min.js
  templates/
    *.html
scripts/
  fastapi-chain.js
requirements.txt
```

## Local Setup

### 1. Install dependencies

Python side:

```bash
pip install -r requirements.txt
```

Node side:

```bash
npm install
```

### 2. Configure `.env`

Copy `.env.example` to `.env` and set at least:

```env
APP_SECRET_KEY=change-this-secret-in-production
APP_DATABASE_URL=sqlite:///./fastapi_vote.db
APP_TIMEZONE=Asia/Shanghai

APP_CHAIN_RPC_URL=https://sepolia.infura.io/v3/YOUR_KEY
APP_CHAIN_PRIVATE_KEY=YOUR_PRIVATE_KEY_WITHOUT_0x
APP_CHAIN_NETWORK_NAME=sepolia
```

Notes:

- `APP_CHAIN_PRIVATE_KEY` is the backend deployer wallet used by FastAPI to deploy each poll contract.
- End users still need their own browser wallet to cast votes on chain.

### 3. Compile contracts

```bash
npm run compile
```

This project is configured to use the bundled `solcjs` compiler for stability in this workspace.

### 4. Start the web app

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Docker Deployment

This repository includes a production-style Docker build that packages:

- FastAPI
- SQLAlchemy + SQLite
- Node.js bridge scripts
- Hardhat contract compilation artifacts

### 1. Prepare `.env`

Create `.env` from `.env.example` and fill in your chain settings:

```env
APP_SECRET_KEY=change-this-secret-in-production
APP_DATABASE_URL=sqlite:///./fastapi_vote.db
APP_TIMEZONE=Asia/Shanghai

APP_CHAIN_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
APP_CHAIN_PRIVATE_KEY=YOUR_PRIVATE_KEY_WITHOUT_0x
APP_CHAIN_NETWORK_NAME=sepolia
```

When running with Docker Compose, the database location is overridden to a persistent container volume at `/app/data/fastapi_vote.db`.

### 2. Build and start

```bash
docker compose up --build -d
```

Open:

```text
http://127.0.0.1:8000
```

### 3. Stop

```bash
docker compose down
```

### 4. Rebuild after code changes

```bash
docker compose up --build -d
```

## Public Internet Deployment

If you want other machines on the internet to access this website, the recommended setup is:

- Run the FastAPI app in Docker
- Put a reverse proxy in front of it
- Serve the site over HTTPS with a real domain name

HTTPS is especially important when users need to interact with browser wallets from a non-localhost address.

### 1. Prepare a domain name

Point a domain or subdomain to your server public IP, for example:

```text
vote.example.com -> your server public IP
```

### 2. Update `.env`

At minimum:

```env
APP_SECRET_KEY=change-this-secret-in-production
APP_TIMEZONE=Asia/Shanghai
APP_SESSION_HTTPS_ONLY=true

APP_CHAIN_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
APP_CHAIN_PRIVATE_KEY=YOUR_PRIVATE_KEY_WITHOUT_0x
APP_CHAIN_NETWORK_NAME=sepolia

APP_PUBLIC_DOMAIN=vote.example.com
```

### 3. Start the public stack

```bash
docker compose -f docker-compose.public.yml up --build -d
```

This stack exposes:

- `80/tcp`
- `443/tcp`

and uses Caddy to reverse proxy requests to the FastAPI container.

### 4. Open firewall / security-group ports

Make sure these ports are reachable from the internet:

- `80`
- `443`

### 5. Visit the site

Open:

```text
https://vote.example.com
```

### 6. Stop the public stack

```bash
docker compose -f docker-compose.public.yml down
```

Detailed deployment notes:
`docs/DEPLOY_PUBLIC_ACCESS.md`

## Web Voting Flow

1. Register two or more users in the web app.
2. Make sure each user has a wallet address bound in `/profile`.
3. Log in as any user and create a poll.
4. The backend deploys a fresh `SecureVoting` contract for that poll.
5. Allowed users open the poll detail page and vote through their browser wallet.
6. The website syncs the wallet transaction hash back into the local database for display.
7. After the poll ends, everyone can open the public result page and view the on-chain result.

## Smart Contract Layer

### Main smart contract features

- Whitelist-based voters (`registerVoter`, `batchRegisterVoters`)
- One wallet can vote or abstain only once
- Time-bounded election (`startTime`, `endTime`)
- Public on-chain vote counts
- Public on-chain abstention counts
- End-of-election result query (`getAllResults`, `getWinner`)

### Contract commands used by the new scheme

Compile and test:

```bash
npm run compile
npm test
```

## Deployment Notes

- Use a strong `APP_SECRET_KEY` in production.
- SQLite is acceptable for demos; switch `APP_DATABASE_URL` to MySQL or PostgreSQL for a larger deployment.
- The current edit/delete rule is conservative: once any on-chain vote or abstain action has been synced, the poll can no longer be edited or deleted from the web app.
- Results are public after poll end by design.
- The repository no longer keeps the old standalone Sepolia CLI scripts. Contract deployment and contract reads now happen through the FastAPI hybrid flow.

## Disclaimer

This is an educational/demo-oriented hybrid voting system, not production-grade election infrastructure.
