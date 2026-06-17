"""Runtime compatibility helpers for Madmext Ads.

The existing /ai-ajans route calls render_template('modules/ai-ajans.html'),
but app.py does not import Flask render_template and the file is served from
/modules rather than Flask's default templates directory.

Python automatically imports sitecustomize on startup when it is on sys.path.
This defines a safe builtins.render_template fallback so the current route
serves the AI Ajans module instead of returning Internal Server Error.
"""

import builtins


def _madmext_render_template(template_name, *args, **kwargs):
    from flask import send_from_directory

    if template_name == 'modules/ai-ajans.html':
        return send_from_directory('modules', 'ai-ajans.html')

    # Fallback for any accidental render_template usage in this lightweight app.
    # The project normally serves static HTML files through send_from_directory.
    if '/' in template_name:
        folder, filename = template_name.rsplit('/', 1)
        return send_from_directory(folder, filename)

    return send_from_directory('.', template_name)


builtins.render_template = _madmext_render_template
