"""Template-backed project cash-flow workbook editing and export."""

CASHFLOW_WORKBOOK_TEMPLATE = USER_DATA_DIR / "_cashflow" / "金义东线资金测算模板.xlsx"


def _cashflow_workbook_state_path(username):
    return user_root(safe_username(username)) / "cashflow_workbook_state.json"


def _cashflow_workbook_state(username):
    value = office_doc_read("cashflow", _cashflow_workbook_state_path(username), {})
    return value if isinstance(value, dict) else {}


def _cashflow_workbook_template():
    if not CASHFLOW_WORKBOOK_TEMPLATE.exists():
        raise ValueError("资金测算模板尚未配置")
    try:
        from openpyxl import load_workbook
        return load_workbook(CASHFLOW_WORKBOOK_TEMPLATE, data_only=False)
    except ImportError as exc:
        raise ValueError("Excel 导出组件不可用") from exc
    except Exception as exc:
        raise ValueError("资金测算模板无法读取") from exc


def _cashflow_workbook_cells(book):
    sheets = []
    for sheet in book.worksheets:
        merged_children = {str(cell) for cell_range in sheet.merged_cells.ranges for row in sheet[cell_range.coord] for cell in row if cell.coordinate != cell_range.start_cell.coordinate}
        cells = {}
        for row in sheet.iter_rows():
            for cell in row:
                value = cell.value
                if cell.coordinate in merged_children:
                    continue
                formula = isinstance(value, str) and value.startswith("=")
                serializable_value = value.isoformat() if hasattr(value, "isoformat") and not formula else value
                fill = cell.fill.fgColor
                fill_color = fill.rgb if fill.type == "rgb" else None
                if fill_color and len(fill_color) == 8:
                    fill_color = "#" + fill_color[-6:]
                cells[cell.coordinate] = {
                    "value": serializable_value if serializable_value is not None else "", "formula": formula,
                    # Original templates use coloured blank cells as the input areas.  Do not
                    # mistake a bold label for an input simply because it has no value.
                    "editable": not formula and (value is None or not cell.font.bold),
                    "fill": fill_color or "", "bold": bool(cell.font.bold),
                    "align": cell.alignment.horizontal or "left",
                    "number_format": cell.number_format or "General",
                }
        widths = {str(key): float(value.width or 12) for key, value in sheet.column_dimensions.items() if value.width}
        heights = {str(key): float(value.height or 18) for key, value in sheet.row_dimensions.items() if value.height}
        sheets.append({"name": sheet.title, "rows": sheet.max_row, "columns": sheet.max_column, "cells": cells,
                       "merged": [str(item) for item in sheet.merged_cells.ranges], "column_widths": widths, "row_heights": heights})
    return sheets


def cashflow_workbook_get(username):
    book = _cashflow_workbook_template()
    state = _cashflow_workbook_state(username)
    return {"ok": True, "template_name": CASHFLOW_WORKBOOK_TEMPLATE.name, "sheets": _cashflow_workbook_cells(book),
            "project_name": str(state.get("project_name", "")), "customer": str(state.get("customer", "")),
            "region": str(state.get("region", "未分区")), "cells": state.get("cells", {}) if isinstance(state.get("cells"), dict) else {},
            "updated_at": str(state.get("updated_at", ""))}


def _cashflow_workbook_clean_cells(raw_cells, book):
    if not isinstance(raw_cells, dict):
        raise ValueError("工作表填写内容格式不正确")
    allowed = {sheet.title: sheet for sheet in book.worksheets}
    cleaned = {}
    for sheet_name, values in raw_cells.items():
        sheet = allowed.get(str(sheet_name))
        if not sheet or not isinstance(values, dict):
            continue
        sheet_values = {}
        for coordinate, value in values.items():
            coordinate = str(coordinate).upper().strip()
            try:
                cell = sheet[coordinate]
            except (ValueError, TypeError):
                continue
            if cell.__class__.__name__ == "MergedCell" or (isinstance(cell.value, str) and cell.value.startswith("=")):
                continue
            text = str(value or "")[:5000]
            if text != "":
                sheet_values[coordinate] = text
        if sheet_values:
            cleaned[sheet.title] = sheet_values
    return cleaned


def cashflow_workbook_save(payload, username):
    book = _cashflow_workbook_template()
    cells = _cashflow_workbook_clean_cells((payload or {}).get("cells", {}), book)
    state = {"project_name": str((payload or {}).get("project_name", "")).strip()[:160],
             "customer": str((payload or {}).get("customer", "")).strip()[:120],
             "region": _cashflow_region((payload or {}).get("region", "未分区")), "cells": cells,
             "updated_at": datetime.now().isoformat(timespec="seconds")}
    office_doc_write("cashflow", _cashflow_workbook_state_path(username), state)
    return {"ok": True, "updated_at": state["updated_at"], "filled_cells": sum(len(values) for values in cells.values())}


def cashflow_workbook_export(username):
    book = _cashflow_workbook_template()
    state = _cashflow_workbook_state(username)
    cells = _cashflow_workbook_clean_cells(state.get("cells", {}), book)
    for sheet_name, values in cells.items():
        sheet = book[sheet_name]
        for coordinate, value in values.items():
            sheet[coordinate] = value
    project_name = str(state.get("project_name") or "项目资金测算").replace("/", "-")[:80]
    output = user_root(safe_username(username)) / "cashflow_exports" / f"{project_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    book.calculation.fullCalcOnLoad = True
    book.calculation.forceFullCalc = True
    buffer = io.BytesIO()
    book.save(buffer)
    raw = buffer.getvalue()
    office_blob_write("cashflow", output, raw,
                      content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return output.name, raw
