# Contributing

## Setup

```bash
git clone https://github.com/Cris-cpp/awsteraskill.git
cd awsteraskill
pip install -r requirements.txt
```

## Running Tests

```bash
pytest tests/ -v          # all tests
pytest tests/test_terraform_parser.py -v  # single file
```

All 51 tests must pass before submitting a PR.

## Project Structure

```
skills/terraform-drift-analyzer/   # installable skill (canonical)
├── SKILL.md                        # Claude activation guide
├── scripts/                        # pipeline scripts
│   ├── terraform_parser.py         # .tf → T.json + architecture.mmd
│   ├── aws_discovery.py            # T.json → A.json (via AWS MCP)
│   ├── drift_detector.py           # T.json + A.json → diff.json
│   └── report_generator.py         # diff.json → report.md
└── references/
    └── usage.md                    # user-facing docs
tests/                              # pytest suite
tests/fixtures/                     # sample .tf files used by tests
```

## Pipeline

```
*.tf files → terraform_parser.py → T.json + architecture.mmd
                                 ↓
              aws_discovery.py → A.json  (AWS MCP only — no boto3)
                                 ↓
              drift_detector.py → diff.json
                                 ↓
           report_generator.py → report.md
```

## Key Rules

- **No boto3, no AWS CLI** — all AWS access via MCP only
- **`report.md` is the only user-facing output** — never expose intermediate files
- **Use `python-hcl2`** for HCL parsing, never regex
- All scripts: exit code 1 on failure, errors to stderr, progress to stdout
- Missing optional fields → `None` (not omitted)

## Adding a Resource Type

1. Add type to `SUPPORTED_TYPES` in `terraform_parser.py`
2. Add fields to `RESOURCE_FIELDS` in `terraform_parser.py`
3. Add MCP action to `MCP_ACTIONS` in `aws_discovery.py`
4. Add normalization block in `normalize_mcp_response` in `aws_discovery.py`
5. Add compare fields to `COMPARE_FIELDS` in `drift_detector.py`
6. Add section label to `SECTION_LABELS` + `SECTION_ORDER` in `report_generator.py`
7. Add tests for each new type

## Submitting a PR

- Branch from `master` for bug fixes, from `marketplace-ready` for marketplace changes
- Run full test suite before opening PR
- One PR per concern — don't bundle unrelated changes
