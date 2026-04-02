# `app/models.py` 模块说明

## 1. 模块定位

`app/models.py` 定义了系统的数据库数据结构，是后端的数据模型层。  
该模块使用 SQLAlchemy ORM，将 Python 对象与数据库表进行映射。

## 2. 主要实体

### 2.1 `User`

表示平台用户，主要字段包括：

- `id`：用户主键
- `username`：唯一用户名
- `password_hash`：加密后的密码摘要
- `wallet_address`：绑定的钱包地址
- `created_at`：注册时间

关联关系：

- `created_polls`：该用户创建的投票
- `votes`：该用户的投票记录

### 2.2 `Poll`

表示一个投票任务，主要字段包括：

- `topic`：投票主题
- `starts_at` / `ends_at`：开始与结束时间
- `options_json`：候选项列表，使用 JSON 字符串存储
- `allowed_user_ids_json`：允许投票的用户 ID 列表，使用 JSON 字符串存储
- `created_by_user_id`：创建者用户 ID
- `chain_contract_address`：链上合约地址
- `chain_deploy_tx_hash`：部署交易哈希
- `chain_network_name`：链名称
- `chain_chain_id`：链 ID
- `chain_deploy_block`：部署区块高度
- `chain_error`：最近一次链交互错误信息
- `chain_deployed_at`：合约部署时间

关联关系：

- `creator`：投票创建者
- `votes`：本地同步到数据库的投票记录

### 2.3 `PollVote`

表示本地同步的一条投票行为记录，主要字段包括：

- `poll_id`：所属投票
- `voter_id`：投票用户
- `selected_option_index`：选择的候选项编号
- `abstained`：是否弃权
- `chain_tx_hash`：链上交易哈希
- `created_at`：记录创建时间

该表通过唯一约束保证“同一用户在同一投票下只能有一条本地同步记录”。

## 3. 设计特点

### 3.1 JSON 字段简化结构

`Poll` 没有单独拆出“候选项表”和“允许用户关联表”，而是把：

- 候选项列表
- 允许用户 ID 列表

直接存成 JSON 字符串。  
这种做法实现简单，适合课程项目、原型系统和中小规模演示。

### 3.2 链上信息与链下信息并存

`Poll` 中既保存应用层信息，也保存链上部署结果。  
这样可以做到：

- 网页快速定位对应的合约地址
- 生成区块浏览器链接
- 用部署区块高度做事件查询起点
- 对链上异常进行本地记录

### 3.3 ORM 关系明确

通过 `relationship()`，系统可以方便地实现：

- 通过用户查询其创建的投票
- 通过投票查询其创建者
- 通过投票查询已同步的投票记录

这使得后续页面渲染和业务查询都更自然。

## 4. 辅助方法

### 4.1 `naive_utc_now()`

返回不带时区的 UTC 当前时间，保证数据库中统一使用 UTC 时间存储。

### 4.2 `Poll.get_options()` / `Poll.set_options()`

负责在 Python 列表与数据库中的 JSON 字符串之间转换候选项。

### 4.3 `Poll.get_allowed_user_ids()` / `Poll.set_allowed_user_ids()`

负责在 Python 列表与数据库中的 JSON 字符串之间转换允许用户列表。

## 5. 在系统中的作用

这个模块是整个系统的数据基础。  
它决定了：

- 用户如何被存储
- 投票如何被表示
- 链上结果如何在链下进行索引与同步

没有这个模块，业务逻辑就无法和数据库形成稳定映射。
