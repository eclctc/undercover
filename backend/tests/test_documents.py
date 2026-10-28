import pytest


@pytest.mark.parametrize(
    ("document", "count", "first"),
    [("policy_wording", 12, "Your plan"), ("claims_manual", 14, "Purpose and scope")],
)
def test_contents_list_every_section(client, document, count, first):
    contents = client.get(f"/api/documents/{document}").json()
    assert [c["section"] for c in contents] == [str(n) for n in range(1, count + 1)]
    assert contents[0]["title"] == first


def test_a_section_comes_back_in_full(client):
    section = client.get("/api/documents/claims_manual/sections/9").json()
    assert section["title"] == "Repeat claims"
    assert section["text"].startswith("## 9. Repeat claims\n")
    assert "## 10." not in section["text"]


def test_the_last_section_runs_to_the_end(client):
    section = client.get("/api/documents/policy_wording/sections/12").json()
    assert section["title"] == "Definitions"
    assert len(section["text"].splitlines()) > 1


@pytest.mark.parametrize(
    "path",
    [
        "/api/documents/claims_manual/sections/99",
        "/api/documents/claims_manual/sections/abc",
    ],
)
def test_unknown_sections_are_404(client, path):
    assert client.get(path).status_code == 404


def test_unknown_documents_are_rejected(client):
    assert client.get("/api/documents/evals").status_code == 422
