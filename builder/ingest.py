"""Turn every file of a brief folder (or a list of brief files) into plain text the builder model can read.

    python3 builder/ingest.py <folder | file...> <out_dir>

Writes <out_dir>/corpus.md (all files, each under its own heading) and one .txt per file.
Handles .md .txt .json .yaml .csv .html .docx .xlsx .xlsm .pdf; anything else is listed with its size.
Never raises on a single bad file: the error is written into the corpus instead.
"""
import json, pathlib, re, subprocess, sys, zipfile, html

TEXT = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".tsv", ".html", ".htm", ".xml", ".eml", ".js", ".ts", ".py", ".sql"}


def docx_text(p):
    with zipfile.ZipFile(p) as z:
        xml = z.read("word/document.xml").decode("utf8", "replace")
    out = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        cells = re.findall(r"<w:tc>.*?</w:tc>", para, re.S)
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", para, re.S))
        out.append(html.unescape(t))
    # tables: rebuild rows so they read as tables
    body = "\n".join(out)
    tables = []
    for tbl in re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S):
        rows = []
        for tr in re.findall(r"<w:tr[ >].*?</w:tr>", tbl, re.S):
            cells = [html.unescape("".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", tc, re.S))) for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)]
            rows.append("| " + " | ".join(c.strip() for c in cells) + " |")
        tables.append("\n".join(rows))
    if tables:
        body += "\n\n## Tables (rebuilt)\n\n" + "\n\n".join(tables)
    return body


def xlsx_text(p):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"### Sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                if row is None or all(v is None or str(v).strip() == "" for v in row): continue
                parts.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
        return "\n".join(parts)
    except ImportError:
        with zipfile.ZipFile(p) as z:
            shared = re.findall(r"<t[^>]*>(.*?)</t>", z.read("xl/sharedStrings.xml").decode("utf8", "replace"), re.S) if "xl/sharedStrings.xml" in z.namelist() else []
            parts = []
            for n in sorted(x for x in z.namelist() if x.startswith("xl/worksheets/sheet")):
                parts.append(f"### {n}")
                for row in re.findall(r"<row[^>]*>(.*?)</row>", z.read(n).decode("utf8", "replace"), re.S):
                    vals = []
                    for c in re.findall(r"<c([^>]*)>(.*?)</c>", row, re.S):
                        v = re.search(r"<v>(.*?)</v>", c[1]) or re.search(r"<t[^>]*>(.*?)</t>", c[1])
                        v = v.group(1) if v else ""
                        if 't="s"' in c[0] and v.isdigit() and int(v) < len(shared): v = shared[int(v)]
                        vals.append(html.unescape(v))
                    parts.append("| " + " | ".join(vals) + " |")
            return "\n".join(parts)


def pdf_text(p):
    for cmd in (["pdftotext", "-layout", str(p), "-"], ["/opt/homebrew/bin/pdftotext", "-layout", str(p), "-"]):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True).stdout
        except Exception:
            continue
    try:
        import pypdf
        return "\n".join(pg.extract_text() or "" for pg in pypdf.PdfReader(str(p)).pages)
    except Exception as e:
        return f"(could not extract PDF text: {e})"


def one(p):
    ext = p.suffix.lower()
    if ext in TEXT or ext == "": return p.read_text(encoding="utf8", errors="replace")
    if ext in (".docx", ".dotx"): return docx_text(p)
    if ext in (".xlsx", ".xlsm"): return xlsx_text(p)
    if ext == ".pdf": return pdf_text(p)
    if ext in (".doc", ".xls", ".rtf", ".odt", ".pptx"):
        try:  # macOS textutil handles doc/rtf/odt
            return subprocess.run(["textutil", "-convert", "txt", "-stdout", str(p)], capture_output=True, text=True, timeout=60, check=True).stdout
        except Exception as e:
            return f"(binary file {p.name}, {p.stat().st_size} bytes, not converted: {e})"
    return f"(binary file {p.name}, {p.stat().st_size} bytes, not converted)"


def ingest(inputs, out_dir):
    out = pathlib.Path(out_dir); (out / "text").mkdir(parents=True, exist_ok=True)
    files = []
    for i in inputs:
        i = pathlib.Path(i)
        if i.is_file() and i.suffix.lower() == ".zip":      # a zipped case folder: unpack it next to the corpus
            dest = out / "unzipped" / i.stem
            with zipfile.ZipFile(i) as z: z.extractall(dest)
            i = dest
        if i.is_dir(): files += sorted(f for f in i.rglob("*") if f.is_file() and not any(s.startswith(".") or s == "__MACOSX" for s in f.relative_to(i).parts))
        elif i.is_file(): files.append(i)
    # BRIEF.md / README first, then the rest
    files.sort(key=lambda f: (0 if f.stem.upper() in ("BRIEF", "README") else 1, str(f)))
    corpus, index = [], []
    for f in files:
        try: t = one(f)
        except Exception as e: t = f"(could not read {f.name}: {type(e).__name__}: {e})"
        name = re.sub(r"[^\w.-]+", "_", str(f.name))
        (out / "text" / (name + ".txt")).write_text(t)
        corpus.append(f"\n\n=================== FILE: {f} ({f.suffix or 'no ext'}) ===================\n\n{t}")
        index.append({"file": str(f), "chars": len(t), "text": str(out / "text" / (name + ".txt"))})
    (out / "corpus.md").write_text("".join(corpus))
    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False))
    return index


if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(__doc__)
    for r in ingest(sys.argv[1:-1], sys.argv[-1]): print(f"{r['chars']:>8}  {r['file']}")
