ANALYSIS_PAGE = "Analyse de parcelle"
USER_MANAGEMENT_PAGE = "Gestion des utilisateurs"

_PAGES_BY_ROLE = {
    "user": (ANALYSIS_PAGE,),
    "admin": (ANALYSIS_PAGE, USER_MANAGEMENT_PAGE),
}


def get_accessible_pages(role):
    """Return the pages available to a role, defaulting to non-admin access."""
    return _PAGES_BY_ROLE.get(role, _PAGES_BY_ROLE["user"])


def can_access_page(role, page):
    """Check whether a role is allowed to open a page."""
    return page in get_accessible_pages(role)
