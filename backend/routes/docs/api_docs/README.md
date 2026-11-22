# GuardGo API documentation

The endpoint reference is split into one Markdown file per registered FastAPI operation.

- [Browse all endpoint documents](endpoints/README.md)

Each endpoint document includes its HTTP method and path, operation metadata, authentication expectations, parameters, request-body model and example, response description and example, common errors, and a cURL starter command.

The files are generated from the route definitions so that paths, operation IDs, summaries, descriptions, and request model names stay aligned with the running API. Regenerate them after route changes:

```bash
python3 scripts/generate_api_docs.py
```

For the authoritative field-level validation rules and generated request/response examples, open `/docs` or `/openapi.json` in the running application.
