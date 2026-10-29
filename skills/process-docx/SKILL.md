---
name: process-docx
description: |
  Used to read, inspect, create, and edit .docx documents (Word), including text, tables, images, styles, headers and footers, and template-based generation. Should be used if you're working with Word documents.
  用于读取、检查、创建和编辑 .docx（Word）文档，涵盖文本、表格、图片、样式、页眉页脚与模板填充。需在处理 Word 文件时使用。
---

# Process DOCX - Word 文档处理

你可能正准备读写 `.docx` 文档。这个技能提供三层能力：
一套可以直接调用的 Python 原语、一个覆盖常见操作的命令行入口、以及一份 OOXML 层面的扩展指南。常规任务不要从零写脚本，先看这里的接口。

## 先判断文件

### 支持的格式

`.docx` 是主要支持格式。`.docm` 可能可以打开，但本技能不处理宏，保存前要确认宏是否仍然保留。

`.doc` 是旧的二进制格式，`python-docx` 不支持。先用 Word 的“另存为”或 LibreOffice 的 `--convert-to docx` 转成 `.docx`，再进入本技能。

### 限制与约束

加密文档、权限受限文档、需要接受修订或处理复杂域代码的文档，不在核心能力范围内。`IMPLEMENTATION.md` 给出了这些方向的入口，但不要假装它们已经被完整封装。

`python-docx` 是文档对象库，不是排版引擎。它能读写内容和大部分格式，不能可靠计算页数、分页和最终打印效果。涉及版式验收时，用 Word 或 LibreOffice 实际打开并渲染。
它能保留大量未知 XML，但不等于完整支持所有 Word 特性。宏、修订记录、复杂域、内容控件、脚注尾注、浮动图和文本框通常需要额外的 XML 处理。
遇到这些内容时，先确认目标是只读、只替换文字、保留原样，还是要重建结构。目标不同，做法不同。

## 依赖与自举

核心依赖只有 `python-docx`，它会自动带入 `lxml` 和 `typing_extensions`。版本清单在 `scripts/requirements.txt`，要求 Python 3.9+ 与 `python-docx>=1.1,<2`。

第一次导入 `docxkit` 或运行 CLI 时，会先检查当前 Python 环境里有没有可用的 `python-docx`。如果没有，就安装到：

```text
<此SKILL目录>\scripts\.deps
```

安装完成后，`.deps` 会被插到 `sys.path` 前面。`.deps` 已在 `.gitignore` 中，可以随时删除，下次会自动重装。全局环境已有合适版本时直接使用全局版本，不重复下载。

不建议手动执行 `pip install python-docx`。需要确认依赖状态或排障时运行：

```text
python <此SKILL目录>\scripts\docx_tool.py doctor
```

它会输出 Python 版本、`python-docx` 版本、实际导入路径、来源是全局还是本地 `.deps`、`lxml` 版本，以及 `.deps` 的绝对路径。

如果环境离线且 `.deps` 不存在，自举会失败。此时要么使用已经装好 `python-docx` 的 Python 环境，要么把一份可用的 `.deps` 目录连同 `scripts` 一起复制过去。

## 调用方式

### 命令行

所有命令都从 `docx_tool.py` 进入，路径按实际技能目录替换：

```text
python <此SKILL目录>\scripts\docx_tool.py doctor
python <此SKILL目录>\scripts\docx_tool.py inspect input.docx
python <此SKILL目录>\scripts\docx_tool.py inspect input.docx --json
python <此SKILL目录>\scripts\docx_tool.py text input.docx -o output.txt
python <此SKILL目录>\scripts\docx_tool.py replace input.docx "旧文字" "新文字" -o output.docx
python <此SKILL目录>\scripts\docx_tool.py new output.docx --template template.docx
python <此SKILL目录>\scripts\docx_tool.py images input.docx -o assets
python <此SKILL目录>\scripts\docx_tool.py selftest
```

`replace` 默认写到 `<原名>.replaced.docx`，不会覆盖输入文件。
`inspect` 默认只输出摘要，加 `--json` 才输出完整结构。
`selftest` 会实际生成、保存、重新打开并检查一份文档，适合在陌生环境里先跑一遍。

### Python

```python
import sys
sys.path.insert(0, r"<此SKILL目录>\scripts")

import docxkit

doc = docxkit.open_docx("input.docx")
print(docxkit.extract_text(doc))

docxkit.replace_text(doc, "旧文字", "新文字")
docxkit.save_docx(doc, "output.docx")
```

`docxkit` 在导入时完成依赖自举。脚本或 notebook 只需要把 `scripts` 目录放进 `sys.path`，不需要重复处理 pip。

命令行 `replace` 默认写到新文件，库函数不会阻止覆盖。需要原地修改时，先复制一份，再覆盖保存。不要在没有备份的情况下对唯一副本做破坏性编辑。

## 常用工作流

1. 先盘点，再修改：先运行 `inspect` 看节、段落、表格、图片和批注的数量，再用 `text` 看正文。确认结构后再写修改脚本，比直接按段落下标改要稳。
   `inspect --json` 适合让机械化读取结构化结果。

2. 替换文字：`replace_text` 处理的是字面文本，不是正则。它会跨 run 查找，并尽量保留第一个 run 的字符格式。替换不会跨段落，也不会进入嵌套表格、脚注或尾注。
   需要正则替换时，先用 `extract_text` 确认文本，再决定是否重建段落；重建会丢失原有 run 级格式。

3. 从模板生成：用 `new_docx(template)` 打开模板，用 `duplicate_paragraph` 复制样板段落，用 `replace_text` 填占位符，最后 `save_docx` 到新路径。
   模板里的样式、页眉页脚和节属性会保留。需要复制表格时，直接深拷贝 `table._tbl` 或按模板重建；`IMPLEMENTATION.md` 有说明。

4. 表格：`read_table` 返回二维字符串列表，`write_table` 写入已有表格，`add_table` 新建表格。单元格文本用 `cell.text` 读写。
   需要保留单元格内多段格式时，直接操作 `cell.paragraphs`。

5. 图片：`extract_images` 会把 `word/media/` 下的图片导出到指定目录。添加图片直接用 python-docx 的 `doc.add_picture(path, width=...)`。
   需要浮动图、文字环绕或精确锚点时，要写 DrawingML，`IMPLEMENTATION.md` 给了入口。

6. 页眉页脚与版式：`set_header_text` 和 `set_footer_text` 修改节的第一段页眉页脚。`set_page_margins` 与 `set_page_size` 接受厘米值。
   多节文档要逐节处理，注意 `is_linked_to_previous`；链接到上一节的页眉不会单独保存内容。

7. 批注清理：`remove_comments(doc)` 删除批注锚点、批注引用以及 comments 相关的 part 和 relationship。它适合清理模板或协作稿，不适合保留批注内容做审计。
   需要查看批注数量和作者时用 `inspect_docx` 的 `comments` 字段。

## API 速查

| 需求                 | 调用                                                                                    |
| -------------------- | --------------------------------------------------------------------------------------- |
| 打开、新建、保存     | `open_docx` / `new_docx` / `save_docx`                                                  |
| 按顺序遍历段落和表格 | `iter_blocks`                                                                           |
| 提取纯文本           | `extract_text`                                                                          |
| 结构盘点             | `inspect_docx`                                                                          |
| 字面替换             | `replace_text`                                                                          |
| 段落增删复制         | `add_paragraph` / `insert_paragraph_after` / `delete_paragraph` / `duplicate_paragraph` |
| 表格读写             | `read_table` / `write_table` / `add_table`                                              |
| 字体与间距           | `set_run_font` / `set_paragraph_spacing`                                                |
| 页面设置             | `set_page_margins` / `set_page_size`                                                    |
| 页眉页脚             | `set_header_text` / `set_footer_text`                                                   |
| 图片导出             | `extract_images`                                                                        |
| 底纹与边框           | `set_paragraph_shading` / `set_paragraph_border` / `set_cell_shading`                   |
| 批注清理             | `remove_comments`                                                                       |
| 原始 XML             | `dump_xml` / `paragraph_list_level`                                                     |

完整的参数、返回值和异常见 `API.md`。

## 自定义功能扩展

这份技能文档及其附件通常而言是只读的，不应该用户未显式说明时进行修改。

如果需要自定义能力或扩展其他能力，以便满足实际工作需求，强烈建议将本技能拷贝一份副本，放在临时目录中，然后在副本中进行能力的修改。

先把问题分成三类：

1. 内容和常规格式：直接用 `docxkit` 的高层函数，或者 python-docx 的 `Document`、`Paragraph`、`Run`、`Table`、`Cell` 对象。
2. python-docx 没有暴露的属性：用 `OxmlElement` 和 `qn` 操作 `paragraph._p`、`run._r`、`table._tbl`、`cell._tc`。`docxkit.ooxml` 里已经有底纹、边框和中文字体的样板。
3. 包级结构：批注、脚注、编号定义、图片关系、内容控件等，需要直接处理 `word/*.xml` 和 `_rels`。先读 `IMPLEMENTATION.md`，不要凭元素名猜 schema。

新增能力时按这个顺序落点：

- 内容读写和对象操作放 `docxkit/core.py`；
- 结构盘点、统计和 JSON 摘要放 `docxkit/inspection.py`；
- 需要直接写 OOXML 的小工具放 `docxkit/ooxml.py`；
- 在 `docxkit/__init__.py` 导出公共名字；
- 在 `API.md` 补签名，在 `selftest.py` 补一条能跑通的验证。

改动后用 `python scripts/docx_tool.py selftest` 验证，再找一份真实文档跑 `inspect` 和 `text`。涉及版式时，用 Word 或 LibreOffice 打开成品检查。

<!-- End of skill process-docx, written by Harry Huang -->
