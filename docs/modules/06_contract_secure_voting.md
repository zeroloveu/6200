# `contracts/SecureVoting.sol` 模块说明

## 1. 模块定位

`SecureVoting.sol` 是整个项目最核心的可信执行模块。  
它负责把投票过程中的关键事实写入区块链，包括：

- 哪些地址有投票资格
- 投票何时开始、何时结束
- 每个候选项获得多少票
- 有多少人选择弃权

链上合约是最终结果的可信来源，网页只负责管理与展示。

## 2. 合约设计目标

本合约面向课程项目与演示场景，设计目标包括：

- 保证投票不可篡改
- 限定投票资格
- 限定投票时间
- 支持弃权
- 支持公开结果查询
- 在实现上保持简洁，便于报告说明和答辩展示

## 3. 状态变量

### 3.1 基础信息

- `owner`：合约拥有者，通常为部署者
- `electionTitle`：投票标题
- `startTime` / `endTime`：投票起止时间

### 3.2 统计信息

- `totalVotes`：有效投票数
- `totalAbstentions`：弃权数
- `totalRegisteredVoters`：已登记选民总数

### 3.3 权限与投票状态

- `isRegisteredVoter[address]`：地址是否具有投票资格
- `hasVoted[address]`：地址是否已经参与过投票

### 3.4 候选项存储

合约使用 `mapping(uint256 => Candidate)` 保存候选项，每个候选项包含：

- `name`
- `voteCount`

## 4. 主要函数

### 4.1 构造函数

部署时接收：

- 投票标题
- 候选项数组
- 起止时间
- 初始允许投票的钱包地址数组

构造函数会完成候选项初始化和首批白名单登记。

### 4.2 `registerVoter()` 与 `batchRegisterVoters()`

只有拥有者可以调用，用于后续扩展白名单选民。  
其中批量接口设置了上限，避免一次登记过多地址造成 gas 失控。

### 4.3 `vote(uint256 candidateId)`

允许合规选民在投票有效期内为某个候选项投票。  
函数会检查：

- 投票是否已经开始
- 投票是否已经结束
- 调用者是否在白名单中
- 调用者是否已经投过票
- 候选项编号是否合法

### 4.4 `abstain()`

允许合规选民在投票有效期内弃权。  
弃权同样计入“已参与”，因此同一地址弃权后不能再投票。

### 4.5 查询函数

- `candidateCount()`：返回候选项数量
- `getCandidate()`：返回单个候选项名称和票数
- `getElectionStatus()`：返回 `PENDING`、`ACTIVE` 或 `ENDED`
- `getAllResults()`：投票结束后返回全部结果
- `getWinner()`：投票结束后返回赢家信息或平票状态

## 5. 安全机制

### 5.1 自定义错误

合约使用多个 `error` 定义代替长字符串 `require`，既能节省 gas，也让逻辑语义更清晰，例如：

- `NotOwner`
- `AlreadyVoted`
- `ElectionNotStarted`
- `ElectionEnded`
- `InvalidCandidateId`

### 5.2 修饰器

- `onlyOwner`：限制管理员操作
- `duringElection`：限制仅在投票进行中调用
- `afterElection`：限制仅在投票结束后查看结果

## 6. 在系统中的作用

本项目采取“链下管理 + 链上记票”的混合架构。  
其中 `SecureVoting.sol` 承担的是“可信结果层”的角色，它保证投票记录和最终统计可被公开验证，是整个系统可信性的核心来源。
