from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected block not found in {path}: {old[:140]!r}")
    file_path.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    '''  useEffect(() => {
    if (!guide.loading && guide.guideState?.status === "not_started") {
      guide.start();
    }
  }, [guide]);
''',
    '''  useEffect(() => {
    if (!guide.loading && guide.guideState?.status === "not_started") {
      guide.start();
    }
  }, [guide.guideState?.status, guide.loading, guide.start]);
''',
)

replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''  useEffect(() => {
    if (!guide.loading && guide.guideState?.status === "not_started") {
      guide.start();
    }
  }, [guide]);
''',
    '''  useEffect(() => {
    if (!guide.loading && guide.guideState?.status === "not_started") {
      guide.start();
    }
  }, [guide.guideState?.status, guide.loading, guide.start]);
''',
)

replace_once(
    "frontend/src/components/guides/GettingStartedBanner.jsx",
    '<Sparkles className="h-4.5 w-4.5" />',
    '<Sparkles className="h-4 w-4" />',
)
