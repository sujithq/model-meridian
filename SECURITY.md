# Security Policy

## Supported versions

Model Meridian is maintained from the default branch and does not currently
publish versioned releases.

| Version | Supported |
| --- | --- |
| Latest `main` | Yes |
| Older commits or forks | No |

Before reporting a vulnerability, confirm that it is reproducible against the
latest commit on `main`.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities in a public issue, discussion, pull
request, or commit.

Use GitHub's **Report a vulnerability** option on the repository's Security tab
when private vulnerability reporting is available. If that option is not
available, contact the repository owner through the contact methods on the
[maintainer's GitHub profile](https://github.com/sujithq) and request a private
reporting channel. Do not include exploit details in an initial public message.

Include the following information when possible:

- A description of the vulnerability and its potential impact.
- The affected commit, workflow, dependency, or generated artifact.
- Reproduction steps or a minimal proof of concept.
- Any prerequisites, configuration, or environment details.
- Suggested mitigations, if known.

The maintainer will make a best effort to acknowledge complete reports within
five business days, assess their impact, and coordinate remediation and
disclosure. Response times may vary because this is a community-maintained
project.

## Scope

Reports may cover the Python scripts, browser automation, GitHub Actions
workflows, dependency configuration, or generated static site. Vulnerabilities
in third-party services or dependencies should also be reported to the
responsible upstream project.

Good-faith research that avoids privacy violations, service disruption, data
destruction, and access beyond what is necessary to demonstrate the issue is
welcome. Please allow reasonable time for remediation before public disclosure.
