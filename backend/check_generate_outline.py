from pathlib import Path

from app.clients.dify import generate_outline
from app.renderers.pptx_renderer import render_pptx
from app.schemas.ppt import PptBrief

brief = PptBrief(
    topic="企业知识库如何利用 RAG 提高问答可靠性",
    audience="企业技术负责人和产品经理",
    slide_count=8,
    requirements="用于10分钟内部分享，表达通俗，不编造数据。",
)

print("开始请求 Dify，请等待……")
outline = generate_outline(brief, user_id="local-test-user")
print(f"成功生成 {len(outline.slides)} 页大纲")

output_dir = Path(__file__).resolve().parent / "outputs"
output_dir.mkdir(parents=True, exist_ok=True)

outline_path = output_dir / "demo_outline.json"
outline_path.write_text(
    outline.model_dump_json(indent=2),
    encoding="utf-8",
)

ppt_path = render_pptx(outline, output_dir / "demo.pptx")
print("PPT 已保存：", ppt_path)