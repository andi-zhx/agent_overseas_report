from __future__ import annotations

from agent_overseas_report.knowledge_base.parsers import parse_document


def test_word_docx_parser_extracts_paragraphs_and_tables(tmp_path) -> None:
    docx = __import__("pytest").importorskip("docx")
    path = tmp_path / "product.docx"
    document = docx.Document()
    document.add_paragraph("产品说明：智能传感器")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "认证"
    table.cell(0, 1).text = "CE"
    document.save(path)

    blocks = parse_document(path, "word")

    assert "智能传感器" in blocks[0].text
    assert "认证 | CE" in blocks[0].text


def test_excel_parser_extracts_each_sheet(tmp_path) -> None:
    openpyxl = __import__("pytest").importorskip("openpyxl")
    path = tmp_path / "market.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "德国"
    worksheet.append(["指标", "数值"])
    worksheet.append(["市场规模", "增长"])
    workbook.save(path)

    blocks = parse_document(path, "excel")

    assert blocks[0].sheet_name == "德国"
    assert "市场规模 | 增长" in blocks[0].text


def test_ppt_parser_extracts_slide_text(tmp_path) -> None:
    pptx = __import__("pytest").importorskip("pptx")
    path = tmp_path / "intro.pptx"
    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "企业介绍"
    presentation.save(path)

    blocks = parse_document(path, "ppt")

    assert blocks[0].slide_number == 1
    assert "企业介绍" in blocks[0].text
