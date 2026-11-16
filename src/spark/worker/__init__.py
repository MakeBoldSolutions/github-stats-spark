"""Scheduled collection worker for the self-hosted deployment.

The worker wraps the existing ``spark unified`` CLI: it runs it on a schedule
in a staging directory, publishes the result atomically, and records a
``status.json`` that the dashboard displays. The CLI itself is unchanged.
"""
