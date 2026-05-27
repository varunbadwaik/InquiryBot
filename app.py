from html import escape


def app(environ, start_response):
    """Minimal WSGI entrypoint for Vercel's Python builder.

    The main chatbot is a Streamlit application in chatbot.py. Vercel's Python
    runtime expects a WSGI/ASGI callable named app, so this endpoint makes the
    repository deployable there and points users to the supported Streamlit
    launch command.
    """
    path = environ.get("PATH_INFO", "/")
    status = "200 OK"
    headers = [("Content-Type", "text/html; charset=utf-8")]

    if path == "/health":
        body = b"OK"
        headers = [("Content-Type", "text/plain; charset=utf-8")]
        start_response(status, headers)
        return [body]

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>InquiryBot</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f7f7f5;
      color: #1e293b;
    }}
    main {{
      max-width: 760px;
      margin: 12vh auto;
      padding: 0 24px;
      line-height: 1.55;
    }}
    code {{
      background: #e8ecef;
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .panel {{
      border: 1px solid #d5d9df;
      background: #fff;
      border-radius: 8px;
      padding: 24px;
    }}
  </style>
</head>
<body>
  <main>
    <div class="panel">
      <h1>InquiryBot</h1>
      <p>This repository contains a Streamlit RAG chatbot. Vercel detected the
      Python entrypoint successfully, but the interactive chatbot should be run
      with Streamlit:</p>
      <p><code>streamlit run chatbot.py</code></p>
      <p>For production hosting, use a platform that supports long-running
      Streamlit apps such as Streamlit Community Cloud, Render, or a VM.</p>
      <p>Current path: <code>{escape(path)}</code></p>
    </div>
  </main>
</body>
</html>""".encode("utf-8")

    start_response(status, headers)
    return [body]
