from athena_cli.task_toolsets import select_task_toolsets


ALLOWED = {
    "browser",
    "clarify",
    "code_execution",
    "delegation",
    "file",
    "image_gen",
    "kanban",
    "memory",
    "session_search",
    "skills",
    "terminal",
    "todo",
    "web",
}


def test_code_task_gets_code_tools_without_browser_noise():
    selected = select_task_toolsets(
        "Corrigir bug na API Python", "Execute os testes do repositório", allowed=ALLOWED
    )
    assert {"terminal", "file", "code_execution", "kanban"} <= set(selected)
    assert "browser" not in selected


def test_research_task_gets_web_and_browser():
    selected = select_task_toolsets(
        "Pesquisar fontes", "Abra os sites e compare as notícias", allowed=ALLOWED
    )
    assert {"web", "browser", "kanban"} <= set(selected)


def test_unknown_task_falls_back_to_all_allowed_tools():
    assert set(select_task_toolsets("Organizar azulejos", None, allowed=ALLOWED)) == ALLOWED


def test_matched_task_never_returns_empty_when_profile_has_only_other_tools():
    assert select_task_toolsets(
        "Corrigir código", None, allowed={"web", "terminal"}
    ) == ["terminal"]
