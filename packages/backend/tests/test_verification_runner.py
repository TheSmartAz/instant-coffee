from app.services.verification_runner import VerificationRunner, parse_failures


def test_parse_failures_extracts_pytest_and_typescript_locations() -> None:
    output = "\n".join(
        [
            "app/api/runs.py:42: AssertionError",
            "src/components/custom/RunInspector.tsx(12,7): error TS2322: Type mismatch",
        ]
    )

    failures = parse_failures("test", output)

    assert failures[0]["file"] == "app/api/runs.py"
    assert failures[0]["line"] == 42
    assert failures[0]["source"] == "pytest"
    assert failures[1]["file"] == "src/components/custom/RunInspector.tsx"
    assert failures[1]["column"] == 7
    assert failures[1]["source"] == "typescript"


def test_verification_runner_skips_non_allowlisted_commands(tmp_path) -> None:
    result = __import__("asyncio").run(
        VerificationRunner(repo_root=tmp_path).run_profile(
            {
                "recommended_commands": [
                    {
                        "name": "unsafe",
                        "command": "echo no",
                        "scope": "repo",
                    }
                ],
                "risk_flags": [],
            }
        )
    )

    assert result.status == "failed"
    assert result.commands[0].status == "skipped"
    assert "allowlist" in result.commands[0].output_summary
