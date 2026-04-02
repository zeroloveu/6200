require("@nomicfoundation/hardhat-toolbox");
require("hardhat-gas-reporter");
const { subtask } = require("hardhat/config");
const { TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD } = require("hardhat/builtin-tasks/task-names");

const localSolcJsPath = require.resolve("solc/soljson.js");
const localSolcVersion = "0.8.26";
const localSolcLongVersion = "0.8.26+commit.8a97fa7a.Emscripten.clang";

// Force Hardhat to use the bundled solcjs compiler. This avoids a recurring
// Windows-native solc issue in this workspace while keeping the build portable.
subtask(TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD, async (args, hre, runSuper) => {
  const requestedVersion = (args.solcVersion || "").trim();
  if (!requestedVersion || requestedVersion === "0.8.26") {
    return {
      compilerPath: localSolcJsPath,
      isSolcJs: true,
      version: localSolcVersion,
      longVersion: localSolcLongVersion
    };
  }

  return runSuper(args);
});

/** @type import("hardhat/config").HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.26",
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
    }
  },
  gasReporter: {
    enabled: process.env.REPORT_GAS === "true",
    currency: "USD",
    noColors: true
  }
};
