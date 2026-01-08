"""
Reusable dropdown footer component.
Provides consistent branding across all dropdown menus.
"""

from dash import html


def create_dropdown_footer():
    """
    Creates a standardized footer for dropdown menus with logo.

    The footer includes:
    - Horizontal separator line
    - Company logo (22px height)
    - "Powered by" text

    Returns:
        html.Div: Footer component with consistent styling and theme support

    Example:
        >>> children = [
        ...     dbc.DropdownMenuItem("Item 1"),
        ...     dbc.DropdownMenuItem("Item 2"),
        ...     create_dropdown_footer()  # Add at end
        ... ]
    """
    return html.Div([
        # Separator line
        html.Hr(className="dropdown-footer-separator"),

        # Logo and text container
        html.Div([
            html.Span("Powered by", className="dropdown-footer-text"),
            html.Img(
                src="/assets/logo.png",
                className="dropdown-footer-logo",
                alt="AMG Logo"
                    )
            
        ], className="dropdown-footer-content")
    ], className="dropdown-footer")
