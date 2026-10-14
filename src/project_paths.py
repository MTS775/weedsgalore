from pathlib import Path


def list_dataset_subdirectories(root):
    dataset_root = Path(root)
    if not dataset_root.is_dir():
        return []
    return sorted(
        (path.resolve() for path in dataset_root.iterdir() if path.is_dir()),
        key=lambda path: path.name.casefold(),
    )


def resolve_project_path(path, project_root):
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = Path(project_root) / resolved
    return resolved.resolve()
