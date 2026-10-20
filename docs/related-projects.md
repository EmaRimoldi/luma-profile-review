# Related projects and launch scope

Reviewed on October 19, 2026. These comparisons describe the projects' public
READMEs, not independent installation, security, or recommendation-quality
audits. The list is a focused sample, not an exhaustive market survey.

| Project | Overlap described by its maintainers | Product context |
| --- | --- | --- |
| [Dosido](https://github.com/nicemohawk/dosido) | Luma CSV ingestion, professional enrichment, model scoring and local Ollama support | Runs organizer-controlled networking rounds with optimized pair assignments |
| [Claude Connect](https://github.com/anthonyisaa/claude-code-meetup-app) | Short onboarding, personalized discovery, match explanations and conversation starters | Event PWA with participant accounts, mutual interest and venue discovery |
| [Event Network](https://github.com/jptoor/event-network) | Professional graph, evidence-based scoring and Luma/LinkedIn workflows | Event application with opt-in networking, check-ins and a hosted data service |

The idea of AI event matchmaking already exists. Our proposed distinction is
an individual attendee's local preparation workflow across events: use the
agent they already have, capture accessible evidence, edit professional
criteria, and prepare a portable guide. This is a product hypothesis, not an
established competitive advantage or a claim that other projects lack every
part of the workflow. No source code was copied from these repositories.

## What can be promoted now

Publish the source and fictional demo as an open-source alpha and invite
people who regularly attend professional events to help test it. A suitable
description is:

> Prepare a personal guide to people you could meet at a Luma event. Answer
> five questions, research accessible professional sources with your agent,
> and get suggestions with reasons, citations and conversation starters.
> Runs locally and supports current-agent, Codex CLI, Claude Code and Ollama
> inference workflows. Alpha; browser setup and source availability vary.

Use fictional screenshots and the exact tested capabilities. Do not advertise
unattended collection of every LinkedIn profile, measured networking outcomes,
unlimited subscription inference, or fully verified support for every host.

## What remains before a broader launch

- Run complete collection and enrichment on several real events; measure
  captured versus displayed profiles, readable sources, time and resume behavior.
- Have users judge suggestions and report useful conversations after events.
  Compare matching strategies with the metrics in [product.md](product.md).
- Exercise browser collection and MCP configuration in each priority host,
  starting with Codex and Claude Code. Verify actual Claude and Ollama inference
  in addition to adapter contracts.
- Test the full installation and onboarding with people outside the repository
  authoring session; remove setup friction they actually encounter.
- Choose distinctive public branding before a broader launch. The current
  repository name describes the integration and does not imply Luma affiliation.

An installer, unattended browser connector, hosted database, chat system and
graph-based ranking should be added only when pilot evidence shows they help
people prepare better conversations.
