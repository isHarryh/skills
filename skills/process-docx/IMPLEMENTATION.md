# 实现指南

这份文档面向需要继续扩展 `docxkit` 的 agent。目标不是把 OOXML 讲全，而是让你知道该在哪一层动手，以及哪些坑最常出现。

## .docx 的包结构

`.docx` 是一个 ZIP 包。把扩展名改成 `.zip` 或用 `zipfile` 打开，会看到类似结构：

```text
[Content_Types].xml
_rels/.rels
word/document.xml
word/styles.xml
word/numbering.xml
word/settings.xml
word/theme/theme1.xml
word/header1.xml
word/footer1.xml
word/footnotes.xml
word/endnotes.xml
word/comments.xml
word/media/image1.png
word/_rels/document.xml.rels
docProps/core.xml
```

`word/document.xml` 存正文，`styles.xml` 存样式，`numbering.xml` 存编号定义，`comments.xml` 存批注内容。`word/_rels/document.xml.rels` 用关系 ID 把正文中的引用映射到图片、页眉页脚、超链接等 part。`[Content_Types].xml` 声明每个 part 的 MIME 类型。

新增 part 时通常要同时处理三件事：写入 part、补 relationship、补 content type。只写 XML 文件而不补关系，Word 打开时会忽略或报修复。

## python-docx 的对象模型

常用对象和它们的 XML 入口：

| 对象 | XML 入口 | 常用属性 |
| --- | --- | --- |
| `Document` | `doc.element` | `paragraphs`、`tables`、`sections`、`styles`、`part` |
| `Paragraph` | `paragraph._p` | `text`、`runs`、`style`、`paragraph_format` |
| `Run` | `run._r` | `text`、`bold`、`italic`、`font` |
| `Table` | `table._tbl` | `rows`、`columns`、`cell(r, c)`、`style` |
| `Cell` | `cell._tc` | `text`、`paragraphs`、`tables` |
| `Section` | `section._sectPr` | `header`、`footer`、页面尺寸、页边距 |
| `Part` | `part.partname`、`part.blob` | `content_type`、`rels` |

`Document.paragraphs` 只包含正文顶层段落，不包含表格单元格、页眉页脚和内容控件里的段落。需要按文档顺序遍历时用 `iter_blocks`，它基于 `doc.element.body` 的子节点派发 `Paragraph` 和 `Table`。

`Paragraph.text` 是只读的。设置整段文字要清空 `w:r` 再 `add_run`；直接改 `paragraph.text` 不会生效。

## 单位和 schema 顺序

OOXML 里的长度单位不统一：

- `w:sz`、`w:szCs`：半磅。12 磅是 `24`。
- `w:spacing` 的 `before`、`after`、`line`：二十分之一磅，也叫 twip。
- `w:ind`：twip。
- `w:pgSz`、`w:pgMar`：twip。
- DrawingML 的图片尺寸：EMU。
- python-docx 的 `Pt`、`Cm`、`Inches`、`Emu` 会帮你换算。

`w:pPr` 和 `w:rPr` 的子元素有固定顺序。顺序错了，Word 可能忽略节点或提示修复。用 python-docx 的 `get_or_add_*` 和 `insert_element_before`，不要随手 `append`。

例如给段落加底纹，`w:shd` 必须排在 `w:tabs`、`w:spacing`、`w:ind`、`w:jc`、`w:rPr` 之前。`docxkit.ooxml.set_paragraph_shading` 就是按这个顺序插入的。

## 文本与 run

Word 经常把一段文字拆成多个 `w:r`。原因可能是局部加粗、拼写检查、修订记录、语言标记，甚至只是编辑历史。`paragraph.text` 会把这些 run 拼起来，但不会告诉你边界。

跨 run 替换的基本做法是：

1. 取段落中所有有文本的 run，拼成完整字符串。
2. 在完整字符串里找到目标区间。
3. 把新文本写进起始 run，清空中间 run，保留结束 run 的后缀。
4. 重新拼字符串，从新位置继续找下一次匹配。

`docxkit.core.replace_text` 就是这么做的。它保留起始 run 的格式，因此替换后的文字通常不会突然变成另一种字体。代价是，如果目标区间跨过不同格式的 run，替换后的格式会以起始 run 为准。

需要注意两点：

- `Paragraph.runs` 只返回 `w:p` 的直接 `w:r` 子节点，不包含 `w:hyperlink` 里的 run。需要处理超链接文字时，用 `paragraph._p.iter(qn("w:r"))` 自己遍历。
- 替换不要跨段落。跨段替换会把段落结构和样式搅乱，通常应该先拆分任务，再逐段处理。

## 段落复制与模板填充

复制段落的可靠做法是深拷贝 XML，再插到原段落后面：

```python
import copy
from docx.text.paragraph import Paragraph

new_p = copy.deepcopy(paragraph._p)
paragraph._p.addnext(new_p)
new_para = Paragraph(new_p, paragraph._parent)
```

如果只想保留段落格式、换掉文字，可以保留 `w:pPr` 和第一个 run 的 `w:rPr`，删掉其余子节点，再添加新 run。`docxkit.duplicate_paragraph` 已经封装了这个动作。

复制带书签、批注或超链接的段落时要小心。书签 ID、批注 ID 和关系 ID 都可能重复。模板填充场景通常不需要这些行内对象，直接清掉更安全。

## 表格

`table.rows` 和 `table.columns` 给出逻辑网格。合并单元格后，多个网格位置会指向同一个 `w:tc`；可以用 `cell._tc` 的身份判断是否重复。

`cell.text` 会把单元格内容替换成一个段落。需要保留单元格里的多段文字或局部格式时，操作 `cell.paragraphs`。

常见 XML 位置：

- 表格样式：`w:tblPr/w:tblStyle`。
- 列宽：`w:tblGrid/w:gridCol` 和单元格 `w:tcW`。只改 `column.width` 有时不够，最好同时改单元格宽度。
- 单元格底纹：`w:tcPr/w:shd`。
- 单元格边框：`w:tcPr/w:tcBorders`。
- 重复表头：`w:trPr/w:tblHeader`。
- 行高：`w:trPr/w:trHeight`。

嵌套表格在 `cell.tables` 里，不在 `doc.tables` 里。需要递归遍历时自己写栈。

复制整张表格可以直接深拷贝 `table._tbl`：

```python
import copy
from docx.table import Table

new_tbl = copy.deepcopy(table._tbl)
table._tbl.addnext(new_tbl)
new_table = Table(new_tbl, table._parent)
```

如果表格里有图片，关系 ID 仍然指向原图片，复制通常可以正常工作。表格里有书签或批注时，ID 可能重复，需要重新分配或删除这些行内对象。

## 样式与字体

优先用样式，不要给每个 run 写一遍直接格式。直接格式会覆盖样式，后续改模板很麻烦。

内置样式名通常是英文：`Normal`、`Heading 1`、`Table Grid`。自定义模板可能使用本地化名称或自己的 styleId。`doc.styles` 按名称索引，遇到不存在的名称会抛 `KeyError`。

`run.font.name` 只设置 `w:rFonts` 的 `ascii` 和 `hAnsi`。中文字体还要设置 `w:eastAsia`：

```python
from docx.oxml.ns import qn

rpr = run._r.get_or_add_rPr()
rfonts = rpr.get_or_add_rFonts()
rfonts.set(qn("w:eastAsia"), "宋体")
```

主题字体用 `w:asciiTheme`、`w:hAnsiTheme`、`w:eastAsiaTheme`，不要和显式字体名混用。

## 节、页眉和页脚

`doc.sections` 返回节列表。每节有自己的页面尺寸、页边距、页眉页脚引用。

`section.header.is_linked_to_previous` 为 `True` 时，这一节沿用上一节的页眉。把它设为 `False` 才会创建独立页眉。读页眉内容前先检查 `w:headerReference` 是否存在，避免为了读取而凭空创建空页眉。

首页不同、奇偶页不同分别由 `section.different_first_page_header_footer` 和 `document.settings.odd_and_even_pages_header_footer` 控制。对应的 part 是 `first_page_header`、`even_page_header` 等。

页码是域，不是普通文本。简单页码可以用 `w:fldSimple w:instr="PAGE"`；复杂域要写 `w:fldChar` 的 begin、separate、end 三个 run。域结果需要 Word 更新，`python-docx` 不会计算页码。

## 图片与关系

`doc.add_picture` 添加的是内联图，XML 结构是 `w:drawing/wp:inline`。尺寸单位是 EMU，常用 `width=Cm(...)` 控制。

浮动图使用 `wp:anchor`，包含 `wp:positionH`、`wp:positionV` 和 `wp:wrap*`。python-docx 没有高层 API，需要直接构造 DrawingML 或复制已有锚点再改属性。

图片文件在 `word/media/`，正文通过 `a:blip r:embed="rId..."` 引用。替换图片有两种做法：改 relationship 的目标 part，或新增图片 part 后改 `r:embed`。改完要确认旧的 media part 是否还被其他位置引用，避免误删。

`docxkit.extract_images` 只导出 `word/media/` 下的图片，不导出 `docProps/thumbnail` 缩略图。

## 批注

批注由三部分组成：

- `word/comments.xml` 里的 `w:comment`，带 `w:id`、作者、时间。
- 正文里的 `w:commentRangeStart`、`w:commentRangeEnd`，用 `w:id` 对应批注。
- 正文里的 `w:commentReference`，通常在一个 run 里。

删除批注要同时清掉锚点、引用、comments part 和相关 relationship。只删 `comments.xml` 会留下悬空引用，Word 可能报修复。`docxkit.remove_comments` 处理了这条链路。

新增批注更麻烦：要分配唯一 ID、写 comments part、补 content type 和 relationship、在正文插入成对的 range 标记和 reference run。没有明确需求时，不建议把新增批注封装成高层 API。

## 多级编号

编号定义在 `word/numbering.xml`：

- `w:abstractNum` 定义一套多级格式，包含 `w:lvl`、`w:numFmt`、`w:lvlText`、`w:start`。
- `w:num` 是实际使用的编号实例，指向某个 `w:abstractNum`。
- 段落用 `w:pPr/w:numPr/w:numId` 和 `w:ilvl` 引用编号实例与层级。

重启编号通常要新建一个 `w:num`，让它指向同一个 `w:abstractNum`，再用 `w:lvlOverride/w:startOverride` 指定起始值。不要直接改已有 `w:num` 的起始值，那会影响所有引用它的段落。

`paragraph_list_level` 只读取层级，不判断编号格式。需要完整列表语义时，自己解析 `numbering.xml`。

## 超链接、书签、域和目录

超链接有两种：

- 外部链接：`w:hyperlink r:id="rId..."`，relationship 的 `TargetMode` 是 `External`。
- 内部链接：`w:hyperlink w:anchor="bookmarkName"`。

书签用成对的 `w:bookmarkStart` 和 `w:bookmarkEnd`，`w:id` 必须唯一。复制带书签的内容时，要重新分配 ID。

域用 `w:fldSimple` 或复杂域的 `w:fldChar` 三段式。目录是 `TOC` 域，页码是 `PAGE` 或 `NUMPAGES` 域。域的结果是缓存文本，必须让 Word 更新。`python-docx` 不会计算目录，也不会分页。

## 修订、内容控件和替代内容

修订记录用 `w:ins`、`w:del`、`w:moveFrom`、`w:moveTo` 等节点。接受或拒绝修订需要移动文字、合并 run、清理标记，不能只删节点。没有明确需求时，先保留原样。

内容控件用 `w:sdt`，内容在 `w:sdtContent` 里。`iter_blocks` 会穿过这层包装，但不会把控件属性暴露成高层对象。需要改占位符或绑定数据时，直接读 `w:sdtPr`。

`mc:AlternateContent` 常出现在图形、文本框和兼容内容里。选择 `mc:Choice` 还是 `mc:Fallback` 要看目标 Word 版本，不要同时保留两份可编辑内容。

## 旧格式与渲染

`.doc` 转 `.docx`：

```text
soffice --headless --convert-to docx --outdir out input.doc
```

Windows 上也可以用 Word COM：

```powershell
$word = New-Object -ComObject Word.Application
$doc = $word.Documents.Open("input.doc")
$doc.SaveAs2("output.docx", 16)
$doc.Close($false)
$word.Quit()
```

转 PDF 或检查分页：

```text
soffice --headless --convert-to pdf --outdir out input.docx
```

Word COM 的 `ExportAsFixedFormat` 也可以导出 PDF。渲染后再看页数、分页、图片位置和字体替换，不要用 `python-docx` 猜这些结果。

## 调试方法

先看 XML：

```python
print(docxkit.dump_xml(paragraph))
print(docxkit.dump_xml(run))
```

需要看整个包时，把 `.docx` 复制到临时目录，改名为 `.zip` 后解压，重点检查 `word/document.xml`、`styles.xml`、`numbering.xml` 和 `_rels/document.xml.rels`。

改完后至少做三步验证：

1. 用 `python-docx` 重新打开，确认不报错。
2. 用 `extract_text` 或 `inspect_docx` 检查关键内容。
3. 需要版式时，用 Word 或 LibreOffice 渲染成 PDF，再看实际页面。

## 扩展检查清单

新增一个能力时，按下面的顺序做：

1. 判断它属于内容读写、结构盘点还是底层 OOXML。
2. 在 `core.py`、`inspection.py` 或 `ooxml.py` 里实现，保持函数只做一件事。
3. 在 `docxkit/__init__.py` 导出公共名字。
4. 在 `API.md` 补签名、参数和限制。
5. 在 `selftest.py` 增加一条可重复的验证。
6. 用一份真实文档测试，确认没有破坏未知 part 和原有格式。
7. 如果涉及版式，渲染后检查，不要只看 XML。

判断标准很简单：调用方不需要知道 `w:pPr` 的顺序，也不需要自己处理 relationship，这个封装才算合格。反过来，如果函数只是把一段 XML 换个名字，它更应该留在 `ooxml.py`，不要伪装成高层 API。
