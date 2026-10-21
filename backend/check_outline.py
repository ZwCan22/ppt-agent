from app.schemas.outline import PptOutline

sample = {
    "slides": [
        {"kind": "cover", "title": "RAG 如何提高问答可靠性", "bullets": []},
        {"kind": "content", "title": "什么是 RAG", "bullets": ["先检索资料，再生成回答"]},
        {"kind": "content", "title": "资料从哪里来", "bullets": ["使用企业知识库"]},
        {"kind": "content", "title": "如何减少错误", "bullets": ["回答应依据检索结果"]},
        {"kind": "content", "title": "如何评估效果", "bullets": ["检查答案和引用来源"]},
        {"kind": "closing", "title": "总结", "bullets": []},
    ]
}

outline = PptOutline.model_validate(sample)
print(f"校验通过，共 {len(outline.slides)} 页")