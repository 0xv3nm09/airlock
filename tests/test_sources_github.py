"""GitHub source tests: files-list passthrough, dependency extraction, tarball fetch."""
import httpx
import pytest

from app.core.config import Settings
from app.core.errors import Unavailable
from app.schemas import PRFile
from app.sources.github import GitHubSource


def make_source(responses: dict[str, object]) -> GitHubSource:
    """GitHubSource whose HTTP calls are served from a fixed route table."""
    source = GitHubSource(Settings())

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in responses:
            payload = responses[path]
            if isinstance(payload, bytes):
                return httpx.Response(200, content=payload, request=request)
            return httpx.Response(200, json=payload, request=request)
        return httpx.Response(404, json={"message": "nope"}, request=request)

    def client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://api.github.com", transport=httpx.MockTransport(handler)
        )

    source._client = client  # type: ignore[method-assign]
    return source


@pytest.mark.asyncio
async def test_files_list_is_not_swallowed():
    """The /files endpoint returns a LIST — the old dict-only _get turned it into {}."""
    source = make_source(
        {
            "/repos/octo/repo/pulls/7": {"title": "T", "body": "B", "base": {"ref": "develop"}},
            "/repos/octo/repo/pulls/7/files": [
                {"filename": "src/a.py", "patch": "+x = 1"},
                {"filename": "src/b.py", "patch": "+y = 2"},
            ],
        }
    )
    pr = await source.get_pr("https://github.com/octo/repo/pull/7")
    assert [f.path for f in pr.files] == ["src/a.py", "src/b.py"]
    assert pr.base_ref == "develop"
    assert pr.language == "python"


@pytest.mark.asyncio
async def test_tarball_fetch():
    source = make_source({"/repos/octo/repo/tarball/main": b"TARDATA"})
    assert await source.fetch_tarball("octo", "repo", "main") == b"TARDATA"


@pytest.mark.asyncio
async def test_tarball_404_is_unavailable():
    source = make_source({})
    with pytest.raises(Unavailable):
        await source.fetch_tarball("octo", "repo", "missing")


def test_deps_from_requirements_patch():
    files = [
        PRFile(
            path="requirements.txt",
            patch="+requests==2.31.0\n+evil-pkg>=0.1\n# comment\n-flask\n",
        )
    ]
    deps = GitHubSource._deps_from_files(files)
    names = {(d.ecosystem, d.name, d.version) for d in deps}
    assert ("PyPI", "requests", "2.31.0") in names
    assert ("PyPI", "evil-pkg", "0.1") in names
    assert all(d.is_new for d in deps)
    assert len(deps) == 2  # comment and removal lines skipped


def test_deps_from_package_json_patch():
    files = [
        PRFile(
            path="package.json",
            patch='+  "imaginary-exfil-pkg": "^1.0.1",\n+  "name": "myrepo",\n+  "version": "2.0.0",\n',
        )
    ]
    deps = GitHubSource._deps_from_files(files)
    assert [(d.ecosystem, d.name, d.version, d.is_new) for d in deps] == [
        ("npm", "imaginary-exfil-pkg", "1.0.1", True)
    ]


def test_deps_dedupe():
    files = [
        PRFile(path="requirements.txt", patch="+requests==2.31.0\n"),
        PRFile(path="requirements-dev.txt", patch="+requests==2.31.0\n"),
    ]
    assert len(GitHubSource._deps_from_files(files)) == 1
