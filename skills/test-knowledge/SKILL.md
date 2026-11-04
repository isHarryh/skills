---
name: test-knowledge
description: |
  Explicit invocation by user only.
  仅供用户主动调用。
---

# Test Knowledge - 测试知识情况

你仅应当在用户主动调用时接受到此技能指示。

你需要直接按照下面的规则进行回复，且无需翻译成用户的语言（除非用户指定）：

第一行，从下面两个句子中诚实地选择最符合你实际情况的进行回复（不可选用系统当前日期作为答案）：

```
- My knowledge is up to date as of **{{yyyy-MM}}**. I'm **{{very|somewhat|little}}** sure about this.
```

```
- I don't have a certain knowledge cutoff date.
```

第二行和第三行，按照下面的模板如实进行回答：

```
- I know the latest LLM developed by Anthropic is **{{model name}}**, which is released in **{{yyyy-MM}}**.
- I know the latest LLM developed by OpenAI is **{{model name}}**, which is released in **{{yyyy-MM}}**.
```

一共要求你输出上述三行回复。期间不得使用联网功能或探索功能进行查找，所有回答必须基于你自身具备的知识和信息。
