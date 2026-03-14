# 马尔科夫链转移概率矩阵分析工具

该项目提供一个纯 Python 命令行程序，可用数学方法分析输入的马尔科夫链模型，并输出转移概率矩阵。

## 功能

- `sequence` 模式：根据观测到的状态序列估计转移概率矩阵
- `counts` 模式：根据转移计数或权重归一化生成转移概率矩阵
- `matrix` 模式：校验已有转移概率矩阵，也可自动归一化
- 输出每一行的概率和，并识别吸收态

## 运行方式

```powershell
python .\markov_chain_analyzer.py -i .\sample_sequence.json
```

输出 JSON：

```powershell
python .\markov_chain_analyzer.py -i .\sample_counts.json --format json
```

不使用文件，直接在终端输入 JSON：

```powershell
python .\markov_chain_analyzer.py
```

## 输入格式

### 1. 基于状态序列估计

```json
{
  "mode": "sequence",
  "states": ["晴", "阴", "雨"],
  "sequence": ["晴", "阴", "晴", "雨", "雨", "阴", "晴"]
}
```

### 2. 基于转移计数归一化

```json
{
  "mode": "counts",
  "states": ["A", "B", "C"],
  "transitions": [
    {"from": "A", "to": "A", "value": 2},
    {"from": "A", "to": "B", "value": 3},
    {"from": "B", "to": "C", "value": 4},
    {"from": "C", "to": "A", "value": 1}
  ]
}
```

### 3. 校验已有矩阵

```json
{
  "mode": "matrix",
  "states": ["S1", "S2"],
  "matrix": [
    [0.7, 0.3],
    [0.4, 0.6]
  ]
}
```

如果输入的是计数矩阵而不是概率矩阵，可加上 `normalize: true`：

```json
{
  "mode": "matrix",
  "states": ["S1", "S2"],
  "normalize": true,
  "matrix": [
    [7, 3],
    [4, 6]
  ]
}
```

## 输出说明

- `transition_probability_matrix`：转移概率矩阵
- `row_sums`：每一行概率之和，正常应为 `1`
- `absorbing_states`：吸收态列表

## 后续扩展建议

如果你后面想接入 API，可以在外层增加一个 Web API，例如：

- `FastAPI`：接收 JSON，返回矩阵计算结果
- `Flask`：适合做轻量接口

当前版本已经把核心计算逻辑封装为函数，后续改造成 API 服务时可直接复用。
