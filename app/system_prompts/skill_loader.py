import os
from typing import List, Optional


class KnowledgeBase:
    """心理学专业知识加载器，将 SKILL.md 和 references/*.md 组装为 LLM System Prompt"""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = base_dir
        self.ref_dir = os.path.join(base_dir, "references")

        skill_path = os.path.join(base_dir, "SKILL.md")
        self.core_knowledge = self._load_skill(skill_path)

    # ---------- private ----------

    def _load_skill(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # 去除 YAML frontmatter（--- 包裹的元数据块）
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]
        return content.strip()

    def _load_reference(self, name: str) -> str:
        path = os.path.join(self.ref_dir, f"{name}.md")
        if not os.path.exists(path):
            raise FileNotFoundError(f"参考文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    # ---------- public ----------

    def list_references(self) -> List[str]:
        """列出 references/ 下所有可用的参考模块名称（不含 .md 后缀）"""
        if not os.path.isdir(self.ref_dir):
            return []
        return sorted(
            f[:-3] for f in os.listdir(self.ref_dir)
            if f.endswith(".md") and not f.startswith(".")
        )

    def generate_prompt(
        self,
        include_refs: Optional[List[str]] = None,
    ) -> str:
        """
        生成完整 System Prompt。

        Args:
            include_refs: 需要注入的参考模块名列表（如 ["cbt-techniques", "emotion-support"]）。
                          传 None 则只包含 SKILL.md 核心知识。

        Returns:
            组装好的 System Prompt 字符串，可直接作为 LLM 的 system message。
        """
        sections = [self.core_knowledge]

        if include_refs:
            sections.append("\n\n---\n\n## 补充专业知识\n")
            for name in include_refs:
                ref = self._load_reference(name)
                sections.append(ref)
                sections.append("")

        return "\n".join(sections).strip()