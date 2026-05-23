# Security Policy

The current codebase is an MVP and should not be connected to production wallets, mainnet contracts, real browser automation, or untrusted tool execution without additional review.

## Default-deny areas

- arbitrary code execution
- wallet transfers
- browser automation
- marketplace bidding
- file-system mutation outside an explicit sandbox
- network access from tools without capability scoping

## Reporting issues

Open a private security advisory or contact the maintainers with reproduction steps, expected impact, and affected components.
