JARVIS MULTI-PROVIDER AI — v2.9

PROVIDERS
---------
Gemini  -> uses the existing persistent Hermes session and Hermes tools/memory.
OpenAI  -> direct OpenAI Responses API. Default model: gpt-5.6-sol.
Claude  -> direct Anthropic Messages API. Default model: claude-sonnet-4-20250514.

SETUP
-----
Double-click CONFIGURE_AI_PROVIDERS.bat.

Jarvis also reads the existing Hermes .env first, so if OPENAI_API_KEY already
exists there, OpenAI is automatically available without copying the key.

VOICE / TEXT EXAMPLES
---------------------
Use OpenAI to explain this error.
Ask Claude to review this design.
Use Gemini to research this problem.
Use OpenAI to fix bugs in the Jarvis project and test it.
Use Claude to inspect the DailyBread project. Do not change anything.
Deploy an agent using OpenAI to fix the Jarvis dashboard and test it.
Deploy an agent using Claude to review Scan2Cookz. Do not change anything.
What AI providers are available?

CODING SAFETY
-------------
OpenAI and Claude receive a provider-independent local coding tool layer:
- list project files
- read files
- search text
- exact targeted replacements
- create/write text files
- safe validation commands

Edits are restricted to the selected project folder and modified files are
backed up under .jarvis_backups before the first change. Validation mode blocks
deploy/publish/push/delete/credential-changing commands.

Gemini coding continues through Hermes, which already has its own local coding
tools, persistent memory, skills, and agent environment.
