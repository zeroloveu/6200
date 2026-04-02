# `app/chain_service.py` 模块说明

## 1. 模块定位

`app/chain_service.py` 是 Python 后端与区块链脚本之间的服务桥接层。  
它并不直接实现链上交互，而是负责把 FastAPI 的调用转换成对 Node.js 脚本的调用。

## 2. 主要职责

- 读取链配置
- 判断链功能是否可用
- 生成区块浏览器地址
- 调用 Node 桥接脚本执行部署、摘要读取和投票事件查询
- 统一处理桥接脚本报错

## 3. 核心组件

### 3.1 `ChainConfig`

这是一个数据类，用来组织链相关配置：

- `rpc_url`
- `private_key`
- `network_name`

它让上层代码可以更清晰地使用链配置，而不是反复直接读取环境变量。

### 3.2 `get_chain_config()`

从环境变量读取链配置，供部署和查询使用。

### 3.3 `is_chain_ready()`

判断链功能是否已具备最基本条件。  
当前规则是：

- 有 RPC 地址
- 有部署私钥

如果这两项缺失，前端页面会提示链功能不可用。

### 3.4 `deploy_poll_contract()`

把投票主题、候选项、时间窗口、允许钱包地址等信息打包成 JSON 载荷，交给 `scripts/fastapi-chain.js` 中的 `deploy` 命令处理。

### 3.5 `fetch_contract_summary()`

调用桥接脚本读取合约摘要，包括：

- 合约标题
- 投票状态
- 候选项与票数
- 已注册投票人数
- 是否弃权
- 是否有赢家或平票

### 3.6 `fetch_voter_action()`

查询某个钱包地址在某个合约中最近一次链上行为，用于同步本地记录。

## 4. 子进程调用机制

### 4.1 `_run_bridge_command()`

该函数是整个模块的核心。  
它通过 `subprocess.run()` 调用 Node.js 脚本，并将 JSON 结果解析为 Python 字典。

当前实现做了几个重要修复：

- 固定使用 UTF-8 解码，避免 Windows 默认编码导致乱码或崩溃
- 对空 `stdout` 做兜底处理
- 对非 JSON 输出给出明确错误
- 统一抛出 `ChainServiceError`

## 5. 浏览器链接生成

模块还提供：

- `build_address_url()`
- `build_tx_url()`

用于在页面中生成 Sepolia 或主网的 Etherscan 链接，方便用户核验链上数据。

## 6. 在系统中的作用

这个模块将 Python 世界和 Node/Ethers.js 世界连接在一起。  
没有它，FastAPI 虽然能处理网页请求，但无法完成合约部署、状态读取和链上事件校验。
