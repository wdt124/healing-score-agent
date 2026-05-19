from app.prompt.knowledge_loader import KnowledgeBase

kb = KnowledgeBase()

print("=== 核心 knowledge.md ===")
print(kb.generate_prompt())
print()

print("=== 注入全部参考 ===")
print(kb.generate_prompt(include_refs=kb.list_references()))