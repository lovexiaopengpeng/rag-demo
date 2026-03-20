from ingest import ingest_files
from pathlib import Path

KB_SOURCE_DIR = Path("docs") #Path("kb_files")   # 你存长期资料的目录

files = []
for f in KB_SOURCE_DIR.glob("*"):
    if f.suffix.lower() in [".txt", ".pdf"]:
        files.append(str(f))

count = ingest_files(files, target="kb")

print(f"✅ 已写入 {count} 个知识块到 KB_VECTOR_DB")
