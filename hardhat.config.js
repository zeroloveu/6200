require("@nomicfoundation/hardhat-toolbox");
require("hardhat-gas-reporter");
require("dotenv").config();

const { SEPOLIA_RPC_URL, PRIVATE_KEY, ETHERSCAN_API_KEY, REPORT_GAS } = process.env;

function sanitizeEnv(value) {
  if (!value) return "";
  const trimmed = value.trim();
  if (!trimmed || trimmed.includes("YOUR_")) return "";
  return trimmed;
}

function normalizePrivateKey(value) {
  const sanitizedValue = sanitizeEnv(value);
  if (!sanitizedValue) return "";

  const prefixedValue = sanitizedValue.startsWith("0x")
    ? sanitizedValue
    : `0x${sanitizedValue}`;

  return /^0x[0-9a-fA-F]{64}$/.test(prefixedValue) ? prefixedValue : "";
}

const sepoliaRpcUrl = sanitizeEnv(SEPOLIA_RPC_URL);
const normalizedPrivateKey = normalizePrivateKey(PRIVATE_KEY);
const etherscanApiKey = sanitizeEnv(ETHERSCAN_API_KEY);

/** @type import("hardhat/config").HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  networks: {
    hardhat: {},
    localhost: {
      url: "http://127.0.0.1:8545"
    },
    sepolia: {
      url: sepoliaRpcUrl,
      accounts: normalizedPrivateKey ? [normalizedPrivateKey] : []
    }
  },
  gasReporter: {
    enabled: REPORT_GAS === "true",
    currency: "USD",
    noColors: true
  },
  etherscan: {
    apiKey: etherscanApiKey
  }
};
