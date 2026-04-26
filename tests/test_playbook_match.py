from pathlib import Path
from server.playbooks.registry import PlaybookRegistry

PLAYBOOK_DIR = Path(__file__).parent.parent / "playbooks"


def test_match_macos_slow():
    reg = PlaybookRegistry.load(PLAYBOOK_DIR)
    pb = reg.match("my mac is slow and laggy", os_name="macos")
    assert pb is not None
    assert pb.id == "macos-slow"


def test_no_match_for_unrelated():
    reg = PlaybookRegistry.load(PLAYBOOK_DIR)
    pb = reg.match("buy more RAM for grandma", os_name="macos")
    assert pb is None


def test_level_tools():
    reg = PlaybookRegistry.load(PLAYBOOK_DIR)
    pb = reg.match("slow mac", os_name="macos")
    assert "get_system_info" in pb.levels["L1"].tools
    assert pb.levels["L3"].tools == ["*"]
