# 部署与配置模块说明

## 1. 模块定位

该模块主要由以下文件组成：

- `.env.example`
- `requirements.txt`
- `package.json`
- `hardhat.config.js`
- `Dockerfile`
- `docker-compose.yml`

它们共同负责项目的依赖管理、运行配置、编译测试以及容器化部署。

## 2. 环境变量配置

项目通过 `.env` 文件管理核心配置，主要包括：

- `APP_SECRET_KEY`：FastAPI 会话签名密钥
- `APP_DATABASE_URL`：数据库连接地址
- `APP_TIMEZONE`：应用展示时区
- `APP_CHAIN_RPC_URL`：区块链节点地址
- `APP_CHAIN_PRIVATE_KEY`：部署合约的钱包私钥
- `APP_CHAIN_NETWORK_NAME`：网络名称，例如 `sepolia`

其中 `.env.example` 只提供模板，不应存放真实密钥。

## 3. Python 依赖

`requirements.txt` 定义 FastAPI、SQLAlchemy、Uvicorn 等 Python 依赖，是后端运行基础。

## 4. Node 依赖

`package.json` 定义了 Hardhat、Ethers.js 相关依赖和脚本命令，例如：

- `npm run compile`
- `npm test`
- `npm run coverage`

## 5. Hardhat 配置

`hardhat.config.js` 负责 Solidity 编译与测试环境配置。  
当前项目做了一个重要兼容处理：

- 强制使用本地 `solcjs`

这样可以降低某些环境下原生 Solidity 编译器不稳定的问题。

## 6. Docker 部署

### 6.1 `Dockerfile`

负责把项目构建成可运行镜像，流程包括：

- 准备 Node 与 Python 运行环境
- 安装 Node 依赖
- 安装 Python 依赖
- 复制项目代码
- 执行合约编译
- 启动 Uvicorn 服务

### 6.2 `docker-compose.yml`

用于一键启动容器，并提供：

- `.env` 加载
- 端口映射
- SQLite 数据持久化卷
- 自动重启策略

## 7. 在系统中的作用

这个模块不是直接面向业务用户的，但它决定了项目是否能够被稳定构建、部署、迁移和演示。  
对于课程项目答辩来说，它也是体现工程化能力的重要部分。
