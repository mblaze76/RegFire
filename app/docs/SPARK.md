# Spark chatbot

Spark's mascot, animation, positioning, and chat bubble remain in the existing UI.
Typed questions and suggestion buttons now call authenticated `POST /api/spark/chat`.
Spark gives guidance and draft text; it cannot change or save event settings.
Voice controls remain a preview: no audio or microphone is connected.

## Free-plan setup

Install Ollama and open its app (or run `ollama serve`). In your own Terminal, run:

```sh
ollama signin
```

The default model is `gemma4:cloud`. No model download or separate API key is needed
for this local development setup. RegFire sends requests to the fixed loopback
gateway `127.0.0.1:11434/api/chat`; Ollama handles cloud authentication on the server
side. Cloud prompts and responses are processed by Ollama's servers. The free plan
has limited starter usage and one concurrent request; see
[Ollama pricing](https://ollama.com/pricing). The app does not purchase credits.

Restart the existing RegFire server after installing this code, then open Spark.
Missing Ollama, missing sign-in, usage limits, and timeout errors appear in the
bubble with **Retry message**. There is no automatic retry that spends more usage.

For local inference instead, download a model yourself and launch RegFire with:

```sh
ollama pull gemma4:e2b
REGFIRE_SPARK_MODEL=gemma4:e2b .venv/bin/python server.py --port 8768
```

The M2 Max / 32 GB development Mac supports Metal acceleration and is suitable
for trying this smaller model. Actual latency depends on available memory and
context. Cloud is the recommended initial chatbot option for larger-model replies.

## Request and privacy boundary

The browser sends only the current section label and up to six completed chat
turns plus the latest question. It does not send event IDs, event records, form
values, speaker profiles, or member lists. Users should not put credentials or
private attendee information into chat. History is held in page memory and clears
on reload; it is not stored in PostgreSQL or browser storage. The existing Spark
position preference remains independent. The server does not log chat bodies or
read API-key variables/files. Ollama's sign-in credentials remain with Ollama.

The endpoint uses existing app sign-in, product-access, same-origin and CSRF checks.
Messages are size-limited, restricted to alternating user/assistant roles, and
prefixed by a server-owned RegFire guidance prompt. One provider request runs at a
time. Replies have a size bound and a 60-second socket timeout; the browser aborts
after 65 seconds. All replies render as plain text, never executable HTML. Only
server configuration selects the model; clients cannot select destinations/models.

For a future hosted Spark backend, direct cloud calls use
`https://ollama.com/api/chat` with the hosted name `gemma4:31b` and a user-created,
server-side API key. That deployment adapter is not part of this local setup.
See [Ollama API docs](https://docs.ollama.com/api/introduction) and
[authentication](https://docs.ollama.com/api/authentication).

## Verification

`tests/test_spark_chat.py` uses synthetic conversations and mocked provider replies
to check the model/context payload, limits, local override, redacted sign-in/usage
errors, timeout handling, concurrency release, and actual HTTP authentication/CSRF
boundary. These checks require neither Ollama sign-in nor a cloud API key. They do
not establish real model quality or cloud-account availability; that requires the
user to finish sign-in and send a question.
