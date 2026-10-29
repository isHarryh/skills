# API 手册

`docxkit` 的公共 API 都从包根导出。调用前把 `scripts` 目录放进 `sys.path`：

```python
import sys
sys.path.insert(0, r"<此SKILL目录>\scripts")

import docxkit
```

导入包时会自动检查 `python-docx`，必要时安装到 `scripts/.deps`。需要查看依赖状态时调用 `doctor()`。

## 依赖

### `doctor() -> dict`

返回当前 Python 与依赖信息，字段包括：

- `python`、`executable`、`platform`
- `version`、`path`、`source`，其中 `source` 为 `global` 或 `local`
- `deps_dir`、`deps_exists`
- `lxml`、`requirements`

```python
info = docxkit.doctor()
print(info["version"], info["path"])
```

### `ensure_deps(verbose=False) -> dict`

确保 `python-docx` 可用，返回与 `doctor()` 相同的包信息。通常不需要直接调用，导入包和 CLI 会自动执行。

### `DEPS_DIR`

本地依赖目录的 `Path`，即 `scripts/.deps`。

## 打开与保存

### `open_docx(path) -> Document`

打开 `.docx`。传入 `.doc` 会抛出 `ValueError`，文件不存在会抛出 `FileNotFoundError`。

### `new_docx(template=None) -> Document`

创建空白文档；传入模板路径时以模板为起点。模板中的样式、节、页眉页脚会保留。

### `save_docx(doc, path) -> Path`

保存文档并自动创建父目录，返回目标路径。

```python
doc = docxkit.new_docx("template.docx")
docxkit.save_docx(doc, "out/result.docx")
```

## 读取与遍历

### `iter_blocks(doc) -> Iterator[Paragraph | Table]`

按正文顺序产出段落和表格。会穿过内容控件 `w:sdt` 和 `w:customXml` 包装，不遍历单元格里的嵌套表格。

```python
for block in docxkit.iter_blocks(doc):
    if isinstance(block, docxkit.Paragraph):
        print("P:", block.text)
    else:
        print("T:", len(block.rows), len(block.columns))
```

### `extract_text(source, *, include_tables=True, include_headers=False, include_footers=False, keep_empty=False) -> str`

提取纯文本。表格按行输出，单元格之间用制表符分隔。`source` 可以是路径或 `Document`。

### `read_table(table) -> list[list[str]]`

读取表格单元格文本。

### `inspect_docx(source, *, max_paragraphs=200, text_chars=160) -> dict`

返回结构化摘要，字段包括：

- `file`：路径与字节数
- `core`：标题、作者、创建时间等核心属性
- `sections`：页面尺寸、页边距、方向、页眉页脚预览
- `styles`：样式名、类型、是否内置
- `paragraphs_total`、`paragraphs_truncated`、`paragraphs`
- `tables`：行列数、首行、前三行预览
- `images`：`word/media/` 下的图片 part、类型、字节数
- `comments`：批注数量和作者

`paragraphs` 只保留前 `max_paragraphs` 条，单段文本截到 `text_chars` 个字符。完整正文用 `extract_text`。

### `list_styles(doc) -> list[dict]`

返回样式的 `name`、`type`、`builtin`。

## 写入与编辑

### `add_paragraph(doc, text="", *, style=None) -> Paragraph`

在正文末尾添加段落。

### `add_heading(doc, text, *, level=1) -> Paragraph`

添加标题段落。`level` 从 1 开始。

### `add_page_break(doc) -> Paragraph`

添加分页符。

### `insert_paragraph_after(paragraph, text="", *, style=None) -> Paragraph`

在指定段落后面插入新段落。

### `delete_paragraph(paragraph) -> None`

从父容器删除段落。

### `duplicate_paragraph(paragraph, text=None) -> Paragraph`

复制段落并插到原段落后面。传入 `text` 时，克隆会保留第一个 run 的字符格式，但会移除超链接、书签等行内内容，只留下新文本。

### `replace_text(doc, old, new, *, count=-1, include_tables=True, include_headers=False) -> int`

按字面文本替换，返回替换次数。

- 支持跨 run 匹配，尽量保留第一个 run 的格式。
- 不跨段落，不进入嵌套表格、脚注、尾注。
- `count=-1` 表示全部替换，正数表示最多替换多少次。
- `include_tables=True` 会处理表格单元格中的段落。
- `include_headers=True` 会处理未链接到上一节的页眉和页脚。

```python
count = docxkit.replace_text(doc, "{{name}}", "Alice")
print(count)
```

### `add_table(doc, data, *, style="Table Grid") -> Table`

按二维数据创建表格并填入。`style=None` 表示不设置表格样式。样式不存在时抛出 `ValueError`。

### `write_table(table, data) -> None`

写入已有表格。数据不能超过表格的行列数。

## 格式与版式

### `set_run_font(run, *, name=None, size=None, bold=None, italic=None, underline=None, color=None, east_asia=None, subscript=None, superscript=None) -> None`

设置字符格式。`size` 可以是磅值，也可以是 `docx.shared.Length`。`color` 接受 `"FF0000"` 或 `"#FF0000"`。`east_asia` 用来设置 `w:eastAsia`，中文环境里不要只设 `name`。

### `set_paragraph_spacing(paragraph, *, before=None, after=None, line=None) -> None`

设置段前、段后和行距。`before`、`after` 单位是磅；`line` 可以是倍数，也可以是 `Length`。

### `set_page_margins(section, *, top, bottom, left, right) -> None`

按厘米设置页边距。

### `set_page_size(section, *, width, height) -> None`

按厘米设置页面宽高。横向页面还需要设置 `section.orientation`，这个函数只改尺寸。

### `set_header_text(section, text) -> None`

设置某节第一段页眉。会自动取消“链接到上一节”。

### `set_footer_text(section, text) -> None`

设置某节第一段页脚。

### `set_paragraph_shading(paragraph, fill) -> None`

给段落加纯色底纹，`fill` 是十六进制颜色。

### `set_paragraph_border(paragraph, *, top=False, bottom=False, left=False, right=False, sz=8, color="000000", space=4) -> None`

设置段落边框。`sz` 的单位是八分之一磅。调用会替换已有边框；全部为 `False` 时清除边框。

### `set_cell_shading(cell, fill) -> None`

给表格单元格加纯色底纹。

## 图片与批注

### `extract_images(source, out_dir) -> list[Path]`

把 `word/media/` 下的图片导出到目录，返回写入的文件路径。不会导出 `docProps/thumbnail` 这类文档缩略图。

### `remove_comments(doc) -> int`

删除批注锚点、批注引用和 comments 相关 part，返回删除的批注引用数量。适合清理模板或协作稿；需要保留批注内容时不要调用。

## OOXML 辅助

### `dump_xml(obj, *, pretty=True, max_chars=None) -> str`

打印 `Document`、`Paragraph`、`Run`、`Table`、`Cell`、`Section` 或 lxml 元素的 OOXML。调试格式问题时先用它看真实节点。

### `paragraph_list_level(paragraph) -> int | None`

读取段落的 `w:numPr/w:ilvl`，返回编号层级；段落自身没有编号时回退到样式定义。普通段落返回 `None`。

## CLI

```text
python scripts/docx_tool.py doctor [--json]
python scripts/docx_tool.py inspect file.docx [--json] [--max-paragraphs N] [--text-chars N]
python scripts/docx_tool.py text file.docx [-o out.txt] [--no-tables] [--headers] [--footers] [--keep-empty]
python scripts/docx_tool.py replace file.docx OLD NEW [-o out.docx] [--count N] [--no-tables] [--headers]
python scripts/docx_tool.py new out.docx [--template template.docx]
python scripts/docx_tool.py images file.docx -o assets
python scripts/docx_tool.py selftest
```

`replace` 没有指定 `-o` 时写入 `<原名>.replaced.docx`，不会覆盖输入。`selftest` 返回非零退出码表示环境或 API 有问题。

## 错误与边界

- `.doc` 不支持，先转 `.docx`。
- `replace_text` 只做字面匹配，不支持正则。
- 替换不跨段落，不处理脚注、尾注和嵌套表格。内容控件里的顶层段落会被遍历，但控件属性不会改变。
- `python-docx` 不计算分页，页码、目录和最终版式要用 Word 或 LibreOffice 渲染确认。
- 复杂域、修订记录、浮动图、文本框和宏未封装；需要时按 `IMPLEMENTATION.md` 直接处理 OOXML。
