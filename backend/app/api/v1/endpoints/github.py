"""GitHub repository verification endpoint.

Accepts a GitHub repository URL, validates it exists (and is accessible via
the public GitHub API), and returns the default branch plus the full list of
branch names.  The branch list is NOT stored — it is only used client-side to
present the branch selection dropdown before the user saves a configuration.
"""
from urllib.parse import urlparse
from typing import List

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

router = APIRouter()

_GITHUB_API = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
# GitHub allows up to 100 branches per page; fetch a few pages to cover most
# real-world repos without an unbounded loop.
_MAX_BRANCH_PAGES = 5


class GithubVerifyRequest(BaseModel):
    repo_url: str

    @field_validator("repo_url")
    @classmethod
    def _normalise(cls, v: str) -> str:
        raw = v.strip()
        if not raw:
            raise ValueError("repo_url must not be empty")
        candidate = raw if "://" in raw else f"https://{raw}"
        parsed = urlparse(candidate)
        host = (parsed.netloc or "").lower()
        if host not in {"github.com", "www.github.com"}:
            raise ValueError("repo_url must point to github.com")
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) < 2:
            raise ValueError("repo_url must include owner and repository")
        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return f"https://github.com/{owner}/{repo}"


class GithubVerifyResponse(BaseModel):
    repo_url: str
    default_branch: str
    branches: List[str]


@router.post(
    "/verify",
    response_model=GithubVerifyResponse,
    summary="Verify a GitHub repository and list its branches",
)
def verify_github_repo(payload: GithubVerifyRequest) -> GithubVerifyResponse:
    """Validate the repository URL against the public GitHub API and return
    its default branch together with all available branch names.

    No GitHub token is required for public repositories.  Private repositories
    will surface as a 404 from GitHub, which we surface to the caller as a
    422 with a human-readable message.
    """
    parsed = urlparse(payload.repo_url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    owner, repo = parts[0], parts[1]

    try:
        with httpx.Client(timeout=10) as client:
            # 1. Verify the repo exists and fetch the default branch
            repo_resp = client.get(
                f"{_GITHUB_API}/repos/{owner}/{repo}", headers=_HEADERS
            )
            if repo_resp.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Repository '{owner}/{repo}' not found on GitHub. "
                        "Check the URL and ensure the repository is public."
                    ),
                )
            if repo_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"GitHub API returned status {repo_resp.status_code}.",
                )

            default_branch: str = repo_resp.json().get("default_branch", "main")

            # 2. Collect branches (paginated, up to _MAX_BRANCH_PAGES pages)
            branches: List[str] = []
            page = 1
            while page <= _MAX_BRANCH_PAGES:
                br_resp = client.get(
                    f"{_GITHUB_API}/repos/{owner}/{repo}/branches",
                    headers=_HEADERS,
                    params={"per_page": 100, "page": page},
                )
                if br_resp.status_code != 200:
                    break
                page_data = br_resp.json()
                if not page_data:
                    break
                branches.extend(b["name"] for b in page_data)
                if len(page_data) < 100:
                    break
                page += 1

            if not branches:
                branches = [default_branch]

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="GitHub API request timed out. Please try again.",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach GitHub: {exc}",
        )

    return GithubVerifyResponse(
        repo_url=payload.repo_url,
        default_branch=default_branch,
        branches=branches,
    )
