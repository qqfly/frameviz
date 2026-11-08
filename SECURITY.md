# Security

The supported deployment model is a local single-user Host bound to loopback. Browser origins and session credentials are checked. Example business WebSockets require a separate random `FRAMEVIZ_BUSINESS_TOKEN` with at least 32 characters; the UI sends it through a WebSocket subprotocol header. Never embed either token in source, public URLs, packages, or logs.

Do not expose the Host or example business services to untrusted networks. A business token grants control of that local example, including its permitted viewer binding; fine-grained multi-user permissions are not implemented.

For vulnerability reports, use the private reporting channel of the repository where you obtained this project, if enabled, or contact its maintainer privately. A public security contact is not configured yet. Do not post credentials or private data in public issues. Include component versions, a minimal synthetic reproducer, and the expected/actual behavior.
